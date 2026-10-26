import importlib.util
import logging
import sys
import threading
import traceback
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pygeodata.catalog import store
from pygeodata.catalog.class_catalog import (
    discover_loaded_classes,
    merge_unloaded_classes,
)
from pygeodata.catalog.entry_catalog import _spec_info_cached, discover_entries
from pygeodata.catalog.types import ClassInfo, EntryInfo
from pygeodata.config import FORMAT_VERSION, get_config
from pygeodata.registries.registry import EntryRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.spec import SpecKeys
from pygeodata.tracked_object import TrackedObject
from pygeodata_browser.entry_store import EntryStore, spec_options_from_catalog

_active_state: 'AppState | None' = None


def _ctx_state() -> 'AppState | None':
    return _active_state


_SKIP_DIRS = {'venv', 'env', '.venv', 'build', 'dist', 'site-packages', 'tests', 'test', 'cache'}
_SKIP_PREFIXES = ('test_', 'conftest', 'setup', 'manage')
_log = logging.getLogger(__name__)


@dataclass(slots=True)
class AppState:
    """Wires the entry and version registries together for the browser.

    ``entries`` is the browser-enriched view; with a catalog it is a lazy
    per-class store (see ``entry_store.EntryStore``), otherwise a plain dict.
    ``groups`` is a thin accessor over the held entry registry instance.
    """

    classes: dict[str, ClassInfo]
    entries: 'EntryStore | dict[str, EntryInfo]'
    diagnostics: dict
    spec_options: dict[str, list[str]]
    entry_registry: EntryRegistry
    version_registry: VersionRegistry

    def get_state_hashes(self, class_name: str) -> list[str]:
        return self.entry_registry.get_state_hashes(class_name)

    def get_object_type(self, class_name: str) -> str | None:
        return self.entry_registry.get_object_type(class_name)


class AppContext:
    def __init__(self) -> None:
        self.state: AppState | None = None
        self.ready = threading.Event()
        self.progress: dict = {}
        self.load_error: str | None = None

    def start_load(self) -> None:
        def _load() -> None:
            try:
                _reconcile()
                _reconcile()
                self.state = build_state(progress=self.progress)
                self.load_error = None
                _prewarm_async(self.state)
                _prewarm_async(self.state)
            except Exception:
                self.load_error = traceback.format_exc()
            finally:
                self.ready.set()

        threading.Thread(target=_load, daemon=True).start()

    def start_reload(self, reimport: bool = False) -> None:
        self.ready.clear()
        self.progress.clear()

        def _reload() -> None:
            try:
                if reimport:
                    root = Path.cwd()
                    py_files = _collect_reimport_files(root)
                    total = len(py_files)
                    self.progress['reimport_done'] = 0
                    self.progress['reimport_total'] = total
                    TrackedObject._registry.clear()
                    for done in _reimport_modules(py_files, root):
                        self.progress['reimport_done'] = done
                    self.progress['reimport_done'] = total
                _reconcile()
                self.state = build_state(progress=self.progress)
                self.load_error = None
            except Exception:
                self.load_error = traceback.format_exc()
            finally:
                self.ready.set()

        threading.Thread(target=_reload, daemon=True).start()

    def is_loading(self) -> bool:
        return not self.ready.is_set()


def _prewarm_async(state: AppState) -> None:
    """Enrich every class in the background, smallest first.

    The UI is usable immediately (identity hydration is instant); this absorbs
    the per-class display-JSON cost so a click on any class — including the
    largest — is warm after a few seconds. State reloads restart the warm pass.
    """

    def _warm():
        try:
            for_class = getattr(state.entries, 'for_class', None)
            if for_class is None:
                return
            todo = [
                class_name
                for class_name in state.entry_registry.class_names
                if state.entries.records_for_class(class_name)
            ]
            todo.sort(key=lambda cn: len(state.entries.records_for_class(cn)))
            for class_name in todo:
                if state is not _ctx_state():
                    return  # a reload replaced this state; stop warming it
                for_class(class_name)
        except Exception:
            _log.debug('prewarm failed', exc_info=True)

    threading.Thread(target=_warm, daemon=True).start()


def _reconcile() -> None:
    """Backfill new cache entries into the catalog and prune rows whose entry is gone."""
    config = get_config()
    store.refresh(config.path_registry, config.cache_roots, FORMAT_VERSION)


