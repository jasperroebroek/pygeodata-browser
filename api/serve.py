import webbrowser
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from pygeodata_browser.web import create_app


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Concurrent request handling: a large dashboard payload must not block
    figure/table previews and status polls behind it.
    """

    daemon_threads = True


def open_registry_browser(
    port: int = 0,
    fast: bool = False,
    reconcile_interval: float = 300,
    reimport_on_reconcile: bool = True,
) -> None:
    """Start the registry browser and open it in the default browser."""
    app = create_app(fast=fast, reconcile_interval=reconcile_interval, reimport_on_reconcile=reimport_on_reconcile)
    server = make_server('127.0.0.1', port, app, server_class=ThreadingWSGIServer)
    host, actual_port = server.server_address
    url = f'http://{host}:{actual_port}'
    print(url)
    webbrowser.open(url)
    server.serve_forever()
