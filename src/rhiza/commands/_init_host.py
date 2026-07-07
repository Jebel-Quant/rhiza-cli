"""Git-host input helpers for ``rhiza init``.

These are the pure/interactive helpers with no dependency on the git
subprocess layer: git-host argument validation, the interactive host prompt,
and version-tag parsing.  They live here to keep :mod:`rhiza.commands.init`
within the module-size budget; ``init`` re-imports them so their historical
import path stays stable.
"""

import re
import sys

import typer
from loguru import logger

from rhiza.models import GitHost


def _validate_git_host(git_host: str | None) -> GitHost | None:
    """Validate git_host parameter.

    Args:
        git_host: Git hosting platform.

    Returns:
        Validated GitHost enum value or None.

    Raises:
        ValueError: If git_host is invalid.
    """
    if git_host is None:
        return None
    try:
        return GitHost(git_host.lower())
    except ValueError:
        logger.error(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'")
        raise ValueError(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'") from None  # noqa: TRY003


def _prompt_git_host() -> GitHost:
    """Prompt user for git hosting platform.

    Returns:
        Git hosting platform choice as a GitHost enum value.
    """
    if sys.stdin.isatty():
        logger.info("Where will your project be hosted?")
        git_host = typer.prompt(
            "Target Git hosting platform (github/gitlab)",
            type=str,
            default="github",
        ).lower()

        while git_host not in GitHost._value2member_map_:
            logger.warning(f"Invalid choice: {git_host}. Please choose 'github' or 'gitlab'")
            git_host = typer.prompt(
                "Target Git hosting platform (github/gitlab)",
                type=str,
                default="github",
            ).lower()
    else:
        git_host = "github"
        logger.debug("Non-interactive mode detected, defaulting to github")

    return GitHost(git_host)


def _parse_version_tags(ls_remote_output: str) -> list[str]:
    r"""Extract version-like tag names (``v?\\d+.\\d+...``) from ``git ls-remote --tags`` output."""
    version_tags: list[str] = []
    for line in ls_remote_output.splitlines():
        if "^{}" in line:  # skip dereferenced annotated-tag objects
            continue
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].startswith("refs/tags/"):
            tag = parts[1][len("refs/tags/") :]
            if re.match(r"^v?\d+\.\d+", tag):
                version_tags.append(tag)
    return version_tags
