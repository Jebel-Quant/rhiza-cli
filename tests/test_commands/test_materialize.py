"""Tests for the deprecated ``materialize`` CLI command.

The ``rhiza materialize`` command is deprecated and delegates to
``rhiza sync`` (with strategy ``"merge"``).  These tests verify that the
CLI wiring is correct and that the deprecation warning is emitted.

Implementation tests for the underlying helpers (e.g. ``_handle_target_branch``)
live in ``test_sync.py``, which is the canonical home for those functions.
"""

import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.materialize import materialize


@pytest.fixture
def git_path(tmp_path):
    """Create a temporary git repository."""
    (tmp_path / ".git").mkdir()
    return tmp_path


class TestMaterializeCLI:
    """Tests for the deprecated materialize CLI command."""

    @patch("rhiza.cli.sync_cmd")
    def test_cli_delegates_to_sync_with_merge_strategy(self, mock_sync, git_path):
        """Materialize CLI delegates to sync with strategy='merge' and emits a deprecation warning."""
        runner = CliRunner()

        # 1. Explicit branch
        result = runner.invoke(cli.app, ["materialize", str(git_path), "--branch", "main"])
        assert result.exit_code == 0
        mock_sync.assert_called_once_with(git_path.resolve(), "main", None, "merge")
        assert "deprecated" in result.output.lower()

        mock_sync.reset_mock()

        # 2. --force flag still uses merge strategy (default branch)
        result = runner.invoke(cli.app, ["materialize", str(git_path), "--force"])
        assert result.exit_code == 0
        mock_sync.assert_called_once_with(git_path.resolve(), "main", None, "merge")

    @patch("rhiza.commands.materialize.sync")
    def test_python_shim_delegates_to_sync(self, mock_sync, tmp_path):
        """materialize() always calls sync() with strategy='merge', ignores force, and emits DeprecationWarning."""
        # 1. Basic call — emits DeprecationWarning, coerces path, passes strategy
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            materialize(tmp_path, "main", None, False)

        mock_sync.assert_called_once_with(Path(tmp_path), "main", None, "merge")
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

        mock_sync.reset_mock()

        # 2. force=True and non-default branch/target are forwarded; strategy is still 'merge'
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            materialize(tmp_path, "develop", "feature/branch", True)

        mock_sync.assert_called_once_with(Path(tmp_path), "develop", "feature/branch", "merge")

        # 3. String path is coerced to Path
        mock_sync.reset_mock()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            materialize(str(tmp_path), "main", None, False)

        mock_sync.assert_called_once_with(Path(str(tmp_path)), "main", None, "merge")
