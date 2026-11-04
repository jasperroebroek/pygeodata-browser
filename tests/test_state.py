"""AppContext: the one reload, the two analysis modes, the file polling and the periodic tick."""

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import write_entry
from pygeodata.analysis import AnalysisError
from pygeodata.config import set_config
from pygeodata.registries.registry import EntryRegistry
from pygeodata.static import analyse_project
from pygeodata_browser import state
from pygeodata_browser.state import AppContext

MODULE = 'state_test_project_loader'


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path):
    with set_config(
        path_cache=tmp_path / 'data_processed',
        path_figures=tmp_path / 'figures',
        path_registry=tmp_path / '.source',
    ):
        yield tmp_path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / 'proj'
    root.mkdir()
    edit(root / f'{MODULE}.py', 1)
    return root


_mtime = [1_700_000_000_000_000_000]


def edit(path: Path, value: int) -> None:
    """Rewrite the module with a distinct mtime, however fast the edits follow each other."""
    path.write_text(
        f'from pygeodata import Data\n\n\nclass StateTestLoader(Data):\n    value = {value}\n',
        encoding='utf-8',
    )
    _mtime[0] += 1_000_000_000
    os.utime(path, ns=(_mtime[0], _mtime[0]))


def tree_hash(ctx: AppContext) -> str:
    assert ctx.state is not None
    return ctx.state.analysis.tree_hashes['StateTestLoader']


def loaded(ctx: AppContext) -> AppContext:
    ctx.reload().join()
    assert ctx.load_error is None, ctx.load_error
    return ctx


