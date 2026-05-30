"""Shared fixtures for test_commands tests.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists without
  shell=True, which is the safe pattern for invoking git in tests.
- S607 (partial executable path): git is resolved via shutil.which() before use, ensuring the
  full path is available at runtime.
"""

import subprocess  # nosec B404
from unittest.mock import patch

import pytest

from rhiza.models import GitContext


@pytest.fixture(autouse=True)
def stub_get_latest_tag():
    """Stub out the remote ls-remote call so unit tests never hit the network.

    Tests that need a specific tag value can override with their own patch.
    Tests that need the real network call (e2e) can un-stub with
    ``@patch('rhiza.commands.init._get_latest_tag', wraps=...)`` or by
    marking the test with ``@pytest.mark.network``.
    """
    with patch("rhiza.commands.init._get_latest_tag", return_value=None):
        yield


@pytest.fixture
def git_ctx():
    """Return a GitContext for testing."""
    return GitContext.default()


@pytest.fixture
def git_setup(git_ctx):
    """Return git executable and env (legacy)."""
    return git_ctx.executable, git_ctx.env


@pytest.fixture
def git_project(tmp_path, git_ctx):
    """Create a minimal git-initialised project directory."""
    project = tmp_path / "project"
    project.mkdir()
    for cmd in [
        [git_ctx.executable, "init"],
        [git_ctx.executable, "config", "user.email", "test@test.com"],
        [git_ctx.executable, "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=project, check=True, capture_output=True, env=git_ctx.env)  # nosec B603
    return project
