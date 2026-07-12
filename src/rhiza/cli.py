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

from rhiza import __version__
from rhiza.commands.summarise import SummariseOptions
from rhiza.commands.summarise import summarise as summarise_cmd
from rhiza.commands.sync import sync as sync_cmd


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
    path_to_template: Annotated[
        Path | None,
        typer.Option(
            "--path-to-template",
            help=(
                "Directory containing template.yml and where template.lock will be written "
                "(defaults to <TARGET>/.rhiza). "
                "Use '.' to keep both files in the project root."
            ),
        ),
    ] = None,
) -> None:
    r"""Sync templates using diff/merge, preserving local customisations.

    This is the primary command for keeping your project up to date with
    the template repository.

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
        rhiza sync --path-to-template /custom/rhiza
        rhiza sync --path-to-template .
    """
    if strategy not in ("merge", "diff"):
        typer.echo(f"Unknown strategy: {strategy}. Must be 'merge' or 'diff'.")
        raise typer.Exit(code=1)
    template_file = lock_file = None
    if path_to_template is not None:
        template_file = path_to_template / "template.yml"
        lock_file = path_to_template / "template.lock"
    with _exit_on_error(subprocess.CalledProcessError, RuntimeError, ValueError):
        sync_cmd(target, branch, target_branch, strategy, template_file=template_file, lock_file=lock_file)


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
    no_header: Annotated[
        bool,
        typer.Option("--no-header", help="Suppress the header section."),
    ] = False,
    no_footer: Annotated[
        bool,
        typer.Option("--no-footer", help="Suppress the footer section."),
    ] = False,
    no_categories: Annotated[
        bool,
        typer.Option("--no-categories", help="Show a flat file list instead of grouping by category."),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: markdown (default), plain, or json.",
        ),
    ] = "markdown",
    title: Annotated[
        str | None,
        typer.Option("--title", help="Override the PR description title (markdown / plain formats)."),
    ] = None,
    compare_ref: Annotated[
        str | None,
        typer.Option(
            "--compare",
            help="Compare against this git ref instead of staged changes (e.g. 'main', 'HEAD~1').",
        ),
    ] = None,
    jinja2_template: Annotated[
        Path | None,
        typer.Option(
            "--template",
            "-t",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to a Jinja2 template file for fully custom output.",
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
        rhiza summarise --format json
        rhiza summarise --no-categories --no-footer
        rhiza summarise --compare main
        rhiza summarise --template my-template.md.j2

    Typical workflow:
        rhiza sync
        git add .
        rhiza summarise --output pr-body.md
        gh pr create --title "chore: Sync with rhiza" --body-file pr-body.md
    """
    with _exit_on_error(RuntimeError):
        summarise_cmd(
            target,
            output,
            options=SummariseOptions(
                include_header=not no_header,
                include_footer=not no_footer,
                include_categories=not no_categories,
                output_format=output_format,
                title=title,
                compare_ref=compare_ref,
                jinja2_template=jinja2_template,
            ),
        )
