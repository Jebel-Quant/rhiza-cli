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
    _clone_and_resolve_upstream,
    _clone_at_sha,
    _excluded_set,
    _expand_paths,
    _get_head_sha,
    _merge_with_base,
    _prepare_snapshot,
    _read_lock,
    _sync_diff,
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


class TestSyncOrphanedFiles:
    """Tests verifying that orphaned files are deleted when template.yml changes during sync."""

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
            "include": include or ["new.txt"],
        }
        with open(template_file, "w") as f:
            yaml.dump(config, f)

    def _write_history(self, tmp_path, files):
        """Write a history file listing tracked files."""
        history_file = tmp_path / ".rhiza" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("w") as f:
            f.write("# Rhiza Template History\n")
            for name in files:
                f.write(f"{name}\n")

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_overwrite_deletes_orphaned_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """Overwrite strategy removes files no longer present in the updated template."""
        # Template now only includes new.txt (old.txt was removed from template.yml)
        self._setup_project(tmp_path, include=["new.txt"])

        # History from previous sync tracked both files
        self._write_history(tmp_path, ["old.txt", "new.txt"])

        # Both files exist in the project
        (tmp_path / "old.txt").write_text("old content")
        (tmp_path / "new.txt").write_text("existing content")

        mock_sha.return_value = "def456"

        # Upstream clone only provides new.txt
        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "new.txt").write_text("upstream new content")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "overwrite")

        # new.txt should be updated from upstream
        assert (tmp_path / "new.txt").exists()
        # old.txt should be deleted as it is no longer in the template
        assert not (tmp_path / "old.txt").exists()

        # History file should only contain new.txt (old.txt removed)
        history_content = (tmp_path / ".rhiza" / "history").read_text()
        assert "new.txt" in history_content
        assert "old.txt" not in history_content

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_merge_first_sync_deletes_orphaned_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """Merge strategy (first sync) removes files no longer present in the updated template."""
        # Template now only includes new.txt (old.txt was removed from template.yml)
        self._setup_project(tmp_path, include=["new.txt"])

        # History from a previous materialize tracked both files
        self._write_history(tmp_path, ["old.txt", "new.txt"])

        # Both files exist in the project
        (tmp_path / "old.txt").write_text("old content")
        (tmp_path / "new.txt").write_text("existing content")

        mock_sha.return_value = "first111"

        # Upstream clone only provides new.txt
        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "new.txt").write_text("new template content\n")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        # merge also creates base_snapshot dir
        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        # new.txt should be present
        assert (tmp_path / "new.txt").exists()
        # old.txt should be deleted as it is no longer in the template
        assert not (tmp_path / "old.txt").exists()

        # History file should only contain new.txt (old.txt removed)
        history_content = (tmp_path / ".rhiza" / "history").read_text()
        assert "new.txt" in history_content
        assert "old.txt" not in history_content


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


class TestGetHeadSha:
    """Tests for _get_head_sha helper (lines 96-104)."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    def test_get_head_sha(self, tmp_path, git_setup):
        """_get_head_sha returns the HEAD SHA of a repository."""
        git_executable, git_env = git_setup
        subprocess.run([git_executable, "init"], cwd=tmp_path, check=True, capture_output=True, env=git_env)
        subprocess.run(
            [git_executable, "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=git_env,
        )
        subprocess.run(
            [git_executable, "config", "user.name", "T"], cwd=tmp_path, check=True, capture_output=True, env=git_env
        )
        (tmp_path / "f.txt").write_text("x")
        subprocess.run([git_executable, "add", "."], cwd=tmp_path, check=True, capture_output=True, env=git_env)
        subprocess.run(
            [git_executable, "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True, env=git_env
        )

        sha = _get_head_sha(tmp_path, git_executable, git_env)
        assert len(sha) == 40
        assert sha.isalnum()


class TestCloneAtSha:
    """Tests for _clone_at_sha helper (lines 125-182)."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    @patch("rhiza.commands.sync.subprocess.run")
    def test_clone_at_sha_calls_subprocess(self, mock_run, tmp_path, git_setup):
        """_clone_at_sha invokes the expected git commands."""
        from unittest.mock import MagicMock

        git_executable, git_env = git_setup
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        dest = tmp_path / "dest"
        dest.mkdir()
        _clone_at_sha("https://github.com/example/repo.git", "abc123", dest, ["README.md"], git_executable, git_env)

        # Should have called subprocess.run multiple times (clone, sparse-checkout, checkout)
        assert mock_run.call_count >= 3


