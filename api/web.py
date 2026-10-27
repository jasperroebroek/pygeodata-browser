import dataclasses
import io
import json
import logging
import os
import shutil
import string
import tarfile
import tempfile
import threading
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_file,
    send_from_directory,
)
from pygeodata.cache import clean_cache, clean_source_registry
from pygeodata.catalog import store
from pygeodata.config import FORMAT_VERSION, get_config
from pygeodata.tracked_object import TrackedObject
from sqlalchemy.engine import Engine

from pygeodata_browser import code_service, export_service, payloads
from pygeodata_browser.logging import configure_logging
from pygeodata_browser.path_actions import open_path, reveal_path
from pygeodata_browser.payloads import (
    _build_table_rows,
    build_classes_payload,
    build_entries_page_payload,
    build_entry_detail_payload,
    build_find_entries_payload,
    build_pinned_entries_payload,
)
from pygeodata_browser.popups import (
    build_graph_popup,
    build_json_popup,
)
from pygeodata_browser.state import AppContext
from werkzeug.exceptions import HTTPException

_ctx: AppContext = AppContext()  # replaced by create_app() on startup


def _loading():
    return ({'loading': True, 'fast': bool(app.config.get('FAST'))}, 202)


app = Flask(__name__, template_folder='templates')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.json.sort_keys = False


def _allowed_roots() -> list[Path]:
    cfg = get_config()
    return [*cfg.cache_roots, cfg.path_registry]


def _assert_allowed_path(path_str: str) -> Path | None:
    try:
        p = Path(path_str).resolve()
    except OSError:
        abort(400)
    for root in _allowed_roots():
        try:
            p.relative_to(root.resolve())
        except ValueError:
            continue
        else:
            return p
    abort(403)
    return None


def _path_allowed(path_str: str) -> bool:
    """Adapt _assert_allowed_path to the bool-returning contract catalog/export.py expects.

    Export treats a boundary violation like any other skippable entry (one
    bad entry shouldn't sink the whole export), unlike _assert_allowed_path's
    other call sites, which still abort the request outright.
    """
    try:
        _assert_allowed_path(path_str)
    except HTTPException:
        return False
    return True


_APP_DIST = Path(__file__).parent / 'static' / 'app'


@app.get('/')
def index() -> Response:
    """The built frontend (``app/`` is its source; release builds ship it prebuilt)."""
    if not (_APP_DIST / 'index.html').exists():
        abort(404, 'Frontend not built: run `npm run build` in the app/ directory')
    return send_from_directory(_APP_DIST, 'index.html')


@app.get('/assets/<path:filename>')
def app_asset(filename: str) -> Response:
    return send_from_directory(_APP_DIST / 'assets', filename)


@app.get('/api/bootstrap')
def api_bootstrap() -> Response:
    """Most recent entry per class — served instantly while the full state builds."""
    source_root = get_config().path_registry
    try:
        engine = store.get_engine(str(source_root.resolve()), format_version=FORMAT_VERSION)
        rows = store.bootstrap_rows(engine)
    except Exception:  # noqa: BLE001 — bootstrap is best-effort; the full load follows
        rows = []
    return jsonify(rows)


@app.get('/api/popup/json')
def api_popup_json():
    path = _assert_allowed_path(request.args['path'])
    return jsonify(build_json_popup(str(path)))


@app.get('/api/popup/graph')
def api_popup_graph():
    return jsonify(
        build_graph_popup(
            request.args['class_name'],
            graph_path=request.args.get('graph_path'),
        ),
    )


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


@app.get('/api/file')
def api_file():
    path = _assert_allowed_path(request.args['path'])
    resp = send_file(path)
    # Cache-root artifacts are content-addressed by state_hash: immutable forever.
    if any(_within(path, root) for root in get_config().cache_roots):
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


@app.post('/api/open')
def api_open():
    raw = (request.get_json(force=True) or {}).get('path', '')
    open_path(str(_assert_allowed_path(raw)))
    return jsonify({'ok': True})


