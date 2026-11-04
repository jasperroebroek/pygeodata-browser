import json
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import make_analysis, make_catalog_context, write_entry
from pygeodata.config import set_config
from pygeodata.registries.registry import EntryRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.views.types import SpecInfo
from pygeodata_browser.models import EntryInfo
from pygeodata_browser.state import AppContext, AppState
from pygeodata_browser.web import _allowed_roots, _assert_allowed_path
from pygeodata_browser.web import app as flask_app


class _FakeEntryRegistry:
    def get_state_hashes(self, class_name: str) -> list[str]:
        return []

    def get_object_type(self, class_name: str) -> str | None:
        return None


def _make_ready_ctx(version_registry: VersionRegistry | None = None):
    """Return an AppContext with a minimal ready AppState."""
    ctx = AppContext()
    ctx.state = AppState(
        classes={},
        entries={},
        diagnostics={},
        spec_options={},
        entry_registry=_FakeEntryRegistry(),
        version_registry=version_registry if version_registry is not None else VersionRegistry(),
        analysis=make_analysis(),
        catalog=make_catalog_context(Path('.')),
    )
    ctx.ready.set()
    return ctx


@pytest.fixture
def app(tmp_path: Path):
    with set_config(
        path_cache=tmp_path / 'data_processed',
        path_figures=tmp_path / 'figures',
        path_registry=tmp_path / '.source',
    ):
        flask_app.config['TESTING'] = True
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# --- AppContext ---


def test_app_context_initial_state() -> None:
    ctx = AppContext()
    assert ctx.state is None
    assert ctx.is_loading()


def test_app_context_reload_clears_ready() -> None:
    ctx = AppContext()
    ctx.ready.set()
    with patch('pygeodata_browser.state.threading.Thread'):
        ctx.reload()
    assert not ctx.ready.is_set()


def test_app_context_offscreen_reload_keeps_ready() -> None:
    ctx = AppContext()
    ctx.ready.set()
    with patch('pygeodata_browser.state.threading.Thread'):
        ctx.reload(show_loading=False)
    assert ctx.ready.is_set()


def test_app_context_is_loading_false_when_ready() -> None:
    ctx = AppContext()
    ctx.ready.set()
    assert not ctx.is_loading()


# --- _allowed_roots ---


