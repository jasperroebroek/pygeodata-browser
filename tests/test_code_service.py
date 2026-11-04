"""Unit tests for pygeodata_browser/code_service.py."""

import json
from pathlib import Path

from conftest import make_analysis, make_entry_store
from pygeodata.config import set_config
from pygeodata.enums import JSONKeys
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.static import analyse_project
from pygeodata.views.types import SpecInfo
from pygeodata_browser import code_service
from pygeodata_browser.models import EntryInfo

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_code_snapshot(
    registry_path: Path,
    source_hash: str,
    class_name: str,
    source_text: str,
    mtime: str = '2026-01-01T00:00:00+00:00',
    object_type: str = 'Data',
) -> None:
    code_dir = registry_path / 'code' / source_hash
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / 'source.py').write_text(source_text, encoding='utf-8')
    (code_dir / 'source.json').write_text(
        json.dumps(
            {
                JSONKeys.CLASS_NAME: class_name,
                JSONKeys.OBJECT_TYPE: object_type,
                JSONKeys.SOURCE_HASH: source_hash,
                JSONKeys.REGISTERED_AT: mtime,
            },
        ),
        encoding='utf-8',
    )


def _make_entry(record_id: str, dep_hash: str | None, params_path: str = '') -> EntryInfo:
    return EntryInfo(
        record_id=record_id,
        class_name='MyLoader',
        object_type='Data',
        params_path=params_path,
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


def _noop(_path: str):
    return None


# ---------------------------------------------------------------------------
# version_diff — error-path branch coverage
# ---------------------------------------------------------------------------


def test_version_diff_error_paths(tmp_path: Path):
    registry = tmp_path / '.source'
    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg_empty = VersionRegistry()

        # dep_hash=None → no_snapshot
        entry_no_dep = _make_entry('rec1', None)
        result = code_service.version_diff(
            vreg_empty, make_analysis(), record_id='rec1', entries=make_entry_store(entry_no_dep)
        )
        assert result == {'error': 'no_snapshot', 'message': 'Snapshot not available for this entry'}

        # unknown record_id → __not_found__ sentinel
        result = code_service.version_diff(vreg_empty, make_analysis(), record_id='missing', entries=make_entry_store())
        assert result.get('__not_found__') is True

        # dep_hash present but unknown to any version group → no_snapshot
        vreg = VersionRegistry(registry)
        entry_bad_dep = _make_entry('rec1', 'nonexistent_dep_hash')
        result = code_service.version_diff(
            vreg, make_analysis(), record_id='rec1', entries=make_entry_store(entry_bad_dep)
        )
        assert result['error'] == 'no_snapshot'

        # neither record_id nor base_version_id → bad_request
        result = code_service.version_diff(vreg_empty, make_analysis())
        assert result['error'] == 'bad_request'


def test_version_diff_explicit_base_version_changed(tmp_path: Path):
    """Explicit base_version_id: class changed between base snapshot and live."""
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'h1', 'MyLoader', 'class MyLoader:\n    x = 1\n', mtime='2026-01-01T00:00:00+00:00')
    _write_code_snapshot(registry, 'h2', 'MyLoader', 'class MyLoader:\n    x = 2\n', mtime='2026-06-01T00:00:00+00:00')

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg = VersionRegistry(registry)
        # versions[-1] is Initial (contains h1); versions[0] is the change group (contains h2)
        initial_vid = vreg.versions[-1].version_id
        change_vid = vreg.versions[0].version_id

        # base=Initial (h1), target=change group (h2) → changed
        result = code_service.version_diff(
            vreg, make_analysis(), base_version_id=initial_vid, target_version_id=change_vid
        )

    assert 'changes' in result
    changes = result['changes']
    assert len(changes) == 1
    c = changes[0]
    assert c['status'] == 'changed'
    assert c['class_name'] == 'MyLoader'
    assert c['hash_old'] == 'h1'
    assert c['hash_new'] == 'h2'


def test_version_diff_result_keys(tmp_path: Path):
    """Result dict must contain changes, base_version_id, has_live_stale."""
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'h1', 'StableClass', 'class StableClass: pass\n', mtime='2026-01-01T00:00:00+00:00')

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg = VersionRegistry(registry)
        initial_vid = vreg.versions[-1].version_id
        result = code_service.version_diff(
            vreg, make_analysis(), base_version_id=initial_vid, target_version_id=initial_vid
        )

    assert set(result.keys()) >= {'changes', 'base_version_id', 'has_live_stale'}


def write_loader(project: Path, body: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / 'loader.py').write_text(f'from pygeodata import Data\n\n\nclass MyLoader(Data):\n    {body}\n')


# ---------------------------------------------------------------------------
# Live code without a stored snapshot
# ---------------------------------------------------------------------------


def test_diff_and_snapshot_fall_back_to_the_current_source(tmp_path: Path) -> None:
    """Edited-but-not-yet-run classes have no stored source; the project's file supplies it."""
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'h1', 'MyLoader', 'class MyLoader(Data):\n    x = 1\n')
    project = tmp_path / 'proj'
    write_loader(project, 'x = 2')
    analysis = analyse_project(project)
    live = analysis.classes['MyLoader'].facts.source_hash

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg = VersionRegistry(registry)
        diff = code_service.diff_hashes('h1', live, full=True, vreg=vreg, analysis=analysis)
        snapshot = code_service.snapshot_html(live, vreg, analysis)
        missing = code_service.diff_hashes('h1', 'unknown', full=False, vreg=vreg, analysis=analysis)

    assert diff is not None
    assert diff['full_new'] == 'class MyLoader(Data):\n    x = 2\n'
    assert [line['type'] for line in diff['hunks'][0]['lines']] == ['ctx', 'del', 'add']
    assert snapshot == {
        'class_name': 'MyLoader',
        'lines': [{'text': 'class MyLoader(Data):', 'cls_link': None}, {'text': '    x = 2', 'cls_link': None}],
    }
    assert missing is None


def test_version_diff_live_is_the_analysed_code(tmp_path: Path) -> None:
    registry = tmp_path / '.source'
    _write_code_snapshot(registry, 'h1', 'MyLoader', 'class MyLoader:\n    x = 1\n')
    project = tmp_path / 'proj'
    write_loader(project, 'x = 2')
    analysis = analyse_project(project)

    with set_config(path_cache=tmp_path / 'data', path_figures=tmp_path / 'figs', path_registry=registry):
        vreg = VersionRegistry(registry)
        result = code_service.version_diff(vreg, analysis, base_version_id=vreg.versions[0].version_id)

    assert result['has_live_stale'] is True
    assert [(c['class_name'], c['status']) for c in result['changes']] == [('MyLoader', 'changed')]
    assert result['changes'][0]['hash_new'] == analysis.classes['MyLoader'].facts.source_hash
