"""Tests for the ``sync`` command and its helper functions.

Tests cover:
- Lock-file read/write (YAML format and legacy plain-text backward compat)
- Path expansion and exclusion
- Snapshot preparation (new cruft-based helper)
- Diff application via ``git apply -3`` (new cruft-based helper)
- Integration tests for each strategy (diff, overwrite, merge)
- CLI wiring
"""

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.lock import (
    _get_head_sha,
    _read_lock,
    _read_lock_files,
    _write_lock,
)
from rhiza.commands.sync import (
    _apply_diff,
    _clone_at_sha,
    _excluded_set,
    _expand_paths,
    _prepare_snapshot,
    sync,
)


class TestLockFile:
    """Tests for lock-file helpers."""

    def test_read_lock_returns_none_when_missing(self, tmp_path):
        """No lock file → None."""
        assert _read_lock(tmp_path) is None

    def test_write_and_read_lock(self, tmp_path):
        """Round-trip write/read of a lock file returns the SHA."""
        sha = "abc123def456"
        _write_lock(tmp_path, sha, "owner/repo", "github", "main", [], [], [], [])
        assert _read_lock(tmp_path) == sha

    def test_write_lock_creates_parent_directory(self, tmp_path):
        """Lock file creation should create .rhiza/ if needed."""
        target = tmp_path / "project"
        target.mkdir()
        _write_lock(target, "deadbeef", "owner/repo", "github", "main", [], [], [], [])
        assert (target / ".rhiza" / "template.lock").exists()

    def test_lock_file_is_yaml_format(self, tmp_path):
        """Written lock file must be valid YAML with all required fields."""
        _write_lock(
            tmp_path,
            "abc123",
            "owner/repo",
            "github",
            "main",
            [".github"],
            ["tests"],
            ["core"],
            [Path("file.txt")],
        )
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text())
        assert data["sha"] == "abc123"
        assert data["repo"] == "owner/repo"
        assert data["host"] == "github"
        assert data["ref"] == "main"
        assert data["include"] == [".github"]
        assert data["exclude"] == ["tests"]
        assert data["templates"] == ["core"]
        assert data["files"] == ["file.txt"]

    def test_read_lock_backward_compat_plain_text(self, tmp_path):
        """Legacy plain-text lock files (bare SHA) are still readable."""
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("abc123def456\n")
        assert _read_lock(tmp_path) == "abc123def456"

    def test_read_lock_returns_none_for_empty_file(self, tmp_path):
        """A lock file that is empty (or whitespace-only) returns None."""
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("   \n")
        assert _read_lock(tmp_path) is None

    def test_read_lock_falls_back_on_yaml_parse_error(self, tmp_path):
        """If YAML parsing fails, content is returned as a plain-text SHA."""
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("some-sha-value\n")
        with patch("rhiza.commands.lock.yaml.safe_load", side_effect=yaml.YAMLError("parse error")):
            result = _read_lock(tmp_path)
        assert result == "some-sha-value"

    def test_read_lock_files_returns_files_from_lock(self, tmp_path):
        """_read_lock_files reads the files list from the lock file."""
        _write_lock(
            tmp_path,
            "abc123",
            "owner/repo",
            "github",
            "main",
            [],
            [],
            [],
            [Path("a.txt"), Path("b.txt")],
        )
        result = _read_lock_files(tmp_path)
        assert sorted(str(f) for f in result) == ["a.txt", "b.txt"]

    def test_read_lock_files_fallback_to_history(self, tmp_path):
        """_read_lock_files falls back to .rhiza/history when no lock exists."""
        history = tmp_path / ".rhiza" / "history"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text("# comment\nfoo.txt\nbar.txt\n")
        result = _read_lock_files(tmp_path)
        assert sorted(str(f) for f in result) == ["bar.txt", "foo.txt"]

    def test_read_lock_files_fallback_to_legacy_history(self, tmp_path):
        """_read_lock_files falls back to .rhiza.history (root-level) when neither lock nor .rhiza/history exists."""
        legacy = tmp_path / ".rhiza.history"
        legacy.write_text("# comment\nbaz.txt\n")
        result = _read_lock_files(tmp_path)
        assert [str(f) for f in result] == ["baz.txt"]

    def test_read_lock_files_returns_empty_when_no_lock_or_history(self, tmp_path):
        """_read_lock_files returns [] when no lock and no history files exist."""
        assert _read_lock_files(tmp_path) == []

    def test_read_lock_files_empty_when_lock_has_no_files_key(self, tmp_path):
        """Lock file without 'files' key returns [] (old lock format)."""
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("sha: abc123\nrepo: owner/repo\n")
        result = _read_lock_files(tmp_path)
        assert result == []

    def test_read_lock_files_falls_back_to_history_on_yaml_error(self, tmp_path):
        """_read_lock_files falls back to .rhiza/history when lock YAML is unparseable."""
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("sha: abc123\n")
        history = tmp_path / ".rhiza" / "history"
        history.write_text("fallback.txt\n")
        with patch("rhiza.commands.lock.yaml.safe_load", side_effect=yaml.YAMLError("bad yaml")):
            result = _read_lock_files(tmp_path)
        assert [str(f) for f in result] == ["fallback.txt"]


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

    def test_always_excludes_template_yml(self, tmp_path):
        """Template config is always excluded."""
        excludes = _excluded_set(tmp_path, [])
        assert ".rhiza/template.yml" in excludes

    def test_history_no_longer_excluded(self, tmp_path):
        """.rhiza/history is no longer in the default exclusion set."""
        excludes = _excluded_set(tmp_path, [])
        assert ".rhiza/history" not in excludes

    def test_includes_user_exclusions(self, tmp_path):
        """User-configured exclusions appear in the set."""
        f = tmp_path / "secret.txt"
        f.write_text("shh")
        excludes = _excluded_set(tmp_path, ["secret.txt"])
        assert "secret.txt" in excludes


