from importlib.metadata import PackageNotFoundError, version

from pygeodata_browser.serve import open_registry_browser

try:
    __version__ = version('pygeodata-browser')
except PackageNotFoundError:  # imported from a source tree that is not installed
    __version__ = '0+unknown'

__all__ = ['open_registry_browser', '__version__']
