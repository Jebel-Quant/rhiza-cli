"""Remote git operations: cloning, sparse checkout, and HEAD resolution."""

import logging
import subprocess  # nosec B404
from pathlib import Path

from rhiza.models._git._base import GitContextBase
from rhiza.models._git.helpers import _log_git_stderr_errors


class RemoteOpsMixin(GitContextBase):
    """Clone/sparse-checkout operations against a remote template repository."""

    def update_sparse_checkout(
        self,
        tmp_dir: Path,
        include_paths: list[str],
        logger: logging.Logger | None = None,
    ) -> None:
        """Update sparse-checkout paths in an already-cloned repository.

        Args:
            tmp_dir: Temporary directory with cloned repository.
            include_paths: Paths to include in sparse checkout.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)

        try:
            logger.debug(f"Updating sparse checkout paths: {include_paths}")
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
            logger.debug("Sparse checkout paths updated")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to update sparse checkout paths")
            _log_git_stderr_errors(e.stderr)
            raise

    def get_head_sha(self, repo_dir: Path) -> str:
        """Return the HEAD commit SHA of a cloned repository.

        Args:
            repo_dir: Path to the git repository.

        Returns:
            The full HEAD SHA.
        """
        result = subprocess.run(  # nosec B603  # noqa: S603
            [self.executable, "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
            env=self.env,
        )
        return result.stdout.strip()

    def clone_repository(
        self,
        git_url: str,
        tmp_dir: Path,
        branch: str,
        include_paths: list[str],
        logger: logging.Logger | None = None,
    ) -> None:
        """Clone template repository with sparse checkout.

        Args:
            git_url: URL of the repository to clone.
            tmp_dir: Temporary directory for cloning.
            branch: Branch to clone from the template repository.
            include_paths: Paths to include in sparse checkout.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)

        try:
            logger.debug("Executing git clone with sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    self.executable,
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    "--branch",
                    branch,
                    git_url,
                    str(tmp_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
            logger.debug("Git clone completed successfully")
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to clone repository from {git_url}")
            _log_git_stderr_errors(e.stderr)
            logger.exception("Please check that:")
            logger.exception("  - The repository exists and is accessible")
            logger.exception(f"  - Branch '{branch}' exists in the repository")
            logger.exception("  - You have network access to the git hosting service")
            raise

        try:
            logger.debug("Initializing sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "sparse-checkout", "init", "--cone"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
            logger.debug("Sparse checkout initialized")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to initialize sparse checkout")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            logger.debug(f"Setting sparse checkout paths: {include_paths}")
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
            logger.debug("Sparse checkout paths configured")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to configure sparse checkout paths")
            _log_git_stderr_errors(e.stderr)
            raise

    def clone_at_sha(
        self,
        git_url: str,
        sha: str,
        dest: Path,
        include_paths: list[str],
        logger: logging.Logger | None = None,
    ) -> None:
        """Clone the template repository and checkout a specific commit.

        Args:
            git_url: URL of the repository to clone.
            sha: Commit SHA to check out.
            dest: Target directory for the clone.
            include_paths: Paths to include in sparse checkout.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    self.executable,
                    "clone",
                    "--filter=blob:none",
                    "--sparse",
                    "--no-checkout",
                    git_url,
                    str(dest),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to clone repository for base snapshot: {git_url}")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "sparse-checkout", "init", "--cone"],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to configure sparse checkout for base snapshot")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [self.executable, "checkout", sha],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=self.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to checkout base commit {sha[:12]}")
            _log_git_stderr_errors(e.stderr)
            raise
