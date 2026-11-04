import json
import re
from dataclasses import replace
from pathlib import Path

from pygeodata.catalog.types import LinkedEntry, ParamRow, ParamRowType
from pygeodata.enums import SpecKeys
from pygeodata.formatting.json import format_json
from pygeodata.registries.registry import SourceRegistry
from pygeodata.registries.versioning import VersionRegistry
from pygeodata.views.filters import Filter, LogicMode, combine, entry_matches_filter, matching_rows, parse_filters
from pygeodata.views.types import ClassInfo
from pygeodata_browser.contracts import (
    ClassCard,
    ClassesPayload,
    CodeVersionEntry,
    CoOutput,
    Counts,
    DepVersionSibling,
    DetailPayload,
    DetailRow,
    EntriesPage,
    EntryDetail,
    EntryIds,
    EntryRef,
    HeaderRow,
    LinkedEntryPayload,
    ParamRowPayload,
    SameInstanceRun,
    VersionOption,
)
from pygeodata_browser.models import EntryInfo
from pygeodata_browser.state import AppState

_LIST_INDEX = re.compile(r'\[\d+\]$')


def _entry_matches_filters(entry: EntryInfo, filters: list[Filter], logic_mode: str) -> bool:
    if not filters:
        return True
    # EntryInfo carries the class_name, rows and spec.crs the entry filters read
    matches = [entry_matches_filter(entry, entry.spec, flt) for flt in filters]
    return combine(matches, LogicMode(logic_mode))


def _matching_rows(entry: EntryInfo, filters: list[Filter], logic_mode: str) -> list[ParamRow]:
    return matching_rows(entry, filters, LogicMode(logic_mode))


# ---------------------------------------------------------------------------
# Small serialisers — one responsibility each
# ---------------------------------------------------------------------------


def _row_payload(row: ParamRow) -> ParamRowPayload:
    return ParamRowPayload(
        group=row.key_group,
        parameter=row.final_key,
        value=row.value_text,
        value_type=row.value_type,
        param_row_type=row.row_type,
        path=row.path,
        depth=row.depth,
    )


def _linked_entries_payload(entry: EntryInfo) -> list[LinkedEntryPayload]:
    claimed: set[int] = set()
    return [_linked_entry_payload(le, entry, claimed) for le in entry.linked_entries]


def _linked_entry_payload(le: LinkedEntry, entry: EntryInfo, claimed: set[int]) -> LinkedEntryPayload:
    """The linked entry's params are flattened into the parent's rows under the
    link's own scope — derive the summary from those, nothing is stored.

    A link's scope is the child scope of its ref row: top-level links use
    ``param_name``, nested ones (e.g. ``features[3]`` inside ``feature_specs``)
    use ``feature_specs › features[3]``. Direct children of that scope are the
    linked loader's own params — ``feature_cls`` naming the actual feature.

    The same param name can occur at several depths (``df_loader`` inside
    ``df_loader``), so the ref row must also name the linked class, and each ref
    row serves one link; ``claimed`` carries that across an entry's links.
    """
    scope = None
    if le.param_name:
        refs = [
            (i, row)
            for i, row in enumerate(entry.rows)
            if i not in claimed
            and row.final_key == le.param_name
            and row.row_type in (ParamRowType.DATA_REF, ParamRowType.CLASS_REF)
        ]
        match = next(((i, row) for i, row in refs if row.value_text == le.class_name), refs[0] if refs else None)
        if match:
            i, row = match
            claimed.add(i)
            scope = f'{row.key_group} › {row.final_key}' if row.key_group else row.final_key
    summary: dict[str, list[str]] = {}
    if scope:
        for row in entry.rows:
            if row.key_group != scope:
                continue
            key = _LIST_INDEX.sub('[]', row.final_key)
            values = summary.setdefault(key, [])
            if key.endswith('[]') or not values:
                values.append(row.value_text)
    return LinkedEntryPayload(
        param_name=le.param_name,
        class_name=le.class_name,
        state_hash=le.state_hash,
        params_summary=summary,
    )


# ---------------------------------------------------------------------------
# Visibility / filtering
# ---------------------------------------------------------------------------


