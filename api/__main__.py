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
    help='Minutes between automatic catalog checks and, with --import-all, project imports (0 disables).',
)
@click.option(
    '--import-all',
    'import_all',
    is_flag=True,
    default=False,
    help=(
        'Read the classes by importing the project in a subprocess instead of from source. '
        'Imports EVERY .py file at the project root and in its packages: a root-level script '
        'without an if __name__ == "__main__" guard RUNS, on every import.'
    ),
)
def main(port: int, fast: bool, reconcile_interval: float, import_all: bool) -> None:
    """Serve the pygeodata registry browser."""
    open_registry_browser(port, fast=fast, reconcile_interval=reconcile_interval * 60, import_all=import_all)


if __name__ == '__main__':
    main()
