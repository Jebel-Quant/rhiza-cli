"""Tests for the deprecated ``materialize`` CLI command.

The ``rhiza materialize`` command is deprecated and delegates to
``rhiza sync`` (with strategy ``"merge"``).  These tests verify that the
CLI wiring is correct and that the deprecation warning is emitted.

Implementation tests for the underlying helpers (e.g. ``_construct_git_url``,
``_handle_target_branch``) live in ``test_sync.py``, which is the canonical
home for those functions.
"""

import warnings
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.materialize import materialize


class TestMaterializeCLI:
    """Tests for the deprecated materialize CLI command."""

    @patch("rhiza.cli.sync_cmd")
    def test_cli_materialize_command(self, mock_sync, tmp_path):
        """Test the CLI materialize command delegates to sync (deprecated)."""
        runner = CliRunner()

        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Run CLI command — materialize is deprecated and delegates to sync
        result = runner.invoke(cli.app, ["materialize", str(tmp_path), "--branch", "main"])
        assert result.exit_code == 0
        mock_sync.assert_called_once_with(tmp_path.resolve(), "main", None, "merge")

    @patch("rhiza.cli.sync_cmd")
    def test_cli_materialize_force_uses_merge_strategy(self, mock_sync, tmp_path):
        """Test that --force maps to merge strategy when delegating to sync."""
        runner = CliRunner()

        # Setup git repo
        (tmp_path / ".git").mkdir()

        result = runner.invoke(cli.app, ["materialize", str(tmp_path), "--force"])
        assert result.exit_code == 0
        mock_sync.assert_called_once_with(tmp_path.resolve(), "main", None, "merge")

    @patch("rhiza.cli.sync_cmd")
    def test_cli_materialize_shows_deprecation_warning(self, mock_sync, tmp_path):
        """Test that the deprecated materialize command shows a deprecation warning."""
        runner = CliRunner()

        (tmp_path / ".git").mkdir()

        result = runner.invoke(cli.app, ["materialize", str(tmp_path)])
        assert result.exit_code == 0
        # The deprecation warning is written to stderr; CliRunner mixes it into output
        assert "deprecated" in result.output.lower()

    @patch("rhiza.commands.materialize.sync")
    def test_python_materialize_delegates_to_sync(self, mock_sync, tmp_path):
        """The Python materialize() shim calls sync() with strategy='merge'."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            materialize(tmp_path, "main", None, False)

        mock_sync.assert_called_once_with(Path(tmp_path), "main", None, "merge")
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    @patch("rhiza.commands.materialize.sync")
    def test_python_materialize_ignores_force(self, mock_sync, tmp_path):
        """The force flag is ignored — sync is always called with 'merge'."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            materialize(tmp_path, "develop", "feature/branch", True)

        mock_sync.assert_called_once_with(Path(tmp_path), "develop", "feature/branch", "merge")
