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
cache roots and the catalog JSON.

## How the project's classes are read

The browser process never imports project code. All class knowledge comes from
one `ProjectAnalysis` held in the app state, in one of two modes fixed at startup:

- **static** (default): `pygeodata.static.analyse_project` parses the project's
  `.py` files in-process; no project code runs.
- **import** (`pygeodata browse --import-all`): `analyse_in_subprocess` imports the
  project in a fresh interpreter and decodes the result.

The **Reload** button re-runs the startup mode's analysis and rebuilds the state at
once. Every 10 s the server stats the project's files (`iter_project_files`; mtimes
only). In static mode a change is re-analysed immediately. In import mode it is only
noted: the UI keeps showing the last import with *Code changed since the last import
— next import at HH:MM · Reload now*, and the subprocess runs at the next
`--reconcile-interval` tick (default 5 min), once however many edits there were. The
same tick rebuilds the state when the catalog file changed. A failed analysis keeps
the last good state and surfaces the error in the UI; unparsable files and duplicate
class names (`analysis.problems`) are listed in the registry diagnostics.

`GET /api/status` reports `mode`, `code_changed_since` and `next_import_at` (epoch
seconds; the last two are set in import mode while code changed since the last import).

> **Hazard:** `--import-all` imports **every** `.py` file at the project root and in
> its packages. A root-level script without an `if __name__ == '__main__':` guard
> **runs** (for example a `run.py` pipeline), on every import, automatically every few
> minutes while you edit. Guard such scripts before using import mode.

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