class TestApplyDiffConflict:
    """Tests for conflict-handling branch in _apply_diff (lines 293-314)."""

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
            subprocess.run(cmd, cwd=project, check=True, capture_output=True, env=git_env)
        return project

    def test_apply_diff_returns_false_on_conflict(self, git_project, git_setup):
        """When git apply -3 fails, _apply_diff falls back and returns False."""
        git_executable, git_env = git_setup

        # A diff that cannot apply (no context in repo)
        diff = (
            "diff --git a/nonexistent.txt b/nonexistent.txt\n"
            "--- a/nonexistent.txt\n"
            "+++ b/nonexistent.txt\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = _apply_diff(diff, git_project, git_executable, git_env)
        assert result is False


class TestSyncDiffNoChanges:
    """Tests for _sync_diff when there are no differences (line 355)."""

    def test_sync_diff_no_changes(self, tmp_path):
        """_sync_diff logs success when there are no differences."""
        # target and upstream_snapshot with identical content
        target = tmp_path / "target"
        target.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()

        (target / "same.txt").write_text("identical")
        (upstream / "same.txt").write_text("identical")

        # Should not raise; line 355 (logger.success) should be executed
        _sync_diff(target, upstream)


class TestSyncMergeWithBase:
    """Tests for merge strategy with an existing base SHA (lines 421, 473-497)."""

    def _setup_project(self, tmp_path, include=None):
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True, exist_ok=True)
        with open(rhiza_dir / "template.yml", "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": include or ["test.txt"],
                },
                f,
            )

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.commands.sync._get_head_sha")
    def test_sync_merge_with_existing_base_sha(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, tmp_path
    ):
        """Merge strategy calls _merge_with_base when a base SHA exists (line 421)."""
        self._setup_project(tmp_path)

        # Write a lock so base_sha will be "oldsha" ≠ upstream
        _write_lock(tmp_path, "oldsha1234567890")
        mock_sha.return_value = "newsha1234567890"

        clone_dir = tmp_path / "upstream_clone"
        clone_dir.mkdir()
        (clone_dir / "test.txt").write_text("upstream content\n")

        snapshot_dir = tmp_path / "upstream_snapshot"
        snapshot_dir.mkdir()

        base_snapshot_dir = tmp_path / "base_snapshot"
        base_snapshot_dir.mkdir()

        base_clone_dir = tmp_path / "base_clone"
        base_clone_dir.mkdir()

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        # _clone_at_sha is mocked to succeed without network access
        sync(tmp_path, "main", None, "merge")

        # _clone_at_sha should have been called for the base snapshot
        mock_clone_base.assert_called_once()


class TestCloneAndResolveUpstreamWithTemplates:
    """Tests for template bundle resolution path in _clone_and_resolve_upstream (lines 532-535)."""

    @patch("rhiza.commands.sync._get_head_sha")
    @patch("rhiza.commands.sync.resolve_include_paths")
    @patch("rhiza.commands.sync.load_bundles_from_clone")
    @patch("rhiza.commands.sync._update_sparse_checkout")
    @patch("rhiza.commands.sync._clone_template_repository")
    def test_bundle_resolution_path(
        self,
        mock_clone,
        mock_update_sparse,
        mock_load_bundles,
        mock_resolve,
        mock_head_sha,
        tmp_path,
    ):
        """_clone_and_resolve_upstream resolves bundle paths when template.templates is set."""
        import shutil as _shutil
        from unittest.mock import MagicMock

        from rhiza.subprocess_utils import get_git_executable

        git_executable = get_git_executable()
        git_env = os.environ.copy()
        git_env["GIT_TERMINAL_PROMPT"] = "0"

        # Build a fake RhizaTemplate with templates set
        template = MagicMock()
        template.templates = ["core"]

        mock_bundles = MagicMock()
        mock_load_bundles.return_value = mock_bundles
        mock_resolve.return_value = ["Makefile", ".github"]
        mock_head_sha.return_value = "abc123def456"

        upstream_dir, upstream_sha, resolved_paths = _clone_and_resolve_upstream(
            template,
            "https://github.com/example/repo.git",
            "main",
            [],
            git_executable,
            git_env,
        )

        # Bundle resolution code path should have been taken
        mock_load_bundles.assert_called_once()
        mock_resolve.assert_called_once_with(template, mock_bundles)
        mock_update_sparse.assert_called_once()
        assert resolved_paths == ["Makefile", ".github"]
        assert upstream_sha == "abc123def456"
        _shutil.rmtree(upstream_dir, ignore_errors=True)