def _collect_reimport_files(root: Path) -> list[Path]:
    """Return project .py files under root sorted deepest-first.

    Deepest-first means leaf modules are loaded before the top-level packages
    that import them, so cascading re-imports are mostly no-ops.
    """
    files = [
        py_file
        for py_file in root.rglob('*.py')
        if not any(p.startswith(('.', '__pycache__')) or p in _SKIP_DIRS for p in py_file.relative_to(root).parts)
        and not py_file.relative_to(root).parts[-1].startswith(_SKIP_PREFIXES)
    ]
    files.sort(key=lambda p: (-len(p.parts), p.name == '__init__.py', p))
    return files


def _reimport_modules(py_files: list[Path], root: Path):
    """Import (or re-execute) a list of project .py files.

    Unlike the CLI helper this re-executes already-loaded modules so edits to
    existing classes are picked up.  Per-module failures are logged and skipped.

    A file already scheduled for reimport may get pulled in transitively by an
    ordinary ``import`` statement while an *earlier* file in this same pass is
    being executed (e.g. file 0 does ``from src.data.gideon import ...`` before
    ``gideon.py``'s own turn at index 4). Since it was popped from ``sys.modules``
    up front, that ordinary import re-executes it fresh right there. If this
    function then re-executed it *again* at its scheduled turn, every class in
    it would collide with the one just registered by the transitive import. So
    each file's turn checks whether ``sys.modules`` already holds a module for
    it that was populated during this pass (not a leftover from before the
    pass) and skips the explicit re-exec in that case -- it is already current.

    Yields the index of each file just before it is processed so callers can
    track progress against len(py_files).
    """
    if root not in sys.path:
        sys.path.insert(0, str(root))

    module_names = {py_file: '.'.join(py_file.relative_to(root).with_suffix('').parts) for py_file in py_files}
    for name in module_names.values():
        sys.modules.pop(name, None)

    reimported_this_pass: set[str] = set()

    for i, py_file in enumerate(py_files):
        module_name = module_names[py_file]
        if module_name in sys.modules and module_name not in reimported_this_pass:
            # Pulled in transitively by an earlier file in this pass -- already fresh.
            reimported_this_pass.add(module_name)
            yield i
            continue
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                reimported_this_pass.add(module_name)
        except Exception:  # noqa: BLE001
            _log.debug('reimport skip %s', module_name, exc_info=True)
        yield i


def build_state(progress: dict | None = None) -> AppState:
    _spec_info_cached.cache_clear()
    version_registry = VersionRegistry()
    entry_registry = EntryRegistry()
    entries = EntryStore(entry_registry, version_registry)
    diagnostics = dict(entry_registry.diagnostics())
    diagnostics['created_entries'] = len(entries)

    classes = merge_unloaded_classes(
        discover_loaded_classes(),
        entry_registry,
        entries=None,
        version_registry=version_registry,
        src=version_registry.source_registry,
        trees=version_registry.tree_registry,
    )

    # Unloaded classes keep the deps-stale dot: their newest versioned entry
    # must match the live dependency tree (same semantics as the eager build).
    for class_name in entry_registry.class_names:
        info = classes.get(class_name)
        if info is not None and not info.loaded:
            info.deps_stale = entries.class_is_stale(class_name)

    def _none_first(keys: Iterable[str]) -> list[str]:
        return sorted(keys, key=lambda k: (k != 'None', k))

    spec_options = spec_options_from_catalog()
    if spec_options is None:
        # No usable catalog — enrich eagerly so the UI keeps its spec pills.
        eager, entry_registry, diagnostics = discover_entries(progress=progress, version_registry=version_registry)
        entries = eager
        bounds_by_key = {str(e.spec.bounds): (e.spec.bounds_display or 'None') for e in eager.values()}
        resolution_keys = _none_first({e.spec.resolution_display or 'None' for e in eager.values()})
        spec_options = {
            SpecKeys.CRS: sorted({e.spec.crs for e in eager.values() if e.spec.crs}),
            SpecKeys.RESOLUTION: [{'value': k, 'label': k} for k in resolution_keys],
            SpecKeys.SHAPE: sorted({e.spec.shape for e in eager.values() if e.spec.shape}),
            SpecKeys.BOUNDS: [{'value': k, 'label': bounds_by_key[k]} for k in _none_first(bounds_by_key)],
        }
    state = AppState(
        classes=classes,
        entries=entries,
        diagnostics=diagnostics,
        spec_options=spec_options,
        entry_registry=entry_registry,
        version_registry=version_registry,
    )
    global _active_state
    _active_state = state
    return state
