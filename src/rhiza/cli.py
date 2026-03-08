"""Rhiza command-line interface (CLI).

This module defines the Typer application entry points exposed by Rhiza.
Commands are thin wrappers around implementations in `rhiza.commands.*`.
"""

import subprocess  # nosec B404
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
import yaml

from rhiza import __version__
from rhiza.commands import init as init_cmd
from rhiza.commands import validate as validate_cmd
from rhiza.commands.list_repos import list_repos as list_repos_cmd
from rhiza.commands.migrate import migrate as migrate_cmd
from rhiza.commands.status import status as status_cmd
from rhiza.commands.summarise import summarise as summarise_cmd
from rhiza.commands.sync import sync as sync_cmd
from rhiza.commands.tree import tree as tree_cmd
from rhiza.commands.uninstall import uninstall as uninstall_cmd


@contextmanager
def _exit_on_error(*exc_types: type[BaseException]) -> Iterator[None]:
    """Context manager that catches specified exceptions and exits with code 1.

    Args:
        *exc_types: Exception types to catch. Defaults to catching Exception
            if none are provided.
    """
    _types: tuple[type[BaseException], ...] = exc_types if exc_types else (Exception,)
    try:
        yield
    except _types:
        raise typer.Exit(code=1) from None


app = typer.Typer(
    help=(
        """
        Rhiza - Manage reusable configuration templates for Python projects

        https://jebel-quant.github.io/rhiza-cli/
        """
    ),
    add_completion=True,
)


def version_callback(value: bool) -> None:
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
) -> None:
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
    language: str = typer.Option(
        "python",
        "--language",
        help="Programming language for the project (python, go, etc.). Defaults to 'python'.",
    ),
    template_repository: str = typer.Option(
        None,
        "--template-repository",
        help=(
            "Custom template repository (format: owner/repo). "
            "Defaults to 'jebel-quant/rhiza' for Python or 'jebel-quant/rhiza-go' for Go."
        ),
    ),
    template_branch: str = typer.Option(
        None,
        "--template-branch",
        help="Custom template branch. Defaults to 'main'.",
    ),
) -> None:
    r"""Initialize or validate .rhiza/template.yml.

    Creates a default `.rhiza/template.yml` configuration file if one
    doesn't exist, or validates the existing configuration.

    The default template includes common project files based on the language.
    The --git-host option determines which CI/CD configuration to include:
    - github: includes .github folder (GitHub Actions workflows)
    - gitlab: includes .gitlab-ci.yml (GitLab CI configuration)

    The --language option determines the project type and files created:
    - python: creates pyproject.toml, src/, and Python project structure
    - go: creates minimal structure (you'll need to run 'go mod init')

    Examples:
      rhiza init
      rhiza init --language go
      rhiza init --language python --git-host github
      rhiza init --git-host gitlab
      rhiza init --template-repository myorg/my-templates
      rhiza init --template-repository myorg/my-templates --template-branch develop
      rhiza init /path/to/project
      rhiza init .. --language go
    """
    if not init_cmd(
        target,
        project_name=project_name,
        package_name=package_name,
        with_dev_dependencies=with_dev_dependencies,
        git_host=git_host,
        language=language,
        template_repository=template_repository,
        template_branch=template_branch,
    ):
        raise typer.Exit(code=1)


@app.command(deprecated=True)
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
) -> None:
    r"""[Deprecated] Use ``rhiza sync`` instead.

    This command is deprecated. ``rhiza sync`` now handles all use cases:

    \b
    - rhiza sync              # first time → copies everything, writes lock
    - rhiza sync              # subsequent → 3-way merge preserving local changes
    - rhiza sync --strategy diff       # dry-run showing what would change

    Examples:
        rhiza sync
        rhiza sync --branch develop
        rhiza sync --target-branch feature/update-templates
    """
    typer.echo(
        "DeprecationWarning: `rhiza materialize` is deprecated and will be removed in a future release. "
        "Use `rhiza sync` instead.",
        err=True,
    )
    with _exit_on_error(subprocess.CalledProcessError, RuntimeError, ValueError):
        sync_cmd(target, branch, target_branch, "merge")


