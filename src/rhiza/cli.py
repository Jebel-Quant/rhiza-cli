"""Rhiza command-line interface (CLI).

This module defines the Typer application entry points exposed by Rhiza.
Commands are thin wrappers around implementations in `rhiza.commands.*`.
"""

from pathlib import Path

import typer

from rhiza.commands.init import init as init_cmd
from rhiza.commands.materialize import materialize as materialize_cmd
from rhiza.commands.validate import validate as validate_cmd

app = typer.Typer(
    help="Rhiza - Manage reusable configuration templates for Python projects",
    add_completion=True,
)


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

    Creates a default .github/template.yml configuration file if one doesn't
    exist, or validates the existing configuration.

    The default template includes common Python project files:
    - .github (workflows, actions, etc.)
    - .editorconfig
    - .gitignore
    - .pre-commit-config.yaml
    - Makefile
    - pytest.ini

    Examples:
        rhiza init
        rhiza init /path/to/project
        rhiza init ..
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
    """Inject Rhiza configuration templates into a target repository.

    Materializes configuration files from the template repository specified
    in .github/template.yml into your project. This command:

    1. Reads .github/template.yml configuration
    2. Performs a sparse clone of the template repository
    3. Copies specified files/directories to your project
    4. Respects exclusion patterns defined in the configuration

    Files that already exist will NOT be overwritten unless --force is used.

    Examples:
        rhiza materialize
        rhiza materialize --branch develop
        rhiza materialize --force
        rhiza materialize /path/to/project -b v2.0 -y
    """
    materialize_cmd(target, branch, force)


@app.command()
def validate(
    target: Path = typer.Argument(
        default=Path("."),  # default to current directory
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Target git repository (defaults to current directory)",
    ),
):
    """Validate Rhiza template configuration.

    Validates the .github/template.yml file to ensure it is syntactically
    correct and semantically valid. Performs comprehensive validation:

    - Checks if template.yml exists
    - Validates YAML syntax
    - Verifies required fields are present (template-repository, include)
    - Validates field types and formats
    - Ensures repository name follows owner/repo format
    - Confirms include paths are not empty

    Returns exit code 0 on success, 1 on validation failure.

    Examples:
        rhiza validate
        rhiza validate /path/to/project
        rhiza validate ..
    """
    if not validate_cmd(target):
        raise typer.Exit(code=1)
