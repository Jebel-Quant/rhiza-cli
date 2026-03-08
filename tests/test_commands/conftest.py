"""Shared fixtures for test_commands tests.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists without
  shell=True, which is the safe pattern for invoking git in tests.
- S607 (partial executable path): git is resolved via shutil.which() before use, ensuring the
  full path is available at runtime.
"""

import shutil
import subprocess

import pytest

from rhiza.subprocess_utils import GitContext


@pytest.fixture
def git_setup():
    """Return a GitContext for use in tests."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not available")
    return GitContext.default()


@pytest.fixture
def git_project(tmp_path, git_setup):
    """Create a minimal git-initialised project directory."""
    git = git_setup
    project = tmp_path / "project"
    project.mkdir()
    for cmd in [
        [git.executable, "init"],
        [git.executable, "config", "user.email", "test@test.com"],
        [git.executable, "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=project, check=True, capture_output=True, env=git.env)  # nosec B603
    return project
