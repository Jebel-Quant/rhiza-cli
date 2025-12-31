"""Git repository scanner for detecting and analyzing repositories."""

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger


class GitRepositoryScanner:
    """Scanner for detecting and analyzing Git repositories in a folder."""

    def __init__(self, root_folder: Path):
        """Initialize scanner with root folder.

        Args:
            root_folder: Root folder to scan for Git repositories.
        """
        self.root_folder = Path(root_folder).resolve()
        if not self.root_folder.exists():
            raise FileNotFoundError(f"Folder not found: {self.root_folder}")
        if not self.root_folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.root_folder}")

    def scan_repositories(self) -> list[dict[str, Any]]:
        """Scan for all Git repositories in the root folder.

        Returns:
            List of repository information dictionaries.
        """
        repos = []
        logger.info(f"Scanning for repositories in: {self.root_folder}")

        # Find all .git directories
        for item in self.root_folder.iterdir():
            if item.is_dir():
                git_dir = item / ".git"
                if git_dir.exists():
                    repo_info = self._get_repository_info(item)
                    if repo_info:
                        repos.append(repo_info)
                        logger.debug(f"Found repository: {item.name}")

        logger.info(f"Found {len(repos)} repositories")
        return repos

    def _get_repository_info(self, repo_path: Path) -> dict[str, Any] | None:
        """Get detailed information about a Git repository.

        Args:
            repo_path: Path to the Git repository.

        Returns:
            Dictionary containing repository information, or None if error.
        """
        try:
            # Get current branch
            branch = self._run_git_command(repo_path, ["branch", "--show-current"])

            # Get status
            status_output = self._run_git_command(repo_path, ["status", "--porcelain"])
            has_changes = bool(status_output.strip())

            # Count commits ahead/behind
            try:
                ahead_behind = self._run_git_command(
                    repo_path,
                    ["rev-list", "--left-right", "--count", f"HEAD...@{{u}}"],
                )
                parts = ahead_behind.split()
                ahead = int(parts[0]) if len(parts) > 0 else 0
                behind = int(parts[1]) if len(parts) > 1 else 0
                has_remote = True
            except (subprocess.CalledProcessError, ValueError, IndexError):
                ahead = 0
                behind = 0
                has_remote = False

            # Get last commit info
            try:
                last_commit_msg = self._run_git_command(
                    repo_path,
                    ["log", "-1", "--pretty=format:%s"],
                )
                last_commit_date = self._run_git_command(
                    repo_path,
                    ["log", "-1", "--pretty=format:%cr"],
                )
            except subprocess.CalledProcessError:
                last_commit_msg = "No commits"
                last_commit_date = "Never"

            # Get remote URL if available
            try:
                remote_url = self._run_git_command(
                    repo_path,
                    ["config", "--get", "remote.origin.url"],
                )
            except subprocess.CalledProcessError:
                remote_url = None

            # Determine status
            status = self._determine_status(has_changes, ahead, behind, has_remote)

            return {
                "name": repo_path.name,
                "path": str(repo_path),
                "branch": branch or "unknown",
                "status": status,
                "has_changes": has_changes,
                "ahead": ahead,
                "behind": behind,
                "has_remote": has_remote,
                "last_commit_msg": last_commit_msg,
                "last_commit_date": last_commit_date,
                "remote_url": remote_url,
            }

        except Exception as e:
            logger.warning(f"Failed to get info for {repo_path.name}: {e}")
            return None

    def _run_git_command(
        self,
        repo_path: Path,
        args: list[str],
        timeout: int = 5,
    ) -> str:
        """Run a Git command in the specified repository.

        Args:
            repo_path: Path to the Git repository.
            args: List of Git command arguments.
            timeout: Command timeout in seconds.

        Returns:
            Command output as string.

        Raises:
            subprocess.CalledProcessError: If command fails.
            subprocess.TimeoutExpired: If command times out.
        """
        result = subprocess.run(
            ["git", "-C", str(repo_path)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()

    def _determine_status(
        self,
        has_changes: bool,
        ahead: int,
        behind: int,
        has_remote: bool,
    ) -> str:
        """Determine repository status based on Git state.

        Args:
            has_changes: Whether repository has uncommitted changes.
            ahead: Number of commits ahead of remote.
            behind: Number of commits behind remote.
            has_remote: Whether repository has a remote configured.

        Returns:
            Status string: 'clean', 'changes', 'ahead', 'behind', 'diverged', 'no-remote'.
        """
        if not has_remote:
            return "no-remote"
        if has_changes:
            return "changes"
        if ahead > 0 and behind > 0:
            return "diverged"
        if ahead > 0:
            return "ahead"
        if behind > 0:
            return "behind"
        return "clean"

    def get_repository_by_name(self, name: str) -> dict[str, Any] | None:
        """Get information for a specific repository by name.

        Args:
            name: Repository name.

        Returns:
            Repository information dictionary, or None if not found.
        """
        repo_path = self.root_folder / name
        if not (repo_path / ".git").exists():
            return None
        return self._get_repository_info(repo_path)

    def execute_git_operation(
        self,
        repo_name: str,
        operation: str,
    ) -> dict[str, Any]:
        """Execute a Git operation on a repository.

        Args:
            repo_name: Name of the repository.
            operation: Git operation to perform (fetch, pull, push, status).

        Returns:
            Dictionary with operation result.
        """
        repo_path = self.root_folder / repo_name

        if not (repo_path / ".git").exists():
            return {
                "success": False,
                "message": f"Repository not found: {repo_name}",
            }

        operations_map = {
            "fetch": ["fetch"],
            "pull": ["pull"],
            "push": ["push"],
            "status": ["status"],
        }

        if operation not in operations_map:
            return {
                "success": False,
                "message": f"Unknown operation: {operation}",
            }

        try:
            args = operations_map[operation]
            output = self._run_git_command(repo_path, args, timeout=30)
            return {
                "success": True,
                "message": output or f"{operation} completed successfully",
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(
                "Git operation '{operation}' failed for repository '{repo_name}': {error}",
                operation=operation,
                repo_name=repo_name,
                error=error_msg,
            )
            return {
                "success": False,
                "message": f"{operation} failed due to an internal error",
            }
        except subprocess.TimeoutExpired:
            logger.error(
                "Git operation '{operation}' timed out for repository '{repo_name}'",
                operation=operation,
                repo_name=repo_name,
            )
            return {
                "success": False,
                "message": f"{operation} timed out",
            }
        except Exception as e:
            logger.exception(
                "Unexpected error during git operation '{operation}' for repository '{repo_name}'",
                operation=operation,
                repo_name=repo_name,
            )
            return {
                "success": False,
                "message": f"{operation} encountered an internal error",
            }
