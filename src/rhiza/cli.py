"""Rhiza command-line interface (CLI).

This module defines the Typer application entry points exposed by Rhiza.
Commands are thin wrappers around implementations in `rhiza.commands.*`.
"""

from pathlib import Path

import typer

from rhiza import __version__
from rhiza.commands import init as init_cmd
from rhiza.commands import materialize as materialize_cmd
from rhiza.commands import validate as validate_cmd

app = typer.Typer(
    help=(
        """
        Rhiza - Manage reusable configuration templates for Python projects

        \x1b]8;;https://jebel-quant.github.io/rhiza-cli/\x1b\\https://jebel-quant.github.io/rhiza-cli/\x1b]8;;\x1b\\
        """
    ),
    add_completion=True,
)


def version_callback(value: bool):
    """Print version information and exit.

    Args:
        value: Whether the --version flag was provided.

    Raises:
        typer.Exit: Always exits after printing version.
    """
    if value:
        typer.echo(f"rhiza version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Rhiza CLI main callback.

    This callback is executed before any command. It handles global options
    like --version.

    Args:
        version: Version flag (handled by callback).
    """


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
    r"""Initialize or validate .github/template.yml.

    \b
    Creates a default `.github/template.yml` configuration file if one
    doesn't exist, or validates the existing configuration.

    \b
    The default template includes common Python project files:
    - .github (workflows, actions, etc.)
    - .editorconfig
    - .gitignore
    - .pre-commit-config.yaml
    - Makefile
    - pytest.ini

    \b
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
    target_branch: str = typer.Option(
        None,
        "--target-branch",
        "--checkout-branch",
        help="Create and checkout a new branch in the target repository for changes",
    ),
    force: bool = typer.Option(False, "--force", "-y", help="Overwrite existing files"),
):
    r"""Inject Rhiza configuration templates into a target repository.

    \b
    Materializes configuration files from the template repository specified
    in .github/template.yml into your project. This command:

    \b
    - Reads .github/template.yml configuration
    - Performs a sparse clone of the template repository
    - Copies specified files/directories to your project
    - Respects exclusion patterns defined in the configuration
    - Files that already exist will NOT be overwritten unless --force is used.

    \b
    Examples:
        rhiza materialize
        rhiza materialize --branch develop
        rhiza materialize --force
        rhiza materialize --target-branch feature/update-templates
        rhiza materialize /path/to/project -b v2.0 -y
    """
    materialize_cmd(target, branch, target_branch, force)


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
    r"""Validate Rhiza template configuration.

    Validates the .github/template.yml file to ensure it is syntactically
    correct and semantically valid.

    \b
    Performs comprehensive validation:
    - Checks if template.yml exists
    - Validates YAML syntax
    - Verifies required fields are present (template-repository, include)
    - Validates field types and formats
    - Ensures repository name follows owner/repo format
    - Confirms include paths are not empty


    Returns exit code 0 on success, 1 on validation failure.

    \b
    Examples:
        rhiza validate
        rhiza validate /path/to/project
        rhiza validate ..
    """
    if not validate_cmd(target):
        raise typer.Exit(code=1)
