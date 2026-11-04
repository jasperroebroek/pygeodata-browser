"""What the browser knows about its catalog: mode, writer, local state, unavailable cache roots.

In mirror mode (read-only) the project directory is never written: pins live under the user's
data directory and thumbnails under the user's cache directory, both keyed by the catalog id. A
project without a catalog file has no stable id (a read-only open indexes in memory under a fresh
one), so its state is keyed by a hash of the resolved project root instead.
"""

import hashlib
import threading
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import msgspec
from platformdirs import user_cache_dir, user_data_dir
from pygeodata.catalog import store
from pygeodata.catalog.types import CatalogEntry, CatalogHeader, Pin
from pygeodata.config import get_config
from pygeodata.fileio import read_typed_json, write_typed_json_atomic
from pygeodata.registries.registry import EntryRegistry
from pygeodata_browser.contracts import CatalogInfo, UnavailableRoot

APP_NAME = 'pygeodata-browser'

_pins_lock = threading.Lock()


def local_key(header: CatalogHeader) -> str:
    if store.catalog_path().is_file():
        return header.catalog_id
    root = str(store.catalog_path().parent.resolve())
    return f'root-{hashlib.sha256(root.encode()).hexdigest()[:16]}'


def mode_reason(read_only: bool, flag: bool | None) -> str:
    if flag is not None:
        return 'set with --read-only' if flag else 'set with --writable'
    if not read_only:
        return 'the catalog was written from this project root'
    if not get_config().catalog_enabled:
        return 'catalog_enabled is False'
    return 'the catalog was written from another project root'


def unavailable_roots(
    registry: EntryRegistry,
    offline_root: dict[str, str],
    since: dict[str, float],
    now: float,
) -> list[UnavailableRoot]:
    if registry.status is None:
        return []
    counts = Counter(offline_root.values())
    return [
        UnavailableRoot(str(path), path.name, counts[str(path)], since.get(str(path), now))
        for path in (root.resolve() for root in registry.status.diff.unavailable_roots)
    ]


def offline_roots(registry: EntryRegistry) -> dict[str, str]:
    """State hash → the unavailable cache root its entry belongs to, for every entry in one."""
    if registry.status is None:
        return {}
    unavailable = set(registry.status.diff.unavailable_roots)
    roots = {state_hash: store.entry_root(entry) for state_hash, entry in registry.entries.items()}
    return {state_hash: str(root.resolve()) for state_hash, root in roots.items() if root in unavailable}


def _is_absolute(entry: CatalogEntry) -> bool:
    return Path(entry.dir_relpath).is_absolute()


@dataclass
class CatalogContext:
    read_only: bool
    reason: str
    header: CatalogHeader
    key: str
    pins_path: Path
    thumbs_dir: Path
    absolute_dir_entries: int
    unavailable_roots: list[UnavailableRoot]

    @classmethod
    def build(
        cls,
        registry: EntryRegistry,
        flag: bool | None,
        offline_root: dict[str, str],
        since: dict[str, float],
    ) -> 'CatalogContext':
        read_only = registry.status.read_only if registry.status is not None else True
        key = local_key(registry.header)
        return cls(
            read_only=read_only,
            reason=mode_reason(read_only, flag),
            header=registry.header,
            key=key,
            pins_path=Path(user_data_dir(APP_NAME)) / key / 'pins.json' if read_only else store.pins_path().resolve(),
            thumbs_dir=Path(user_cache_dir(APP_NAME)) / key / 'thumbs',
            absolute_dir_entries=sum(_is_absolute(e) for e in registry.entries.values()),
            unavailable_roots=unavailable_roots(registry, offline_root, since, time.time()),
        )

    def pinned_hashes(self) -> list[str]:
        if not self.read_only:
            return store.pinned_hashes()
        return [pin.state_hash for pin in sorted(self._load_pins(), key=lambda pin: pin.pinned_at)]

    def set_pinned(self, state_hash: str, pinned: bool) -> None:
        if not self.read_only:
            store.set_pinned(state_hash, pinned)
            return
        with _pins_lock:
            pins = self._load_pins()
            if pinned:
                if not any(pin.state_hash == state_hash for pin in pins):
                    pins.append(Pin(state_hash=state_hash, pinned_at=time.time()))
            else:
                pins = [pin for pin in pins if pin.state_hash != state_hash]
            self.pins_path.parent.mkdir(parents=True, exist_ok=True)
            write_typed_json_atomic(self.pins_path, pins)

    def _load_pins(self) -> list[Pin]:
        try:
            return read_typed_json(self.pins_path, list[Pin])
        except (OSError, msgspec.DecodeError):
            return []

    def info(self) -> CatalogInfo:
        return CatalogInfo(
            mode='mirror' if self.read_only else 'writable',
            read_only=self.read_only,
            reason=self.reason,
            catalog_id=self.header.catalog_id,
            writer=self.header.writer,
            pins_path=str(self.pins_path),
            thumbs_path=str(self.thumbs_dir),
            absolute_dir_entries=self.absolute_dir_entries,
            unavailable_roots=self.unavailable_roots,
        )
