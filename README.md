# pygeodata-browser

QC and code-review dashboard for [pygeodata](../pygeodata) projects. Serves the
registry browser: class column, entries table, entry detail popups, code
versioning view, export view, and bounds map.

The CLI stays in core — `pygeodata browse` delegates to this package, and its options
are defined there once. `python -m pygeodata_browser [OPTIONS]` runs that same command
(`pygeodata browse [OPTIONS]`), settings modules included.

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
— next import at HH:MM · Reload*, and the subprocess runs at the next
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

## Mirror mode

A project that runs on a server and is mirrored to a laptop (Nextcloud, rsync, ...) is
browsed on the laptop without ever writing into the mirror. The browser is **read-only**
("mirror mode") when the catalog's `writer.root` differs from the local project root (the
rule of `pygeodata.catalog.store.open_catalog`) or when `catalog_enabled` is False;
`pygeodata browse --read-only` / `--writable` override the detection. The mode and why
are shown at the top of the registry diagnostics, together with a health checklist
(unindexed entry dirs with the reason for each kind, missing dirs, unavailable cache roots,
offline entries, analysis problems, entries with absolute dir paths) and the catalog details:
the writer's root, host, versions and time, the `catalog_id` and the local paths below. A
mirror never reads entry dirs, so it cannot say why dirs are unindexed.

In mirror mode:

- the catalog is opened with `EntryRegistry(read_only=True)`: no save, prune or refresh,
  Reload rebuilds from the catalog file only;
- pins are kept in `user_data_dir("pygeodata-browser")/<catalog_id>/pins.json` (pygeodata's
  `Pin` type); the server's `.catalog.pins.json` is not shown. Writable mode keeps using
  `.catalog.pins.json`;
- delete entry, clean cache and clean registry are disabled in the UI and answer `409`;
- with `--import-all` the analysis subprocess runs with `PYTHONDONTWRITEBYTECODE=1`
  (unless `--writable`), so no `__pycache__` appears in the mirror. Project code that
  writes on import is still the project's own business.

Thumbnails are cached in `user_cache_dir("pygeodata-browser")/<catalog_id>/thumbs/` in both
modes, never in the project. A project without a catalog file has no stable id, so its local
state is keyed `root-<hash of the resolved project root>` instead.

A catalog written by an older (or newer) pygeodata cannot be rebuilt on a mirror: the UI shows
*The catalog was written by an older pygeodata; run `pygeodata catalog build` where it is
written (<root>)* rather than a traceback.

### Unavailable cache roots

A cache root that is missing or empty (an unsynced mirror, an unmounted share) keeps its
entries in the catalog (`CatalogDiff.unavailable_roots`), in both modes. The UI says so: a
banner above the entry list, a grey `offline` badge on the affected rows with download and
open disabled, the same badge and an explanation in the detail pane, and an
`Online` / `Offline (n)` filter beside the kind filter. Rows and details carry
`offline_root`, computed once per state build; `/api/classes` and `/api/class-entries` take
`offline_filter=all|online|offline`. `/api/classes` also returns the `catalog` info shown in
the Activity panel, including since when (first seen by this server process) each root is
unavailable.

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

Requires pygeodata 0.5.x; release a compatible pygeodata first when both change. The
release workflow runs `ci.yml` (the tests against pygeodata `main` and the minimum release,
and the frontend checks) before publishing.
