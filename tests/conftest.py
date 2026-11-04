from pathlib import Path
from types import SimpleNamespace

import pytest
from pygeodata._version import FORMAT_VERSION
from pygeodata.analysis import ClassRecord, ProjectAnalysis
from pygeodata.catalog.types import CatalogHeader, CatalogWriter
from pygeodata.config import set_config
from pygeodata.dependencies import ClassFacts
from pygeodata.paths import CachePathConstructor
from pygeodata.records import EntryRecord
from pygeodata_browser.catalog_context import CatalogContext
from pygeodata_browser.entry_store import EntryStore
from pygeodata_browser.models import EntryInfo


@pytest.fixture(autouse=True)
def registry_tmp_path(tmp_path):
    with set_config(
        path_registry=tmp_path / '.source',
        path_cache=tmp_path / 'data_processed',
        path_tables=tmp_path / 'tables',
        path_figures=tmp_path / 'figures',
        path_catalog=tmp_path / '.catalog.json',
    ):
        yield


def write_entry(
    cache_root: Path,
    state_hash: str,
    class_name: str = 'MyLoader',
    dep_hash: str = '',
    object_type: str = 'Data',
) -> Path:
    """Write the cache files of one entry; its dir is named by its state hash."""
    entry_dir = cache_root / state_hash
    entry_dir.mkdir(parents=True, exist_ok=True)
    paths = CachePathConstructor(entry_dir)
    EntryRecord(
        class_name=class_name,
        source_hash='src001',
        dependency_tree_hash=dep_hash,
        instance_hash='inst001',
        params_hash='par001',
        spec_hash='spec001',
        state_hash=state_hash,
        object_type=object_type,
        co_output_hashes=[],
        format_version=FORMAT_VERSION,
    ).dump(paths.state_hash_path)
    paths.params_path.write_text('{}')
    return entry_dir


def make_analysis(mode: str = 'static', **source_hashes: str) -> ProjectAnalysis:
    """An analysis of classes named by keyword, each a Data class with the given source hash and no dependencies."""
    classes = {
        name: ClassRecord(
            facts=ClassFacts(
                name=name,
                object_type='Data',
                source_hash=source_hash,
                call_deps=frozenset(),
                bases=frozenset(),
            ),
            path=f'{name}.py',
            lineno=1,
            tree_hash=f'tree-{source_hash}',
        )
        for name, source_hash in source_hashes.items()
    }
    return ProjectAnalysis(mode=mode, root='.', classes=classes)


def make_catalog_context(tmp_path: Path, read_only: bool = False) -> CatalogContext:
    header = CatalogHeader(
        catalog_version=1,
        schema_fingerprint='f',
        catalog_id='cid',
        writer=CatalogWriter(root=str(tmp_path), host='h', pygeodata='0', python='3', written_at=0.0),
        roots={},
    )
    return CatalogContext(
        read_only=read_only,
        reason='test',
        header=header,
        key='cid',
        pins_path=tmp_path / 'pins.json',
        thumbs_dir=tmp_path / 'thumbs',
        absolute_dir_entries=0,
        unavailable_roots=[],
    )


def make_entry_store(*entries: EntryInfo) -> EntryStore:
    """A real EntryStore over the given, already enriched entries (their records are derived from them)."""
    records = [
        EntryRecord(
            class_name=e.class_name,
            source_hash='',
            dependency_tree_hash=e.dep_hash or '',
            instance_hash=e.instance_hash or '',
            params_hash=e.params_hash or '',
            spec_hash=e.spec_hash or '',
            state_hash=e.record_id,
            object_type=e.object_type,
            co_output_hashes=[],
            format_version=e.format_version,
        )
        for e in entries
    ]
    registry = SimpleNamespace(entries={rec.state_hash: SimpleNamespace(record=rec) for rec in records})
    store = EntryStore(registry, lambda class_name: None)
    for entry in entries:
        store._by_id[entry.record_id] = entry
        store._entries_by_class.setdefault(entry.class_name, []).append(entry)
    return store
