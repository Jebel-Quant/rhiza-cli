"""Git utility helpers for Rhiza models."""

import os
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass, field
from pathlib import Path

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

    def assert_status_clean(self, target: Path) -> None:
        """Raise RuntimeError if the target repository has uncommitted changes.

        Runs ``git status --porcelain`` and raises if the output is non-empty,
        preventing a sync from running on a dirty working tree.

        Args:
            target: Path to the target repository.

        Raises:
            RuntimeError: If the working tree has uncommitted changes.
        """
        result = subprocess.run(  # nosec B603  # noqa: S603
            [self.executable, "status", "--porcelain"],
            cwd=target,
            capture_output=True,
            text=True,
            env=self.env,
        )
        if result.stdout.strip():
            logger.error("Working tree is not clean. Please commit or stash your changes before syncing.")
            logger.error("Uncommitted changes:")
            for line in result.stdout.strip().splitlines():
                logger.error(f"  {line}")
            raise RuntimeError("Working tree is not clean. Please commit or stash your changes before syncing.")  # noqa: TRY003

    def handle_target_branch(self, target: Path, target_branch: str | None) -> None:
        """Handle target branch creation or checkout if specified.

        Args:
            target: Path to the target repository.
            target_branch: Optional branch name to create/checkout.
        """
        if not target_branch:
            return

        logger.info(f"Creating/checking out target branch: {target_branch}")
        try:
            result = subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "rev-parse", "--verify", target_branch],
                cwd=target,
                capture_output=True,
                text=True,
                env=self.env,
            )

            if result.returncode == 0:
                logger.info(f"Branch '{target_branch}' exists, checking out...")
                subprocess.run(  # nosec B603  # noqa: S603
                    [self.executable, "checkout", target_branch],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
            else:
                logger.info(f"Creating new branch '{target_branch}'...")
                subprocess.run(  # nosec B603  # noqa: S603
                    [self.executable, "checkout", "-b", target_branch],
                    cwd=target,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create/checkout branch '{target_branch}'")
            _log_git_stderr_errors(e.stderr)
            logger.error("Please ensure you have no uncommitted changes or conflicts")
            raise


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
