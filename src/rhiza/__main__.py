"""Rhiza module entry point.

This module allows running the Rhiza CLI with `python -m rhiza` by
delegating execution to the Typer application defined in `rhiza.cli`.
"""

from importlib.metadata import entry_points

import typer
from loguru import logger

from rhiza.cli import app


def load_plugins(app: typer.Typer) -> None:
    """Load plugins from entry points."""
    # Any installed package that registers a `rhiza.plugins` entry point is
    # mounted as a subcommand.
    plugin_entries = entry_points(group="rhiza.plugins")

    for entry in plugin_entries:
        try:
            plugin_app = entry.load()
            # This adds the plugin as a subcommand, e.g., 'rhiza <plugin>'
            app.add_typer(plugin_app, name=entry.name)
        except Exception as e:  # noqa: BLE001  # third-party plugin code may raise anything; a broken plugin must not crash the CLI
            logger.warning(f"Failed to load plugin {entry.name}: {e}")


def main() -> None:
    """Console-script entry point: load plugins, then run the CLI.

    Used by both the ``rhiza`` console script (``project.scripts``) and
    ``python -m rhiza`` so that entry-point plugins load identically for
    either invocation.
    """
    load_plugins(app)
    app()


if __name__ == "__main__":
    main()
