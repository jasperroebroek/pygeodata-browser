import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

project = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
sys.path.insert(0, str(project))
os.chdir(project)

from pygeodata.cli import _import_project_modules
from pygeodata_browser.serve import ThreadingWSGIServer
from pygeodata_browser.web import create_app

print(f'imported {_import_project_modules(project, verbose=False)} modules', flush=True)
app = create_app(fast=True, reconcile_interval=0)
print('serving on http://127.0.0.1:8780 (legacy at /, svelte at /app/)', flush=True)
make_server('127.0.0.1', 8780, app, server_class=ThreadingWSGIServer).serve_forever()
