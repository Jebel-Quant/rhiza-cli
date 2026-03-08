"""Utilities for secure subprocess execution.

This module provides helper functions to resolve executable paths
to prevent PATH manipulation security vulnerabilities.
"""

import os
import shutil
from dataclasses import dataclass, field


@dataclass
class GitContext:
    """Bundles the git executable path and environment for subprocess calls.

    Attributes:
        executable: Absolute path to the git binary (from ``get_git_executable()``).
        env: Environment mapping to pass to every git subprocess.
    """

    executable: str
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "GitContext":
        """Construct a GitContext using the system git and a clean copy of os.environ."""
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return cls(executable=get_git_executable(), env=env)


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
