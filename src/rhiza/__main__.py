"""Rhiza module entry point.

This module allows running the Rhiza CLI with `python -m rhiza` by
delegating execution to the Typer application defined in `rhiza.cli`.
"""

from importlib.metadata import entry_points

import typer

from rhiza.cli import app


def load_plugins(app: typer.Typer):
    """Load plugins from entry points."""
    # 'rhiza.plugins' matches the group we defined in rhiza-tools
    plugin_entries = entry_points(group="rhiza.plugins")

    for entry in plugin_entries:
        try:
            plugin_app = entry.load()
            # This adds the plugin as a subcommand, e.g., 'rhiza tools bump'
            app.add_typer(plugin_app, name=entry.name)
        except Exception as e:
            print(f"Failed to load plugin {entry.name}: {e}")


load_plugins(app)


if __name__ == "__main__":
    app()
