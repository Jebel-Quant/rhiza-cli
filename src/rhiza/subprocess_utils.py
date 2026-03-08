"""Utilities for secure subprocess execution.

This module provides helper functions to resolve executable paths
to prevent PATH manipulation security vulnerabilities.
"""

import dataclasses
import shutil


@dataclasses.dataclass
class GitContext:
    """Holds the resolved git executable path for injection into helpers.

    Attributes:
        executable: Absolute path to the git binary.
    """

    executable: str

    @classmethod
    def default(cls) -> "GitContext":
        """Create a GitContext using the git executable found on PATH.

        Returns:
            A GitContext backed by the system git binary.

        Raises:
            RuntimeError: If git is not found in PATH.
        """
        return cls(executable=get_git_executable())


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