def _entry_matches_spec_filters(entry: EntryInfo, spec_filters: dict) -> bool:
    for dim in (SpecKeys.CRS, SpecKeys.SHAPE):
        selected = spec_filters.get(dim)
        if not selected:
            continue
        val = getattr(entry.spec, dim)
        if isinstance(selected, list):
            if selected and val not in selected:
                return False
        elif val != selected:
            return False

    selected_resolution = spec_filters.get(SpecKeys.RESOLUTION)
    if selected_resolution:
        entry_resolution = entry.spec.resolution_display or 'None'
        if isinstance(selected_resolution, list):
            if selected_resolution and entry_resolution not in selected_resolution:
                return False
        elif entry_resolution != selected_resolution:
            return False

    selected_bounds = spec_filters.get(SpecKeys.BOUNDS)
    if selected_bounds:
        entry_bounds = str(entry.spec.bounds)
        if isinstance(selected_bounds, list):
            if selected_bounds and entry_bounds not in selected_bounds:
                return False
        elif entry_bounds != selected_bounds:
            return False

    return True


def _entry_is_visible(
    *,
    class_name: str,
    entry: EntryInfo,
    selected_classes: list[str],
    kind_filter: str,
    spec_filters: dict,
    filters: list[Filter],
    logic_mode: str,
    hide_stale: bool = False,
    offline_filter: str = 'all',
    snapshot_filter: list[str] | None = None,
) -> bool:
    if hide_stale and (entry.dep_hash_stale or entry.format_version_stale):
        return False
    if (offline_filter == 'online' and entry.offline) or (offline_filter == 'offline' and not entry.offline):
        return False
    if snapshot_filter and entry.dep_hash not in snapshot_filter:  # snapshot_filter is a resolved set of dep_hashes
        return False
    if selected_classes and class_name not in selected_classes:
        return False
    if kind_filter != 'all' and (entry.object_type or '').lower() != kind_filter and class_name not in selected_classes:
        return False
    if not _entry_matches_spec_filters(entry, spec_filters):
        return False
    return _entry_matches_filters(entry, filters, logic_mode)


# ---------------------------------------------------------------------------
# Query helpers — build filtered views of state
# ---------------------------------------------------------------------------


def _sidebar_counts(
    state: AppState,
    *,
    kind_filter: str,
    spec_filters: dict,
    filters: list[Filter],
    logic_mode: str,
    hide_stale: bool = False,
    offline_filter: str = 'all',
    snapshot_filter: list[str] | None = None,
) -> dict[str, int]:
    if not filters and not spec_filters:
        # Fast path: identity-column counts; per-entry display never loads.
        return state.entries.count_by_class(
            kind_filter=kind_filter,
            snapshot_dep_hashes=set(snapshot_filter) if snapshot_filter else None,
            hide_stale=hide_stale,
            object_type_by_class={name: ci.object_type for name, ci in state.classes.items()},
            offline_filter=offline_filter,
        )
    counts: dict[str, int] = {}
    for class_name, class_info in state.classes.items():
        if kind_filter != 'all' and (class_info.object_type or '').lower() != kind_filter:
            continue
        record_ids = state.entry_registry.get_state_hashes(class_name)
        n = sum(
            1
            for rid in record_ids
            if _entry_is_visible(
                class_name=class_name,
                entry=state.entries[rid],
                selected_classes=[],
                kind_filter=kind_filter,
                spec_filters=spec_filters,
                filters=filters,
                logic_mode=logic_mode,
                hide_stale=hide_stale,
                offline_filter=offline_filter,
                snapshot_filter=snapshot_filter,
            )
        )
        if n:
            counts[class_name] = n
    return counts


