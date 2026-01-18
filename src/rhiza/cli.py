"""Rhiza command-line interface (CLI).

This module defines the Typer application entry points exposed by Rhiza.
Commands are thin wrappers around implementations in `rhiza.commands.*`.
"""

from pathlib import Path
from typing import Annotated

import typer

from rhiza import __version__
from rhiza.commands import init as init_cmd
from rhiza.commands import materialize as materialize_cmd
from rhiza.commands import validate as validate_cmd
from rhiza.commands.migrate import migrate as migrate_cmd
from rhiza.commands.summarise import summarise as summarise_cmd
from rhiza.commands.uninstall import uninstall as uninstall_cmd
from rhiza.commands.welcome import welcome as welcome_cmd

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
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target directory (defaults to current directory)",
        ),
    ] = Path("."),
    project_name: str = typer.Option(
        None,
        "--project-name",
        help="Custom project name (defaults to directory name)",
    ),
    package_name: str = typer.Option(
        None,
        "--package-name",
        help="Custom package name (defaults to normalized project name)",
    ),
    with_dev_dependencies: bool = typer.Option(
        False,
        "--with-dev-dependencies",
        help="Include development dependencies in pyproject.toml",
    ),
    git_host: str = typer.Option(
        None,
        "--git-host",
        help="Target Git hosting platform (github or gitlab). Determines which CI/CD files to include. "
        "If not provided, will prompt interactively.",
    ),
    template_repository: str = typer.Option(
        None,
        "--template-repository",
        help="Custom template repository (format: owner/repo). Defaults to 'jebel-quant/rhiza'.",
    ),
    template_branch: str = typer.Option(
        None,
        "--template-branch",
        help="Custom template branch. Defaults to 'main'.",
    ),
):
    r"""Initialize or validate .rhiza/template.yml.

    Creates a default `.rhiza/template.yml` configuration file if one
    doesn't exist, or validates the existing configuration.

    The default template includes common Python project files.
    The --git-host option determines which CI/CD configuration to include:
    - github: includes .github folder (GitHub Actions workflows)
    - gitlab: includes .gitlab-ci.yml (GitLab CI configuration)

    Examples:
      rhiza init
      rhiza init --git-host github
      rhiza init --git-host gitlab
      rhiza init --template-repository myorg/my-templates
      rhiza init --template-repository myorg/my-templates --template-branch develop
      rhiza init /path/to/project
      rhiza init ..
    """
    init_cmd(
        target,
        project_name=project_name,
        package_name=package_name,
        with_dev_dependencies=with_dev_dependencies,
        git_host=git_host,
        template_repository=template_repository,
        template_branch=template_branch,
    )


@app.command()
def materialize(
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target git repository (defaults to current directory)",
        ),
    ] = Path("."),
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

    Materializes configuration files from the template repository specified
    in .rhiza/template.yml into your project. This command:

    - Reads .rhiza/template.yml configuration
    - Performs a sparse clone of the template repository
    - Copies specified files/directories to your project
    - Respects exclusion patterns defined in the configuration
    - Files that already exist will NOT be overwritten unless --force is used.

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
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target git repository (defaults to current directory)",
        ),
    ] = Path("."),
):
    r"""Validate Rhiza template configuration.

    Validates the .rhiza/template.yml file to ensure it is syntactically
    correct and semantically valid.

    Performs comprehensive validation:
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


@app.command()
def migrate(
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target git repository (defaults to current directory)",
        ),
    ] = Path("."),
):
    r"""Migrate project to the new .rhiza folder structure.

    This command helps transition projects to use the new `.rhiza/` folder
    structure for storing Rhiza state and configuration files. It performs
    the following migrations:

    - Creates the `.rhiza/` directory in the project root
    - Moves `.github/rhiza/template.yml` or `.github/template.yml` to `.rhiza/template.yml`
    - Moves `.rhiza.history` to `.rhiza/history`

    The new `.rhiza/` folder structure separates Rhiza's state and configuration
    from the `.github/` directory, providing better organization.

    If files already exist in `.rhiza/`, the migration will skip them and leave
    the old files in place. You can manually remove old files after verifying
    the migration was successful.

    Examples:
        rhiza migrate
        rhiza migrate /path/to/project
    """
    migrate_cmd(target)


@app.command()
def welcome():
    r"""Display a friendly welcome message and explain what Rhiza is.

    Shows a welcome message, explains Rhiza's purpose, key features,
    and provides guidance on getting started with the tool.

    Examples:
        rhiza welcome
    """
    welcome_cmd()


@app.command()
def uninstall(
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target git repository (defaults to current directory)",
        ),
    ] = Path("."),
    force: bool = typer.Option(
        False,
        "--force",
        "-y",
        help="Skip confirmation prompt and proceed with deletion",
    ),
):
    r"""Remove all Rhiza-managed files from the repository.

    Reads the `.rhiza.history` file and removes all files that were
    previously materialized by Rhiza templates. This provides a clean
    way to uninstall all template-managed files from a project.

    The command will:
    - Read the list of files from `.rhiza.history`
    - Prompt for confirmation (unless --force is used)
    - Delete all listed files that exist
    - Remove empty directories left behind
    - Delete the `.rhiza.history` file itself

    Use this command when you want to completely remove Rhiza templates
    from your project.

    Examples:
        rhiza uninstall
        rhiza uninstall --force
        rhiza uninstall /path/to/project
        rhiza uninstall /path/to/project -y
    """
    uninstall_cmd(target, force)


@app.command()
def summarise(
    target: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Target git repository (defaults to current directory)",
        ),
    ] = Path("."),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (defaults to stdout)",
        ),
    ] = None,
):
    r"""Generate a summary of staged changes for PR descriptions.

    Analyzes staged git changes and generates a structured PR description
    that includes:

    - Summary statistics (files added/modified/deleted)
    - Changes categorized by type (workflows, configs, docs, tests, etc.)
    - Template repository information
    - Last sync date

    This is useful when creating pull requests after running `rhiza materialize`
    to provide reviewers with a clear overview of what changed.

    Examples:
        rhiza summarise
        rhiza summarise --output pr-description.md
        rhiza summarise /path/to/project -o description.md

    Typical workflow:
        rhiza materialize
        git add .
        rhiza summarise --output pr-body.md
        gh pr create --title "chore: Sync with rhiza" --body-file pr-body.md
    """
    summarise_cmd(target, output)
