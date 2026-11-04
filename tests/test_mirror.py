"""Mirror mode (read-only) and unavailable cache roots."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import write_entry
from PIL import Image
from pygeodata.catalog import store
from pygeodata.catalog.types import CatalogData, CatalogOutdatedError
from pygeodata.config import get_config, set_config
from pygeodata.enums import ObjectType
from pygeodata_browser import catalog_context, web
from pygeodata_browser.state import AppContext, catalog_error

FIGURE = 'f' * 16
DATA = 'd' * 16
OTHER_FIGURE = 'e' * 16


@pytest.fixture
def user_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / 'user'
    monkeypatch.setattr(catalog_context, 'user_data_dir', lambda app: str(root / 'data' / app))
    monkeypatch.setattr(catalog_context, 'user_cache_dir', lambda app: str(root / 'cache' / app))
    return root


def configure(root: Path):
    return set_config(
        path_registry=root / '.source',
        path_cache=root / 'data_processed',
        path_tables=root / 'tables',
        path_figures=root / 'figures',
        path_catalog=root / '.catalog.json',
    )


def make_project(root: Path) -> Path:
    """A project with one Data and one Figure entry (with a PNG), indexed in its catalog."""
    root.mkdir()
    with configure(root):
        cfg = get_config()
        write_entry(cfg.get_cache_root(ObjectType.DATA), DATA, 'Loader', object_type='Data')
        figure_dir = write_entry(cfg.get_cache_root(ObjectType.FIGURE), FIGURE, 'Plot', object_type='Figure')
        Image.new('RGB', (40, 20)).save(figure_dir / 'out.png')
        store.refresh(cfg.cache_roots)
    return root


def mirror_of(project: Path, tmp_path: Path) -> Path:
    """A copy of the project; its catalog says it was written from the original root."""
    mirror = tmp_path / 'mirror'
    shutil.copytree(project, mirror)
    return mirror


def tree_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(root.rglob('*'))}


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch):
    def start(root: Path, read_only: bool | None = None):
        ctx = AppContext(root=root, read_only=read_only)
        ctx.reload().join()
        monkeypatch.setattr(web, '_ctx', ctx)
        web.app.config['TESTING'] = True
        return ctx, web.app.test_client()

    return start


def test_mirror_is_detected_from_the_writer_root(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    with configure(project):
        ctx, _ = serve(project)
        assert not ctx.state.catalog.read_only
        assert ctx.state.catalog.reason == 'the catalog was written from this project root'
    with configure(mirror):
        ctx, _ = serve(mirror)
        assert ctx.state.catalog.read_only
        assert ctx.state.catalog.reason == 'the catalog was written from another project root'


def test_flags_override_the_detection(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    with configure(project):
        ctx, _ = serve(project, read_only=True)
        assert ctx.state.catalog.read_only
        assert ctx.state.catalog.reason == 'set with --read-only'
    with configure(mirror):
        ctx, _ = serve(mirror, read_only=False)
        assert not ctx.state.catalog.read_only
        assert ctx.state.catalog.reason == 'set with --writable'


def test_catalog_disabled_is_read_only(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    with configure(project), set_config(catalog_enabled=False):
        ctx, _ = serve(project)
        assert ctx.state.catalog.read_only
        assert ctx.state.catalog.reason == 'catalog_enabled is False'


def test_mirror_writes_nothing_into_the_project(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    with configure(mirror):
        write_entry(get_config().path_cache, 'a' * 16, 'Late', object_type='Data')  # not in the catalog
        before = tree_snapshot(mirror)
        ctx, client = serve(mirror)

        assert client.get('/api/classes').status_code == 200
        page = client.get('/api/class-entries?classes=Plot').get_json()
        assert [r['record_id'] for r in page['table_rows']] == [FIGURE]
        assert client.get(f'/api/entry/{FIGURE}').status_code == 200
        assert client.get('/api/bootstrap').status_code == 200
        assert client.put(f'/api/pins/{FIGURE}').get_json()['pins'][0]['record_id'] == FIGURE
        assert client.get('/api/pins').get_json()['pins'][0]['record_id'] == FIGURE
        assert client.get(f'/api/thumb/{FIGURE}?w=360').status_code == 200
        assert client.post('/api/rebuild').status_code == 202
        ctx.reload().join()
        assert client.delete(f'/api/pins/{FIGURE}').get_json()['pins'] == []

        assert tree_snapshot(mirror) == before
        assert 'a' * 16 not in CatalogData.from_file(mirror / '.catalog.json').entries


def test_local_state_lives_under_the_user_directories(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    catalog_id = CatalogData.from_file(project / '.catalog.json').header.catalog_id

    with configure(mirror):
        _, client = serve(mirror)
        client.put(f'/api/pins/{FIGURE}')
        client.get(f'/api/thumb/{FIGURE}?w=360')
    pins = json.loads((user_dirs / 'data' / 'pygeodata-browser' / catalog_id / 'pins.json').read_text())
    assert [p['state_hash'] for p in pins] == [FIGURE]
    assert (user_dirs / 'cache' / 'pygeodata-browser' / catalog_id / 'thumbs' / f'{FIGURE}_360.png').is_file()
    assert not (mirror / '.catalog.pins.json').exists()

    with configure(project):
        _, client = serve(project)
        client.put(f'/api/pins/{DATA}')
        assert client.get('/api/pins').get_json()['pins'][0]['record_id'] == DATA
        client.get(f'/api/thumb/{FIGURE}?w=720')
    assert (project / '.catalog.pins.json').is_file()
    assert (user_dirs / 'cache' / 'pygeodata-browser' / catalog_id / 'thumbs' / f'{FIGURE}_720.png').is_file()
    assert not (project / '.source' / 'thumbs').exists()


def test_mirror_pins_are_not_the_servers(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    with configure(project):
        store.set_pinned(DATA, pinned=True)
    mirror = mirror_of(project, tmp_path)
    with configure(mirror):
        _, client = serve(mirror)
        assert client.get('/api/pins').get_json()['pins'] == []


def test_without_a_catalog_file_the_local_state_is_keyed_by_the_project_root(
    tmp_path: Path, user_dirs: Path, serve
) -> None:
    project = make_project(tmp_path / 'proj')
    (project / '.catalog.json').unlink()
    with configure(project):
        ctx, client = serve(project, read_only=True)
        key = ctx.state.catalog.key
        assert key.startswith('root-')
        client.put(f'/api/pins/{DATA}')
        ctx.reload().join()
        assert ctx.state.catalog.key == key
    assert (user_dirs / 'data' / 'pygeodata-browser' / key / 'pins.json').is_file()
    assert not (project / '.catalog.json').exists()


@pytest.mark.parametrize(
    ('method', 'url', 'body'),
    [
        ('delete', f'/api/entry/{FIGURE}', None),
        ('post', '/api/clean-cache', {'dry_run': True}),
        ('post', '/api/clean-cache', {'dry_run': False}),
        ('post', '/api/clean-source', {'dry_run': True}),
        ('post', '/api/clean-source', {'dry_run': False}),
    ],
)
def test_destructive_endpoints_refuse_in_mirror_mode(tmp_path: Path, user_dirs: Path, serve, method, url, body) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    with configure(mirror):
        _, client = serve(mirror)
        before = tree_snapshot(mirror)
        assert getattr(client, method)(url, json=body).status_code == 409
        assert tree_snapshot(mirror) == before


def test_clean_source_is_available_when_writable(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    with configure(project):
        _, client = serve(project)
        assert client.post('/api/clean-source', json={'dry_run': True}).status_code == 200


@pytest.mark.parametrize('mirror', [True, False])
def test_entries_of_an_empty_cache_root_are_offline(tmp_path: Path, user_dirs: Path, serve, mirror: bool) -> None:
    project = make_project(tmp_path / 'proj')
    root = mirror_of(project, tmp_path) if mirror else project
    with configure(root):
        shutil.rmtree(get_config().path_figures / FIGURE)  # the figures root is left empty
        ctx, client = serve(root)

        catalog = ctx.state.catalog.info()
        figures = str(get_config().path_figures)
        assert [(r.path, r.name, r.entries) for r in catalog.unavailable_roots] == [(figures, 'figures', 1)]
        assert ctx.state.diagnostics.offline_entries == 1

        rows = client.get('/api/class-entries?classes=Plot,Loader').get_json()['table_rows']
        assert {r['record_id']: r['offline_root'] for r in rows} == {DATA: None, FIGURE: figures}

        detail = client.get(f'/api/entry/{FIGURE}').get_json()['selected_entry']
        assert detail['offline_root'] == figures
        assert detail['figure_preview'] is None
        assert client.get(f'/api/thumb/{FIGURE}').status_code == 404

        def listed(offline_filter: str) -> set[str]:
            query = f'?offline_filter={offline_filter}'
            cards = client.get(f'/api/classes{query}').get_json()['class_cards']
            ids = client.get(f'/api/class-entries{query}&ids_only=1').get_json()['ids']
            assert {c['class_name'] for c in cards if c['visible_record_count']} == {
                {DATA: 'Loader', FIGURE: 'Plot'}[i] for i in ids
            }
            return set(ids)

        assert listed('all') == {DATA, FIGURE}
        assert listed('online') == {DATA}
        assert listed('offline') == {FIGURE}
        assert client.get('/api/class-entries?classes=Plot&offline_filter=online').get_json()['total'] == 0


def test_a_present_root_marks_nothing_offline(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    with configure(project):
        ctx, client = serve(project)
        assert ctx.state.catalog.info().unavailable_roots == []
        rows = client.get('/api/class-entries?classes=Plot').get_json()['table_rows']
        assert rows[0]['offline_root'] is None


def test_unavailable_since_survives_a_reload(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    with configure(project):
        shutil.rmtree(get_config().path_figures / FIGURE)
        ctx, _ = serve(project)
        first = ctx.state.catalog.unavailable_roots[0].since
        ctx.reload().join()
        assert ctx.state.catalog.unavailable_roots[0].since == first


def set_catalog_version(path: Path, version: int) -> None:
    data = json.loads(path.read_text())
    data['header']['catalog_version'] = version
    path.write_text(json.dumps(data))


def test_an_outdated_catalog_on_a_mirror_says_where_to_rebuild(tmp_path: Path, user_dirs: Path, serve) -> None:
    project = make_project(tmp_path / 'proj')
    mirror = mirror_of(project, tmp_path)
    set_catalog_version(mirror / '.catalog.json', 0)
    with configure(mirror):
        ctx = AppContext(root=mirror)
        ctx.reload().join()
        assert ctx.state is None
        assert ctx.load_error == (
            'The catalog was written by an older pygeodata; run `pygeodata catalog build` '
            f'where it is written ({project}).'
        )
        assert 'Traceback' not in ctx.load_error


def test_a_newer_catalog_says_to_upgrade(tmp_path: Path, user_dirs: Path) -> None:
    project = make_project(tmp_path / 'proj')
    set_catalog_version(project / '.catalog.json', 999)
    with configure(project):
        ctx = AppContext(root=project)
        ctx.reload().join()
        assert ctx.state is None
        assert ctx.load_error.startswith('The catalog was written by a newer pygeodata; upgrade pygeodata here.')


def test_catalog_error_without_a_writer_root() -> None:
    assert catalog_error(CatalogOutdatedError('x')).endswith('where it is written.')
