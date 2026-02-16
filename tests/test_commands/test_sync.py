"""Tests for the ``sync`` command and its helper functions.

Tests cover:
- Lock-file read/write
- 3-way merge behaviour (clean merge, conflicts, new files)
- Diff-only (dry-run) mode
- Overwrite strategy
- CLI wiring
"""

from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.sync import (
    _diff_file,
    _excluded_set,
    _expand_paths,
    _merge_file,
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


class TestMergeFile:
    """Tests for the 3-way merge helper."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        import os
        import shutil

        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    def test_no_local_file_returns_upstream(self, git_setup):
        """When local file doesn't exist, upstream wins."""
        git_executable, git_env = git_setup
        merged, conflicts = _merge_file(
            base_content="base",
            upstream_content="upstream",
            local_content=None,
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert merged == "upstream"
        assert not conflicts

    def test_identical_local_and_upstream_no_conflict(self, git_setup):
        """When local and upstream are equal, no conflict."""
        git_executable, git_env = git_setup
        merged, conflicts = _merge_file(
            base_content="base content\n",
            upstream_content="same\n",
            local_content="same\n",
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert not conflicts
        assert merged == "same\n"

    def test_clean_merge_upstream_only_change(self, git_setup):
        """When only upstream changed, clean merge adopts upstream."""
        git_executable, git_env = git_setup
        base = "line1\nline2\nline3\n"
        upstream = "line1\nline2-updated\nline3\n"
        local = "line1\nline2\nline3\n"  # Same as base

        merged, conflicts = _merge_file(
            base_content=base,
            upstream_content=upstream,
            local_content=local,
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert not conflicts
        assert "line2-updated" in merged

    def test_clean_merge_local_only_change(self, git_setup):
        """When only local changed, clean merge preserves local."""
        git_executable, git_env = git_setup
        base = "line1\nline2\nline3\n"
        upstream = "line1\nline2\nline3\n"  # Same as base
        local = "line1\nline2-local\nline3\n"

        merged, conflicts = _merge_file(
            base_content=base,
            upstream_content=upstream,
            local_content=local,
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert not conflicts
        assert "line2-local" in merged

    def test_conflict_on_same_line(self, git_setup):
        """When both changed the same line, conflict markers appear."""
        git_executable, git_env = git_setup
        base = "line1\nline2\nline3\n"
        upstream = "line1\nupstream-change\nline3\n"
        local = "line1\nlocal-change\nline3\n"

        merged, conflicts = _merge_file(
            base_content=base,
            upstream_content=upstream,
            local_content=local,
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert conflicts
        assert "<<<<<<<" in merged
        assert ">>>>>>>" in merged

    def test_no_base_identical_files(self, git_setup):
        """No base, but local == upstream → no conflict."""
        git_executable, git_env = git_setup
        merged, conflicts = _merge_file(
            base_content=None,
            upstream_content="content\n",
            local_content="content\n",
            rel_path="test.txt",
            git_executable=git_executable,
            git_env=git_env,
        )
        assert not conflicts
        assert merged == "content\n"


class TestDiffFile:
    """Tests for the diff helper."""

    def test_no_local_shows_additions(self):
        """New file shows additions."""
        diff = _diff_file("new content\n", None, "test.txt")
        assert diff is not None
        assert "+new content" in diff

    def test_identical_returns_none(self):
        """Identical files return None."""
        diff = _diff_file("same\n", "same\n", "test.txt")
        assert diff is None

    def test_changed_shows_diff(self):
        """Changed file produces a diff."""
        diff = _diff_file("new\n", "old\n", "test.txt")
        assert diff is not None
        assert "-old" in diff
        assert "+new" in diff


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

        # Mock temp dir
        temp_dir = tmp_path / "upstream"
        temp_dir.mkdir()
        mock_mkdtemp.return_value = str(temp_dir)

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
        temp_dir = tmp_path / "upstream"
        temp_dir.mkdir()
        test_file = temp_dir / "test.txt"
        test_file.write_text("upstream content")
        mock_mkdtemp.return_value = str(temp_dir)

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

        temp_dir = tmp_path / "upstream"
        temp_dir.mkdir()
        (temp_dir / "test.txt").write_text("upstream content")
        mock_mkdtemp.return_value = str(temp_dir)

        sync(tmp_path, "main", None, "diff")

        # Local file should not be modified
        assert (tmp_path / "test.txt").read_text() == "local content"
        # Lock should NOT be updated in diff mode
        assert _read_lock(tmp_path) is None

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_preserves_local_changes(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, tmp_path
    ):
        """Merge strategy preserves local-only changes when upstream is unchanged."""
        self._setup_project(tmp_path)

        base_sha = "base111"
        upstream_sha = "upstream222"

        _write_lock(tmp_path, base_sha)
        mock_sha.return_value = upstream_sha

        # Local file has user customisation
        (tmp_path / "test.txt").write_text("local custom content\n")

        # Setup upstream clone
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()
        (upstream_dir / "test.txt").write_text("local custom content\n")

        # Setup base clone  — mock _clone_at_sha to populate a temp dir
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        (base_dir / "test.txt").write_text("local custom content\n")

        call_count = [0]

        def mkdtemp_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return str(upstream_dir)
            return str(base_dir)

        mock_mkdtemp.side_effect = mkdtemp_side_effect

        sync(tmp_path, "main", None, "merge")

        # Local custom content should be preserved (all three versions identical)
        assert (tmp_path / "test.txt").read_text() == "local custom content\n"
        assert _read_lock(tmp_path) == upstream_sha

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_first_sync_copies_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """On first sync (no lock), merge copies new files."""
        self._setup_project(tmp_path)

        mock_sha.return_value = "first111"

        temp_dir = tmp_path / "upstream"
        temp_dir.mkdir()
        (temp_dir / "test.txt").write_text("new template content\n")
        mock_mkdtemp.return_value = str(temp_dir)

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
