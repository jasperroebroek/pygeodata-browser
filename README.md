# pygeodata-browser

QC and code-review dashboard for [pygeodata](../pygeodata) projects. Serves the
registry browser: class column, entries table, entry detail popups, code
versioning view, export view, and bounds map.

The CLI stays in core — `pygeodata browse` delegates to this package. To run
standalone:

```
python -m pygeodata_browser
```

The package reads the same on-disk layout as the legacy in-repo browser
(`.source/` registries, cache roots, `.source/catalog.db`) and is a drop-in
replacement for it.

## Install

```
pip install pygeodata-browser
# or, from the core package:
pip install pygeodata[browser]
```

## Development

```
ruff format . && ruff check .
python -m pytest -q
```
