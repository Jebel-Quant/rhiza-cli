"""Shared fixtures for test_commands tests.

Security Notes:
- S101 (assert usage): Asserts are the standard way to validate test conditions in pytest.
- S603 (subprocess without shell=True): Subprocess calls use explicit argument lists without
  shell=True, which is the safe pattern for invoking git in tests.
- S607 (partial executable path): git is resolved via shutil.which() before use, ensuring the
  full path is available at runtime.
"""

import subprocess

import pytest
from loguru import logger

from rhiza.models import GitContext


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


@pytest.fixture
def log_sink():
    """Capture loguru output into a list for assertions."""
    messages: list[str] = []
    handler_id = logger.add(lambda msg: messages.append(msg), format="{message}", colorize=False)
    yield messages
    logger.remove(handler_id)