@app.command()
def sync(
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
    strategy: str = typer.Option(
        "merge",
        "--strategy",
        "-s",
        help="Sync strategy: 'merge' (3-way merge preserving local changes) or 'diff' (dry-run showing changes)",
    ),
) -> None:
    r"""Sync templates using diff/merge, preserving local customisations.

    This is the primary command for keeping your project up to date with
    the template repository. It replaces the deprecated ``materialize`` command.

    On **first sync** (no lock file) the command copies all template files and
    records the current template HEAD in `.rhiza/template.lock`.  On
    **subsequent syncs** it computes the diff between the last-synced commit
    and the current HEAD then applies it via ``git apply -3`` so local edits
    are preserved.

    The command tracks the last-synced template commit in
    `.rhiza/template.lock`. On subsequent syncs it computes the diff
    between two snapshots of the template:

    \b
    - base:     the template at the last-synced commit
    - upstream: the template at the current branch HEAD
    - local:    the file in your project (possibly customised)

    Files that changed only upstream are updated automatically.
    Files that changed only locally are left untouched.
    Files that changed in both places are merged; conflicts are marked
    with standard git conflict markers for manual resolution.

    Strategies:
    \b
    - merge:  3-way merge preserving local changes (default)
    - diff:   dry-run showing what would change

    Examples:
        rhiza sync
        rhiza sync --strategy diff
        rhiza sync --branch develop
        rhiza sync --target-branch feature/update-templates
    """
    if strategy not in ("merge", "diff"):
        typer.echo(f"Unknown strategy: {strategy}. Must be 'merge' or 'diff'.")
        raise typer.Exit(code=1)
    with _exit_on_error(subprocess.CalledProcessError, RuntimeError, ValueError):
        sync_cmd(target, branch, target_branch, strategy)


@app.command()
def status(
    target: Annotated[
        Path,
        typer.Argument(
            help="Path to target repository",
        ),
    ] = Path("."),
) -> None:
    """Show the current sync status from template.lock."""
    with _exit_on_error(FileNotFoundError, ValueError, TypeError, yaml.YAMLError):
        status_cmd(target.resolve())


@app.command()
def tree(
    target: Annotated[
        Path,
        typer.Argument(
            help="Path to target repository",
        ),
    ] = Path("."),
) -> None:
    r"""List files managed by Rhiza in a tree-style view.

    Reads .rhiza/template.lock and displays the files that were synced
    from the template repository as a directory tree.

    Examples:
        rhiza tree
        rhiza tree /path/to/project
    """
    with _exit_on_error(FileNotFoundError, ValueError, TypeError, yaml.YAMLError):
        tree_cmd(target.resolve())


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
) -> None:
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
) -> None:
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


@app.command(name="list")
def list_repos(
    topic: str = typer.Option(
        "rhiza",
        "--topic",
        "-t",
        help="GitHub topic to search for (default: 'rhiza')",
    ),
) -> None:
    r"""List GitHub repositories tagged with a given topic.

    Queries the GitHub Search API for repositories tagged with the
    specified topic and displays them in a formatted table with the
    repository name, description, and last-updated date.

    Set the ``GITHUB_TOKEN`` environment variable to avoid API rate limits.

    Examples:
        rhiza list
        rhiza list --topic rhiza-go
    """
    if not list_repos_cmd(topic):
        raise typer.Exit(code=1)


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
) -> None:
    r"""Remove all Rhiza-managed files from the repository.

    Reads the `.rhiza/history` file and removes all files that were
    previously synced by Rhiza templates. This provides a clean
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
    with _exit_on_error(RuntimeError):
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
) -> None:
    r"""Generate a summary of staged changes for PR descriptions.

    Analyzes staged git changes and generates a structured PR description
    that includes:

    - Summary statistics (files added/modified/deleted)
    - Changes categorized by type (workflows, configs, docs, tests, etc.)
    - Template repository information
    - Last sync date

    This is useful when creating pull requests after running `rhiza sync`
    to provide reviewers with a clear overview of what changed.

    Examples:
        rhiza summarise
        rhiza summarise --output pr-description.md
        rhiza summarise /path/to/project -o description.md

    Typical workflow:
        rhiza sync
        git add .
        rhiza summarise --output pr-body.md
        gh pr create --title "chore: Sync with rhiza" --body-file pr-body.md
    """
    with _exit_on_error(RuntimeError):
        summarise_cmd(target, output)