class CountingAnalyser:
    """Stands in for the import-mode subprocess, analysing from source."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, root: Path, *, timeout: float, env: dict[str, str] | None = None):
        self.calls += 1
        return analyse_project(root)


# --- failures ---


def test_load_error_recorded_on_exception(project: Path) -> None:
    ctx = AppContext(root=project)

    with patch('pygeodata_browser.state.build_state', side_effect=RuntimeError('boom')):
        ctx.reload().join()

    assert ctx.ready.is_set(), 'ready must be set even when the build raises'
    assert 'RuntimeError' in ctx.load_error
    assert 'boom' in ctx.load_error
    assert ctx.state is None


def test_load_error_cleared_on_success(project: Path) -> None:
    ctx = AppContext(root=project)
    ctx.load_error = 'stale error'

    loaded(ctx)

    assert ctx.load_error is None


def test_analysis_error_keeps_the_previous_state_and_surfaces_the_error(project: Path) -> None:
    ctx = loaded(AppContext(mode='import', root=project))
    good_state, good_version = ctx.state, ctx.version

    with patch('pygeodata_browser.state.analyse_in_subprocess', side_effect=AnalysisError('import failed: boom')):
        ctx.reload().join()

    assert ctx.ready.is_set()
    assert ctx.state is good_state
    assert ctx.version == good_version
    assert ctx.load_error == 'import failed: boom'


def test_a_static_analysis_exception_keeps_the_previous_state(project: Path) -> None:
    ctx = loaded(AppContext(root=project))
    good_state = ctx.state

    with patch('pygeodata_browser.state.analyse_project', side_effect=RuntimeError('unreadable')):
        ctx.reload(show_loading=False).join()

    assert ctx.state is good_state
    assert 'unreadable' in ctx.load_error


# --- no project code in this process ---


@pytest.mark.parametrize('mode', ['static', 'import'])
def test_project_modules_are_never_imported_into_the_server(project: Path, mode: str) -> None:
    ctx = AppContext(mode=mode, root=project)

    loaded(ctx)

    assert 'StateTestLoader' in ctx.state.analysis.classes
    assert ctx.state.analysis.mode == mode
    assert 'StateTestLoader' in ctx.state.classes
    assert MODULE not in sys.modules


# --- reload ---


def test_delete_then_reload_completes(tmp_path: Path, project: Path) -> None:
    cache_dir = write_entry(tmp_path / 'data_processed', 'del001', 'MyClass')
    assert 'del001' in EntryRegistry().entries
    shutil.rmtree(cache_dir)

    ctx = AppContext(root=project)
    ctx.ready.set()
    ctx.reload()

    assert ctx.ready.wait(timeout=10)


def test_reload_picks_up_a_new_entry(tmp_path: Path, project: Path) -> None:
    ctx = loaded(AppContext(root=project))
    initial_count = len(ctx.state.entries)

    write_entry(tmp_path / 'data_processed', 'new001', 'NewClass')
    loaded(ctx)

    assert len(ctx.state.entries) == initial_count + 1


def test_reload_runs_the_analysis_at_once_even_when_nothing_changed(project: Path) -> None:
    analyser = CountingAnalyser()
    with patch('pygeodata_browser.state.analyse_in_subprocess', analyser):
        ctx = loaded(AppContext(mode='import', root=project))
        ctx.reload().join()

    assert analyser.calls == 2


def test_analysis_problems_reach_the_diagnostics(project: Path) -> None:
    (project / 'broken.py').write_text('class Broken(:\n', encoding='utf-8')

    ctx = loaded(AppContext(root=project))

    assert any('broken.py' in problem for problem in ctx.state.diagnostics.problems)


# --- static mode: re-analyse on change ---


def test_static_mode_reanalyses_when_a_project_file_changes(project: Path) -> None:
    ctx = loaded(AppContext(root=project))
    before, version = tree_hash(ctx), ctx.version

    ctx.poll_code()
    assert ctx.version == version, 'nothing changed: no rebuild'

    edit(project / f'{MODULE}.py', 2)
    ctx.poll_code()

    assert ctx.version == version + 1
    assert tree_hash(ctx) != before
    assert ctx.ready.is_set()
    assert ctx.code_changed_since is None


def test_static_mode_follows_an_added_file(project: Path) -> None:
    ctx = loaded(AppContext(root=project))
    (project / 'second.py').write_text('from pygeodata import Table\n\n\nclass SecondLoader(Table):\n    pass\n')

    ctx.poll_code()

    assert 'SecondLoader' in ctx.state.analysis.classes


# --- import mode: note, then import at the tick ---


def test_import_mode_notes_a_change_and_imports_once_at_the_tick(project: Path) -> None:
    analyser = CountingAnalyser()
    now = [1000.0]
    with patch('pygeodata_browser.state.analyse_in_subprocess', analyser):
        ctx = loaded(AppContext(mode='import', root=project, clock=lambda: now[0]))
        imported_hash = tree_hash(ctx)
        assert analyser.calls == 1

        for value in (2, 3, 4):
            now[0] += 30
            edit(project / f'{MODULE}.py', value)
            ctx.poll_code()

        assert analyser.calls == 1, 'edits are only noted'
        assert ctx.code_changed_since == 1030.0, 'the first edit is the one noted'
        assert tree_hash(ctx) == imported_hash, 'the last import result keeps showing'

        ctx.tick()
        assert analyser.calls == 2
        assert tree_hash(ctx) != imported_hash
        assert ctx.code_changed_since is None

        ctx.tick()
        assert analyser.calls == 2, 'no change since the last import: no import'


def test_import_mode_tick_does_not_import_without_changes(project: Path) -> None:
    analyser = CountingAnalyser()
    with patch('pygeodata_browser.state.analyse_in_subprocess', analyser):
        ctx = loaded(AppContext(mode='import', root=project))

        ctx.tick()

    assert analyser.calls == 1


def test_import_mode_tick_notices_an_edit_the_poll_has_not_seen(project: Path) -> None:
    analyser = CountingAnalyser()
    with patch('pygeodata_browser.state.analyse_in_subprocess', analyser):
        ctx = loaded(AppContext(mode='import', root=project))
        edit(project / f'{MODULE}.py', 2)

        ctx.tick()

    assert analyser.calls == 2


# --- catalog ---


def test_tick_rebuilds_when_the_catalog_changed(tmp_path: Path, project: Path) -> None:
    ctx = loaded(AppContext(root=project))
    version = ctx.version

    ctx.tick()
    assert ctx.version == version

    write_entry(tmp_path / 'data_processed', 'cat001', 'CatClass')
    EntryRegistry()
    ctx.tick()

    assert ctx.version == version + 1


def test_tick_and_poll_do_nothing_while_loading(project: Path) -> None:
    ctx = AppContext(root=project)

    with patch.object(ctx, 'reload') as reload:
        ctx.poll_code()
        ctx.tick()

    reload.assert_not_called()


def test_code_signature_lists_the_files_the_analyses_read(project: Path) -> None:
    (project / 'data').mkdir()
    (project / 'data' / 'not_a_package.py').write_text('x = 1')

    assert set(state.code_signature(project)) == {str(project / f'{MODULE}.py')}
