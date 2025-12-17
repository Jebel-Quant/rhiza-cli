"""Rhiza command-line interface (CLI).

This module defines the Typer application entry points exposed by Rhiza.
Commands are thin wrappers around implementations in `rhiza.commands.*`.
"""

from pathlib import Path

import typer

from rhiza.commands.init import init as init_cmd
from rhiza.commands.inject import inject as inject_cmd

app = typer.Typer(help="rhiza — configuration materialization tools")


@app.command()
def init(
    target: Path = typer.Argument(
        default=Path("."),  # default to current directory
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Target directory (defaults to current directory)",
    ),
):
    """Initialize or validate .github/template.yml.

    Creates a default .github/template.yml file if it doesn't exist,
    or validates an existing one.

    Parameters
    ----------
    target:
        Path to the target directory. Defaults to the current working directory.
    """
    init_cmd(target)


@app.command()
def materialize(
    target: Path = typer.Argument(
        default=Path("."),  # default to current directory
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Target git repository (defaults to current directory)",
    ),
    branch: str = typer.Option("main", "--branch", "-b", help="Rhiza branch to use"),
    force: bool = typer.Option(False, "--force", "-y", help="Overwrite existing files"),
):
    """Inject Rhiza configuration into a target repository.

    Parameters
    ----------
    target:
        Path to the target Git repository directory. Defaults to the
        current working directory.
    branch:
        Name of the Rhiza branch to use when sourcing templates.
    force:
        If True, overwrite existing files without prompting.
    """
    inject_cmd(target, branch, force)
