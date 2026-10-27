# pygeodata-browser

QC and code-review dashboard for [pygeodata](../pygeodata) projects. Serves the
registry browser: class column, entries table, entry detail popups, code
versioning view, export view, and bounds map.

The CLI stays in core — `pygeodata browse` delegates to this package. To run
standalone:

```
python -m pygeodata_browser
```

It reads a pygeodata project's on-disk state: the `.source/` registries, the
cache roots and `.source/catalog.db`.

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

### Frontend

The UI is a Svelte app in `app/`. Its build output, `api/static/app/`, is what
the server serves at `/`; it is not committed.

```
cd app
npm ci
npx vite --port 5173      # dev server with hot reload; proxies /api to the browser on :8780
npm run check             # type check
npm run build             # writes api/static/app/ (needed for `pygeodata browse` from a checkout)
```

`app/e2e/` holds Playwright scripts (screenshots, toggle and detail checks, timings); see its README.

## Release

The version comes from the git tag (setuptools-scm); there is no version string
to bump. Pushing a version tag publishes to PyPI:

```
git tag v0.1.0 && git push --tags
```

`.github/workflows/release.yml` builds the frontend, builds the wheel and sdist
(both ship the prebuilt frontend, so installing never needs Node), checks them
with `scripts/check_dist.py`, and publishes through PyPI trusted publishing.

Requires pygeodata 0.3.x; release a compatible pygeodata first when both change.
