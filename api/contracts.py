"""The browser's JSON responses: one type per payload, encoded with msgspec; field names are the JSON keys.

``app/src/lib/api.ts`` and ``apiCode.ts`` mirror these; ``tests/test_contracts.py`` keeps the field names in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pygeodata.catalog.store import SkippedDirs
from pygeodata.catalog.types import CatalogWriter, ParamRowType
from pygeodata.registries.registry_types import ChangeStatus
from pygeodata.views.types import SpecInfo

JsonValue = dict[str, 'JsonValue'] | list['JsonValue'] | str | int | float | bool | None

Mode = Literal['static', 'import']


@dataclass
class Ok:
    ok: bool = True


@dataclass
class LoadingPayload:
    fast: bool
    loading: Literal[True] = True


@dataclass
class StatusPayload:
    ready: bool
    load_error: str | None
    version: int
    has_live_classes: bool
    mode: Mode
    code_changed_since: float | None
    next_import_at: float | None
    fast: bool


@dataclass
class BootstrapRow:
    state_hash: str
    class_name: str
    object_type: str
    source_hash: str
    dependency_tree_hash: str
    instance_hash: str
    params_hash: str
    spec_hash: str
    created_at: float


@dataclass
class FileRef:
    """An output file of an entry as the browser serves it: absolute path and display label."""

    label: str
    path: str
    kind: str


@dataclass
class ParamRowPayload:
    group: str
    parameter: str
    value: str
    value_type: str
    param_row_type: ParamRowType
    path: str
    depth: int


@dataclass
class EntryRef:
    record_id: str
    class_name: str
    object_type: str | None


@dataclass
class FoundEntries:
    entries: list[EntryRef]


@dataclass
class PinsPayload:
    pins: list[EntryRef]


# --- classes ---------------------------------------------------------------


@dataclass
class ClassCard:
    class_name: str
    object_type: str | None
    loaded: bool
    call_dependency_names: list[str]
    inheritance_dependency_names: list[str]
    total_record_count: int
    visible_record_count: int
    selected: bool
    source_stale: bool
    deps_stale: bool
    format_version_stale: bool


@dataclass
class SpecOption:
    value: str
    label: str


@dataclass
class SpecOptions:
    crs: list[str]
    resolution: list[SpecOption]
    shape: list[str]
    bounds: list[SpecOption]


@dataclass
class VersionOption:
    version_id: str
    mtime: str
    label: str
    class_names: list[str]
    changed_class_names: list[str]
    has_entries: bool


@dataclass
class Diagnostics:
    entries: int
    catalog_id: str
    read_only: bool | None
    unindexed_dirs: int
    unindexed_reasons: SkippedDirs | None
    missing_dirs: int
    unavailable_roots: list[str]
    created_entries: int
    offline_entries: int
    problems: list[str]
    stale_hidden: int = 0


@dataclass
class UnavailableRoot:
    path: str
    name: str
    entries: int
    since: float


@dataclass
class CatalogInfo:
    mode: Literal['mirror', 'writable']
    read_only: bool
    reason: str
    catalog_id: str
    writer: CatalogWriter
    pins_path: str
    thumbs_path: str
    absolute_dir_entries: int
    unavailable_roots: list[UnavailableRoot]


@dataclass
class Counts:
    classes: int
    classes_loaded: int
    entries: int
    visible_classes: int
    visible_entries: int


@dataclass
class ClassesPayload:
    class_cards: list[ClassCard]
    spec_options: SpecOptions
    version_options: list[VersionOption]
    diagnostics: Diagnostics
    catalog: CatalogInfo
    counts: Counts


# --- entry pages -----------------------------------------------------------


@dataclass
class HeaderRow:
    class_name: str
    record_id: str
    object_type: str | None
    spec: SpecInfo
    focused: bool
    source_stale: bool
    dep_hash_stale: bool
    format_version_stale: bool
    offline_root: str | None
    dep_hash: str | None
    row_type: Literal['header'] = 'header'


@dataclass
class DetailRow(ParamRowPayload):
    class_name: str
    record_id: str
    row_type: Literal['detail'] = 'detail'


@dataclass
class EntriesPage:
    table_rows: list[HeaderRow | DetailRow]
    total: int
    offset: int
    limit: int


@dataclass
class EntryIds:
    ids: list[str]
    total: int


@dataclass
class ExportTable:
    table_rows: list[HeaderRow | DetailRow]


# --- entry detail ----------------------------------------------------------


@dataclass
class LinkedEntryPayload:
    param_name: str
    class_name: str
    state_hash: str | None
    params_summary: dict[str, list[str]]


@dataclass
class CoOutput:
    record_id: str
    class_name: str
    object_type: str | None
    state_hash: str | None
    offline: bool
    primary_file: FileRef | None
    rows: list[ParamRowPayload]
    diff_rows: list[ParamRowPayload]


@dataclass
class SameInstanceRun:
    record_id: str
    class_name: str
    state_hash: str | None
    offline: bool
    primary_file: FileRef | None
    spec: SpecInfo


@dataclass
class DepVersionSibling:
    record_id: str
    dep_hash: str | None
    dep_hash_stale: bool
    version_id: str | None
    version_label: str | None
    is_self: bool
    spec: SpecInfo


@dataclass
class CodeVersionEntry:
    source_hash: str
    mtime: str
    is_version_change: bool


@dataclass
class EntryDetail:
    record_id: str
    state_hash: str | None
    instance_hash: str | None
    class_name: str
    object_type: str | None
    dep_hash_stale: bool
    format_version_stale: bool
    offline_root: str | None
    dep_hash: str | None
    params_path: str
    state_hash_path: str | None
    execution_graph_path: str | None
    spec: SpecInfo
    primary_file: FileRef | None
    sidecar_files: list[FileRef]
    figure_preview: str | None
    table_preview: str | None
    co_outputs: list[CoOutput]
    same_instance_runs: list[SameInstanceRun]
    rows: list[ParamRowPayload]
    params_tree: dict[str, JsonValue]
    linked_entries: list[LinkedEntryPayload]


@dataclass
class ClassDetail:
    class_name: str
    object_type: str | None
    loaded: bool
    call_dependency_names: list[str]
    inheritance_dependency_names: list[str]
    source_available: bool
    graph_available: bool
    class_source_path: str | None
    class_graph_path: str | None
    class_registry_path: str | None
    class_tree_path: str | None
    source_stale: bool
    deps_stale: bool


@dataclass
class DetailPayload(ClassDetail):
    code_versions: list[CodeVersionEntry]
    entry_version_id: str | None
    entry_version_label: str | None
    dep_version_siblings: list[DepVersionSibling]
    selected_entry: EntryDetail


# --- popups ----------------------------------------------------------------


@dataclass
class JsonPopup:
    title: str
    json: JsonValue


@dataclass
class GraphSvgPopup:
    title: str
    svg: str


@dataclass
class GraphPdfPopup:
    title: str
    pdf_path: str


# --- code ------------------------------------------------------------------


@dataclass
class VersionsPayload:
    versions: list[VersionOption]
    has_live_classes: bool


@dataclass
class ResolvedDepHash:
    version_id: str | None
    source_hash: str


@dataclass
class ResolvedSourceHash:
    version_id: str


@dataclass
class SnapshotLine:
    text: str
    cls_link: str | None


@dataclass
class SnapshotPayload:
    class_name: str | None
    lines: list[SnapshotLine]


@dataclass
class DiffSegment:
    type: Literal['eq', 'del', 'ins']
    text: str


@dataclass
class DiffLine:
    type: Literal['ctx', 'del', 'add']
    text: str
    line_old: int | None
    line_new: int | None
    segments: list[DiffSegment] | None = None


@dataclass
class DiffHunk:
    header: str
    start_old: int
    start_new: int
    lines: list[DiffLine]


@dataclass
class DiffPayload:
    hunks: list[DiffHunk]


@dataclass
class FullDiffPayload(DiffPayload):
    full_old: str
    full_new: str


@dataclass
class VersionChange:
    class_name: str
    status: ChangeStatus
    hash_old: str | None
    hash_new: str | None


@dataclass
class VersionDiff:
    changes: list[VersionChange]
    base_version_id: str | None
    has_live_stale: bool


@dataclass
class VersionDiffError:
    error: Literal['bad_request', 'no_snapshot']
    message: str


# --- maintenance and export ------------------------------------------------


@dataclass
class CleanResult:
    lines: list[str]
    dry_run: bool


@dataclass
class ExportStart:
    job_id: str
    total: int
    warnings: list[str]


@dataclass
class ExportStatus:
    status: Literal['running', 'complete', 'error']
    done: int
    total: int
    error: str | None
    warnings: list[str]
