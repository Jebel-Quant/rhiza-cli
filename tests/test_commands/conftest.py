"""Shared fixtures for test_commands tests.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists without
  shell=True, which is the safe pattern for invoking git in tests.
- S607 (partial executable path): git is resolved via shutil.which() before use, ensuring the
  full path is available at runtime.
"""

import os
import shutil
import subprocess

import pytest


@pytest.fixture
def git_setup():
    """Return git executable and env."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not available")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return git, env


@pytest.fixture
def git_project(tmp_path, git_setup):
    """Create a minimal git-initialised project directory."""
    git_executable, git_env = git_setup
    project = tmp_path / "project"
    project.mkdir()
    for cmd in [
        [git_executable, "init"],
        [git_executable, "config", "user.email", "test@test.com"],
        [git_executable, "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=project, check=True, capture_output=True, env=git_env)  # nosec B603
    return project
