import click

from pygeodata_browser.serve import open_registry_browser


@click.command()
@click.option('--port', default=0, show_default=True, help='Port to listen on (0 = random free port).')
@click.option(
    '--fast/--no-fast',
    'fast',
    default=False,
    help='Serve the UI immediately from the catalog bootstrap while the full state builds.',
)
@click.option(
    '--reconcile-interval',
    default=0.0,
    show_default=True,
    type=float,
    help='Minutes between automatic catalog reconciles (0 disables).',
)
def main(port: int, fast: bool, reconcile_interval: float) -> None:
    """Serve the pygeodata registry browser."""
    open_registry_browser(port, fast=fast, reconcile_interval=reconcile_interval * 60, reimport_on_reconcile=False)


if __name__ == '__main__':
    main()
