import pytest
from pygeodata.config import set_config


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