def _build_visible_groups(
    state: AppState,
    *,
    selected_classes: list[str],
    kind_filter: str,
    spec_filters: dict,
    filters: list[Filter],
    logic_mode: str,
    hide_stale: bool = False,
    offline_filter: str = 'all',
    snapshot_filter: list[str] | None = None,
) -> list[tuple[str, list[EntryInfo]]]:
    visible_groups: list[tuple[str, list[EntryInfo]]] = []

    for class_name, class_info in sorted(state.classes.items()):
        if (
            kind_filter != 'all'
            and (class_info.object_type or '').lower() != kind_filter
            and class_name not in selected_classes
        ):
            continue

        # The selected-class check lives in _entry_is_visible, but the entries
        # lookup happens first — with lazy per-class enrichment that would
        # enrich every class on a single selection, so skip early here instead.
        if selected_classes and class_name not in selected_classes:
            continue

        record_ids = state.entry_registry.get_state_hashes(class_name)

        visible_entries = [
            state.entries[rid]
            for rid in record_ids
            if _entry_is_visible(
                class_name=class_name,
                entry=state.entries[rid],
                selected_classes=selected_classes,
                kind_filter=kind_filter,
                spec_filters=spec_filters,
                filters=filters,
                logic_mode=logic_mode,
                hide_stale=hide_stale,
                offline_filter=offline_filter,
                snapshot_filter=snapshot_filter,
            )
        ]

        if visible_entries:
            visible_groups.append((class_name, visible_entries))

    return visible_groups


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _build_class_cards(
    state: AppState,
    *,
    sidebar_counts: dict[str, int],
    selected_classes: list[str],
    snapshot_dep_hashes: set[str] | None = None,
) -> list[ClassCard]:
    # When a snapshot filter is active, derive stale status from the visible entries:
    # a class is stale if any of its snapshot entries have dep_hash_stale=True.
    snapshot_stale_classes: set[str] = set()
    if snapshot_dep_hashes is not None:
        for class_name in state.entry_registry.class_names:
            if class_name in snapshot_stale_classes:
                continue
            for rec in state.entries.records_for_class(class_name):
                if rec.dependency_tree_hash in snapshot_dep_hashes and state.entries.dep_hash_stale(
                    class_name,
                    rec.dependency_tree_hash,
                ):
                    snapshot_stale_classes.add(class_name)
                    break

    class_cards = []
    for class_name, class_info in sorted(state.classes.items()):
        record_ids = state.entry_registry.get_state_hashes(class_name)
        format_version_stale = any(not rec.is_current_format for rec in state.entries.records_for_class(class_name))
        if snapshot_dep_hashes is not None:
            source_stale = class_name in snapshot_stale_classes
            deps_stale = False
        else:
            source_stale = class_info.source_stale
            deps_stale = class_info.deps_stale
        class_cards.append(
            ClassCard(
                class_name=class_name,
                object_type=class_info.object_type,
                loaded=class_info.known,
                call_dependency_names=class_info.call_dependency_names,
                inheritance_dependency_names=class_info.inheritance_dependency_names,
                total_record_count=len(record_ids),
                visible_record_count=sidebar_counts.get(class_name, 0),
                selected=class_name in selected_classes,
                source_stale=source_stale,
                deps_stale=deps_stale,
                format_version_stale=format_version_stale,
            ),
        )
    return class_cards


def _build_table_rows(
    *,
    visible_groups: list[tuple[str, list[EntryInfo]]],
    classes: dict[str, ClassInfo],
    selected_entry: str | None,
    filters: list[Filter],
    logic_mode: str,
    row_display: str,
) -> list[HeaderRow | DetailRow]:
    table_rows: list[HeaderRow | DetailRow] = []

    for class_name, group_entries in visible_groups:
        ci = classes.get(class_name)
        for entry in group_entries:
            table_rows.append(
                HeaderRow(
                    class_name=class_name,
                    record_id=entry.record_id,
                    object_type=entry.object_type,
                    spec=entry.spec,
                    focused=entry.record_id == selected_entry,
                    source_stale=ci.source_stale if ci else False,
                    dep_hash_stale=entry.dep_hash_stale,
                    format_version_stale=entry.format_version_stale,
                    offline_root=entry.offline_root,
                    dep_hash=entry.dep_hash,
                ),
            )

            if row_display == 'all':
                detail_rows = entry.rows
            elif row_display == 'selected':
                detail_rows = _matching_rows(entry, filters, logic_mode)
            else:
                detail_rows = []

            for row in detail_rows:
                table_rows.append(
                    DetailRow(**vars(_row_payload(row)), class_name=class_name, record_id=entry.record_id),
                )

    return table_rows


def _co_output_diff_rows(co_entry: EntryInfo, main_entry: EntryInfo) -> list[ParamRowPayload]:
    main_by_path = {r.path: r.value_text for r in main_entry.rows}
    return [_row_payload(r) for r in co_entry.rows if main_by_path.get(r.path) != r.value_text]


def _co_output_payload(entry: EntryInfo, main_entry: EntryInfo) -> CoOutput:
    return CoOutput(
        record_id=entry.record_id,
        class_name=entry.class_name,
        object_type=entry.object_type,
        state_hash=entry.state_hash,
        offline=entry.offline,
        primary_file=entry.primary_file,
        rows=[_row_payload(r) for r in entry.rows],
        diff_rows=_co_output_diff_rows(entry, main_entry),
    )


