"""Git utility helpers for Rhiza models."""

import os
import shutil
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class GitContext:
    """Bundles the git executable path and environment for subprocess calls.

    All git-invoking functions in the sync helpers accept a
    :class:`GitContext` instead of resolving the executable on their own,
    making them easily testable via binary injection.

    Attributes:
        executable: Absolute path to the git binary.
        env: Environment variables passed to every git subprocess.
    """

    executable: str
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "GitContext":
        """Create a GitContext using the system git and process environment.

        Returns:
            A :class:`GitContext` populated with the real git executable path
            and a copy of the current process environment with
            ``GIT_TERMINAL_PROMPT`` set to ``"0"``.
        """
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return cls(executable=get_git_executable(), env=env)


def _normalize_to_list(value: str | list[str] | None) -> list[str]:
    r"""Convert a value to a list of strings.

    Handles the case where YAML multi-line strings (using |) are parsed as
    a single string instead of a list. Splits the string by newlines and
    strips whitespace from each item.

    Args:
        value: A string, list of strings, or None.

    Returns:
        A list of strings. Empty list if value is None or empty.

    Examples:
        >>> _normalize_to_list(None)
        []
        >>> _normalize_to_list([])
        []
        >>> _normalize_to_list(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> _normalize_to_list('single line')
        ['single line']
        >>> _normalize_to_list('line1\\n' + 'line2\\n' + 'line3')
        ['line1', 'line2', 'line3']
        >>> _normalize_to_list('  item1  \\n' + '  item2  ')
        ['item1', 'item2']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Split by newlines and filter out empty strings
        # Handle both actual newlines (\n) and literal backslash-n (\\n)
        items = value.split("\\n") if "\\n" in value and "\n" not in value else value.split("\n")
        return [item.strip() for item in items if item.strip()]
    return []


def get_git_executable() -> str:
    """Get the absolute path to the git executable.

    This function ensures we use the full path to git to prevent
    security issues related to PATH manipulation.

    Returns:
        str: Absolute path to the git executable.

    Raises:
        RuntimeError: If git executable is not found in PATH.
    """
    git_path = shutil.which("git")
    if git_path is None:
        msg = "git executable not found in PATH. Please ensure git is installed and available."
        raise RuntimeError(msg)
    return git_path


def _log_git_stderr_errors(stderr: str | None) -> None:
    """Extract and log only relevant error messages from git stderr.

    Args:
        stderr: Git command stderr output.
    """
    if stderr:
        for line in stderr.strip().split("\n"):
            line = line.strip()
            if line and (line.startswith("fatal:") or line.startswith("error:")):
                logger.error(line)