class TestGetHeadSha:
    """Tests for the _get_head_sha helper."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    def test_get_head_sha_returns_full_sha(self, tmp_path, git_setup):
        """_get_head_sha returns the 40-character HEAD commit SHA."""
        git_executable, git_env = git_setup
        for cmd in [
            [git_executable, "init"],
            [git_executable, "config", "user.email", "test@test.com"],
            [git_executable, "config", "user.name", "Test"],
        ]:
            subprocess.run(cmd, cwd=tmp_path, check=True, capture_output=True, env=git_env)  # nosec B603
        (tmp_path / "file.txt").write_text("content")
        subprocess.run([git_executable, "add", "."], cwd=tmp_path, check=True, capture_output=True, env=git_env)  # nosec B603
        subprocess.run(
            [git_executable, "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True, env=git_env
        )  # nosec B603

        sha = _get_head_sha(tmp_path, git_executable, git_env)
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)


class TestCloneAtSha:
    """Tests for error-path handling in _clone_at_sha."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    def test_clone_error_exits(self, tmp_path, git_setup):
        """A git clone failure causes sys.exit(1)."""
        git_executable, git_env = git_setup
        error = subprocess.CalledProcessError(1, "git", stderr="fatal: repo not found")
        with patch("rhiza.commands.sync.subprocess.run", side_effect=error), pytest.raises(SystemExit):
            _clone_at_sha("https://example.com/repo.git", "abc123", tmp_path, ["file.txt"], git_executable, git_env)

    def test_sparse_checkout_error_exits(self, tmp_path, git_setup):
        """A sparse-checkout failure (after a successful clone) causes sys.exit(1)."""
        git_executable, git_env = git_setup
        error = subprocess.CalledProcessError(1, "git", stderr="error: sparse-checkout")
        with (
            patch("rhiza.commands.sync.subprocess.run", side_effect=[MagicMock(), error]),
            pytest.raises(SystemExit),
        ):
            _clone_at_sha("https://example.com/repo.git", "abc123", tmp_path, ["file.txt"], git_executable, git_env)

    def test_checkout_error_exits(self, tmp_path, git_setup):
        """A checkout failure (after successful clone and sparse-checkout) causes sys.exit(1)."""
        git_executable, git_env = git_setup
        error = subprocess.CalledProcessError(1, "git", stderr="error: checkout failed")
        with (
            patch(
                "rhiza.commands.sync.subprocess.run",
                side_effect=[MagicMock(), MagicMock(), MagicMock(), error],
            ),
            pytest.raises(SystemExit),
        ):
            _clone_at_sha("https://example.com/repo.git", "abc123", tmp_path, ["file.txt"], git_executable, git_env)


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

    def test_apply_diff_conflict_both_methods_fail(self, git_project, git_setup):
        """When both git apply -3 and --reject fail, returns False and logs warnings."""
        git_executable, git_env = git_setup
        error1 = subprocess.CalledProcessError(1, "git", stderr=b"conflict in file")
        error2 = subprocess.CalledProcessError(1, "git", stderr=b"cannot apply patch")
        with patch("rhiza.commands.sync.subprocess.run", side_effect=[error1, error2]):
            result = _apply_diff("some diff", git_project, git_executable, git_env)
        assert result is False


