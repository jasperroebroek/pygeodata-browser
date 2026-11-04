from pathlib import Path

import pytest
from pygeodata._version import FORMAT_VERSION
from pygeodata.config import set_config
from pygeodata.paths import CachePathConstructor
from pygeodata.records import EntryRecord


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
