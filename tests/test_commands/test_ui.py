"""Tests for Rhiza UI functionality."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rhiza.ui.git_scanner import GitRepositoryScanner


class TestGitRepositoryScanner:
    """Tests for GitRepositoryScanner class."""

    def test_scanner_initialization(self, tmp_path: Path):
        """Test scanner initialization with valid folder."""
        scanner = GitRepositoryScanner(tmp_path)
        assert scanner.root_folder == tmp_path.resolve()

    def test_scanner_invalid_folder(self):
        """Test scanner initialization with invalid folder."""
        with pytest.raises(FileNotFoundError):
            GitRepositoryScanner(Path("/nonexistent/folder"))

    def test_scanner_file_instead_of_folder(self, tmp_path: Path):
        """Test scanner initialization with file instead of folder."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(NotADirectoryError):
            GitRepositoryScanner(test_file)

    def test_scan_empty_folder(self, tmp_path: Path):
        """Test scanning folder with no repositories."""
        scanner = GitRepositoryScanner(tmp_path)
        repos = scanner.scan_repositories()
        assert repos == []

    def test_scan_folder_with_repos(self, tmp_path: Path):
        """Test scanning folder with Git repositories."""
        # Create a mock Git repository
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / ".git").mkdir()

        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        (repo2 / ".git").mkdir()

        # Create a non-git directory
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_get_repository_info") as mock_get_info:
            mock_get_info.return_value = {"name": "test", "status": "clean"}
            repos = scanner.scan_repositories()
            assert len(repos) == 2
            assert mock_get_info.call_count == 2

    def test_determine_status_clean(self):
        """Test status determination for clean repository."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=False,
            ahead=0,
            behind=0,
            has_remote=True,
        )
        assert status == "clean"

    def test_determine_status_changes(self):
        """Test status determination for repository with changes."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=True,
            ahead=0,
            behind=0,
            has_remote=True,
        )
        assert status == "changes"

    def test_determine_status_ahead(self):
        """Test status determination for repository ahead of remote."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=False,
            ahead=2,
            behind=0,
            has_remote=True,
        )
        assert status == "ahead"

    def test_determine_status_behind(self):
        """Test status determination for repository behind remote."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=False,
            ahead=0,
            behind=3,
            has_remote=True,
        )
        assert status == "behind"

    def test_determine_status_diverged(self):
        """Test status determination for diverged repository."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=False,
            ahead=1,
            behind=2,
            has_remote=True,
        )
        assert status == "diverged"

    def test_determine_status_no_remote(self):
        """Test status determination for repository without remote."""
        scanner = GitRepositoryScanner(Path("."))
        status = scanner._determine_status(
            has_changes=False,
            ahead=0,
            behind=0,
            has_remote=False,
        )
        assert status == "no-remote"

    def test_run_git_command_success(self, tmp_path: Path):
        """Test running successful Git command."""
        scanner = GitRepositoryScanner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="main\n", stderr="")
            result = scanner._run_git_command(tmp_path, ["branch", "--show-current"])
            assert result == "main"
            mock_run.assert_called_once()

    def test_run_git_command_failure(self, tmp_path: Path):
        """Test running failed Git command."""
        scanner = GitRepositoryScanner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            with pytest.raises(subprocess.CalledProcessError):
                scanner._run_git_command(tmp_path, ["invalid-command"])

    def test_get_repository_by_name_exists(self, tmp_path: Path):
        """Test getting repository information by name when it exists."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_get_repository_info") as mock_get_info:
            mock_get_info.return_value = {"name": "test-repo", "status": "clean"}
            repo = scanner.get_repository_by_name("test-repo")
            assert repo is not None
            assert repo["name"] == "test-repo"

    def test_get_repository_by_name_not_exists(self, tmp_path: Path):
        """Test getting repository information by name when it doesn't exist."""
        scanner = GitRepositoryScanner(tmp_path)
        repo = scanner.get_repository_by_name("nonexistent")
        assert repo is None

    def test_execute_git_operation_fetch(self, tmp_path: Path):
        """Test executing fetch operation on repository."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            mock_run.return_value = "Fetching origin..."
            result = scanner.execute_git_operation("test-repo", "fetch")
            assert result["success"] is True
            assert "fetch" in result["message"].lower() or "success" in result["message"].lower()

    def test_execute_git_operation_invalid_repo(self, tmp_path: Path):
        """Test executing operation on non-existent repository."""
        scanner = GitRepositoryScanner(tmp_path)
        result = scanner.execute_git_operation("nonexistent", "fetch")
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_execute_git_operation_invalid_operation(self, tmp_path: Path):
        """Test executing invalid Git operation."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)
        result = scanner.execute_git_operation("test-repo", "invalid-op")
        assert result["success"] is False
        assert "unknown" in result["message"].lower()

    def test_execute_git_operation_failure(self, tmp_path: Path):
        """Test executing Git operation that fails."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="Error message")
            result = scanner.execute_git_operation("test-repo", "fetch")
            assert result["success"] is False
            assert "failed" in result["message"].lower()

    def test_execute_git_operation_timeout(self, tmp_path: Path):
        """Test executing Git operation that times out."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
            result = scanner.execute_git_operation("test-repo", "fetch")
            assert result["success"] is False
            assert "timed out" in result["message"].lower()

    def test_execute_git_operation_unexpected_exception(self, tmp_path: Path):
        """Test executing Git operation that raises unexpected exception."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")
            result = scanner.execute_git_operation("test-repo", "fetch")
            assert result["success"] is False
            assert "internal error" in result["message"].lower()

    def test_get_repository_info_exception(self, tmp_path: Path):
        """Test _get_repository_info when an exception occurs."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")
            result = scanner._get_repository_info(repo_dir)
            assert result is None

    def test_get_repository_info_no_commits(self, tmp_path: Path):
        """Test _get_repository_info for repository with no commits."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            def side_effect(path, args):
                if args[0] == "branch":
                    return "main"
                elif args[0] == "status":
                    return ""
                elif args[0] == "rev-list":
                    raise subprocess.CalledProcessError(1, "git")
                elif args[0] == "log":
                    raise subprocess.CalledProcessError(1, "git")
                elif args[0] == "config":
                    raise subprocess.CalledProcessError(1, "git")
                return ""

            mock_run.side_effect = side_effect
            result = scanner._get_repository_info(repo_dir)
            assert result is not None
            assert result["last_commit_msg"] == "No commits"
            assert result["last_commit_date"] == "Never"
            assert result["remote_url"] is None
            assert result["has_remote"] is False


class TestUiCommand:
    """Tests for the UI command functionality."""

    def test_ui_function_call(self, tmp_path: Path):
        """Test calling the ui function directly."""
        from unittest.mock import patch

        from rhiza.commands.ui import ui

        with patch("rhiza.commands.ui._launch_terminal_ui") as mock_launch:
            ui(tmp_path)
            mock_launch.assert_called_once_with(tmp_path)

    def test_launch_terminal_ui_success(self, tmp_path: Path):
        """Test successful launch of terminal UI."""
        from unittest.mock import MagicMock, patch

        from rhiza.commands.ui import _launch_terminal_ui

        with patch("rhiza.ui.tui.RhizaApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app
            _launch_terminal_ui(tmp_path)
            mock_app_class.assert_called_once_with(tmp_path)
            mock_app.run.assert_called_once()

    def test_launch_terminal_ui_keyboard_interrupt(self, tmp_path: Path):
        """Test terminal UI with keyboard interrupt."""
        from unittest.mock import MagicMock, patch

        from rhiza.commands.ui import _launch_terminal_ui

        with patch("rhiza.ui.tui.RhizaApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app.run.side_effect = KeyboardInterrupt()
            mock_app_class.return_value = mock_app
            # Should handle KeyboardInterrupt gracefully
            _launch_terminal_ui(tmp_path)

    def test_launch_terminal_ui_runtime_error(self, tmp_path: Path):
        """Test terminal UI with runtime error."""
        from unittest.mock import MagicMock, patch

        from rhiza.commands.ui import _launch_terminal_ui

        with patch("rhiza.ui.tui.RhizaApp") as mock_app_class:
            mock_app = MagicMock()
            mock_app.run.side_effect = RuntimeError("UI startup failed")
            mock_app_class.return_value = mock_app
            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="UI startup failed"):
                _launch_terminal_ui(tmp_path)

    def test_get_repository_info_with_commits_and_remote(self, tmp_path: Path):
        """Test _get_repository_info for repository with commits and valid remote."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            def side_effect(path, args):
                if args[0] == "branch":
                    return "main"
                elif args[0] == "status":
                    return ""
                elif args[0] == "rev-list":
                    return "2 3"  # 2 ahead, 3 behind
                elif args[0] == "log":
                    if "--pretty=format:%s" in args:
                        return "Latest commit message"
                    elif "--pretty=format:%cr" in args:
                        return "2 hours ago"
                elif args[0] == "config":
                    return "git@github.com:user/repo.git"
                return ""

            mock_run.side_effect = side_effect
            result = scanner._get_repository_info(repo_dir)
            assert result is not None
            assert result["last_commit_msg"] == "Latest commit message"
            assert result["last_commit_date"] == "2 hours ago"
            assert result["remote_url"] == "git@github.com:user/repo.git"
            assert result["has_remote"] is True
            assert result["ahead"] == 2
            assert result["behind"] == 3

    def test_get_repository_info_malformed_ahead_behind(self, tmp_path: Path):
        """Test _get_repository_info when ahead/behind output is malformed."""
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        scanner = GitRepositoryScanner(tmp_path)

        with patch.object(scanner, "_run_git_command") as mock_run:
            def side_effect(path, args):
                if args[0] == "branch":
                    return "main"
                elif args[0] == "status":
                    return ""
                elif args[0] == "rev-list":
                    # Return malformed data that will cause ValueError or IndexError
                    return "not-a-number"
                elif args[0] == "log":
                    return "commit"
                elif args[0] == "config":
                    raise subprocess.CalledProcessError(1, "git")
                return ""

            mock_run.side_effect = side_effect
            result = scanner._get_repository_info(repo_dir)
            assert result is not None
            assert result["ahead"] == 0
            assert result["behind"] == 0
            assert result["has_remote"] is False