def test_allowed_roots_includes_registry(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        roots = _allowed_roots()
    assert any(str(tmp_path / '.source') in str(r) for r in roots)


def test_allowed_roots_includes_tables(tmp_path: Path) -> None:
    with set_config(path_tables=tmp_path / 'tables'):
        roots = _allowed_roots()
    assert any(str(tmp_path / 'tables') in str(r) for r in roots)


# --- _assert_allowed_path ---


def test_assert_allowed_path_within_root(tmp_path: Path) -> None:
    allowed = tmp_path / 'data_processed'
    allowed.mkdir()
    f = allowed / 'file.tif'
    f.touch()
    with set_config(path_cache=allowed, path_figures=tmp_path / 'figures', path_registry=tmp_path / '.source'):
        with flask_app.test_request_context():
            result = _assert_allowed_path(str(f))
    assert result is not None


def test_assert_allowed_path_outside_root_aborts(tmp_path: Path) -> None:
    outside = tmp_path / 'secret' / 'data.tif'
    outside.parent.mkdir(parents=True)
    outside.touch()
    with (
        set_config(
            path_cache=tmp_path / 'data_processed',
            path_figures=tmp_path / 'figures',
            path_registry=tmp_path / '.source',
        ),
        flask_app.test_request_context(),
        pytest.raises(Exception),
    ):  # abort(403) raises werkzeug HTTPException
        _assert_allowed_path(str(outside))


# --- Flask routes ---


def test_api_status_returns_ready_flag(client, app) -> None:
    # Wait briefly for the background load (it may or may not finish)
    resp = client.get('/api/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'ready' in data
    assert 'load_error' in data
    assert data['mode'] == 'static'
    assert data['code_changed_since'] is None
    assert data['next_import_at'] is None


def test_api_status_reports_the_pending_import(client) -> None:
    ctx = _make_ready_ctx()
    ctx.mode = 'import'
    ctx.next_tick_at = 2000.0
    with patch('pygeodata_browser.web._ctx', ctx):
        assert client.get('/api/status').get_json()['next_import_at'] is None
        ctx.code_changed_since = 1500.0
        data = client.get('/api/status').get_json()

    assert (data['mode'], data['code_changed_since'], data['next_import_at']) == ('import', 1500.0, 2000.0)


def test_api_status_surfaces_load_error(client, app) -> None:
    from pygeodata_browser import web as web_mod

    web_mod._ctx.load_error = 'something went wrong'
    resp = client.get('/api/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['load_error'] == 'something went wrong'
    web_mod._ctx.load_error = None


def test_api_classes_returns_202_while_loading(client) -> None:
    resp = client.get('/api/classes')
    # Either 202 (loading) or 200 (loaded) — both are valid
    assert resp.status_code in (200, 202)


def test_api_rebuild_triggers_reload(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with (
            patch('pygeodata_browser.web._ctx', ctx),
            patch('pygeodata_browser.state.threading.Thread') as thread_cls,
        ):
            resp = flask_app.test_client().post('/api/rebuild')
    assert resp.status_code == 202
    assert resp.get_json().get('loading') is True
    thread_cls.assert_called_once()


def test_api_clean_cache_judges_entries_by_the_analysed_classes(client, tmp_path: Path, app) -> None:
    cache = tmp_path / 'data_processed'
    write_entry(cache, 'cur001', 'MyLoader', dep_hash='tree-h1')
    write_entry(cache, 'old001', 'MyLoader', dep_hash='tree-old')
    ctx = _make_ready_ctx()
    ctx.state.analysis = make_analysis(MyLoader='h1')
    with patch('pygeodata_browser.web._ctx', ctx):
        resp = client.post('/api/clean-cache', json={'dry_run': True})

    assert resp.status_code == 200
    lines = resp.get_json()['lines']
    assert any('old001' in line for line in lines)
    assert not any('cur001' in line for line in lines)


def test_api_clean_cache_refuses_when_no_classes_are_known(client, tmp_path: Path, app) -> None:
    write_entry(tmp_path / 'data_processed', 'old001', 'MyLoader', dep_hash='tree-old')
    with patch('pygeodata_browser.web._ctx', _make_ready_ctx()):
        resp = client.post('/api/clean-cache', json={'dry_run': False})

    assert resp.status_code == 409
    assert (tmp_path / 'data_processed' / 'old001').exists()


def test_api_popup_json_valid(client, tmp_path: Path, app) -> None:
    # Write a JSON file inside an allowed root
    with app.app_context():
        roots = _allowed_roots()

    cache_root = next((r for r in roots if 'data_processed' in str(r)), None)
    if cache_root is None:
        pytest.skip('No cache root available')

    cache_root.mkdir(parents=True, exist_ok=True)
    f = cache_root / 'test.json'
    f.write_text(json.dumps({'hello': 'world'}))

    resp = client.get(f'/api/popup/json?path={f}')
    assert resp.status_code == 200
    assert resp.get_json()['json'] == {'hello': 'world'}


def test_api_popup_json_outside_root_forbidden(client, tmp_path: Path) -> None:
    outside = tmp_path / 'secret.json'
    outside.write_text('{}')
    resp = client.get(f'/api/popup/json?path={outside}')
    assert resp.status_code == 403


def test_api_file_serves_table_html(client, tmp_path: Path, app) -> None:
    with app.app_context():
        roots = _allowed_roots()
    tables_root = next((r for r in roots if 'tables' in str(r)), None)
    if tables_root is None:
        pytest.skip('No tables root available')

    tables_root.mkdir(parents=True, exist_ok=True)
    f = tables_root / 'preview.html'
    f.write_text('<table><tr><td>1</td></tr></table>')

    resp = client.get(f'/api/file?path={f}')
    assert resp.status_code == 200
    assert b'<table>' in resp.data


# --- /api/code routes ---


def _write_code_snapshot(
    registry_path: Path,
    source_hash: str,
    class_name: str,
    source_text: str,
    mtime: str = '2026-01-01T00:00:00+00:00',
    object_type: str = 'Data',
) -> None:
    code_dir = registry_path / 'code' / source_hash
    code_dir.mkdir(parents=True)
    (code_dir / 'source.py').write_text(source_text, encoding='utf-8')
    (code_dir / 'source.json').write_text(
        json.dumps(
            {
                'class_name': class_name,
                'object_type': object_type,
                'source_hash': source_hash,
                'registered_at': mtime,
            },
        ),
        encoding='utf-8',
    )


def test_api_code_versions_empty(client) -> None:
    ctx = _make_ready_ctx()
    with patch('pygeodata_browser.web._ctx', ctx):
        resp = client.get('/api/code/versions')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'versions' in data
    assert 'has_live_classes' in data
    assert len(data['versions']) == 0


def test_api_code_versions_only_shows_changes(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    # Single entry for MyLoader — first registration, not a version change
    _write_code_snapshot(registry, 'v1hash', 'MyLoader', 'class MyLoader: pass', mtime='2026-01-01T00:00:00+00:00')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/versions')
    versions = resp.get_json()['versions']
    # Single registration → only one group (no change groups)
    assert len(versions) == 1
    assert 'v1' in versions[0]['label']


def test_api_code_versions_shows_second_entry(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'v1hash', 'MyLoader', 'class MyLoader: pass', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'v2hash', 'MyLoader', 'class MyLoader: pass\n', mtime='2026-06-01T00:00:00+00:00')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/versions')
    versions = resp.get_json()['versions']
    # Two entries: the change group (v2) + first group (v1)
    assert len(versions) == 2
    # First entry: the actual change group
    assert versions[0]['class_names'] == ['MyLoader']
    assert versions[0]['mtime'] == '2026-06-01T00:00:00+00:00'
    assert 'v2' in versions[0]['label']
    # Second entry: first (original) group
    assert 'v1' in versions[1]['label']
    # v1 timestamp uses the oldest registration (Jan 1), not the change time
    assert 'Jan' in versions[1]['label']


def test_api_code_resolve_dep_hash(tmp_path: Path) -> None:
    """resolve-dep-hash uses max mtime across ALL nodes, not just the clicked class."""
    registry = tmp_path / '.source'
    # MyLoader: two versions
    _write_code_snapshot(registry, 'v1hash', 'MyLoader', 'class MyLoader: pass', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'v2hash', 'MyLoader', 'class MyLoader: pass\n', mtime='2026-06-01T00:00:00+00:00')
    # MyDep: registered once at a time between v1 and v2 of MyLoader
    _write_code_snapshot(registry, 'dep1hash', 'MyDep', 'class MyDep: pass', mtime='2026-03-01T00:00:00+00:00')

    snapshot_dir = registry / 'snapshots' / 'snapshot_old'
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / 'tree.json').write_text(
        json.dumps(
            {
                # Snapshot uses MyLoader v1 (2026-01-01) but MyDep at 2026-03-01
                'nodes': {
                    'MyLoader': {'hash': 'v1hash', 'object_type': 'Data'},
                    'MyDep': {'hash': 'dep1hash', 'object_type': 'Data'},
                },
                'dependency_tree_hash': 'snapshot_old',
                'call_edges': [],
                'inheritance_edges': [],
                'root_class': 'MyLoader',
                'registered_at': '2026-01-01T00:00:00+00:00',
            },
        ),
        encoding='utf-8',
    )

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/resolve-dep-hash?dep_hash=snapshot_old&class_name=MyLoader')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['source_hash'] == 'v1hash'
    # Max node mtime is 2026-03-01 (MyDep), which is before the v2 change at 2026-06-01.
    # The snapshot therefore belongs to the Initial group.
    assert data['version_id'] == ctx.state.version_registry.versions[-1].version_id


def test_api_code_resolve_dep_hash_missing(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/resolve-dep-hash?dep_hash=doesnotexist&class_name=Foo')
    assert resp.status_code == 404


def test_api_code_resolve_dep_hash_missing_params(client) -> None:
    resp = client.get('/api/code/resolve-dep-hash')
    assert resp.status_code == 400


def test_api_code_version_classes_empty(app) -> None:
    ctx = _make_ready_ctx()
    with patch('pygeodata_browser.web._ctx', ctx):
        resp = app.test_client().get('/api/code/version-classes')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_code_version_classes_returns_latest(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'v1hash', 'MyLoader', 'class MyLoader: pass', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'v2hash', 'MyLoader', 'class MyLoader: pass\n', mtime='2026-06-01T00:00:00+00:00')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/version-classes')
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['class_name'] == 'MyLoader'
    assert data[0]['source_hash'] == 'v2hash'
    assert data[0]['is_loaded'] is False


def test_api_code_version_classes_initial_group(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'v1hash', 'MyLoader', 'class MyLoader: pass', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'v2hash', 'MyLoader', 'class MyLoader: pass\n', mtime='2026-06-01T00:00:00+00:00')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            initial_id = ctx.state.version_registry.versions[-1].version_id
            resp = flask_app.test_client().get(f'/api/code/version-classes?version_id={initial_id}')
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]['source_hash'] == 'v1hash'


def test_api_code_snapshot_returns_html(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'abc123', 'MyLoader', 'class MyLoader: pass')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/snapshot?source_hash=abc123')
    data = resp.get_json()
    assert data['class_name'] == 'MyLoader'
    assert 'html' not in data
    assert isinstance(data['lines'], list)
    assert any('MyLoader' in line['text'] for line in data['lines'])


def test_api_code_snapshot_not_found(tmp_path: Path) -> None:
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/snapshot?source_hash=doesnotexist')
    assert resp.status_code == 404


def test_api_code_snapshot_missing_hash(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/snapshot')
    assert resp.status_code == 400


# --- /api/code/diff ---


def test_api_code_diff_returns_unified_diff(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'aaa', 'MyLoader', 'class MyLoader:\n    x = 1\n')
    _write_code_snapshot(registry, 'bbb', 'MyLoader', 'class MyLoader:\n    x = 2\n')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        flask_app.config['TESTING'] = True
        ctx = _make_ready_ctx(VersionRegistry(registry))
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/diff?hash_old=aaa&hash_new=bbb')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'hunks' in data
    all_lines = [l for h in data['hunks'] for l in h['lines']]
    assert any('x = 1' in l['text'] for l in all_lines if l['type'] == 'del')
    assert any('x = 2' in l['text'] for l in all_lines if l['type'] == 'add')


def test_api_code_diff_missing_params(client) -> None:
    resp = client.get('/api/code/diff?hash_old=aaa')
    assert resp.status_code == 400


def test_api_code_diff_not_found(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/diff?hash_old=doesnotexist&hash_new=alsonotexist')
    assert resp.status_code == 404


def test_api_code_diff_identical_files(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'aaa', 'MyLoader', 'class MyLoader: pass\n')
    _write_code_snapshot(registry, 'bbb', 'MyLoader', 'class MyLoader: pass\n')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        flask_app.config['TESTING'] = True
        ctx = _make_ready_ctx(VersionRegistry(registry))
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/diff?hash_old=aaa&hash_new=bbb')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['hunks'] == []


# --- /api/code/version-diff ---


def _make_entry(record_id: str, dep_hash: str | None):
    """Minimal EntryInfo for version-diff tests."""
    return EntryInfo(
        record_id=record_id,
        class_name='MyLoader',
        object_type='Data',
        params_path='',
        state_hash_path=None,
        execution_graph_path=None,
        state_hash=None,
        instance_hash=None,
        params_hash=None,
        spec_hash=None,
        spec=SpecInfo(),
        rows=[],
        dep_hash=dep_hash,
    )


def test_api_code_version_diff_no_snapshot(tmp_path: Path) -> None:
    entry = _make_entry('rec1', None)
    ctx = _make_ready_ctx()
    ctx.state.entries = {'rec1': entry}
    with patch('pygeodata_browser.web._ctx', ctx):
        resp = flask_app.test_client().get('/api/code/version-diff?record_id=rec1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['error'] == 'no_snapshot'


def test_api_code_version_diff_missing_record(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/version-diff?record_id=doesnotexist')
    assert resp.status_code == 404


def test_api_code_version_diff_missing_param(tmp_path: Path) -> None:
    with set_config(path_registry=tmp_path / '.source'):
        ctx = _make_ready_ctx()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/version-diff')
    assert resp.status_code == 400


def test_api_code_version_diff_returns_changes(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    # Two code snapshots: v1hash (older) and v2hash (newer) = the "live" state.
    # The tree snapshot for 'snapshot1' references v1hash → base is Initial (contains v1hash).
    snapshot_dir = registry / 'snapshots' / 'snapshot1'
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / 'tree.json').write_text(
        json.dumps(
            {
                'nodes': {'MyLoader': {'hash': 'v1hash', 'object_type': 'Data'}},
                'dependency_tree_hash': 'snapshot1',
                'call_edges': [],
                'inheritance_edges': [],
                'root_class': 'MyLoader',
                'registered_at': '2026-01-01T00:00:00+00:00',
            },
        ),
        encoding='utf-8',
    )
    _write_code_snapshot(
        registry,
        'v1hash',
        'MyLoader',
        'class MyLoader:\n    x = 1\n',
        mtime='2026-01-01T00:00:00+00:00',
    )
    _write_code_snapshot(
        registry,
        'v2hash',
        'MyLoader',
        'class MyLoader:\n    x = 2\n',
        mtime='2026-06-01T00:00:00+00:00',
    )

    entry = _make_entry('rec1', 'snapshot1')
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        ctx = _make_ready_ctx(VersionRegistry(registry))
        ctx.state.entries = {'rec1': entry}
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get('/api/code/version-diff?record_id=rec1')

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) >= {'changes', 'base_version_id', 'has_live_stale'}
    changes = data['changes']
    assert len(changes) == 1
    c = changes[0]
    assert c['class_name'] == 'MyLoader'
    assert c['status'] == 'changed'
    assert c['hash_old'] == 'v1hash'
    assert c['hash_new'] == 'v2hash'


def test_api_code_version_diff_explicit_base(tmp_path: Path) -> None:
    """base_version_id and target_version_id can be passed explicitly."""
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'h1', 'MyLoader', 'class MyLoader:\n    x = 1\n', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'h2', 'MyLoader', 'class MyLoader:\n    x = 2\n', mtime='2026-06-01T00:00:00+00:00')

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg = VersionRegistry(registry)
        initial_vid = vreg.versions[-1].version_id
        change_vid = vreg.versions[0].version_id
        ctx = _make_ready_ctx(vreg)
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            resp = flask_app.test_client().get(
                f'/api/code/version-diff?base_version_id={initial_vid}&target_version_id={change_vid}',
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['changes'][0]['status'] == 'changed'


# --- /api/export/* ---


def _run_export(client, record_ids, include_snapshots=False):
    """Helper: start → poll until complete → download. Returns (tar_names, download_resp)."""
    import io
    import tarfile as tarlib
    import time

    resp = client.post('/api/export/start', json={'record_ids': record_ids, 'include_snapshots': include_snapshots})
    assert resp.status_code == 200
    job = resp.get_json()
    job_id = job['job_id']

    for _ in range(100):
        status = client.get(f'/api/export/status/{job_id}').get_json()
        if status['status'] == 'complete':
            break
        assert status['status'] == 'running', f'unexpected status: {status}'
        time.sleep(0.05)
    else:
        raise AssertionError('export job never completed')

    dl = client.get(f'/api/export/download/{job_id}')
    assert dl.status_code == 200
    buf = io.BytesIO(dl.data)
    with tarlib.open(fileobj=buf, mode='r') as tar:
        names = tar.getnames()
    return names


def test_api_export_while_loading(client) -> None:
    resp = client.post('/api/export/start', json={'record_ids': ['abc']})
    assert resp.status_code in (200, 202)


def test_api_export_returns_tar(tmp_path: Path) -> None:
    cache_root = tmp_path / 'data_processed'
    (write_entry(cache_root, 'abc123') / 'output.tif').write_bytes(b'TIFFDATA')
    ctx = _make_ready_ctx()

    with set_config(
        path_cache=cache_root,
        path_figures=tmp_path / 'figures',
        path_registry=tmp_path / '.source',
    ):
        ctx.state.entry_registry = EntryRegistry()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            names = _run_export(flask_app.test_client(), ['abc123'], include_snapshots=False)

    assert 'cache/abc123/parameters.json' in names
    assert 'cache/abc123/meta.json' in names
    assert 'cache/abc123/output.tif' in names
    assert not any(n.startswith('code/') for n in names)
    assert not any(n.startswith('snapshots/') for n in names)


def test_api_export_includes_snapshots(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    cache_root = tmp_path / 'data_processed'
    src_hash = 'srchash1'
    code_dir = registry / 'code' / src_hash
    code_dir.mkdir(parents=True)
    (code_dir / 'source.py').write_text('class MyLoader: pass')
    (code_dir / 'source.json').write_text('{}')

    dep_hash = 'dephash1'
    snapshot_dir = registry / 'snapshots' / dep_hash
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / 'tree.json').write_text(
        json.dumps(
            {
                'dependency_tree_hash': dep_hash,
                'nodes': {'MyLoader': {'hash': src_hash, 'object_type': 'Data'}},
                'call_edges': [],
                'inheritance_edges': [],
                'root_class': 'MyLoader',
                'registered_at': '2026-01-01T00:00:00+00:00',
            },
        ),
    )

    write_entry(cache_root, 'abc123', dep_hash=dep_hash)
    ctx = _make_ready_ctx()

    with set_config(
        path_cache=cache_root,
        path_figures=tmp_path / 'figures',
        path_registry=registry,
    ):
        ctx.state.entry_registry = EntryRegistry()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            names = _run_export(flask_app.test_client(), ['abc123'], include_snapshots=True)

    assert 'cache/abc123/parameters.json' in names
    assert f'code/{src_hash}/source.py' in names
    assert f'code/{src_hash}/source.json' in names
    assert f'snapshots/{dep_hash}/tree.json' in names


def test_api_export_skips_unknown_record_ids(tmp_path: Path) -> None:
    ctx = _make_ready_ctx()

    with set_config(
        path_cache=tmp_path / 'data_processed',
        path_figures=tmp_path / 'figures',
        path_registry=tmp_path / '.source',
    ):
        ctx.state.entry_registry = EntryRegistry()
        flask_app.config['TESTING'] = True
        with patch('pygeodata_browser.web._ctx', ctx):
            names = _run_export(flask_app.test_client(), ['doesnotexist'])

    assert names == []


def test_api_export_status_not_found(client) -> None:
    resp = client.get('/api/export/status/doesnotexist')
    assert resp.status_code == 404


def test_api_export_download_not_found(client) -> None:
    resp = client.get('/api/export/download/doesnotexist')
    assert resp.status_code == 404


def test_api_status_reports_fast_flag(client) -> None:
    resp = client.get('/api/status')
    assert resp.status_code == 200
    assert 'fast' in resp.get_json()


def test_loading_payload_reports_fast(app, monkeypatch) -> None:
    from pygeodata_browser import web
    from pygeodata_browser.state import AppContext

    monkeypatch.setattr(web, '_ctx', AppContext())  # never started — permanently loading
    resp = app.test_client().get('/api/classes')
    assert resp.status_code == 202
    assert isinstance(resp.get_json().get('fast'), bool)


# --- Frontend routes ---


def test_root_serves_built_frontend_and_assets(client, tmp_path: Path) -> None:
    dist = tmp_path / 'app'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text('<div id="app"></div>', encoding='utf-8')
    (dist / 'assets' / 'index.js').write_text('console.log(1)', encoding='utf-8')
    with patch('pygeodata_browser.web._APP_DIST', dist):
        assert client.get('/').data == b'<div id="app"></div>'
        assert client.get('/assets/index.js').data == b'console.log(1)'


def test_root_explains_missing_build(client, tmp_path: Path) -> None:
    with patch('pygeodata_browser.web._APP_DIST', tmp_path / 'missing'):
        resp = client.get('/')
    assert resp.status_code == 404
    assert b'npm run build' in resp.data
