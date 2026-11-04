from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pygeodata._version import FORMAT_VERSION
from pygeodata.catalog import store
from pygeodata.paths import CachePathConstructor
from pygeodata.views.types import SpecInfo, spec_info

if TYPE_CHECKING:
    from pygeodata.catalog.types import CatalogEntry, LinkedEntry, ParamRow
    from pygeodata.catalog.types import FileRef as CatalogFileRef
    from pygeodata.records import SpecRecord


@dataclass
class FileRef:
    """An output file of an entry as the browser serves it: absolute path and display label."""

    label: str
    path: str
    kind: str


@dataclass
class EntryInfo:
    """One entry as the browser displays it, assembled from a ``CatalogEntry`` and its ``SpecRecord``."""

    class_name: str
    object_type: str | None
    params_path: str
    state_hash_path: str | None
    execution_graph_path: str | None
    state_hash: str | None
    instance_hash: str | None
    params_hash: str | None
    spec_hash: str | None
    spec: SpecInfo
    rows: list[ParamRow]
    linked_entries: list[LinkedEntry] = field(default_factory=list)
    co_output_hashes: list[str] = field(default_factory=list)
    primary_file: FileRef | None = None
    sidecar_files: list[FileRef] = field(default_factory=list)
    format_version: int = 0
    record_id: str = ''
    dep_hash: str | None = None
    dep_hash_stale: bool = False
    offline_root: str | None = None
    co_outputs: list[EntryInfo] = field(default_factory=list)

    @property
    def format_version_stale(self) -> bool:
        return self.format_version != FORMAT_VERSION

    @property
    def offline(self) -> bool:
        return self.offline_root is not None

    @property
    def entry_dir(self) -> Path:
        return Path(self.params_path).parent


def entry_info(entry: CatalogEntry, spec: SpecRecord | None) -> EntryInfo:
    rec = entry.record
    entry_dir = store.entry_dir(entry)
    paths = CachePathConstructor(entry_dir)

    def file_ref(ref: CatalogFileRef) -> FileRef:
        return FileRef(label=Path(ref.relpath).name, path=str(entry_dir / ref.relpath), kind=ref.kind)

    return EntryInfo(
        record_id=rec.state_hash,
        class_name=rec.class_name,
        object_type=rec.object_type,
        params_path=str(paths.params_path),
        state_hash_path=str(paths.state_hash_path),
        execution_graph_path=str(paths.execution_graph_path),
        state_hash=rec.state_hash,
        instance_hash=rec.instance_hash,
        params_hash=rec.params_hash,
        spec_hash=rec.spec_hash,
        spec=spec_info(spec),
        rows=entry.rows,
        linked_entries=entry.linked_entries,
        co_output_hashes=rec.co_output_hashes,
        primary_file=file_ref(entry.primary_file) if entry.primary_file else None,
        sidecar_files=[file_ref(f) for f in entry.sidecar_files],
        format_version=rec.format_version,
        dep_hash=rec.dependency_tree_hash,
    )
