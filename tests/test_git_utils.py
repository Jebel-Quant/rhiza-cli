"""Tests for the _git_utils module.

Tests get_git_executable for normal operation and RuntimeError
when git is not found in PATH.
"""

import os
from unittest.mock import patch

import pytest

from rhiza.models._git_utils import GitContext, get_git_executable


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
            patch("rhiza.models._git_utils.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="git executable not found in PATH"),
        ):
            get_git_executable()


class TestGitContext:
    """Tests for the GitContext dataclass."""

    def test_direct_construction(self):
        """GitContext can be constructed with explicit executable and env."""
        ctx = GitContext(executable="/usr/bin/git", env={"KEY": "value"})
        assert ctx.executable == "/usr/bin/git"
        assert ctx.env == {"KEY": "value"}

    def test_env_defaults_to_empty_dict(self):
        """Env defaults to an empty dict when not supplied."""
        ctx = GitContext(executable="/usr/bin/git")
        assert ctx.env == {}

    def test_default_uses_system_git(self):
        """GitContext.default() uses the real git executable."""
        ctx = GitContext.default()
        assert ctx.executable is not None
        assert "git" in ctx.executable

    def test_default_sets_git_terminal_prompt(self):
        """GitContext.default() sets GIT_TERMINAL_PROMPT=0 in the environment."""
        ctx = GitContext.default()
        assert ctx.env.get("GIT_TERMINAL_PROMPT") == "0"

    def test_default_copies_environment(self):
        """GitContext.default() makes a copy of the process environment."""
        ctx = GitContext.default()
        # The returned env dict should be an independent copy, not os.environ itself.
        assert ctx.env is not os.environ
        # Sentinel variable from the current process should be present.
        for key, value in os.environ.items():
            if key != "GIT_TERMINAL_PROMPT":
                assert ctx.env.get(key) == value
                break
