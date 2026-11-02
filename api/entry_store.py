"""Lazy, per-class entry enrichment over the catalog.

The startup state build hydrates identity columns only (fast); EntryInfo
display data (param rows, files, spec strings) is enriched per class on first
access and memoized. Record-derived lookups (instance-hash siblings, params-hash
groups, dep-hash sets, per-class counts) never touch the display JSON, so the
common dashboard requests stay on the fast path.
"""

from pygeodata.catalog import store
from pygeodata.catalog.entry_catalog import _enrich_params_path, _entry_info_from_display, _spec_info
from pygeodata.catalog.types import EntryInfo, FileRef, LinkedEntry, ParamRow, ParamRowType
from pygeodata.config import FORMAT_VERSION, get_config
from pygeodata.registries.registry import EntryRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.spec import SpecKeys
from pygeodata.tracked_object import TrackedObject


class EntryStore:
    """Mapping-like lazy view of the entry registry (state_hash -> EntryInfo)."""

    def __init__(self, entry_registry: EntryRegistry, version_registry: VersionRegistry | None = None):
        self._registry = entry_registry
        self._vreg = version_registry
        self._records_by_class: dict[str, list] = {}
        self._records_by_id: dict[str, object] = {}
        self._class_of: dict[str, str] = {}
        for rec in entry_registry.records.values():
            if rec.state_hash is None:
                continue
            self._records_by_class.setdefault(rec.class_name or '', []).append(rec)
            self._records_by_id[rec.state_hash] = rec
            self._class_of[rec.state_hash] = rec.class_name or ''
        self._entries_by_class: dict[str, list[EntryInfo]] = {}
        self._by_id: dict[str, EntryInfo] = {}
        self._stale_by_class: dict[str, bool] = {}
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

        records = self._records_by_class.get(class_name, [])
        by_hash = _display_for_hashes([rec.state_hash for rec in records]) if records else {}
        entries: list[EntryInfo] = []
        for rec in records:
            disp = by_hash.get(rec.state_hash) if by_hash is not None else None
            entry = (
                _entry_info_from_display(rec, disp) if disp is not None else _enrich_params_path(rec.params_path, rec)
            )
            entry.record_id = rec.state_hash
            self._set_dep_staleness(entry)
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

    def class_of(self, record_id: str) -> str | None:
        return self._class_of.get(record_id)

    def record(self, record_id: str):
        return self._records_by_id.get(record_id)

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

    def class_is_stale(self, class_name: str) -> bool:
        """True if the class's newest versioned entry is behind the live dep tree.

        Mirrors ``merge_unloaded_classes``: the most recently versioned entry's
        dep_hash represents the class; a current newest entry clears the dot.
        """
        cached = self._stale_by_class.get(class_name)
        if cached is not None:
            return cached
        stale = False
        best_mtime = None
        for rec in self._records_by_class.get(class_name, []):
            if not rec.dependency_tree_hash:
                continue
            version = self._vreg.version_for_dep_hash(rec.dependency_tree_hash) if self._vreg else None
            mtime = version.mtime if version else ''
            if best_mtime is None or mtime >= best_mtime:
                best_mtime = mtime
                stale = self.dep_hash_stale(class_name, rec.dependency_tree_hash)
        self._stale_by_class[class_name] = stale
        return stale

    def dep_hash_stale(self, class_name: str, dep_hash: str) -> bool:
        """Per-(class, dep_hash) staleness, memoized — same logic as the eager build."""
        key = (class_name, dep_hash)
        cached = self._stale_by_dep.get(key)
        if cached is not None:
            return cached
        obj_cls = TrackedObject.find_object_class(class_name)
        if obj_cls is not None:
            stale = obj_cls.get_dependency_tree_hash() != dep_hash
        else:
            stale = self._vreg.is_dependency_hash_stale(dep_hash) if self._vreg else False
        self._stale_by_dep[key] = stale
        return stale

    def format_version_stale(self, record_id: str) -> bool:
        rec = self.record(record_id)
        return rec is not None and (rec.format_version or FORMAT_VERSION) != FORMAT_VERSION

    def count_by_class(
        self,
        *,
        kind_filter: str,
        snapshot_dep_hashes: set[str] | None,
        hide_stale: bool,
        object_type_by_class: dict[str, str | None],
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
                if hide_stale and (
                    (rec.dependency_tree_hash and self.dep_hash_stale(class_name, rec.dependency_tree_hash))
                    or self.format_version_stale(rec.state_hash)
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
    ) -> list[str] | None:
        """Visible record ids from identity columns only — no display JSON.

        Valid only when no param filters and no spec filters are active; callers
        must fall back to the enriched path otherwise. Returns None when this
        store does not support the fast path (eager, non-catalog builds).
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
                if hide_stale and (
                    (rec.dependency_tree_hash and self.dep_hash_stale(class_name, rec.dependency_tree_hash))
                    or self.format_version_stale(rec.state_hash)
                ):
                    continue
                ids.append(rec.state_hash)
        return ids


def _display_for_hashes(state_hashes: list[str]) -> dict[str, dict] | None:
    """Display payload for a specific set of entries, or None when the catalog is unusable."""
    if not state_hashes or not get_config().path_catalog.is_file():
        return None
    catalog = store.load_catalog()
    if not catalog['entries']:
        return None

    files_by_hash: dict[str, dict] = {}
    for state_hash in state_hashes:
        entry_row = catalog['entries'].get(state_hash)
        if entry_row is None:
            continue
        entry_dir = store.entry_abs_path(entry_row['dir_relpath'])
        files_by_hash.setdefault(state_hash, {})
        for f in catalog['files'].get(state_hash, []):
            ref = FileRef(label=f['label'], path=str(entry_dir / f['relpath']), kind=f['kind'])
            files_by_hash[state_hash].setdefault(f['role'], []).append(ref)

    display: dict[str, dict] = {}
    for state_hash in state_hashes:
        entry_row = catalog['entries'].get(state_hash)
        if entry_row is None:
            continue
        entry_dir = store.entry_abs_path(entry_row['dir_relpath'])
        files = files_by_hash.get(state_hash, {})
        rows = [ParamRow(**{**r, 'row_type': ParamRowType(r['row_type'])}) for r in (entry_row['rows'] or [])]
        linked = [LinkedEntry(**le) for le in (entry_row['linked_entries'] or [])]
        display[state_hash] = {
            'entry_dir': entry_dir,
            'spec': _spec_info(entry_row['crs_hash'], entry_row['transform_hash'], entry_row['shape_hash']),
            'rows': rows,
            'linked_entries': linked,
            'primary_file': files.get('primary', [None])[0],
            'sidecar_files': files.get('sidecar', []),
        }
    return display or None


def spec_options_from_catalog() -> dict | None:
    """Distinct spec dimensions straight from the catalog, with display labels.

    Only distinct (crs, transform, shape) triples reconstruct a SpatialSpec
    (memoized in ``_spec_info``), so this stays cheap regardless of entry count.
    """
    if not get_config().path_catalog.is_file():
        return None
    catalog = store.load_catalog()
    if not catalog['entries']:
        return None
    triples = {(row['crs_hash'], row['transform_hash'], row['shape_hash']) for row in catalog['entries'].values()}

    specs = [_spec_info(crs, transform, shape) for crs, transform, shape in triples]
    resolution_labels = {spec.resolution_display for spec in specs if spec.resolution_display}
    bounds_by_key = {spec.bounds: (spec.bounds_display or 'None') for spec in specs if spec.bounds}

    # The eager build derives options from entries, so entries missing a
    # dimension contribute a 'None' key for resolution and bounds.
    if any(not spec.resolution_display for spec in specs):
        resolution_labels.add('None')
    if any(not spec.bounds for spec in specs):
        bounds_by_key['None'] = 'None'

    def _none_first(keys):
        return sorted(keys, key=lambda k: (k != 'None', k))

    return {
        SpecKeys.CRS: sorted({spec.crs for spec in specs if spec.crs}),
        SpecKeys.RESOLUTION: [{'value': k, 'label': k} for k in _none_first(resolution_labels)],
        SpecKeys.SHAPE: sorted({spec.shape for spec in specs if spec.shape}),
        SpecKeys.BOUNDS: [{'value': k, 'label': bounds_by_key[k]} for k in _none_first(bounds_by_key)],
    }