def _same_instance_run_payload(sibling: EntryInfo) -> SameInstanceRun:
    return SameInstanceRun(
        record_id=sibling.record_id,
        class_name=sibling.class_name,
        state_hash=sibling.state_hash,
        offline=sibling.offline,
        primary_file=sibling.primary_file,
        spec=sibling.spec,
    )


def _preview_path(entry: EntryInfo, kind: str) -> str | None:
    file = entry.primary_file
    return file.path if file and file.kind == kind and not entry.offline else None


def _entry_detail_payload(entry: EntryInfo, same_instance_runs: list[EntryInfo]) -> EntryDetail:
    return EntryDetail(
        record_id=entry.record_id,
        state_hash=entry.state_hash,
        instance_hash=entry.instance_hash,
        class_name=entry.class_name,
        object_type=entry.object_type,
        dep_hash_stale=entry.dep_hash_stale,
        format_version_stale=entry.format_version_stale,
        offline_root=entry.offline_root,
        dep_hash=entry.dep_hash,
        params_path=entry.params_path,
        state_hash_path=entry.state_hash_path,
        execution_graph_path=entry.execution_graph_path,
        spec=entry.spec,
        primary_file=entry.primary_file,
        sidecar_files=entry.sidecar_files,
        figure_preview=_preview_path(entry, 'image'),
        table_preview=_preview_path(entry, 'table'),
        co_outputs=[_co_output_payload(e, entry) for e in entry.co_outputs],
        same_instance_runs=[_same_instance_run_payload(s) for s in same_instance_runs],
        rows=[_row_payload(r) for r in entry.rows],
        params_tree=format_json(_params_tree(entry)),
        linked_entries=_linked_entries_payload(entry),
    )


