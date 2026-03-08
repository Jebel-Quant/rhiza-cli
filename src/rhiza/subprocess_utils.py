"""Shared subprocess utility helpers for Rhiza."""

from loguru import logger


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
