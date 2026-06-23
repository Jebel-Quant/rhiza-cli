"""The public :class:`GitContext` facade composing the git engine mixins."""

import os
import subprocess  # nosec B404
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from rhiza.models._git.helpers import _log_git_stderr_errors, get_git_executable
from rhiza.models._git.merge import MergeMixin


@dataclass
class GitContext(MergeMixin):
    """Bundles the git executable path and environment for subprocess calls.

    All git-invoking functions in the sync helpers accept a
    :class:`GitContext` instead of resolving the executable on their own,
    making them easily testable via binary injection.

    The git operations are organised into focused mixins
    (:class:`~rhiza.models._git.remote.RemoteOpsMixin`,
    :class:`~rhiza.models._git.diff.DiffMixin`,
    :class:`~rhiza.models._git.merge.MergeMixin`); this class composes them and
    adds the working-tree/branch operations.  See ADR-0005 for the rationale.

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
