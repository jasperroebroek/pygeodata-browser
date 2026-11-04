import logging
import os
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pygeodata.analysis import AnalysisError, ProjectAnalysis, analyse_in_subprocess
from pygeodata.catalog.types import CatalogNewerError, CatalogOutdatedError
from pygeodata.config import get_config
from pygeodata.project import iter_project_files
from pygeodata.registries.registry import EntryRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.static import analyse_project
from pygeodata.views.classes import merge_unknown_classes, source_classes
from pygeodata.views.entries import spec_options
from pygeodata.views.types import ClassInfo, spec_info
from pygeodata_browser.catalog_context import CatalogContext, offline_roots
from pygeodata_browser.entry_store import EntryStore
from pygeodata_browser.models import EntryInfo

_log = logging.getLogger(__name__)

POLL_INTERVAL = 10.0
IMPORT_TIMEOUT = 600.0

Mode = Literal['static', 'import']


class CatalogError(Exception):
    """The catalog cannot be read here; the message says what to do about it."""


KNOWN_ERRORS = (AnalysisError, CatalogError)


def catalog_signature() -> tuple[int, int] | None:
    try:
        stat = get_config().path_catalog.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def code_signature(root: Path) -> dict[str, int]:
    """Modification times of the files both analyses read; stats only, nothing is read."""
    signature: dict[str, int] = {}
    for path in iter_project_files(root):
        try:
            signature[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue
    return signature


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
    analysis: ProjectAnalysis
    catalog: CatalogContext

    def get_state_hashes(self, class_name: str) -> list[str]:
        return self.entry_registry.get_state_hashes(class_name)

    def get_object_type(self, class_name: str) -> str | None:
        return self.entry_registry.get_object_type(class_name)


class AppContext:
    """The state the server serves and the one way it is rebuilt: :meth:`reload`.

    The project is analysed in the mode fixed at startup — read from source in this process, or
    imported in a subprocess; the browser process never imports project code. Between reloads
    the project's files are polled by mtime: static mode re-analyses on a change, import mode
    only notes it and imports at the next :meth:`tick`, so a burst of edits costs one import.
    """

    def __init__(
        self,
        mode: Mode = 'static',
        root: Path | None = None,
        clock: Callable[[], float] = time.time,
        read_only: bool | None = None,
    ) -> None:
        self.mode = mode
        self.read_only = read_only
        self.root = root if root is not None else Path.cwd()
        self._clock = clock
        self.state: AppState | None = None
        self.ready = threading.Event()
        self.load_error: str | None = None
        self.version: int = 0
        self.code_changed_since: float | None = None
        self.next_tick_at: float | None = None
        self._code_sig: dict[str, int] | None = None
        self._catalog_sig: tuple[int, int] | None = None
        self._lock = threading.Lock()

    def is_loading(self) -> bool:
        return not self.ready.is_set()

    def reload(self, *, show_loading: bool = True) -> threading.Thread:
        """Analyse the project again and rebuild the state, in a thread.

        With ``show_loading`` the UI shows the loading screen until the new state is ready;
        without, the old state keeps serving until the new one is complete and a single
        reference assignment swaps it in. A failure keeps the previous state and sets ``load_error``.
        """
        if show_loading:
            self.ready.clear()
        thread = threading.Thread(target=self._rebuild, daemon=True)
        thread.start()
        return thread

    def _rebuild(self) -> None:
        with self._lock:
            try:
                self._code_sig = code_signature(self.root)
                self.code_changed_since = None
                state = build_state(self._analyse(), self.read_only, self._unavailable_since())
            except Exception as exc:
                self.load_error = str(exc) if isinstance(exc, KNOWN_ERRORS) else traceback.format_exc()
                _log.warning('reload failed; keeping the previous state', exc_info=True)
            else:
                self.state = state
                self.load_error = None
                self._catalog_sig = catalog_signature()
                self.version += 1
                _prewarm_async(self, state)
            finally:
                self.ready.set()

    def _analyse(self) -> ProjectAnalysis:
        if self.mode == 'import':
            if self.read_only is False:
                return analyse_in_subprocess(self.root, timeout=IMPORT_TIMEOUT)
            # the mode is only known once the catalog is open: don't risk __pycache__ directories in a mirror
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
            return analyse_in_subprocess(self.root, timeout=IMPORT_TIMEOUT, env=env)
        return analyse_project(self.root)

    def _unavailable_since(self) -> dict[str, float]:
        state = self.state
        return {r.path: r.since for r in state.catalog.unavailable_roots} if state is not None else {}

    def _busy(self) -> bool:
        return self.is_loading() or self._lock.locked()

    def poll_code(self) -> None:
        """Stat the project's files: static mode re-analyses on a change, import mode notes it."""
        if self._busy() or code_signature(self.root) == self._code_sig:
            return
        if self.mode == 'static':
            self.reload(show_loading=False).join()
        elif self.code_changed_since is None:
            self.code_changed_since = self._clock()

    def tick(self) -> None:
        """The periodic check: import mode imports if code changed since its last import; both follow the catalog."""
        if self._busy():
            return
        if self.mode == 'import':
            self.poll_code()
        if self.code_changed_since is not None or catalog_signature() != self._catalog_sig:
            self.reload(show_loading=False).join()

    def start_watching(self, reconcile_interval: float, poll_interval: float = POLL_INTERVAL) -> None:
        """Poll the project's files every ``poll_interval`` s and tick every ``reconcile_interval`` s (0: never)."""

        def _watch() -> None:
            next_tick = self._clock() + reconcile_interval
            while True:
                self.next_tick_at = next_tick if reconcile_interval > 0 else None
                time.sleep(poll_interval)
                self.poll_code()
                if reconcile_interval > 0 and self._clock() >= next_tick:
                    self.tick()
                    next_tick = self._clock() + reconcile_interval

        threading.Thread(target=_watch, daemon=True).start()


def _prewarm_async(ctx: AppContext, state: AppState) -> None:
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
                if state is not ctx.state:
                    return  # a reload replaced this state; stop warming it
                for_class(class_name)
        except Exception:
            _log.debug('prewarm failed', exc_info=True)

    threading.Thread(target=_warm, daemon=True).start()


def catalog_error(exc: CatalogOutdatedError | CatalogNewerError) -> str:
    if isinstance(exc, CatalogNewerError):
        return f'The catalog was written by a newer pygeodata; upgrade pygeodata here. ({exc})'
    where = f' ({exc.writer_root})' if exc.writer_root else ''
    return f'The catalog was written by an older pygeodata; run `pygeodata catalog build` where it is written{where}.'


def build_state(
    analysis: ProjectAnalysis,
    read_only: bool | None = None,
    unavailable_since: dict[str, float] | None = None,
) -> AppState:
    spec_info.cache_clear()
    version_registry = VersionRegistry()
    try:
        entry_registry = EntryRegistry(read_only=read_only)
    except (CatalogOutdatedError, CatalogNewerError) as exc:
        raise CatalogError(catalog_error(exc)) from exc
    offline_root = offline_roots(entry_registry)
    catalog = CatalogContext.build(entry_registry, read_only, offline_root, unavailable_since or {})
    entries = EntryStore(entry_registry, analysis.tree_hashes.get, version_registry, offline_root)
    diagnostics = dict(entry_registry.diagnostics())
    diagnostics['created_entries'] = len(entries)
    diagnostics['offline_entries'] = len(offline_root)
    diagnostics['problems'] = analysis.problems

    classes = merge_unknown_classes(
        source_classes(analysis),
        entry_registry,
        analysis.tree_hashes.get,
        version_registry=version_registry,
        src=version_registry.source_registry,
        trees=version_registry.tree_registry,
    )

    return AppState(
        classes=classes,
        entries=entries,
        diagnostics=diagnostics,
        spec_options=spec_options(entry_registry),
        entry_registry=entry_registry,
        version_registry=version_registry,
        analysis=analysis,
        catalog=catalog,
    )
