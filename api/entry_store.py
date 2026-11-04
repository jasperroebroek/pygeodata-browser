"""Lazy, per-class entry enrichment over the catalog.

The startup state build reads identity columns only (fast); EntryInfo display
data (param rows, files, spec strings) is assembled per class on first access
and memoized. Record-derived lookups (instance-hash siblings, params-hash
groups, dep-hash sets, per-class counts) never build it, so the common
dashboard requests stay on the fast path.
"""

from collections.abc import Callable

from pygeodata.enums import Staleness
from pygeodata.registries.registry import EntryRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.staleness import dependency_staleness
from pygeodata_browser.models import EntryInfo, entry_info


class EntryStore:
    """Mapping-like lazy view of the entry registry (state_hash -> EntryInfo)."""

    def __init__(
        self,
        entry_registry: EntryRegistry,
        current: Callable[[str], str | None],
        version_registry: VersionRegistry | None = None,
        offline_root: dict[str, str] | None = None,
    ):
        self._registry = entry_registry
        self._current = current
        self._vreg = version_registry
        self._offline_root = offline_root or {}
        self._records_by_class: dict[str, list] = {}
        self._class_of: dict[str, str] = {}
        for entry in entry_registry.entries.values():
            rec = entry.record
            self._records_by_class.setdefault(rec.class_name or '', []).append(rec)
            self._class_of[rec.state_hash] = rec.class_name or ''
        self._entries_by_class: dict[str, list[EntryInfo]] = {}
        self._by_id: dict[str, EntryInfo] = {}
        self._stale_by_dep: dict[tuple[str, str], bool] = {}

    # --- Mapping interface -------------------------------------------------

    def __len__(self) -> int:
        return len(self._class_of)

    def __contains__(self, record_id: object) -> bool:
        return record_id in self._class_of

    def __getitem__(self, record_id: str) -> EntryInfo:
        entry = self._by_id.get(record_id)
        if entry is None:
            class_name = self._class_of.get(record_id)
            if class_name is None:
                raise KeyError(record_id)
            self.for_class(class_name)
            entry = self._by_id.get(record_id)
            if entry is None:
                raise KeyError(record_id)
        return entry

    def get(self, record_id: str, default=None):
        try:
            return self[record_id]
        except KeyError:
            return default

    def values(self) -> list[EntryInfo]:
        self.enrich_all()
        return list(self._by_id.values())

    def items(self):
        return [(e.record_id, e) for e in self.values()]

    def keys(self):
        return list(self._class_of)

    # --- Enrichment --------------------------------------------------------

    def for_class(self, class_name: str) -> list[EntryInfo]:
        cached = self._entries_by_class.get(class_name)
        if cached is not None:
            return cached

        entries: list[EntryInfo] = []
        for rec in self._records_by_class.get(class_name, []):
            entry = entry_info(self._registry.entries[rec.state_hash], self._registry.get_spec(rec.state_hash))
            self._set_dep_staleness(entry)
            entry.offline_root = self._offline_root.get(entry.record_id)
            entries.append(entry)
            self._by_id[entry.record_id] = entry
        self._entries_by_class[class_name] = entries
        return entries

    def enrich_all(self) -> None:
        for class_name in self._records_by_class:
            self.for_class(class_name)

    def _set_dep_staleness(self, entry: EntryInfo) -> None:
        if entry.dep_hash:
            entry.dep_hash_stale = self.dep_hash_stale(entry.class_name, entry.dep_hash)

    # --- Record-derived fast helpers (no display JSON) ----------------------

    def records_for_class(self, class_name: str) -> list:
        return self._records_by_class.get(class_name, [])

    def class_of(self, record_id: str) -> str:
        return self._class_of[record_id]

    def dep_hashes(self) -> set[str]:
        return {
            rec.dependency_tree_hash
            for recs in self._records_by_class.values()
            for rec in recs
            if rec.dependency_tree_hash
        }

    def ids_by_instance_hash(self, instance_hash: str) -> list[str]:
        return [
            rec.state_hash
            for recs in self._records_by_class.values()
            for rec in recs
            if rec.instance_hash == instance_hash and rec.state_hash is not None
        ]

    def ids_by_params_hash(self, class_name: str, params_hash: str, spec_hash: str) -> list[str]:
        return [
            rec.state_hash
            for rec in self._records_by_class.get(class_name, [])
            if rec.params_hash == params_hash and rec.spec_hash == spec_hash and rec.state_hash is not None
        ]

    def offline_count(self) -> int:
        return len(self._offline_root)

    def _hidden_by_offline(self, state_hash: str, offline_filter: str) -> bool:
        return (offline_filter == 'online' and state_hash in self._offline_root) or (
            offline_filter == 'offline' and state_hash not in self._offline_root
        )

    def dep_hash_stale(self, class_name: str, dep_hash: str) -> bool:
        """Per-(class, dep_hash) staleness, memoized."""
        key = (class_name, dep_hash)
        cached = self._stale_by_dep.get(key)
        if cached is None:
            cached = dependency_staleness(class_name, dep_hash, self._current, self._vreg) is Staleness.STALE
            self._stale_by_dep[key] = cached
        return cached

    def count_by_class(
        self,
        *,
        kind_filter: str,
        snapshot_dep_hashes: set[str] | None,
        hide_stale: bool,
        object_type_by_class: dict[str, str | None],
        offline_filter: str = 'all',
    ) -> dict[str, int]:
        """Kind/snapshot/stale counts per class from identity columns only."""
        counts: dict[str, int] = {}
        for class_name, recs in self._records_by_class.items():
            if kind_filter != 'all' and (object_type_by_class.get(class_name) or '').lower() != kind_filter:
                continue
            n = 0
            for rec in recs:
                if rec.state_hash is None:
                    continue
                if snapshot_dep_hashes is not None and rec.dependency_tree_hash not in snapshot_dep_hashes:
                    continue
                if self._hidden_by_offline(rec.state_hash, offline_filter):
                    continue
                if hide_stale and (
                    (rec.dependency_tree_hash and self.dep_hash_stale(class_name, rec.dependency_tree_hash))
                    or not rec.is_current_format
                ):
                    continue
                n += 1
            if n:
                counts[class_name] = n
        return counts

    def visible_ids(
        self,
        *,
        selected_classes: list[str],
        kind_filter: str,
        snapshot_dep_hashes: set[str] | None,
        hide_stale: bool,
        object_type_by_class: dict[str, str | None],
        offline_filter: str = 'all',
    ) -> list[str]:
        """Visible record ids from identity columns only — no display JSON.

        Valid only when no param filters and no spec filters are active; callers
        must fall back to the enriched path otherwise.
        """
        ids: list[str] = []
        for class_name in sorted(self._records_by_class):
            if selected_classes and class_name not in selected_classes:
                continue
            if kind_filter != 'all' and (object_type_by_class.get(class_name) or '').lower() != kind_filter:
                continue
            for rec in self._records_by_class[class_name]:
                if rec.state_hash is None:
                    continue
                if snapshot_dep_hashes is not None and rec.dependency_tree_hash not in snapshot_dep_hashes:
                    continue
                if self._hidden_by_offline(rec.state_hash, offline_filter):
                    continue
                if hide_stale and (
                    (rec.dependency_tree_hash and self.dep_hash_stale(class_name, rec.dependency_tree_hash))
                    or not rec.is_current_format
                ):
                    continue
                ids.append(rec.state_hash)
        return ids