@app.post('/api/reveal')
def api_reveal():
    raw = (request.get_json(force=True) or {}).get('path', '')
    reveal_path(str(_assert_allowed_path(raw)))
    return jsonify({'ok': True})


@app.get('/api/status')
def api_status():
    return jsonify(
        {
            'ready': _ctx.ready.is_set(),
            'progress': _ctx.progress,
            'load_error': _ctx.load_error,
            'has_live_classes': bool(TrackedObject._registry),
            'fast': bool(app.config.get('FAST')),
        },
    )


def _query_json(name: str, default):
    raw = request.args.get(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        abort(400)


@app.get('/api/classes')
def api_classes():
    """Class cards + filter options — changes only on reload or filter change."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    return jsonify(
        build_classes_payload(
            _ctx.state,
            kind_filter=request.args.get('kind_filter', 'all'),
            spec_filters=_query_json('spec_filters', {}),
            filters=_query_json('filters', []),
            logic_mode=request.args.get('logic_mode', 'AND'),
            hide_stale=request.args.get('hide_stale') == '1',
            version_filter=request.args.get('version_filter') or None,
        ),
    )


@app.get('/api/class-entries')
def api_class_entries():
    """One paginated page of visible header rows across the selected classes."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    classes = [c for c in request.args.get('classes', '').split(',') if c]
    ids_only = request.args.get('ids_only') == '1'
    only_ids = None
    if request.args.get('pinned_only') == '1':
        pinned = build_pinned_entries_payload(_ctx.state, store.pinned_hashes(_catalog_engine()))
        only_ids = {p['record_id'] for p in pinned}
        classes = classes or sorted({p['class_name'] for p in pinned})
    if not classes and not ids_only:
        return jsonify({'table_rows': [], 'total': 0, 'offset': 0, 'limit': 0})
    return jsonify(
        build_entries_page_payload(
            _ctx.state,
            selected_classes=classes,
            kind_filter=request.args.get('kind_filter', 'all'),
            spec_filters=_query_json('spec_filters', {}),
            filters=_query_json('filters', []),
            logic_mode=request.args.get('logic_mode', 'AND'),
            hide_stale=request.args.get('hide_stale') == '1',
            version_filter=request.args.get('version_filter') or None,
            offset=request.args.get('offset', 0, type=int),
            limit=request.args.get('limit', 50, type=int),
            row_display=request.args.get('row_display', 'none'),
            selected_entry=request.args.get('selected_entry') or None,
            ids_only=ids_only,
            max_rows=request.args.get('max_rows', type=int),
            only_ids=only_ids,
        ),
    )


_MIN_HASH_PREFIX = 4


@app.get('/api/find-entries')
def api_find_entries() -> Response | tuple[dict, int]:
    """Quick-switcher lookup by id (state hash) prefix; short or non-hex queries match nothing."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    q = request.args.get('q', '').strip().lower()
    if len(q) < _MIN_HASH_PREFIX or not set(q) <= set(string.hexdigits.lower()):
        return jsonify({'entries': []})
    return jsonify({'entries': build_find_entries_payload(_ctx.state, q)})


def _catalog_engine() -> Engine:
    return store.get_engine(str(get_config().path_registry.resolve()), FORMAT_VERSION)


def _pins_response() -> Response:
    pins = store.pinned_hashes(_catalog_engine())
    return jsonify({'pins': build_pinned_entries_payload(_ctx.state, pins)})


@app.get('/api/pins')
def api_pins() -> Response | tuple[dict, int]:
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    return _pins_response()


@app.put('/api/pins/<record_id>')
def api_pin(record_id: str) -> Response | tuple[dict, int]:
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    if record_id not in _ctx.state.entries:
        abort(404)
    store.set_pinned(_catalog_engine(), record_id, pinned=True)
    return _pins_response()


@app.delete('/api/pins/<record_id>')
def api_unpin(record_id: str) -> Response | tuple[dict, int]:
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    store.set_pinned(_catalog_engine(), record_id, pinned=False)
    return _pins_response()


@app.get('/api/entry/<record_id>')
def api_entry_detail(record_id: str):
    """Detail payload for a single entry; ETag revalidation instead of re-send."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    entry = _ctx.state.entries.get(record_id)
    if entry is None:
        abort(404)
    vreg = _ctx.state.version_registry
    etag = f'"{record_id[:16]}-{entry.dep_hash_stale:d}-{entry.format_version_stale:d}-{len(vreg.versions)}"'
    if request.headers.get('If-None-Match') == etag:
        return '', 304
    detail = build_entry_detail_payload(_ctx.state, record_id=record_id)
    if detail is None:
        abort(404)
    resp = jsonify(detail)
    resp.headers['ETag'] = etag
    # Staleness badges and code versions are volatile: revalidate, never serve stale.
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


_THUMB_WIDTHS = (360, 720)


@app.get('/api/thumb/<record_id>')
def api_thumb(record_id: str):
    """Server-resized preview of an entry's primary image, cached under .source/thumbs."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    entry = _ctx.state.entries.get(record_id)
    if entry is None or entry.primary_file is None or entry.primary_file.kind != 'image':
        abort(404)
    width = request.args.get('w', 720, type=int)
    if width not in _THUMB_WIDTHS:
        width = 720
    source = Path(entry.primary_file.path)
    _assert_allowed_path(str(source))

    thumbs_dir = get_config().path_registry.resolve() / 'thumbs'
    thumb_path = thumbs_dir / f'{record_id}_{width}.png'
    if not thumb_path.exists():
        import io

        from PIL import Image

        thumbs_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            img.thumbnail((width, width * 8))
            buf = io.BytesIO()
            img.convert('RGBA' if img.mode in ('RGBA', 'LA', 'P') else 'RGB').save(buf, 'PNG', optimize=True)
        tmp_path = thumb_path.with_suffix('.tmp')
        tmp_path.write_bytes(buf.getvalue())
        tmp_path.replace(thumb_path)

    resp = send_file(thumb_path)
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


@app.post('/api/rebuild')
def api_rebuild():
    body = request.get_json(force=True, silent=True) or {}
    reimport = bool(body.get('reimport', False))
    _ctx.start_reload(reimport=reimport)
    return _loading()


@app.delete('/api/entry/<record_id>')
def api_delete_entry(record_id: str):
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    entry = _ctx.state.entries.get(record_id)
    if entry is None:
        abort(404)
    cache_dir = Path(entry.params_path).parent
    _assert_allowed_path(str(cache_dir))
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    _ctx.start_reload()
    return jsonify({'ok': True})


@app.post('/api/clean-cache')
def api_clean_cache():
    body = request.get_json(force=True) or {}
    dry_run = bool(body.get('dry_run', True))
    buf = io.StringIO()
    with redirect_stdout(buf):
        clean_cache(dry_run=dry_run, delete_unregistered=False)
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    if not dry_run:
        _ctx.start_reload()
    return jsonify({'lines': lines, 'dry_run': dry_run})


@app.post('/api/clean-source')
def api_clean_source():
    body = request.get_json(force=True) or {}
    dry_run = bool(body.get('dry_run', True))
    buf = io.StringIO()
    with redirect_stdout(buf):
        clean_source_registry(dry_run=dry_run)
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    if not dry_run:
        _ctx.start_reload()
    return jsonify({'lines': lines, 'dry_run': dry_run})


@app.get('/api/code/versions')
def api_code_versions():
    """Return merged version groups sorted newest first, with a synthetic Initial entry last."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    from pygeodata.tracked_object import TrackedObject

    _entries = _ctx.state.entries
    if hasattr(_entries, 'dep_hashes'):
        entry_dep_hashes = _entries.dep_hashes()
    else:
        entry_dep_hashes = {e.dep_hash for e in _entries.values() if e.dep_hash}
    return jsonify(
        {
            'versions': payloads.version_groups_payload(_ctx.state.version_registry, entry_dep_hashes),
            'has_live_classes': bool(TrackedObject._registry),
        },
    )


@app.get('/api/code/resolve-dep-hash')
def api_code_resolve_dep_hash():
    """Resolve a dep_tree_hash + class_name to version_id and source_hash.

    Returns ``{"version_id": "<uuid>", "source_hash": "<hex>"}``
    or 404 if the snapshot or class is not found.
    """
    dep_hash = request.args.get('dep_hash', '')
    class_name = request.args.get('class_name', '')
    if not dep_hash or not class_name:
        abort(400)
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    vreg = _ctx.state.version_registry
    source_hash = vreg.tree_registry.get_class_source_hash(dep_hash, class_name)
    if not source_hash:
        abort(404)
    version = vreg.dep_hash_to_version.get(dep_hash)
    return jsonify({'version_id': version.version_id if version else None, 'source_hash': source_hash})


@app.get('/api/code/source-hash-version')
def api_code_source_hash_version():
    """Resolve a source_hash to its version group.

    Returns ``{"version_id": "<uuid>"}`` or 404.
    """
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()

    source_hash = request.args.get('source_hash', '')
    if not source_hash:
        abort(400)

    version = _ctx.state.version_registry.version_for_source_hash(source_hash)
    if version is None:
        abort(404)

    return jsonify({'version_id': version.version_id})


@app.get('/api/code/version-classes')
def api_code_version_classes():
    """Return all classes at their state for the given version group.

    Pass ``version_id=<uuid>`` to select a specific group, or omit for the newest group.
    """
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    version_id = request.args.get('version_id', '')
    return jsonify(
        [dataclasses.asdict(c) for c in code_service.version_classes(version_id, _ctx.state.version_registry)],
    )


@app.get('/api/code/version-changes')
def api_code_version_changes():
    """Return a complete per-class change summary for a version group.

    Pass ``version_id=<uuid>``.  Returns a list of
    ``{class_name, status, hash_old, hash_new}`` entries, or 404 if unknown.
    """
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    version_id = request.args.get('version_id', '')
    if not version_id:
        abort(400)
    vreg = _ctx.state.version_registry
    changes = vreg.version_change_summary_from_id(version_id)
    if changes is None:
        abort(404)
    return jsonify([c.to_dict() for c in changes])


@app.get('/api/code/snapshot')
def api_code_snapshot():
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()
    source_hash = request.args.get('source_hash', '')
    if not source_hash:
        abort(400)
    result = code_service.snapshot_html(source_hash, _ctx.state.version_registry)
    if result is None:
        abort(404)
    return jsonify(result)


@app.get('/api/code/diff')
def api_code_diff():
    """Return unified diff between two source snapshots."""
    hash_old = request.args.get('hash_old', '')
    hash_new = request.args.get('hash_new', '')
    if not hash_old or not hash_new:
        abort(400)
    full = request.args.get('full') == '1'
    result = code_service.unified_diff_payload(
        hash_old,
        hash_new,
        full,
        _assert_allowed_path,
        _ctx.state.version_registry,
    )
    if result is None:
        abort(404)
    return jsonify(result)


@app.get('/api/code/version-diff')
def api_code_version_diff():
    """Compare two version snapshots and return a per-class change list.

    Pass either:
      - record_id          to use the entry's version as base (target defaults to 'live')
      - base_version_id    to set the base explicitly (version_id or 'live')
    Optional: target_version_id (version_id or 'live'; defaults to 'live')

    Returns {changes, base_version_id, has_live_stale}.
    """
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()

    record_id = request.args.get('record_id') or None
    base_version_id = request.args.get('base_version_id') or None
    target_version_id = request.args.get('target_version_id') or 'live'

    if record_id is None and base_version_id is None:
        abort(400)

    result = code_service.version_diff(
        _ctx.state.version_registry,
        record_id=record_id,
        entries=_ctx.state.entries if record_id else None,
        base_version_id=base_version_id,
        target_version_id=target_version_id,
    )
    if result.get('__not_found__'):
        abort(404)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Export routes
# ---------------------------------------------------------------------------


@app.post('/api/export/start')
def api_export_start():
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()

    body = request.get_json(force=True) or {}
    record_ids = body.get('record_ids', [])
    include_snapshots = body.get('include_snapshots', True)

    files, warnings = export_service.collect_export_files(
        record_ids,
        _ctx.state.entries,
        include_snapshots,
        _path_allowed,
        tree_registry=_ctx.state.version_registry.tree_registry,
    )

    job_id = str(uuid.uuid4())
    export_service.create_job(job_id, len(files), warnings)
    threading.Thread(
        target=export_service.run_export_job,
        args=(job_id, files),
        daemon=True,
    ).start()
    return jsonify({'job_id': job_id, 'total': len(files), 'warnings': warnings})


@app.get('/api/export/status/<job_id>')
def api_export_status(job_id: str):
    job = export_service.get_job(job_id)
    if job is None:
        abort(404)
    return jsonify(
        {
            'status': job['status'],
            'done': job['done'],
            'total': job['total'],
            'error': job['error'],
            'warnings': job['warnings'],
        },
    )


@app.get('/api/export/download/<job_id>')
def api_export_download(job_id: str):
    job = export_service.get_job(job_id)
    if job is None or job['status'] != 'complete' or not job['tmp_path']:
        abort(404)

    tmp_path = job['tmp_path']

    def _cleanup():
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        export_service.pop_job(job_id)

    resp = send_file(
        tmp_path,
        mimetype='application/x-tar',
        as_attachment=True,
        download_name='pygeodata_export.tar',
    )
    resp.call_on_close(_cleanup)
    return resp


@app.post('/api/export/table')
def api_export_table():
    """Return table rows for a specific set of record IDs (for the export view)."""
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()

    body = request.get_json(force=True) or {}
    record_ids: list[str] = body.get('record_ids', [])

    entries = _ctx.state.entries
    seen: set[str] = set()
    groups: dict[str, list] = {}
    for rid in record_ids:
        if rid in seen or rid not in entries:
            continue
        seen.add(rid)
        e = entries[rid]
        groups.setdefault(e.class_name, []).append(e)

    visible_groups = list(groups.items())
    rows = _build_table_rows(
        visible_groups=visible_groups,
        classes=_ctx.state.classes,
        selected_entry=None,
        filters=[],
        logic_mode='AND',
        row_display='all',
    )
    return jsonify({'table_rows': rows})


@app.get('/api/export/single/<record_id>')
def api_export_single(record_id: str):
    if _ctx.is_loading() or _ctx.state is None:
        return _loading()

    data_path, download_name, needs_tar = export_service.single_entry_tar_path(
        record_id,
        _ctx.state.entries,
        _path_allowed,
    )
    if data_path is None:
        abort(404)

    if needs_tar:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix='.tar')
        os.close(tmp_fd)
        with tarfile.open(tmp_name, 'w:') as tar:
            tar.add(data_path, arcname=data_path.name)
        return send_file(tmp_name, as_attachment=True, download_name=download_name)

    return send_file(data_path, as_attachment=True, download_name=download_name)


def create_app(
    fast: bool = False,
    reconcile_interval: float = 300,
    reimport_on_reconcile: bool = True,
) -> Flask:
    """``fast`` serves the UI immediately from the bootstrap payload while the
    full state builds; the default blocks until the first full state is ready.
    A daemon thread reconciles the catalog (and optionally reimports project
    modules) every ``reconcile_interval`` seconds.
    """
    global _ctx
    configure_logging(logging.INFO)
    app.config['FAST'] = fast
    _ctx = AppContext()
    _ctx.start_load()
    if reconcile_interval > 0:

        def _periodic_reconcile() -> None:
            while True:
                time.sleep(reconcile_interval)
                if not _ctx.is_loading():
                    _ctx.start_reload(reimport=reimport_on_reconcile)

        threading.Thread(target=_periodic_reconcile, daemon=True).start()
    return app