def _params_tree(entry: EntryInfo) -> dict:
    """The raw params tree — read from disk on demand, never during import."""
    path = Path(entry.params_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def _dep_version_sibling_payload(
    entry: EntryInfo,
    vreg: VersionRegistry,
    *,
    is_self: bool = False,
) -> DepVersionSibling:
    version = vreg.version_for_dep_hash(entry.dep_hash) if entry.dep_hash else None
    return DepVersionSibling(
        record_id=entry.record_id,
        dep_hash=entry.dep_hash,
        dep_hash_stale=entry.dep_hash_stale,
        version_id=version.version_id if version else None,
        version_label=vreg.label(version) if version else None,
        is_self=is_self,
        spec=entry.spec,
    )


def version_groups_payload(vreg: VersionRegistry, entry_dep_hashes: set[str] | None = None) -> list[VersionOption]:
    """Serialize VersionRegistry.versions for the browser API.

    entry_dep_hashes: the set of dep_hashes from live entries.  When provided,
    each group is annotated with has_entries=True iff at least one entry's
    dep_hash maps to that group.  When omitted, has_entries is always True.
    """
    if entry_dep_hashes is not None:
        version_has_entries: dict[str, bool] = {v.version_id: False for v in vreg.versions}
        for dh in entry_dep_hashes:
            v = vreg.version_for_dep_hash(dh)
            if v is not None:
                version_has_entries[v.version_id] = True
    else:
        version_has_entries = {v.version_id: True for v in vreg.versions}

    return [
        VersionOption(
            version_id=vi.version_id,
            mtime=vi.mtime,
            label=vreg.label(vi),
            class_names=vi.class_names,
            changed_class_names=vi.changed_class_names,
            has_entries=version_has_entries.get(vi.version_id, False),
        )
        for vi in vreg.versions
    ]


def _class_version_history(class_name: str, src: SourceRegistry) -> list[CodeVersionEntry]:
    """Return code versions for a class sorted oldest-first."""
    return [
        CodeVersionEntry(
            source_hash=s.source_hash,
            mtime=s.registered_at,
            is_version_change=src.is_version_change(s),
        )
        for s in src.get_states(class_name)
    ]


def _build_detail_payload(*, state: AppState, entry: EntryInfo) -> DetailPayload | None:
    class_info = state.classes.get(entry.class_name)
    if class_info is None:
        return None
    vreg = state.version_registry
    siblings: list[EntryInfo] = []
    if entry.instance_hash:
        sibling_ids = sorted(
            rid for rid in state.entries.ids_by_instance_hash(entry.instance_hash) if rid != entry.record_id
        )
        siblings = [state.entries.get(rid) for rid in sibling_ids if rid in state.entries]
    dep_version_entries: list[EntryInfo] = []
    if entry.params_hash and entry.spec_hash:
        dep_ids = sorted(state.entries.ids_by_params_hash(entry.class_name, entry.params_hash, entry.spec_hash))
        dep_version_entries = [state.entries.get(rid) for rid in dep_ids if rid in state.entries]
        dep_version_entries.sort(
            key=lambda e: (
                vreg.version_for_dep_hash(e.dep_hash).mtime
                if e.dep_hash and vreg.version_for_dep_hash(e.dep_hash)
                else ''
            ),
            reverse=True,
        )
    entry_version = vreg.version_for_dep_hash(entry.dep_hash) if entry.dep_hash else None
    return DetailPayload(
        class_name=class_info.class_name,
        object_type=class_info.object_type,
        loaded=class_info.known,
        call_dependency_names=class_info.call_dependency_names,
        inheritance_dependency_names=class_info.inheritance_dependency_names,
        source_available=bool(class_info.class_source_path),
        graph_available=bool(class_info.class_graph_path),
        class_source_path=class_info.class_source_path,
        class_graph_path=class_info.class_graph_path,
        class_registry_path=class_info.class_registry_path,
        class_tree_path=class_info.class_tree_path,
        source_stale=class_info.source_stale,
        deps_stale=class_info.deps_stale,
        code_versions=_class_version_history(entry.class_name, vreg.source_registry),
        entry_version_id=entry_version.version_id if entry_version else None,
        entry_version_label=vreg.label(entry_version) if entry_version else None,
        dep_version_siblings=[
            _dep_version_sibling_payload(e, vreg, is_self=e.record_id == entry.record_id) for e in dep_version_entries
        ],
        selected_entry=_entry_detail_payload(entry, siblings),
    )


# ---------------------------------------------------------------------------
# Dep-hash (snapshot) options
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Split endpoints — the Svelte client fetches classes, entry pages, and one
# entry's detail separately so a click never re-downloads the whole table.
# ---------------------------------------------------------------------------


def build_classes_payload(
    state: AppState,
    *,
    kind_filter: str = 'all',
    spec_filters: dict | None = None,
    filters: list[dict] | None = None,
    logic_mode: str = 'AND',
    hide_stale: bool = False,
    offline_filter: str = 'all',
    version_filter: str | None = None,
) -> ClassesPayload:
    vreg = state.version_registry
    parsed_filters = parse_filters(filters or [])
    spec_filters = spec_filters or {}
    version_obj = vreg.version_by_id(version_filter) if version_filter else None
    dep_hash_set = vreg.dep_hashes_for_version(version_obj) if version_obj is not None else None

    sidebar_counts = _sidebar_counts(
        state,
        kind_filter=kind_filter,
        spec_filters=spec_filters,
        filters=parsed_filters,
        logic_mode=logic_mode,
        hide_stale=hide_stale,
        offline_filter=offline_filter,
        snapshot_filter=dep_hash_set,
    )

    if hide_stale:
        stale_hidden = 0
        for class_name in state.entry_registry.class_names:
            for rec in state.entries.records_for_class(class_name):
                if rec.dependency_tree_hash and state.entries.dep_hash_stale(class_name, rec.dependency_tree_hash):
                    stale_hidden += 1
    else:
        stale_hidden = 0

    return ClassesPayload(
        class_cards=_build_class_cards(
            state,
            sidebar_counts=sidebar_counts,
            selected_classes=[],
            snapshot_dep_hashes=dep_hash_set,
        ),
        spec_options=state.spec_options,
        version_options=version_groups_payload(vreg),
        diagnostics=replace(state.diagnostics, stale_hidden=stale_hidden),
        catalog=state.catalog.info(),
        counts=Counts(
            classes=len(state.classes),
            classes_loaded=sum(1 for c in state.classes.values() if c.known),
            entries=len(state.entries),
            visible_classes=len(sidebar_counts),
            visible_entries=sum(sidebar_counts.values()),
        ),
    )


def build_entries_page_payload(
    state: AppState,
    *,
    selected_classes: list[str],
    kind_filter: str = 'all',
    spec_filters: dict | None = None,
    filters: list[dict] | None = None,
    logic_mode: str = 'AND',
    hide_stale: bool = False,
    offline_filter: str = 'all',
    version_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
    row_display: str = 'none',
    selected_entry: str | None = None,
    ids_only: bool = False,
    max_rows: int | None = None,
    only_ids: set[str] | None = None,
) -> EntriesPage | EntryIds:
    """One page of visible header rows across the selected classes.

    ``only_ids`` further restricts the result to those entries (the pinned view).

    Filtering always sees the full class; only the payload is paginated, so
    ``total`` is exact for the current filter state. ``max_rows`` additionally
    caps a page by param rows (at least one entry), so pages of wide classes
    stay cheap to transfer and lay out; clients page on by the headers received. With ``ids_only`` (and
    ``selected_classes`` empty = all classes) it returns the visible record ids
    — the export view's fallback set — without building any table rows.
    """
    vreg = state.version_registry
    parsed_filters = parse_filters(filters or [])
    spec_filters = spec_filters or {}
    version_obj = vreg.version_by_id(version_filter) if version_filter else None
    dep_hash_set = vreg.dep_hashes_for_version(version_obj) if version_obj is not None else None

    if ids_only and not parsed_filters and not spec_filters and only_ids is None:
        ids = state.entries.visible_ids(
            selected_classes=selected_classes,
            kind_filter=kind_filter,
            snapshot_dep_hashes=dep_hash_set,
            hide_stale=hide_stale,
            object_type_by_class={name: ci.object_type for name, ci in state.classes.items()},
            offline_filter=offline_filter,
        )
        return EntryIds(ids=ids, total=len(ids))

    visible_groups = _build_visible_groups(
        state,
        selected_classes=selected_classes,
        kind_filter=kind_filter,
        spec_filters=spec_filters,
        filters=parsed_filters,
        logic_mode=logic_mode,
        hide_stale=hide_stale,
        offline_filter=offline_filter,
        snapshot_filter=dep_hash_set,
    )
    entries = [
        (class_name, e)
        for class_name, group in visible_groups
        for e in group
        if only_ids is None or e.record_id in only_ids
    ]
    total = len(entries)
    if ids_only:
        return EntryIds(ids=[e.record_id for _, e in entries], total=total)
    offset = max(offset, 0)
    limit = max(min(limit, 500), 1)
    page = entries[offset : offset + limit]
    if max_rows and row_display != 'none':
        budget = max_rows
        for n, (_, e) in enumerate(page):
            budget -= len(e.rows)
            if budget < 0:
                page = page[: max(n, 1)]
                break

    page_groups: list[tuple[str, list[EntryInfo]]] = []
    for class_name, e in page:
        if page_groups and page_groups[-1][0] == class_name:
            page_groups[-1][1].append(e)
        else:
            page_groups.append((class_name, [e]))

    return EntriesPage(
        table_rows=_build_table_rows(
            visible_groups=page_groups,
            classes=state.classes,
            selected_entry=selected_entry,
            filters=parsed_filters,
            logic_mode=logic_mode,
            row_display=row_display,
        ),
        total=total,
        offset=offset,
        limit=limit,
    )


def build_entry_detail_payload(state: AppState, *, record_id: str) -> DetailPayload | None:
    entry = state.entries.get(record_id)
    if entry is None:
        return None
    return _build_detail_payload(state=state, entry=entry)


def _entry_ref(state: AppState, record_id: str) -> EntryRef:
    """Identity of one entry (id, class, kind) without enriching its class."""
    class_name = state.entries.class_of(record_id)
    info = state.classes.get(class_name)
    return EntryRef(record_id=record_id, class_name=class_name, object_type=info.object_type if info else None)


def build_find_entries_payload(state: AppState, prefix: str, limit: int = 20) -> list[EntryRef]:
    """Entries whose id starts with ``prefix``."""
    ids = [record_id for record_id in sorted(state.entries.keys()) if record_id.startswith(prefix)]
    return [_entry_ref(state, record_id) for record_id in ids[:limit]]


def build_pinned_entries_payload(state: AppState, pins: list[str]) -> list[EntryRef]:
    """Pinned entries that still exist, in pin order."""
    return [_entry_ref(state, record_id) for record_id in pins if record_id in state.entries]
