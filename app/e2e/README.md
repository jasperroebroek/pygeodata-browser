# e2e tools

Playwright scripts against a running dev setup (global install at `/usr/local/lib/node_modules/playwright`). Screenshots go to `shots/`.

```bash
# API on :8780, run from the project to browse; `dot` (Graphviz) must be on PATH
cd ~/Projects/apes && PATH=$CONDA_PREFIX/bin:$PATH python ~/Packages/pygeodata-browser/app/e2e/serve_dev.py
# Vite on :5173
cd app && npx vite --port 5173 --strictPort
```

| script | purpose |
|---|---|
| `node shot.mjs <name> <url> '<steps-json>'` | Screenshot driver (1600×1000). Steps: `click`, `dbl`, `hover`, `wait`, `waitFor`, `type`, `press`, `eval`, `shot`. |
| `python -I pdiff.py a.png b.png out.png` | Pixel diff with red overlay (needs PIL). |
| `node toggles.mjs [url]` | Functional checks of every toolbar/sidebar toggle. |
| `node detail.mjs` | Detail pane and code-view actions. |
| `node perf.mjs legacy\|svelte` | Load/click/scroll timings and API bytes. |
| `node prof.mjs [url]` | CPU profile of one page append. |

The checks assume the `apes` project (e.g. class `AridityIndex` with 8 entries).
