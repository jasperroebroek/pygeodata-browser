# Changelog

## 0.5.0 (unreleased)

Released together with pygeodata 0.5.0, which it requires (`pygeodata>=0.5,<0.6`).
The version jumps from 0.2 to 0.5 so the two packages share their version numbers from now on.

### The browser never imports your project
- Classes are read from the project's source by default: no project code runs in the
  browser process, and edits show up within about ten seconds.
- `--import-all` imports the project in a fresh subprocess instead. Changed code is
  noted ("Code changed since the last import — next import at HH:MM"), and the import
  runs at the next `--reconcile-interval` tick, once per burst of edits. **Importing
  runs every `.py` file at the project root and in its packages: a root-level script
  without an `if __name__ == '__main__':` guard is executed on every import.**
- One **Reload** button re-runs the analysis and rebuilds the view at once.
- Removed `--reimport-on-reconcile` and `--verbose-import`.
  `python -m pygeodata_browser` now runs `pygeodata browse`, with the same options.

### Mirrors and missing cache roots
- Mirror mode: when the catalog was written from another project root (a synced copy
  of a remote project), the browser is read-only and never writes into the project.
  Pins go to your user data directory; deleting entries and the clean actions are
  disabled. `--read-only` / `--writable` override the detection.
- Thumbnails are always cached in your user cache directory, never in the project.
- Entries whose cache root is missing or empty get an `offline` badge, a banner per
  root, disabled file actions and an Online / Offline (n) filter.

### Interface
- Registry diagnostics redesigned: mode and why, counts, a health checklist that
  explains each warning and what to do (e.g. dirs written by an older cache format,
  which `pygeodata clean-cache` removes), analysis problems, and the catalog's
  writer next to this browser's versions.
- Errors show in a wide, copyable box with Reload and close buttons.
- The Code tab follows reloads, so runs and reimports appear while it is open.
- The co-outputs card in the entry detail is shown again.
- A class's stale dot compares its cache entries with the current code, so deleting
  `.source/` or a run served from the cache no longer marks current classes stale.
- Removed the "Has warnings" / "Has error" filters, which never matched anything.

### Internals
- Every API response is a typed contract (`api/contracts.py`, encoded with msgspec);
  a test keeps the frontend's TypeScript types in step.
- CI: tests against pygeodata `main` and the minimum supported release, frontend
  checks, weekly; publishing waits for CI.