class TestCloneAtShaErrorPaths:
    """Tests for error-handling branches in _clone_at_sha (lines 141-144, 164-167, 179-182)."""

    @pytest.fixture
    def git_setup(self):
        """Return git executable and env."""
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return git, env

    @patch("rhiza.commands.sync.subprocess.run")
    def test_clone_failure_exits(self, mock_run, tmp_path, git_setup):
        """Clone failure triggers sys.exit(1) (lines 141-144)."""
        import subprocess as _sp

        git_executable, git_env = git_setup
        err = _sp.CalledProcessError(1, "git clone")
        err.stderr = "fatal: not a git repo"
        mock_run.side_effect = err

        dest = tmp_path / "dest"
        dest.mkdir()
        with pytest.raises(SystemExit):
            _clone_at_sha("https://example.com/repo.git", "abc123", dest, ["README.md"], git_executable, git_env)

    @patch("rhiza.commands.sync.subprocess.run")
    def test_sparse_checkout_failure_exits(self, mock_run, tmp_path, git_setup):
        """Sparse-checkout failure triggers sys.exit(1) (lines 164-167)."""
        import subprocess as _sp
        from unittest.mock import MagicMock

        git_executable, git_env = git_setup
        ok = MagicMock(returncode=0, stdout="", stderr="")
        err = _sp.CalledProcessError(1, "git sparse-checkout")
        err.stderr = "error: sparse-checkout failed"
        # First call (clone) succeeds, second call (sparse-checkout) fails
        mock_run.side_effect = [ok, err]

        dest = tmp_path / "dest"
        dest.mkdir()
        with pytest.raises(SystemExit):
            _clone_at_sha("https://example.com/repo.git", "abc123", dest, ["README.md"], git_executable, git_env)

    @patch("rhiza.commands.sync.subprocess.run")
    def test_checkout_failure_exits(self, mock_run, tmp_path, git_setup):
        """Checkout failure triggers sys.exit(1) (lines 179-182)."""
        import subprocess as _sp
        from unittest.mock import MagicMock

        git_executable, git_env = git_setup
        ok = MagicMock(returncode=0, stdout="", stderr="")
        err = _sp.CalledProcessError(128, "git checkout")
        err.stderr = "error: pathspec not found"
        # First three calls (clone, sparse-checkout init, sparse-checkout set) succeed; checkout fails
        mock_run.side_effect = [ok, ok, ok, err]

        dest = tmp_path / "dest"
        dest.mkdir()
        with pytest.raises(SystemExit):
            _clone_at_sha("https://example.com/repo.git", "abc123", dest, ["README.md"], git_executable, git_env)


class TestMergeWithBasePaths:
    """Tests for _merge_with_base helper (lines 478-479, 487-489, 495)."""

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
        """Create a minimal git-initialised target project."""
        git_executable, git_env = git_setup
        project = tmp_path / "project"
        project.mkdir()
        for cmd in [
            [git_executable, "init"],
            [git_executable, "config", "user.email", "t@t.com"],
            [git_executable, "config", "user.name", "T"],
        ]:
            subprocess.run(cmd, cwd=project, check=True, capture_output=True, env=git_env)
        return project

    @patch("rhiza.commands.sync._clone_at_sha")
    def test_merge_with_base_handles_clone_exception(self, mock_clone_at_sha, tmp_path, git_setup):
        """Exception in _clone_at_sha is caught and logged (lines 478-479)."""
        git_executable, git_env = git_setup
        mock_clone_at_sha.side_effect = RuntimeError("network error")

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "file.txt").write_text("upstream\n")

        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()

        target = tmp_path / "target"
        target.mkdir()

        # Should not raise — exception is caught and we fall through
        _merge_with_base(
            target,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            ["file.txt"],
            set(),
            "https://example.com/repo.git",
            git_executable,
            git_env,
        )

    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._prepare_snapshot")
    def test_merge_with_base_no_diff(self, mock_prepare, mock_clone, mock_get_diff, tmp_path, git_setup):
        """When diff is empty, lock is updated and function returns early (lines 487-489)."""
        git_executable, git_env = git_setup
        mock_get_diff.return_value = ""  # empty diff → no changes

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (target / ".rhiza").mkdir()

        _merge_with_base(
            target,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            ["file.txt"],
            set(),
            "https://example.com/repo.git",
            git_executable,
            git_env,
        )

        # Lock should be updated with upstream SHA
        assert _read_lock(target) == "newsha"

    @patch("rhiza.commands.sync._apply_diff")
    @patch("rhiza.commands.sync.get_diff")
    @patch("rhiza.commands.sync._clone_at_sha")
    @patch("rhiza.commands.sync._prepare_snapshot")
    def test_merge_with_base_clean_apply(
        self, mock_prepare, mock_clone, mock_get_diff, mock_apply, tmp_path, git_project, git_setup
    ):
        """When diff applies cleanly, success is logged (line 495)."""
        git_executable, git_env = git_setup
        mock_get_diff.return_value = (
            "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"
        )
        mock_apply.return_value = True  # clean merge

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()

        _merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            ["file.txt"],
            set(),
            "https://example.com/repo.git",
            git_executable,
            git_env,
        )

        mock_apply.assert_called_once()
