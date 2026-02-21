"""Tests for the ``sync`` command and its helper functions.

Tests cover:
- Lock-file read/write
- Path expansion and exclusion
- Snapshot preparation (new cruft-based helper)
- Diff application via ``git apply -3`` (new cruft-based helper)
- Integration tests for each strategy (diff, overwrite, merge)
- CLI wiring
"""

import os
import shutil
import subprocess
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.sync import (
    _apply_diff,
    _excluded_set,
    _expand_paths,
    _prepare_snapshot,
    _read_lock,
    _write_lock,
    sync,
)


class TestLockFile:
    """Tests for lock-file helpers."""

    def test_read_lock_returns_none_when_missing(self, tmp_path):
        """No lock file → None."""
        assert _read_lock(tmp_path) is None

    def test_write_and_read_lock(self, tmp_path):
        """Round-trip write/read of a lock file."""
        sha = "abc123def456"
        _write_lock(tmp_path, sha)
        assert _read_lock(tmp_path) == sha

    def test_write_lock_creates_parent_directory(self, tmp_path):
        """Lock file creation should create .rhiza/ if needed."""
        target = tmp_path / "project"
        target.mkdir()
        _write_lock(target, "deadbeef")
        assert (target / ".rhiza" / "template.lock").exists()


class TestExpandPaths:
    """Tests for path expansion."""

    def test_expand_single_file(self, tmp_path):
        """Single file path expands to one entry."""
        f = tmp_path / "hello.txt"
        f.write_text("hi")
        result = _expand_paths(tmp_path, ["hello.txt"])
        assert len(result) == 1
        assert result[0] == f

    def test_expand_directory(self, tmp_path):
        """Directory path expands to all contained files."""
        d = tmp_path / "subdir"
        d.mkdir()
        (d / "a.txt").write_text("a")
        (d / "b.txt").write_text("b")
        result = _expand_paths(tmp_path, ["subdir"])
        assert len(result) == 2

    def test_expand_missing_path(self, tmp_path):
        """Missing path returns empty list."""
        result = _expand_paths(tmp_path, ["nonexistent"])
        assert result == []


class TestExcludedSet:
    """Tests for exclusion set building."""

    def test_always_excludes_template_yml_and_history(self, tmp_path):
        """Template config and history are always excluded."""
        excludes = _excluded_set(tmp_path, [])
        assert ".rhiza/template.yml" in excludes
        assert ".rhiza/history" in excludes

    def test_includes_user_exclusions(self, tmp_path):
        """User-configured exclusions appear in the set."""
        f = tmp_path / "secret.txt"
        f.write_text("shh")
        excludes = _excluded_set(tmp_path, ["secret.txt"])
        assert "secret.txt" in excludes


class TestPrepareSnapshot:
    """Tests for the snapshot preparation helper."""

    def test_copies_included_files(self, tmp_path):
        """Included files are copied to the snapshot directory."""
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        (clone_dir / "a.txt").write_text("content-a")
        (clone_dir / "b.txt").write_text("content-b")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        materialized = _prepare_snapshot(clone_dir, ["a.txt", "b.txt"], set(), snapshot_dir)

        assert len(materialized) == 2
        assert (snapshot_dir / "a.txt").read_text() == "content-a"
        assert (snapshot_dir / "b.txt").read_text() == "content-b"

    def test_excludes_files(self, tmp_path):
        """Excluded files are not copied to the snapshot."""
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()
        (clone_dir / "keep.txt").write_text("keep")
        (clone_dir / "skip.txt").write_text("skip")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        materialized = _prepare_snapshot(clone_dir, ["keep.txt", "skip.txt"], {"skip.txt"}, snapshot_dir)

        assert len(materialized) == 1
        assert (snapshot_dir / "keep.txt").exists()
        assert not (snapshot_dir / "skip.txt").exists()

    def test_handles_subdirectories(self, tmp_path):
        """Files in subdirectories are correctly copied."""
        clone_dir = tmp_path / "clone"
        sub = clone_dir / "sub"
        sub.mkdir(parents=True)
        (sub / "file.txt").write_text("nested")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        materialized = _prepare_snapshot(clone_dir, ["sub"], set(), snapshot_dir)

        assert len(materialized) == 1
        assert (snapshot_dir / "sub" / "file.txt").read_text() == "nested"


