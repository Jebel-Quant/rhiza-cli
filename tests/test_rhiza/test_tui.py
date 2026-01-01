"""Tests for Rhiza TUI components."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRepoCard:
    """Tests for RepoCard widget."""

    def test_repo_card_initialization(self, tmp_path: Path):
        """Test RepoCard initialization."""
        from rhiza.ui.git_scanner import GitRepositoryScanner
        from rhiza.ui.tui import RepoCard

        scanner = GitRepositoryScanner(tmp_path)
        repo_info = {
            "name": "test-repo",
            "status": "clean",
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "has_changes": False,
            "last_commit_msg": "Initial commit",
            "last_commit_date": "2 hours ago",
        }

        card = RepoCard(repo_info, scanner)
        assert card.repo_info == repo_info
        assert card.scanner == scanner

    def test_repo_card_compose(self, tmp_path: Path):
        """Test RepoCard compose method."""
        from rhiza.ui.git_scanner import GitRepositoryScanner
        from rhiza.ui.tui import RepoCard

        scanner = GitRepositoryScanner(tmp_path)
        repo_info = {
            "name": "test-repo",
            "status": "clean",
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "has_changes": False,
            "last_commit_msg": "Initial commit",
            "last_commit_date": "2 hours ago",
        }

        card = RepoCard(repo_info, scanner)
        # Call compose to ensure it returns something
        widgets = list(card.compose())
        assert len(widgets) > 0


class TestStatsBar:
    """Tests for StatsBar widget."""

    def test_stats_bar_initialization(self):
        """Test StatsBar initialization."""
        from rhiza.ui.tui import StatsBar

        stats = StatsBar()
        assert stats.total_repos == 0
        assert stats.clean_repos == 0
        assert stats.changed_repos == 0
        assert stats.ahead_repos == 0
        assert stats.behind_repos == 0

    def test_stats_bar_update(self):
        """Test StatsBar update_stats method."""
        from rhiza.ui.tui import StatsBar

        stats = StatsBar()
        repos = [
            {"status": "clean"},
            {"status": "clean"},
            {"status": "changes"},
            {"status": "ahead"},
            {"status": "behind"},
            {"status": "diverged"},
        ]

        stats.update_stats(repos)
        assert stats.total_repos == 6
        assert stats.clean_repos == 2
        assert stats.changed_repos == 1
        assert stats.ahead_repos == 2  # ahead + diverged
        assert stats.behind_repos == 2  # behind + diverged

    def test_stats_bar_compose(self):
        """Test StatsBar compose method."""
        from rhiza.ui.tui import StatsBar

        stats = StatsBar()
        # Call compose to ensure it returns something
        widgets = list(stats.compose())
        assert len(widgets) > 0


class TestRhizaApp:
    """Tests for RhizaApp."""

    def test_rhiza_app_initialization(self, tmp_path: Path):
        """Test RhizaApp initialization."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        assert app.folder == tmp_path
        assert app.scanner is not None
        assert app.repos == []

    def test_rhiza_app_compose(self, tmp_path: Path):
        """Test RhizaApp compose method."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        # Call compose to ensure it returns something
        widgets = list(app.compose())
        assert len(widgets) > 0

    @pytest.mark.asyncio
    async def test_rhiza_app_on_mount(self, tmp_path: Path):
        """Test RhizaApp on_mount method."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        # Mock the action_refresh method
        with patch.object(app, "action_refresh") as mock_refresh:
            mock_refresh.return_value = None
            await app.on_mount()
            assert app.title == "🌳 Rhiza UI - Multi-Repository Manager"
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_operation_success(self, tmp_path: Path):
        """Test execute_operation with successful operation."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        # Mock the scanner and action_refresh
        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": True, "message": "Operation succeeded"}
            mock_refresh.return_value = None

            await app.execute_operation("test-repo", "fetch")

            mock_exec.assert_called_once_with("test-repo", "fetch")
            mock_refresh.assert_called_once()
            # Check that notify was called with success message
            assert mock_notify.call_count == 2  # One for start, one for success

    @pytest.mark.asyncio
    async def test_execute_operation_failure(self, tmp_path: Path):
        """Test execute_operation with failed operation."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        # Mock the scanner and action_refresh
        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": False, "message": "Operation failed"}
            mock_refresh.return_value = None

            await app.execute_operation("test-repo", "fetch")

            mock_exec.assert_called_once_with("test-repo", "fetch")
            mock_refresh.assert_called_once()
            # Check that notify was called with error message
            assert mock_notify.call_count == 2  # One for start, one for error

    @pytest.mark.asyncio
    async def test_action_fetch_all(self, tmp_path: Path):
        """Test action_fetch_all method."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}, {"name": "repo2"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": True, "message": "Success"}
            mock_refresh.return_value = None

            await app.action_fetch_all()

            assert mock_exec.call_count == 2
            mock_refresh.assert_called_once()
            # Check that notify was called
            assert mock_notify.call_count >= 2  # Start + end messages

    @pytest.mark.asyncio
    async def test_action_pull_all(self, tmp_path: Path):
        """Test action_pull_all method."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": True, "message": "Success"}
            mock_refresh.return_value = None

            await app.action_pull_all()

            mock_exec.assert_called_once_with("repo1", "pull")
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_push_all(self, tmp_path: Path):
        """Test action_push_all method."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": True, "message": "Success"}
            mock_refresh.return_value = None

            await app.action_push_all()

            mock_exec.assert_called_once_with("repo1", "push")
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_button_pressed_refresh(self, tmp_path: Path):
        """Test on_button_pressed for refresh button."""
        from textual.widgets import Button

        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        # Create a mock button pressed event
        mock_button = MagicMock(spec=Button)
        mock_button.id = "refresh"
        mock_event = MagicMock()
        mock_event.button = mock_button

        with patch.object(app, "action_refresh") as mock_refresh:
            mock_refresh.return_value = None
            await app.on_button_pressed(mock_event)
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_button_pressed_fetch_all(self, tmp_path: Path):
        """Test on_button_pressed for fetch-all button."""
        from textual.widgets import Button

        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        mock_button = MagicMock(spec=Button)
        mock_button.id = "fetch-all"
        mock_event = MagicMock()
        mock_event.button = mock_button

        with patch.object(app, "action_fetch_all") as mock_fetch:
            mock_fetch.return_value = None
            await app.on_button_pressed(mock_event)
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_button_pressed_pull_all(self, tmp_path: Path):
        """Test on_button_pressed for pull-all button."""
        from textual.widgets import Button

        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        mock_button = MagicMock(spec=Button)
        mock_button.id = "pull-all"
        mock_event = MagicMock()
        mock_event.button = mock_button

        with patch.object(app, "action_pull_all") as mock_pull:
            mock_pull.return_value = None
            await app.on_button_pressed(mock_event)
            mock_pull.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_button_pressed_push_all(self, tmp_path: Path):
        """Test on_button_pressed for push-all button."""
        from textual.widgets import Button

        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        mock_button = MagicMock(spec=Button)
        mock_button.id = "push-all"
        mock_event = MagicMock()
        mock_event.button = mock_button

        with patch.object(app, "action_push_all") as mock_push:
            mock_push.return_value = None
            await app.on_button_pressed(mock_event)
            mock_push.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_button_pressed_repo_operation(self, tmp_path: Path):
        """Test on_button_pressed for individual repo operation."""
        from textual.widgets import Button

        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)

        mock_button = MagicMock(spec=Button)
        mock_button.id = "fetch-test-repo"
        mock_event = MagicMock()
        mock_event.button = mock_button

        with patch.object(app, "execute_operation") as mock_exec:
            mock_exec.return_value = None
            await app.on_button_pressed(mock_event)
            mock_exec.assert_called_once_with("test-repo", "fetch")

    @pytest.mark.asyncio
    async def test_action_refresh_with_repos(self, tmp_path: Path):
        """Test action_refresh with actual repositories."""
        from unittest.mock import AsyncMock

        from rhiza.ui.tui import RhizaApp

        # Create a mock repo
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        app = RhizaApp(tmp_path)

        # Mock query_one and notify
        mock_stats = MagicMock()
        mock_repo_list = MagicMock()
        mock_repo_list.remove_children = AsyncMock()
        mock_repo_list.mount = AsyncMock()

        with patch.object(app, "query_one") as mock_query, patch.object(app, "notify") as mock_notify, patch.object(
            app.scanner, "scan_repositories"
        ) as mock_scan:
            # Set up the mocks
            mock_scan.return_value = [
                {
                    "name": "test-repo",
                    "status": "clean",
                    "branch": "main",
                    "ahead": 0,
                    "behind": 0,
                    "has_changes": False,
                    "last_commit_msg": "Test commit",
                    "last_commit_date": "1 hour ago",
                }
            ]

            def query_side_effect(selector, widget_type=None):
                if selector == "#stats":
                    return mock_stats
                elif selector == "#repo-list":
                    return mock_repo_list
                return MagicMock()

            mock_query.side_effect = query_side_effect

            await app.action_refresh()

            # Verify calls
            assert mock_notify.call_count >= 2
            mock_stats.update_stats.assert_called_once()
            mock_repo_list.remove_children.assert_called_once()
            mock_repo_list.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_fetch_all_with_failures(self, tmp_path: Path):
        """Test action_fetch_all with some failures."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}, {"name": "repo2"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            # First succeeds, second fails
            mock_exec.side_effect = [
                {"success": True, "message": "Success"},
                {"success": False, "message": "Failed"},
            ]
            mock_refresh.return_value = None

            await app.action_fetch_all()

            assert mock_exec.call_count == 2
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_pull_all_with_failures(self, tmp_path: Path):
        """Test action_pull_all with some failures."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": False, "message": "Failed"}
            mock_refresh.return_value = None

            await app.action_pull_all()

            mock_exec.assert_called_once_with("repo1", "pull")
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_push_all_with_failures(self, tmp_path: Path):
        """Test action_push_all with some failures."""
        from rhiza.ui.tui import RhizaApp

        app = RhizaApp(tmp_path)
        app.repos = [{"name": "repo1"}]

        with patch.object(app.scanner, "execute_git_operation") as mock_exec, patch.object(
            app, "action_refresh"
        ) as mock_refresh, patch.object(app, "notify") as mock_notify:
            mock_exec.return_value = {"success": False, "message": "Failed"}
            mock_refresh.return_value = None

            await app.action_push_all()

            mock_exec.assert_called_once_with("repo1", "push")
            mock_refresh.assert_called_once()