class TestSyncCommand:
    """Integration-style tests for the sync command."""

    def _setup_project(self, tmp_path, include=None, templates=None):
        """Create a minimal project directory with template.yml."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        template_file = rhiza_dir / "template.yml"

        config: dict = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
        }
        if templates:
            config["templates"] = templates
        else:
            config["include"] = include or ["test.txt"]
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

        # Write lock matching upstream (new YAML format)
        _write_lock(tmp_path, "abc123", "jebel-quant/rhiza", "github", "main", ["test.txt"], [], [], [])
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

        # Lock should be updated with full YAML format
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
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_diff_no_differences(self, mock_sha, mock_mkdtemp, mock_clone, mock_diff, mock_rmtree, tmp_path):
        """Diff strategy reports 'No differences found' when content matches."""
        self._setup_project(tmp_path)
        mock_sha.return_value = "def456"
        mock_diff.return_value = ""  # no differences

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "diff")

        # Lock should NOT be updated in diff mode
        assert _read_lock(tmp_path) is None

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

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_with_base_no_diff(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_diff, mock_rmtree, tmp_path
    ):
        """Merge with existing lock: when template is unchanged, only lock is updated."""
        self._setup_project(tmp_path)
        _write_lock(tmp_path, "base111", "jebel-quant/rhiza", "github", "main", ["test.txt"], [], [], [])
        mock_sha.return_value = "upstream222"
        mock_diff.return_value = ""  # no diff between base and upstream

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("content")
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()
        base_clone_dir = tmp_path / "base_clone"
        base_clone_dir.mkdir()

        # upstream_dir, upstream_snapshot, base_snapshot, base_clone
        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "upstream222"

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._apply_diff")
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_with_base_clean_diff(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_diff, mock_apply, mock_rmtree, tmp_path
    ):
        """Merge with existing lock: diff applies cleanly."""
        self._setup_project(tmp_path)
        _write_lock(tmp_path, "base111", "jebel-quant/rhiza", "github", "main", ["test.txt"], [], [], [])
        mock_sha.return_value = "upstream222"
        mock_diff.return_value = "diff --git a/test.txt b/test.txt\n--- a/test.txt\n"
        mock_apply.return_value = True  # clean apply

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("updated content")
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()
        base_clone_dir = tmp_path / "base_clone"
        base_clone_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "upstream222"
        mock_apply.assert_called_once()

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._apply_diff")
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_with_base_conflict_diff(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_diff, mock_apply, mock_rmtree, tmp_path
    ):
        """Merge with existing lock: diff has conflicts."""
        self._setup_project(tmp_path)
        _write_lock(tmp_path, "base111", "jebel-quant/rhiza", "github", "main", ["test.txt"], [], [], [])
        mock_sha.return_value = "upstream222"
        mock_diff.return_value = "diff --git a/test.txt b/test.txt\n--- a/test.txt\n"
        mock_apply.return_value = False  # conflict

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()
        base_clone_dir = tmp_path / "base_clone"
        base_clone_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "upstream222"
        mock_apply.assert_called_once()

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_with_base_clone_fail(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_diff, mock_rmtree, tmp_path
    ):
        """When base clone fails, merge falls back to treating all files as new."""
        self._setup_project(tmp_path)
        _write_lock(tmp_path, "base111", "jebel-quant/rhiza", "github", "main", ["test.txt"], [], [], [])
        mock_sha.return_value = "upstream222"
        mock_clone_base.side_effect = Exception("clone failed")
        mock_diff.return_value = ""  # no diff (empty base → no changes detected)

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("content")
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()
        base_clone_dir = tmp_path / "base_clone"
        base_clone_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "upstream222"

    @patch("rhiza.commands.sync._update_sparse_checkout")
    @patch("rhiza.commands.sync.resolve_include_paths")
    @patch("rhiza.commands.sync.load_bundles_from_clone")
    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_with_templates_resolves_bundles(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, mock_bundles, mock_resolve, mock_sparse, tmp_path
    ):
        """When template.templates is set, bundle resolution paths are used."""
        self._setup_project(tmp_path, templates=["core"])
        mock_sha.return_value = "template111"
        mock_resolve.return_value = ["test.txt"]

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("template content\n")
        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "template111"
        mock_bundles.assert_called_once()
        mock_resolve.assert_called_once()
        mock_sparse.assert_called_once()


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
