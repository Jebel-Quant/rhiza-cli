"""Tests for the subprocess_utils module.

Tests get_git_executable for normal operation and RuntimeError
when git is not found in PATH.
"""

from unittest.mock import patch

import pytest

from rhiza.models import get_git_executable


class TestGetGitExecutable:
    """Tests for get_git_executable function."""

    def test_returns_path_when_git_found(self):
        """Returns the path to the git executable when git is available."""
        result = get_git_executable()
        assert result is not None
        assert "git" in result

    def test_raises_when_git_not_found(self):
        """Raises RuntimeError when git is not found in PATH."""
        with (
            patch("rhiza.models.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="git executable not found in PATH"),
        ):
            get_git_executable()
