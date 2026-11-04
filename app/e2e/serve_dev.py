import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

project = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
os.chdir(project)

from pygeodata_browser.serve import ThreadingWSGIServer
from pygeodata_browser.web import create_app

app = create_app(fast=True, reconcile_interval=0)
print('serving on http://127.0.0.1:8780', flush=True)
make_server('127.0.0.1', 8780, app, server_class=ThreadingWSGIServer).serve_forever()