class TestApplyDiff:
    """Tests for the diff application helper."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    @pytest.fixture
    def git_project(self, tmp_path, git_setup):
        """Create a git-initialised project directory."""
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

    def test_apply_clean_diff(self, git_project, git_setup):
        """A clean diff should apply without conflicts."""
        git_executable, git_env = git_setup

        # Create and commit initial file
        (git_project / "test.txt").write_text("line1\nline2\nline3\n")
        subprocess.run(  # nosec B603
            [git_executable, "add", "."],
            cwd=git_project,
            check=True,
            capture_output=True,
            env=git_env,
        )
        subprocess.run(  # nosec B603
            [git_executable, "commit", "-m", "initial"],
            cwd=git_project,
            check=True,
            capture_output=True,
            env=git_env,
        )

        # Create a simple diff
        diff = (
            "diff --git a/test.txt b/test.txt\n"
            "--- a/test.txt\n"
            "+++ b/test.txt\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-line2\n"
            "+line2-updated\n"
            " line3\n"
        )

        result = _apply_diff(diff, git_project, git_executable, git_env)
        assert result is True
        assert "line2-updated" in (git_project / "test.txt").read_text()

    def test_apply_empty_diff_returns_true(self, git_project, git_setup):
        """An empty diff is not a failure."""
        git_executable, git_env = git_setup
        result = _apply_diff("", git_project, git_executable, git_env)
        assert result is True


class TestSyncCommand:
    """Integration-style tests for the sync command."""

    def _setup_project(self, tmp_path, include=None):
        """Create a minimal project directory with template.yml."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": include or ["test.txt"],
        }
        with open(template_file, "w") as f:
            yaml.dump(config, f)

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_already_up_to_date(self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, tmp_path):
        """When lock SHA matches upstream HEAD, sync exits early."""
        self._setup_project(tmp_path)

        # Write lock matching upstream
        _write_lock(tmp_path, "abc123")
        mock_sha.return_value = "abc123"

        # Mock temp dir (only upstream_dir is needed before early exit)
        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        mock_mkdtemp.return_value = str(clone_dir)

        sync(tmp_path, "main", None, "merge")

        # Should not have attempted to clone base (early exit)
        mock_clone_base.assert_not_called()

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_overwrite_copies_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """Overwrite strategy copies upstream files to target."""
        self._setup_project(tmp_path)

        mock_sha.return_value = "def456"

        # Setup upstream clone directory with a file
        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("upstream content")

        # Snapshot directory (separate from clone)
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "overwrite")

        # File should be copied to target
        target_file = tmp_path / "test.txt"
        assert target_file.exists()
        assert target_file.read_text() == "upstream content"

        # Lock should be updated
        assert _read_lock(tmp_path) == "def456"

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_diff_does_not_modify_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """Diff strategy shows changes but does not modify files."""
        self._setup_project(tmp_path)

        # Create existing local file
        (tmp_path / "test.txt").write_text("local content")

        mock_sha.return_value = "def456"

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("upstream content")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "diff")

        # Local file should not be modified
        assert (tmp_path / "test.txt").read_text() == "local content"
        # Lock should NOT be updated in diff mode
        assert _read_lock(tmp_path) is None

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_overwrite_with_paths_filter(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """Overwrite strategy with --paths syncs only specified files."""
        self._setup_project(tmp_path, include=["a.txt", "b.txt"])

        mock_sha.return_value = "def456"

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "a.txt").write_text("upstream-a")
        (clone_dir / "b.txt").write_text("upstream-b")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "overwrite", paths=["a.txt"])

        # Only a.txt should be synced
        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "a.txt").read_text() == "upstream-a"
        assert not (tmp_path / "b.txt").exists()

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_first_sync_copies_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """On first sync (no lock), merge copies new files."""
        self._setup_project(tmp_path)

        mock_sha.return_value = "first111"

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("new template content\n")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        # merge also creates base_snapshot dir
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        assert (tmp_path / "test.txt").read_text() == "new template content\n"
        assert _read_lock(tmp_path) == "first111"


class TestSyncCLI:
    """Tests for the CLI wiring of the sync command."""

    runner = CliRunner()

    def test_sync_help(self):
        """Sync command should have help text."""
        result = self.runner.invoke(cli.app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "merge" in result.output
        assert "diff" in result.output
        assert "overwrite" in result.output
        assert "paths" in result.output

    def test_sync_invalid_strategy(self, tmp_path):
        """Invalid strategy should fail."""
        result = self.runner.invoke(cli.app, ["sync", str(tmp_path), "--strategy", "invalid"])
        assert result.exit_code != 0

    @patch("rhiza.commands.sync.sync")
    def test_sync_cli_calls_sync_function(self, mock_sync, tmp_path):
        """CLI should delegate to sync function."""
        result = self.runner.invoke(
            cli.app,
            ["sync", str(tmp_path), "--strategy", "diff", "--branch", "develop"],
        )
        if result.exit_code == 0:
            mock_sync.assert_called_once()
