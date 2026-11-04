from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('pygeodata-browser')
except PackageNotFoundError:  # imported from a source tree that is not installed
    __version__ = '0+unknown'
