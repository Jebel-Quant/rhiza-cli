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


#
#
# try:
#     import textual
#
#     TEXTUAL_AVAILABLE = True
# except ImportError:
#     TEXTUAL_AVAILABLE = False
#
#
# @pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="Textual not installed")
# class TestTextualUI:
#     """Tests for Textual TUI functionality."""
#
#     def test_create_app(self, tmp_path: Path):
#         """Test creating Textual application."""
#         from rhiza.ui.tui import RhizaApp
#
#         app = RhizaApp(tmp_path)
#         assert app is not None
#         assert app.folder == tmp_path
#         assert len(app.BINDINGS) == 5
#
#
# try:
#     import flask
#
#     FLASK_AVAILABLE = True
# except ImportError:
#     FLASK_AVAILABLE = False
#
#
# @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
# class TestUIServer:
#     """Tests for UI server functionality."""
#
#     def test_create_app(self, tmp_path: Path):
#         """Test creating Flask application."""
#         from rhiza.ui.server import create_app
#
#         app = create_app(tmp_path)
#         assert app is not None
#         assert app.config["folder"] == tmp_path
#
#     def test_index_route(self, tmp_path: Path):
#         """Test index route returns HTML."""
#         from rhiza.ui.server import create_app
#
#         app = create_app(tmp_path)
#         client = app.test_client()
#         response = client.get("/")
#         assert response.status_code == 200
#         assert b"Rhiza UI" in response.data
#
#     def test_repositories_api(self, tmp_path: Path):
#         """Test repositories API endpoint."""
#         from rhiza.ui.server import create_app
#
#         # Create a test repository
#         repo_dir = tmp_path / "test-repo"
#         repo_dir.mkdir()
#         (repo_dir / ".git").mkdir()
#
#         app = create_app(tmp_path)
#         client = app.test_client()
#
#         with patch("rhiza.ui.server.GitRepositoryScanner.scan_repositories") as mock_scan:
#             mock_scan.return_value = [{"name": "test-repo", "status": "clean", "branch": "main"}]
#             response = client.get("/api/repositories")
#             assert response.status_code == 200
#             data = response.get_json()
#             assert "repositories" in data
#             assert len(data["repositories"]) == 1
#
#     def test_git_operation_api(self, tmp_path: Path):
#         """Test Git operation API endpoint."""
#         from rhiza.ui.server import create_app
#
#         app = create_app(tmp_path)
#         client = app.test_client()
#
#         with patch("rhiza.ui.server.GitRepositoryScanner.execute_git_operation") as mock_exec:
#             mock_exec.return_value = {"success": True, "message": "Operation completed"}
#             response = client.post(
#                 "/api/git-operation",
#                 json={"repo_name": "test-repo", "operation": "fetch"},
#             )
#             assert response.status_code == 200
#             data = response.get_json()
#             assert data["success"] is True
#
#     def test_git_operation_api_missing_params(self, tmp_path: Path):
#         """Test Git operation API with missing parameters."""
#         from rhiza.ui.server import create_app
#
#         app = create_app(tmp_path)
#         client = app.test_client()
#
#         response = client.post("/api/git-operation", json={})
#         assert response.status_code == 400
