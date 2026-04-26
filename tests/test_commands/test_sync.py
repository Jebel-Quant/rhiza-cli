"""Tests for the ``sync`` command and its helper functions.

Tests cover:
- Lock-file read/write
- Path expansion and exclusion
- Snapshot preparation (new cruft-based helper)
- Diff application via ``git apply -3`` (new cruft-based helper)
- Integration tests for each strategy (diff, merge)
- CLI wiring
"""

import subprocess  # nosec B404
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands._sync_helpers import (
    _clean_orphaned_files,
    _delete_orphaned_file,
    _files_from_snapshot,
    _read_previously_tracked_files,
    _warn_about_workflow_files,
    _write_lock,
)
from rhiza.commands.sync import sync
from rhiza.models import GitContext, RhizaTemplate, TemplateLock
from rhiza.models._git_utils import _log_git_stderr_errors

# ---------------------------------------------------------------------------
# Module-level helpers shared across test classes
# ---------------------------------------------------------------------------


def _setup_project(tmp_path, include=None):
    """Create a minimal mock project directory with .git, pyproject.toml, and .rhiza/template.yml."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    rhiza_dir = tmp_path / ".rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "template-repository": "jebel-quant/rhiza",
        "template-branch": "main",
        "include": include or ["test.txt"],
    }
    with open(rhiza_dir / "template.yml", "w") as f:
        yaml.dump(config, f)


def _commit_all(project, git_ctx, message="add files"):
    """Stage all files in *project* and create a commit — test helper for git-based scenarios."""
    subprocess.run([git_ctx.executable, "add", "."], cwd=project, check=True, capture_output=True, env=git_ctx.env)  # nosec B603
    subprocess.run(  # nosec B603
        [git_ctx.executable, "commit", "-m", message],
        cwd=project,
        check=True,
        capture_output=True,
        env=git_ctx.env,
    )


def _write_history(tmp_path, files):
    """Write a history file listing tracked files."""
    history_file = tmp_path / ".rhiza" / "history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("w") as f:
        f.write("# Rhiza Template History\n")
        for name in files:
            f.write(f"{name}\n")


class TestLockFile:
    """Tests for lock-file helpers."""

    def test_no_lock_file_when_missing(self, tmp_path):
        """No lock file → lock path does not exist."""
        assert not (tmp_path / ".rhiza" / "template.lock").exists()

    def test_write_and_read_lock_sha(self, tmp_path):
        """Round-trip: write lock then read back sha via from_yaml."""
        sha = "abc123def456"
        _write_lock(tmp_path, TemplateLock(sha=sha))
        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == sha

    def test_write_lock_creates_parent_directory(self, tmp_path):
        """Lock file creation should create .rhiza/ if needed."""
        target = tmp_path / "project"
        target.mkdir()
        _write_lock(target, TemplateLock(sha="deadbeef"))
        assert (target / ".rhiza" / "template.lock").exists()

    def test_write_lock_yaml_format(self, tmp_path):
        """Lock file is written as YAML with all required fields including files."""
        # Create the file so it exists on disk (lock must not record absent files).
        (tmp_path / "Makefile").write_text("all:\n\techo done\n")
        lock = TemplateLock(
            sha="abc123def456",
            repo="jebel-quant/rhiza",
            host="github",
            ref="main",
            include=[".github/", ".rhiza/"],
            exclude=[],
            templates=[],
            files=["Makefile"],
        )
        _write_lock(tmp_path, lock)
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["sha"] == "abc123def456"
        assert data["repo"] == "jebel-quant/rhiza"
        assert data["host"] == "github"
        assert data["ref"] == "main"
        assert data["include"] == [".github/", ".rhiza/"]
        assert data["exclude"] == []
        assert data["templates"] == []
        assert data["files"] == ["Makefile"]

    def test_write_lock_filters_missing_files(self, tmp_path):
        """Files listed in the lock that don't exist in target are excluded."""
        # Only create one of the two files so the other is filtered out.
        (tmp_path / "exists.txt").write_text("here")
        lock = TemplateLock(
            sha="deadbeef12345678",
            files=["exists.txt", "missing.txt"],
        )
        _write_lock(tmp_path, lock)
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["files"] == ["exists.txt"]

    def test_write_lock_empty_files_when_all_missing(self, tmp_path):
        """When no listed files exist on disk the saved files list is empty."""
        lock = TemplateLock(
            sha="cafebabe12345678",
            files=["ghost_a.txt", "ghost_b.txt"],
        )
        _write_lock(tmp_path, lock)
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["files"] == []

    def test_write_lock_preserves_all_existing_files(self, tmp_path):
        """When all listed files exist on disk none are filtered out."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        lock = TemplateLock(
            sha="1234567890abcdef",
            files=["a.txt", "b.txt"],
        )
        _write_lock(tmp_path, lock)
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["files"] == ["a.txt", "b.txt"]

    def test_write_lock_files_sorted_alphabetically(self, tmp_path):
        """Files in the lock are written in alphabetical order regardless of input order."""
        for name in ["z.txt", "a.txt", "m.txt"]:
            (tmp_path / name).write_text(name)
        lock = TemplateLock(
            sha="1234567890abcdef",
            files=["z.txt", "a.txt", "m.txt"],
        )
        _write_lock(tmp_path, lock)
        lock_path = tmp_path / ".rhiza" / "template.lock"
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["files"] == ["a.txt", "m.txt", "z.txt"]

    def test_write_lock_no_tmp_file_left(self, tmp_path):
        """After _write_lock completes, no .tmp or .fd file should remain."""
        _write_lock(tmp_path, TemplateLock(sha="deadbeef12345678"))
        rhiza_dir = tmp_path / ".rhiza"
        assert not list(rhiza_dir.glob("template.lock.tmp"))
        assert not list(rhiza_dir.glob("template.lock.fd"))

    def test_write_lock_atomic_replace(self, tmp_path):
        """_write_lock uses an atomic rename so the lock is never partially written."""
        sha_first = "aaa111bbb222ccc3"
        sha_second = "ddd444eee555fff6"
        _write_lock(tmp_path, TemplateLock(sha=sha_first))
        _write_lock(tmp_path, TemplateLock(sha=sha_second))
        # The final lock must contain exactly the second SHA.
        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == sha_second

    def test_write_lock_without_fcntl(self, tmp_path):
        """_write_lock logs debug when fcntl is not available."""
        with patch("rhiza.commands._sync_helpers._FCNTL_AVAILABLE", False):
            _write_lock(tmp_path, TemplateLock(sha="cafebabe12345678"))

        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == "cafebabe12345678"


class TestApplyDiff:
    """Tests for the diff application helper."""

    def test_apply_clean_diff(self, git_project, git_ctx):
        """A clean diff should apply without conflicts."""
        # Create and commit initial file
        (git_project / "test.txt").write_text("line1\nline2\nline3\n")
        subprocess.run(  # nosec B603
            [git_ctx.executable, "add", "."],
            cwd=git_project,
            check=True,
            capture_output=True,
            env=git_ctx.env,
        )
        subprocess.run(  # nosec B603
            [git_ctx.executable, "commit", "-m", "initial"],
            cwd=git_project,
            check=True,
            capture_output=True,
            env=git_ctx.env,
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

        result = git_ctx._apply_diff(diff, git_project)
        assert result is True
        assert "line2-updated" in (git_project / "test.txt").read_text()

    def test_apply_empty_diff_returns_true(self, git_project, git_ctx):
        """An empty diff is not a failure."""
        result = git_ctx._apply_diff("", git_project, git_ctx)
        assert result is True


class TestAssertGitStatusClean:
    """Tests for _assert_git_status_clean."""

    def test_clean_working_tree_does_not_raise(self, git_project, git_ctx):
        """A clean working tree should not raise."""
        # Create and commit a file so the tree is clean
        (git_project / "README.md").write_text("# test\n")
        _commit_all(git_project, git_ctx, "initial commit")
        # Should not raise
        git_ctx.assert_status_clean(git_project)

    def test_dirty_working_tree_raises(self, git_project, git_ctx):
        """An uncommitted change should raise RuntimeError."""
        (git_project / "README.md").write_text("# test\n")
        _commit_all(git_project, git_ctx, "initial commit")
        # Introduce an uncommitted change
        (git_project / "dirty.txt").write_text("untracked change")
        with pytest.raises(RuntimeError, match="Working tree is not clean"):
            git_ctx.assert_status_clean(git_project)

    def test_staged_changes_raises(self, git_project, git_ctx):
        """Staged-but-not-committed changes should raise RuntimeError."""
        (git_project / "README.md").write_text("# test\n")
        _commit_all(git_project, git_ctx, "initial commit")
        # Stage a new file without committing
        (git_project / "staged.txt").write_text("staged content")
        subprocess.run(  # nosec B603
            [git_ctx.executable, "add", "staged.txt"],
            cwd=git_project,
            check=True,
            capture_output=True,
            env=git_ctx.env,
        )
        with pytest.raises(RuntimeError, match="Working tree is not clean"):
            git_ctx.assert_status_clean(git_project)


class TestSyncCommand:
    """Integration-style tests for the sync command."""

    @patch("rhiza.models._git_utils.subprocess.run")
    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_sync_diff_does_not_modify_files(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, mock_run, tmp_path):
        """Diff strategy shows changes but does not modify files."""
        # Setup git status check mock to return clean
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        _setup_project(tmp_path)

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
        assert not (tmp_path / ".rhiza" / "template.lock").exists()

    @patch("rhiza.models._git_utils.subprocess.run")
    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_sync_merge_first_sync_copies_files(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, mock_run, tmp_path
    ):
        """On first sync (no lock), merge copies new files."""
        # Setup git status check mock to return clean
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        _setup_project(tmp_path)

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
        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == "first111"

    def test_sync_diff_no_changes(self, tmp_path, git_ctx):
        """_sync_diff logs success when there are no differences."""
        # target and upstream_snapshot with identical content
        target = tmp_path / "target"
        target.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()

        (target / "same.txt").write_text("identical")
        (upstream / "same.txt").write_text("identical")

        # Should not raise; line 355 (logger.success) should be executed
        git_ctx.sync_diff(target, upstream)


class TestSyncOrphanedFiles:
    """Tests verifying that orphaned files are deleted when template.yml changes during sync."""

    @patch("rhiza.models._git_utils.subprocess.run")
    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_merge_first_sync_deletes_orphaned_files(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, mock_run, tmp_path
    ):
        """Merge strategy (first sync) removes files no longer present in the updated template."""
        # Setup git status check mock to return clean
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        # Template now only includes new.txt (old.txt was removed from template.yml)
        _setup_project(tmp_path, include=["new.txt"])

        # History from a previous materialize tracked both files
        _write_history(tmp_path, ["old.txt", "new.txt"])

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

        # template.lock should record the currently materialized files
        lock_content = TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock")
        assert lock_content.files == ["new.txt"]


class TestSyncCLI:
    """Tests for the CLI wiring of the sync command."""

    runner = CliRunner()

    def test_sync_help(self):
        """Sync command should have help text."""
        result = self.runner.invoke(cli.app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "merge" in result.output
        assert "diff" in result.output

    def test_sync_invalid_strategy(self, tmp_path):
        """Invalid strategy should fail."""
        result = self.runner.invoke(cli.app, ["sync", str(tmp_path), "--strategy", "invalid"])
        assert result.exit_code != 0

    @patch("rhiza.cli.sync_cmd")
    def test_sync_cli_calls_sync_function(self, mock_sync, tmp_path):
        """CLI should delegate to sync function."""
        result = self.runner.invoke(
            cli.app,
            ["sync", str(tmp_path), "--strategy", "diff", "--branch", "develop"],
        )
        assert result.exit_code == 0
        mock_sync.assert_called_once()

    @patch("rhiza.cli.sync_cmd")
    def test_sync_cli_exits_with_error_on_conflict(self, mock_sync, tmp_path):
        """CLI should exit with code 1 when sync raises RuntimeError due to conflicts."""
        mock_sync.side_effect = RuntimeError("Sync completed with merge conflicts")
        result = self.runner.invoke(
            cli.app,
            ["sync", str(tmp_path)],
        )
        assert result.exit_code == 1
        mock_sync.assert_called_once()


class TestApplyDiffConflict:
    """Tests for conflict-handling branch in _apply_diff."""

    def test_apply_diff_returns_false_on_conflict(self, git_project, git_ctx):
        """When git apply -3 fails, _apply_diff falls back and returns False."""
        # A diff that cannot apply (no context in repo)
        diff = (
            "diff --git a/nonexistent.txt b/nonexistent.txt\n"
            "--- a/nonexistent.txt\n"
            "+++ b/nonexistent.txt\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = git_ctx._apply_diff(diff, git_project)
        assert result is False

    def test_apply_diff_logs_rej_file_details_on_conflict(self, git_project, git_ctx):
        """After a conflict, a warning message names each .rej file explicitly."""
        from loguru import logger as _logger

        messages: list[str] = []
        handler_id = _logger.add(lambda msg: messages.append(msg), format="{message}", colorize=False)
        try:
            (git_project / "config.txt").write_text("timeout = 30\n")
            _commit_all(git_project, git_ctx)
            # Local change diverges from base so the patch won't apply cleanly
            (git_project / "config.txt").write_text("timeout = 99\n")

            base = git_project.parent / "base"
            base.mkdir()
            upstream = git_project.parent / "upstream"
            upstream.mkdir()
            (base / "config.txt").write_text("timeout = 30\n")
            (upstream / "config.txt").write_text("timeout = 60\n")

            diff = git_ctx.get_diff(base, upstream)
            git_ctx._apply_diff(diff, git_project)
        finally:
            _logger.remove(handler_id)

        # The warning must mention the specific file, not just a generic "*.rej" glob.
        combined = " ".join(messages)
        assert "config.txt" in combined


class TestScanConflictArtifacts:
    """Unit tests for GitContext._scan_conflict_artifacts."""

    def test_finds_rej_file(self, tmp_path, git_ctx):
        """A .rej file in the target directory is returned in rej_files."""
        (tmp_path / "foo.py.rej").write_text("+new line\n")
        rej, markers = git_ctx._scan_conflict_artifacts(tmp_path)
        assert "foo.py.rej" in rej
        assert markers == []

    def test_finds_conflict_marker_in_text_file(self, tmp_path, git_ctx):
        """A file containing <<<<<<< is returned in marker_files."""
        (tmp_path / "settings.yml").write_text("<<<<<<< ours\nfoo\n=======\nbar\n>>>>>>> upstream\n")
        rej, markers = git_ctx._scan_conflict_artifacts(tmp_path)
        assert rej == []
        assert "settings.yml" in markers

    def test_clean_tree_returns_empty_lists(self, tmp_path, git_ctx):
        """No artifacts in a clean directory → both lists are empty."""
        (tmp_path / "README.md").write_text("# clean\n")
        rej, markers = git_ctx._scan_conflict_artifacts(tmp_path)
        assert rej == []
        assert markers == []

    def test_rej_file_not_included_in_marker_scan(self, tmp_path, git_ctx):
        """A .rej file is only reported in rej_files, not also in marker_files."""
        # .rej files often contain diff context that looks like conflict markers
        (tmp_path / "a.txt.rej").write_text("<<<<<<< ours\nfoo\n")
        rej, markers = git_ctx._scan_conflict_artifacts(tmp_path)
        assert "a.txt.rej" in rej
        assert markers == []

    def test_nested_files_detected(self, tmp_path, git_ctx):
        """.rej and marker files in subdirectories are detected."""
        subdir = tmp_path / "src" / "deep"
        subdir.mkdir(parents=True)
        (subdir / "module.py.rej").write_text("+foo\n")
        (subdir / "other.py").write_text("<<<<<<< ours\nfoo\n=======\nbar\n>>>>>>> upstream\n")
        rej, markers = git_ctx._scan_conflict_artifacts(tmp_path)
        assert any("module.py.rej" in r for r in rej)
        assert any("other.py" in m for m in markers)


class TestSyncMergeWithBase:
    """Tests for merge strategy with an existing base SHA."""

    @patch("rhiza.models._git_utils.subprocess.run")
    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_sync_merge_with_existing_base_sha(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, mock_run, tmp_path
    ):
        """Merge strategy calls _merge_with_base when a base SHA exists."""
        # Setup git status check mock to return clean
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        _setup_project(tmp_path)

        # Write a lock so base_sha will be "oldsha" ≠ upstream
        _write_lock(tmp_path, TemplateLock(sha="oldsha1234567890"))
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

        # clone_at_sha is mocked to succeed without network access
        sync(tmp_path, "main", None, "merge")

        # clone_at_sha should have been called for the base snapshot
        mock_clone_base.assert_called_once()


class TestMergeWithBasePaths:
    """Tests for _merge_with_base helper."""

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    def test_merge_with_base_handles_clone_exception(self, mock_clone_at_sha, tmp_path, git_ctx):
        """Exception in clone_at_sha is caught and logged."""
        mock_clone_at_sha.side_effect = RuntimeError("network error")

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "file.txt").write_text("upstream\n")

        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()

        target = tmp_path / "target"
        target.mkdir()

        # Should not raise — exception is caught and we fall through
        git_ctx._merge_with_base(
            target,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["file.txt"]),
            set(),
            TemplateLock(sha="newsha"),
        )

    @patch("rhiza.models._git_utils.GitContext.get_diff")
    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.models._git_utils._prepare_snapshot")
    def test_merge_with_base_no_diff(self, mock_prepare, mock_clone, mock_get_diff, tmp_path, git_ctx):
        """When diff is empty, lock is updated and function returns early."""
        mock_get_diff.return_value = ""  # empty diff → no changes

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (target / ".rhiza").mkdir()

        git_ctx._merge_with_base(
            target,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["file.txt"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        # Lock should be updated with upstream SHA
        assert TemplateLock.from_yaml(target / ".rhiza" / "template.lock").config["sha"] == "newsha"
        assert TemplateLock.from_yaml(target / ".rhiza" / "template.lock").config["sha"] == "newsha"

    @patch("rhiza.models._git_utils.GitContext._apply_diff")
    @patch("rhiza.models._git_utils.GitContext.get_diff")
    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.models._git_utils._prepare_snapshot")
    def test_merge_with_base_clean_apply(
        self, mock_prepare, mock_clone, mock_get_diff, mock_apply, tmp_path, git_project, git_ctx
    ):
        """When diff applies cleanly, success is logged."""
        mock_get_diff.return_value = (
            "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"
        )
        mock_apply.return_value = True  # clean merge

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()

        result = git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["file.txt"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        assert result is True
        mock_apply.assert_called_once()

    @patch("rhiza.models._git_utils.GitContext._apply_diff")
    @patch("rhiza.models._git_utils.GitContext.get_diff")
    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.models._git_utils._prepare_snapshot")
    def test_merge_with_base_conflict_returns_false(
        self, mock_prepare, mock_clone, mock_get_diff, mock_apply, tmp_path, git_project, git_ctx
    ):
        """When diff has conflicts, _merge_with_base returns False."""
        mock_get_diff.return_value = (
            "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"
        )
        mock_apply.return_value = False  # conflict

        upstream_snapshot = tmp_path / "upstream"
        upstream_snapshot.mkdir()
        base_snapshot = tmp_path / "base"
        base_snapshot.mkdir()

        result = git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["file.txt"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        assert result is False
        mock_apply.assert_called_once()


# ===========================================================================
# Detailed 3-way merge tests
# ===========================================================================


class TestThreeWayMergeApplyDiff:
    """Detailed integration tests for the 3-way merge mechanism in _apply_diff.

    These tests use real git repositories and real diffs produced by
    ``get_diff(base_snapshot, upstream_snapshot)``, exercising the full
    ``git apply -3`` pipeline without network access.

    Scenarios covered:
    - Upstream modifies an existing file → clean apply
    - Upstream adds a completely new file
    - Upstream removes a file
    - Upstream modifies multiple files
    - Upstream renames content within a file (multiline context)
    - Conflicting changes → fallback to ``--reject``, returns False, .rej files created
    """

    def test_upstream_modifies_existing_file(self, tmp_path, git_project, git_ctx):
        """Upstream changes a line in a committed file → clean apply, file updated."""
        # Commit the 'base' content into the project
        (git_project / "Makefile").write_text("install:\n\techo old\n")
        _commit_all(git_project, git_ctx)

        # Snapshots: base identical to project, upstream has updated echo command
        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "Makefile").write_text("install:\n\techo old\n")
        (upstream / "Makefile").write_text("install:\n\techo new\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        assert "echo new" in (git_project / "Makefile").read_text()

    def test_upstream_adds_new_file(self, tmp_path, git_project, git_ctx):
        """Upstream introduces a file that didn't exist in the base → file created."""
        # Start with an existing committed file (needed so git repo has at least one commit)
        (git_project / "README.md").write_text("# Project\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        # base has no new_tool.yml; upstream adds it
        (upstream / "new_tool.yml").write_text("version: 1\nenabled: true\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        assert (git_project / "new_tool.yml").exists()
        assert "enabled: true" in (git_project / "new_tool.yml").read_text()

    def test_upstream_removes_a_file(self, tmp_path, git_project, git_ctx):
        """Upstream deletes a file that existed at base → file removed from project."""
        # Commit the file that will be deleted
        (git_project / "legacy_config.yml").write_text("old: setting\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "legacy_config.yml").write_text("old: setting\n")
        # upstream does NOT have the file → deletion diff

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        assert not (git_project / "legacy_config.yml").exists()

    def test_upstream_modifies_multiple_files(self, tmp_path, git_project, git_ctx):
        """Upstream updates several files in one diff → all are patched cleanly."""
        (git_project / "ci.yml").write_text("steps:\n  - run: test-v1\n")
        (git_project / "lint.yml").write_text("steps:\n  - run: lint-v1\n")
        (git_project / "release.yml").write_text("steps:\n  - run: release-v1\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        for f, old, new in [
            ("ci.yml", "test-v1", "test-v2"),
            ("lint.yml", "lint-v1", "lint-v2"),
            ("release.yml", "release-v1", "release-v2"),
        ]:
            (base / f).write_text(f"steps:\n  - run: {old}\n")
            (upstream / f).write_text(f"steps:\n  - run: {new}\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        assert "test-v2" in (git_project / "ci.yml").read_text()
        assert "lint-v2" in (git_project / "lint.yml").read_text()
        assert "release-v2" in (git_project / "release.yml").read_text()

    def test_upstream_adds_lines_to_end_of_file(self, tmp_path, git_project, git_ctx):
        """Upstream appends new make targets to an existing Makefile."""
        makefile_base = "install:\n\tpip install .\n"
        (git_project / "Makefile").write_text(makefile_base)
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "Makefile").write_text(makefile_base)
        (upstream / "Makefile").write_text(makefile_base + "\ntest:\n\tpytest\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        content = (git_project / "Makefile").read_text()
        assert "pip install" in content
        assert "pytest" in content

    def test_conflict_creates_rej_file_and_returns_false(self, tmp_path, git_project, git_ctx):
        """When local edits conflict with template update, .rej file is produced and logged by name."""
        from loguru import logger as _logger

        messages: list[str] = []
        handler_id = _logger.add(lambda msg: messages.append(msg), format="{message}", colorize=False)
        try:
            # Commit original
            (git_project / "settings.cfg").write_text("timeout = 30\n")
            _commit_all(git_project, git_ctx)

            # User makes a local change to the SAME line
            (git_project / "settings.cfg").write_text("timeout = 99\n")

            # Template also changes the same line to a different value
            base = tmp_path / "base"
            base.mkdir()
            upstream = tmp_path / "upstream"
            upstream.mkdir()
            (base / "settings.cfg").write_text("timeout = 30\n")
            (upstream / "settings.cfg").write_text("timeout = 60\n")

            diff = git_ctx.get_diff(base, upstream)
            result = git_ctx._apply_diff(diff, git_project)
        finally:
            _logger.remove(handler_id)

        # Apply cannot succeed — local file diverged from the context
        assert result is False
        # The .rej file should exist, marking the conflict
        assert (git_project / "settings.cfg.rej").exists()
        # Warning must name the specific file rather than just saying "check *.rej files"
        combined = " ".join(messages)
        assert "settings.cfg" in combined

    def test_upstream_mixed_add_modify_delete(self, tmp_path, git_project, git_ctx):
        """Upstream adds one file, modifies another, removes a third — all in one diff."""
        (git_project / "kept.yml").write_text("version: 1\n")
        (git_project / "gone.yml").write_text("deprecated: true\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()

        # kept.yml is modified; gone.yml is removed; new.yml is added
        (base / "kept.yml").write_text("version: 1\n")
        (base / "gone.yml").write_text("deprecated: true\n")
        (upstream / "kept.yml").write_text("version: 2\n")
        (upstream / "new.yml").write_text("feature: true\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project)

        assert result is True
        assert "version: 2" in (git_project / "kept.yml").read_text()
        assert not (git_project / "gone.yml").exists()
        assert (git_project / "new.yml").exists()
        assert "feature: true" in (git_project / "new.yml").read_text()


class TestMergeFileFallback:
    """Tests for _parse_diff_filenames and _merge_file_fallback / _apply_diff merge-file path.

    These tests verify the fallback path that activates when ``git apply -3``
    reports "lacks the necessary blob" — i.e. the template's blob objects are
    absent from the target repo's object store.  The fallback uses
    ``git merge-file`` on the on-disk snapshot files, which requires no shared
    git history.

    Scenarios covered:
    - _parse_diff_filenames extracts (path, is_new, is_deleted) correctly
    - Non-overlapping diverged changes merge cleanly (no conflict)
    - Overlapping changes produce conflict markers and return False
    - New-file entries are copied from upstream
    - Deleted-file entries are removed from target
    - _apply_diff routes to merge-file when snapshots are provided and blob is absent
    """

    # ------------------------------------------------------------------
    # _parse_diff_filenames unit tests
    # ------------------------------------------------------------------

    def test_parse_diff_filenames_modified(self, tmp_path, git_setup):
        """Detects a modified file correctly."""
        git_executable, git_env = git_setup
        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "ci.yml").write_text("version: 1\n")
        (upstream / "ci.yml").write_text("version: 2\n")

        diff = GitContext(executable=git_executable, env=git_env).get_diff(base, upstream)
        ctx = GitContext(executable=git_executable, env=git_env)
        entries = ctx._parse_diff_filenames(diff)

        assert len(entries) == 1
        rel_path, is_new, is_deleted = entries[0]
        assert rel_path == "ci.yml"
        assert not is_new
        assert not is_deleted

    def test_parse_diff_filenames_new_file(self, tmp_path, git_setup):
        """Detects a file added by upstream."""
        git_executable, git_env = git_setup
        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "added.yml").write_text("new: true\n")

        diff = GitContext(executable=git_executable, env=git_env).get_diff(base, upstream)
        ctx = GitContext(executable=git_executable, env=git_env)
        entries = ctx._parse_diff_filenames(diff)

        assert len(entries) == 1
        rel_path, is_new, is_deleted = entries[0]
        assert rel_path == "added.yml"
        assert is_new
        assert not is_deleted

    def test_parse_diff_filenames_deleted_file(self, tmp_path, git_setup):
        """Detects a file removed by upstream."""
        git_executable, git_env = git_setup
        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "gone.yml").write_text("old: true\n")

        diff = GitContext(executable=git_executable, env=git_env).get_diff(base, upstream)
        ctx = GitContext(executable=git_executable, env=git_env)
        entries = ctx._parse_diff_filenames(diff)

        assert len(entries) == 1
        rel_path, is_new, is_deleted = entries[0]
        assert rel_path == "gone.yml"
        assert not is_new
        assert is_deleted

    def test_parse_diff_filenames_mixed(self, tmp_path, git_setup):
        """Handles a diff with add, modify, and delete in one pass."""
        git_executable, git_env = git_setup
        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "keep.yml").write_text("v: 1\n")
        (base / "drop.yml").write_text("old: yes\n")
        (upstream / "keep.yml").write_text("v: 2\n")
        (upstream / "new.yml").write_text("fresh: yes\n")

        diff = GitContext(executable=git_executable, env=git_env).get_diff(base, upstream)
        ctx = GitContext(executable=git_executable, env=git_env)
        entries = ctx._parse_diff_filenames(diff)

        paths = {e[0]: e for e in entries}
        assert paths["keep.yml"] == ("keep.yml", False, False)
        assert paths["drop.yml"] == ("drop.yml", False, True)
        assert paths["new.yml"] == ("new.yml", True, False)

    # ------------------------------------------------------------------
    # _merge_file_fallback integration tests
    # ------------------------------------------------------------------

    def test_non_overlapping_divergence_merges_cleanly(self, tmp_path, git_project, git_ctx):
        """Non-overlapping local and template changes both survive the merge.

        Simulates the real-world case where Renovate bumped tool versions
        locally while the template also changed an unrelated distant line —
        the scenario that was causing the CI failure with 'lacks blob' errors.

        The file must be large enough that the two changed sections are in
        separate diff hunks; otherwise git merge-file treats them as a conflict.
        """
        # A realistic workflow file — local changes are in the install step
        # (near the top) while the template change is in the upload step
        # (near the bottom), separated by many context lines.
        base_content = (
            "name: CI\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Install uv\n"
            "        uses: astral-sh/setup-uv@v7\n"
            "        with:\n"
            "          version: '0.10'\n"
            "      - name: Build\n"
            "        run: make build\n"
            "      - name: Test\n"
            "        run: make test\n"
            "      - name: Lint\n"
            "        run: make lint\n"
            "      - name: Type-check\n"
            "        run: make typecheck\n"
            "      - name: Upload\n"
            "        uses: actions/upload-artifact@v3\n"
            "        with:\n"
            "          name: dist\n"
            "          path: dist\n"
        )
        # Local: Renovate bumped setup-uv (near top of file)
        local_content = base_content.replace("setup-uv@v7", "setup-uv@v8").replace("'0.10'", "'0.12'")
        # Template: bumped upload-artifact (near bottom of file — different hunk)
        upstream_content = base_content.replace("upload-artifact@v3", "upload-artifact@v4")

        (git_project / "ci.yml").write_text(base_content)
        _commit_all(git_project, git_ctx)

        # Diverge the local file (Renovate bump, not committed)
        (git_project / "ci.yml").write_text(local_content)

        base = tmp_path / "base"
        base.mkdir()
        (base / "ci.yml").write_text(base_content)

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "ci.yml").write_text(upstream_content)

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._merge_file_fallback(diff, git_project, base, upstream)

        assert result is True
        content = (git_project / "ci.yml").read_text()
        # Local Renovate bumps are preserved
        assert "setup-uv@v8" in content
        assert "'0.12'" in content
        # Template's upload-artifact bump is applied
        assert "upload-artifact@v4" in content

    def test_overlapping_changes_leave_conflict_markers(self, tmp_path, git_project, git_ctx):
        """Overlapping edits produce conflict markers and return False."""
        (git_project / "settings.cfg").write_text("timeout = 30\n")
        _commit_all(git_project, git_ctx)

        # Local changed timeout to 99; template changes it to 60
        (git_project / "settings.cfg").write_text("timeout = 99\n")

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "settings.cfg").write_text("timeout = 30\n")
        (upstream / "settings.cfg").write_text("timeout = 60\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._merge_file_fallback(diff, git_project, base, upstream)

        assert result is False
        content = (git_project / "settings.cfg").read_text()
        assert "<<<<<<<" in content
        assert "timeout = 99" in content
        assert "timeout = 60" in content

    def test_new_file_is_copied_from_upstream(self, tmp_path, git_project, git_ctx):
        """Files added by the template are created in the target."""
        (git_project / "README.md").write_text("# hi\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "new_workflow.yml").write_text("name: deploy\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._merge_file_fallback(diff, git_project, base, upstream)

        assert result is True
        assert (git_project / "new_workflow.yml").exists()
        assert "deploy" in (git_project / "new_workflow.yml").read_text()

    def test_deleted_file_is_removed_from_target(self, tmp_path, git_project, git_ctx):
        """Files removed from the template are deleted in the target."""
        (git_project / "legacy.cfg").write_text("old: setting\n")
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "legacy.cfg").write_text("old: setting\n")

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._merge_file_fallback(diff, git_project, base, upstream)

        assert result is True
        assert not (git_project / "legacy.cfg").exists()

    # ------------------------------------------------------------------
    # _apply_diff routing test
    # ------------------------------------------------------------------

    def test_apply_diff_routes_to_merge_file_when_blob_absent(self, tmp_path, git_project, git_ctx):
        """_apply_diff uses git merge-file when git apply -3 reports 'lacks blob'.

        ``git apply -3`` produces "lacks the necessary blob" when the patch's
        index blob hash is absent from the target repo — which is always the
        case for diffs produced by ``_get_diff`` (temp-dir blobs).  If the
        context also doesn't match (because the file diverged), git cannot
        apply the patch at all.  With snapshots provided, ``_apply_diff`` must
        route to ``_merge_file_fallback`` instead of ``--reject``.

        We commit the diverged content so that the working tree matches the
        index and git apply -3 actually reaches the blob lookup stage.
        """
        base_content = (
            "name: CI\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Install uv\n"
            "        uses: astral-sh/setup-uv@v7\n"
            "        with:\n"
            "          version: '0.10'\n"
            "      - name: Build\n"
            "        run: make build\n"
            "      - name: Test\n"
            "        run: make test\n"
            "      - name: Lint\n"
            "        run: make lint\n"
            "      - name: Type-check\n"
            "        run: make typecheck\n"
            "      - name: Upload\n"
            "        uses: actions/upload-artifact@v3\n"
            "        with:\n"
            "          name: dist\n"
            "          path: dist\n"
        )
        # Local (committed): Renovate bumped setup-uv (near top)
        local_content = base_content.replace("setup-uv@v7", "setup-uv@v8").replace("'0.10'", "'0.12'")
        # Template: bumped upload-artifact (near bottom — separate hunk)
        upstream_content = base_content.replace("upload-artifact@v3", "upload-artifact@v4")

        # Commit the DIVERGED local content so git apply -3 can reach the blob lookup
        (git_project / "ci.yml").write_text(local_content)
        _commit_all(git_project, git_ctx)

        base = tmp_path / "base"
        base.mkdir()
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (base / "ci.yml").write_text(base_content)
        (upstream / "ci.yml").write_text(upstream_content)

        diff = git_ctx.get_diff(base, upstream)
        result = git_ctx._apply_diff(diff, git_project, base_snapshot=base, upstream_snapshot=upstream)

        assert result is True
        content = (git_project / "ci.yml").read_text()
        # Local Renovate bumps are preserved by merge-file
        assert "setup-uv@v8" in content
        assert "'0.12'" in content
        # Template's upload-artifact bump is applied
        assert "upload-artifact@v4" in content


class TestThreeWayMergeWithBase:
    """End-to-end tests for the _merge_with_base function.

    These tests exercise the complete merge pipeline:
    ``_merge_with_base`` → ``get_diff`` → ``_apply_diff`` (``git apply -3``).
    ``clone_at_sha`` is mocked to avoid network access; all other logic
    runs against real files and a real git repository.
    """

    def _populate_base_snapshot_from_clone(self, base_clone, include_paths, excludes, base_snapshot):
        """Helper to prepare a base snapshot without a real git clone."""
        from rhiza.models._git_utils import _prepare_snapshot

        _prepare_snapshot(base_clone, include_paths, excludes, base_snapshot)

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    def test_merge_applies_upstream_changes(self, mock_clone, tmp_path, git_project, git_ctx):
        """_merge_with_base applies diff(base→upstream) to the target cleanly."""
        # Commit base content in target
        (git_project / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
        (git_project / "Makefile").write_text("test:\n\tpytest\n")
        _commit_all(git_project, git_ctx)

        # base_snapshot == what was present at last sync
        base_snapshot = tmp_path / "base_snapshot"
        base_snapshot.mkdir()
        (base_snapshot / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
        (base_snapshot / "Makefile").write_text("test:\n\tpytest\n")

        # upstream_snapshot == current template HEAD (bumped version, added lint target)
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "0.2.0"\n')
        (upstream_snapshot / "Makefile").write_text("test:\n\tpytest\n\nlint:\n\truff check .\n")

        def populate_base_clone(git_url, sha, dest, include_paths):
            # Populate the clone directory so _prepare_snapshot can copy files
            (dest / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
            (dest / "Makefile").write_text("test:\n\tpytest\n")

        mock_clone.side_effect = populate_base_clone

        git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["pyproject.toml", "Makefile"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        pyproject = (git_project / "pyproject.toml").read_text()
        makefile = (git_project / "Makefile").read_text()
        assert 'version = "0.2.0"' in pyproject, "version should be bumped"
        assert "ruff check" in makefile, "lint target should be added"

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    def test_merge_no_changes_updates_lock_only(self, mock_clone, tmp_path, git_project, git_ctx):
        """When base and upstream are identical, no files are modified but lock is updated."""
        (git_project / "ci.yml").write_text("on: push\n")
        _commit_all(git_project, git_ctx)
        (git_project / ".rhiza").mkdir(exist_ok=True)

        identical_content = "on: push\n"
        base_snapshot = tmp_path / "base_snapshot"
        base_snapshot.mkdir()
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (base_snapshot / "ci.yml").write_text(identical_content)
        (upstream_snapshot / "ci.yml").write_text(identical_content)

        def populate_base_clone(git_url, sha, dest, include_paths):
            (dest / "ci.yml").write_text(identical_content)

        mock_clone.side_effect = populate_base_clone

        git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "upstream_sha_abc",
            "base_sha_xyz",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["ci.yml"]),
            set(),
            TemplateLock(sha="upstream_sha_abc"),
        )

        # File must be unchanged
        assert (git_project / "ci.yml").read_text() == identical_content
        # Lock should be updated to upstream SHA
        assert TemplateLock.from_yaml(git_project / ".rhiza" / "template.lock").config["sha"] == "upstream_sha_abc"

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    def test_merge_upstream_adds_new_file(self, mock_clone, tmp_path, git_project, git_ctx):
        """_merge_with_base handles upstream adding a file that wasn't in base."""
        (git_project / "existing.yml").write_text("key: value\n")
        _commit_all(git_project, git_ctx)

        base_snapshot = tmp_path / "base_snapshot"
        base_snapshot.mkdir()
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (base_snapshot / "existing.yml").write_text("key: value\n")
        (upstream_snapshot / "existing.yml").write_text("key: value\n")
        (upstream_snapshot / "new_workflow.yml").write_text("name: deploy\n")

        def populate_base_clone(git_url, sha, dest, include_paths):
            (dest / "existing.yml").write_text("key: value\n")

        mock_clone.side_effect = populate_base_clone

        git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["existing.yml"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        assert (git_project / "new_workflow.yml").exists()
        assert "deploy" in (git_project / "new_workflow.yml").read_text()

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    def test_merge_upstream_removes_file(self, mock_clone, tmp_path, git_project, git_ctx):
        """_merge_with_base handles upstream removing a file from the template."""
        (git_project / "legacy.cfg").write_text("old: setting\n")
        (git_project / "main.cfg").write_text("current: setting\n")
        _commit_all(git_project, git_ctx)

        base_snapshot = tmp_path / "base_snapshot"
        base_snapshot.mkdir()
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (base_snapshot / "legacy.cfg").write_text("old: setting\n")
        (base_snapshot / "main.cfg").write_text("current: setting\n")
        # upstream removes legacy.cfg entirely
        (upstream_snapshot / "main.cfg").write_text("current: setting\n")

        def populate_base_clone(git_url, sha, dest, include_paths):
            (dest / "legacy.cfg").write_text("old: setting\n")
            (dest / "main.cfg").write_text("current: setting\n")

        mock_clone.side_effect = populate_base_clone

        git_ctx._merge_with_base(
            git_project,
            upstream_snapshot,
            "newsha",
            "oldsha",
            base_snapshot,
            RhizaTemplate(template_repository="example/repo", include=["legacy.cfg", "main.cfg"]),
            set(),
            TemplateLock(sha="newsha"),
        )

        assert not (git_project / "legacy.cfg").exists(), "legacy.cfg should be deleted"
        assert (git_project / "main.cfg").exists(), "main.cfg should remain"


class TestThreeWayMergeSyncMergeStrategy:
    """Integration tests for ``_sync_merge`` end-to-end (the merge strategy entry point).

    Tests the full merge pipeline from first-sync to subsequent-sync, verifying
    that lock files, history files, and orphan cleanup all work correctly
    alongside the 3-way merge.
    """

    @pytest.fixture
    def project_with_template(self, git_project, git_setup):
        """Set up a target project with a valid template.yml."""
        git_executable, git_env = git_setup
        project = git_project
        (project / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
        rhiza = project / ".rhiza"
        rhiza.mkdir()
        with open(rhiza / "template.yml", "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": ["Makefile"],
                },
                f,
            )
        subprocess.run([git_executable, "add", "."], cwd=project, check=True, capture_output=True, env=git_env)  # nosec B603
        subprocess.run(  # nosec B603
            [git_executable, "commit", "-m", "init"],
            cwd=project,
            check=True,
            capture_output=True,
            env=git_env,
        )
        return project

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_sync_merge_subsequent_applies_diff(
        self,
        mock_warn,
        mock_clone,
        tmp_path,
        project_with_template,
        git_ctx,
    ):
        """On a subsequent sync (lock exists), the diff is applied via 3-way merge."""
        target = project_with_template

        # Commit a file that matches what was in the last sync
        makefile_v1 = "install:\n\tpip install .\n"
        (target / "Makefile").write_text(makefile_v1)
        _commit_all(target, git_ctx)

        # Write a lock indicating we last synced at "base_sha"
        _write_lock(target, TemplateLock(sha="base_sha_123"))

        # Create fake upstream snapshot (what the template looks like now)
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "Makefile").write_text(makefile_v1 + "\ntest:\n\tpytest\n")

        # base_snapshot is populated by the mock_clone side_effect
        def populate_base(git_url, sha, dest, include_paths):
            (dest / "Makefile").write_text(makefile_v1)

        mock_clone.side_effect = populate_base

        git_ctx.sync_merge(
            target=target,
            upstream_snapshot=upstream_snapshot,
            upstream_sha="upstream_sha_456",
            base_sha="base_sha_123",
            materialized=[Path("Makefile")],
            template=RhizaTemplate(template_repository="example/repo", include=["Makefile"]),
            excludes=set(),
            lock=TemplateLock(sha="upstream_sha_456"),
        )

        content = (target / "Makefile").read_text()
        assert "pip install" in content, "original content should be preserved"
        assert "pytest" in content, "upstream addition should be applied"
        # Lock file should be updated
        assert TemplateLock.from_yaml(target / ".rhiza" / "template.lock").config["sha"] == "upstream_sha_456"

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_sync_merge_first_run_copies_without_merge(
        self,
        mock_warn,
        mock_clone,
        tmp_path,
        project_with_template,
        git_ctx,
    ):
        """On first sync (no lock), files are copied directly without diff/merge."""
        target = project_with_template

        # No lock file → first sync
        assert not (target / ".rhiza" / "template.lock").exists()

        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "Makefile").write_text("install:\n\tpip install .\n")

        git_ctx.sync_merge(
            target=target,
            upstream_snapshot=upstream_snapshot,
            upstream_sha="first_sha_abc",
            base_sha=None,
            materialized=[Path("Makefile")],
            template=RhizaTemplate(template_repository="example/repo", include=["Makefile"]),
            excludes=set(),
            lock=TemplateLock(sha="first_sha_abc"),
        )

        assert (target / "Makefile").exists()
        assert "pip install" in (target / "Makefile").read_text()
        assert TemplateLock.from_yaml(target / ".rhiza" / "template.lock").config["sha"] == "first_sha_abc"
        # clone_at_sha should NOT have been called (no base to clone)
        mock_clone.assert_not_called()

    @patch("rhiza.models._git_utils.GitContext.clone_at_sha")
    @patch("rhiza.commands._sync_helpers._warn_about_workflow_files")
    def test_sync_merge_restores_files_missing_from_target(
        self,
        mock_warn,
        mock_clone,
        tmp_path,
        project_with_template,
        git_ctx,
    ):
        """Files in materialized but absent from target are restored after merge.

        This covers the scenario where the template snapshot is unchanged since
        the last sync (no diff to apply) but some template-managed files do not
        exist in the target repository.
        They should be copied from the upstream snapshot, not silently excluded
        from the lock.
        """
        target = project_with_template

        makefile_content = "install:\n\tpip install .\n"
        license_content = "MIT License\n"

        # Only Makefile exists in the target; LICENSE is missing.
        (target / "Makefile").write_text(makefile_content)
        _commit_all(target, git_ctx)

        _write_lock(target, TemplateLock(sha="base_sha_123", files=["Makefile", "LICENSE"]))

        # Upstream snapshot contains both files (template unchanged).
        upstream_snapshot = tmp_path / "upstream_snapshot"
        upstream_snapshot.mkdir()
        (upstream_snapshot / "Makefile").write_text(makefile_content)
        (upstream_snapshot / "LICENSE").write_text(license_content)

        # The base clone will also contain both files (no diff → nothing to apply).
        def populate_base(git_url, sha, dest, include_paths):
            (dest / "Makefile").write_text(makefile_content)
            (dest / "LICENSE").write_text(license_content)

        mock_clone.side_effect = populate_base

        git_ctx.sync_merge(
            target=target,
            upstream_snapshot=upstream_snapshot,
            upstream_sha="upstream_sha_456",
            base_sha="base_sha_123",
            materialized=[Path("Makefile"), Path("LICENSE")],
            template=RhizaTemplate(template_repository="example/repo", include=["Makefile", "LICENSE"]),
            excludes=set(),
            lock=TemplateLock(sha="upstream_sha_456", files=["Makefile", "LICENSE"]),
        )

        # LICENSE was missing from the target but should now be restored.
        assert (target / "LICENSE").exists(), "LICENSE should have been restored from upstream snapshot"
        assert (target / "LICENSE").read_text() == license_content
        # Makefile should be untouched.
        assert (target / "Makefile").read_text() == makefile_content
        # Lock must record both files.
        lock_path = target / ".rhiza" / "template.lock"
        lock_data = yaml.safe_load(lock_path.read_text())
        assert "LICENSE" in lock_data["files"], "LICENSE must appear in the lock after restore"


class TestHandleTargetBranch:
    """Tests for git_ctx.handle_target_branch."""

    def test_no_branch_is_noop(self, tmp_path, git_ctx):
        """Passing None for target_branch should not call git."""
        with patch("rhiza.models._git_utils.subprocess.run") as mock_run:
            git_ctx.handle_target_branch(tmp_path, None)
        mock_run.assert_not_called()

    def test_creates_new_branch(self, tmp_path, git_ctx):
        """When the branch does not exist, ``checkout -b`` is called."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            result = Mock()
            if "rev-parse" in cmd:
                result.returncode = 1  # branch not found
            else:
                result.returncode = 0
            return result

        with patch("rhiza.models._git_utils.subprocess.run", side_effect=_side_effect) as mock_run:
            git_ctx.handle_target_branch(tmp_path, "new-branch")

        calls = [str(c) for c in mock_run.call_args_list]
        assert any("checkout" in c and "-b" in c for c in calls)

    def test_checks_out_existing_branch(self, tmp_path, git_ctx):
        """When the branch already exists, a plain ``checkout`` is called."""

        def _side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0  # branch found
            return result

        with patch("rhiza.models._git_utils.subprocess.run", side_effect=_side_effect) as mock_run:
            git_ctx.handle_target_branch(tmp_path, "existing-branch")

        calls = [str(c) for c in mock_run.call_args_list]
        assert any("checkout" in c and "existing-branch" in c for c in calls)

    def test_checkout_failure_propagates(self, tmp_path, git_ctx):
        """A CalledProcessError during checkout is re-raised."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "rev-parse" in cmd:
                r = Mock()
                r.returncode = 0
                return r
            raise subprocess.CalledProcessError(1, cmd, stderr="error: conflict")

        with pytest.raises(subprocess.CalledProcessError):
            git_ctx.handle_target_branch(tmp_path, "bad-branch")


class TestWarnAboutWorkflowFiles:
    """Tests for _warn_about_workflow_files."""

    def test_no_warning_without_workflow_files(self):
        """No warning is emitted when there are no workflow files."""
        with patch("rhiza.commands._sync_helpers.logger") as mock_logger:
            _warn_about_workflow_files([Path("Makefile"), Path(".github/CODEOWNERS")])
        mock_logger.warning.assert_not_called()

    def test_warning_with_workflow_files(self):
        """A warning is emitted when workflow files are present."""
        with patch("rhiza.commands._sync_helpers.logger") as mock_logger:
            _warn_about_workflow_files([Path(".github/workflows/ci.yml")])
        mock_logger.warning.assert_called_once()
        assert "workflow" in mock_logger.warning.call_args[0][0].lower()


class TestCloneTemplateRepository:
    """Tests for GitContext.clone_repository error handling.

    Note: clone_repository is now an instance method on GitContext.
    These tests verify error handling through subprocess patching.
    """

    def test_clone_failure_logs_and_reraises(self, tmp_path, git_ctx):
        """A clone failure logs the error and re-raises the exception."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "clone" in cmd:
                raise subprocess.CalledProcessError(128, cmd, stderr="fatal: repository not found")
            return Mock(returncode=0)

        with (
            patch("rhiza.models._git_utils.subprocess.run", side_effect=_side_effect),
            pytest.raises(subprocess.CalledProcessError),
        ):
            git_ctx.clone_repository("https://github.com/bad/repo.git", tmp_path, "main", [".github"])

    @pytest.mark.parametrize(
        "fail_at",
        [
            pytest.param(0, id="clone fails"),
            pytest.param(1, id="sparse-checkout init fails"),
            pytest.param(2, id="sparse-checkout set fails"),
        ],
    )
    def test_subprocess_failure_reraises(self, tmp_path, git_ctx, fail_at):
        """Any subprocess failure in clone_repository re-raises CalledProcessError."""
        ok = MagicMock(returncode=0, stdout="", stderr="")
        err = subprocess.CalledProcessError(1, ["git"])
        err.stderr = "error"
        with (
            patch("rhiza.models._git_utils.subprocess.run", side_effect=[ok] * fail_at + [err]),
            pytest.raises(subprocess.CalledProcessError),
        ):
            git_ctx.clone_repository("https://github.com/example/repo.git", tmp_path, "main", [".github"])


class TestLogGitStderrErrors:
    """Tests for _log_git_stderr_errors."""

    @pytest.mark.parametrize(
        ("stderr", "expected_calls"),
        [
            ("fatal: repository not found\nHint: some hint", ["fatal: repository not found"]),
            ("error: pathspec 'bad' did not match", ["error: pathspec 'bad' did not match"]),
            (None, []),
            ("Hint: some helpful hint\nremote: counting objects", []),
        ],
    )
    def test_stderr_logging(self, stderr, expected_calls):
        """Appropriate lines are logged as errors; irrelevant lines and None are ignored."""
        with patch("rhiza.models._git_utils.logger") as mock_logger:
            _log_git_stderr_errors(stderr)
        assert mock_logger.error.call_count == len(expected_calls)
        for expected in expected_calls:
            mock_logger.error.assert_any_call(expected)


class TestCleanOrphanedFiles:
    """Tests for _clean_orphaned_files and _read_previously_tracked_files."""

    def test_no_cleanup_when_no_lock(self, tmp_path):
        """No files are deleted when there is no previous tracking info."""
        _clean_orphaned_files(tmp_path, [Path("Makefile")])
        # Should complete without error and delete nothing

    def test_deletes_orphaned_files(self, tmp_path):
        """Files in the lock but not in materialized are deleted."""
        # Create a file that was previously tracked
        old_file = tmp_path / "old-file.txt"
        old_file.write_text("old content")

        # Write a lock file referencing the old file
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [".github"],
            "exclude": [],
            "templates": [],
            "files": ["old-file.txt"],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        _clean_orphaned_files(tmp_path, [Path("Makefile")])

        assert not old_file.exists(), "orphaned file should have been deleted"

    def test_protected_files_not_deleted(self, tmp_path):
        """template.yml is never deleted even if it appears orphaned."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_yml = rhiza_dir / "template.yml"
        template_yml.write_text("template-repository: owner/repo\n")

        lock_data = {
            "sha": "abc123",
            "repo": "owner/repo",
            "host": "github",
            "ref": "main",
            "include": [".github"],
            "exclude": [],
            "templates": [],
            "files": [".rhiza/template.yml"],
        }
        (rhiza_dir / "template.lock").write_text(yaml.dump(lock_data))

        _clean_orphaned_files(tmp_path, [])

        assert template_yml.exists(), ".rhiza/template.yml must never be auto-deleted"

    def test_read_previously_tracked_files_legacy_history(self, tmp_path):
        """Falls back to .rhiza/history when no template.lock files list."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        (rhiza_dir / "history").write_text("Makefile\n.github/workflows/ci.yml\n# comment\n")

        files = _read_previously_tracked_files(tmp_path)
        assert Path("Makefile") in files
        assert Path(".github/workflows/ci.yml") in files

    def test_skips_nonexistent_file(self, tmp_path):
        """When file does not exist, a debug message is logged and nothing raises."""
        # file_path points to a file that does NOT exist in target
        _delete_orphaned_file(tmp_path, Path("nonexistent_file.txt"))
        # No exception means success

    def test_deletion_exception_is_caught(self, tmp_path):
        """Exception during unlink is caught and logged."""
        file_path = Path("orphan.txt")
        full_path = tmp_path / file_path
        full_path.write_text("content")

        with patch.object(Path, "unlink", side_effect=PermissionError("cannot delete")):
            # Should not raise - exception is caught
            _delete_orphaned_file(tmp_path, file_path)

    def test_no_orphaned_files_returns_early(self, tmp_path):
        """When all tracked files are still materialized, no deletions happen."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        history_file = rhiza_dir / "history"
        history_file.write_text("file_a.txt\nfile_b.txt\n")

        # All tracked files are also in materialized_files → no orphans
        materialized = [Path("file_a.txt"), Path("file_b.txt")]

        # Should not raise or delete anything
        _clean_orphaned_files(tmp_path, materialized)

    def test_returns_files_from_template_lock(self, tmp_path):
        """Files listed in template.lock are returned."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        lock_file = rhiza_dir / "template.lock"
        lock_file.write_text("sha: abc123\nrepo: owner/repo\nfiles:\n  - Makefile\n  - .github/workflows/ci.yml\n")

        files = _read_previously_tracked_files(tmp_path)

        assert Path("Makefile") in files
        assert Path(".github/workflows/ci.yml") in files
        assert len(files) == 2

    def test_falls_back_to_history_when_lock_raises(self, tmp_path):
        """When template.lock is unreadable, falls back to history file."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)

        # Write a lock file so lock_file.exists() is True
        lock_file = rhiza_dir / "template.lock"
        lock_file.write_text("sha: abc\n")

        # Write a history file as fallback
        history_file = rhiza_dir / "history"
        history_file.write_text("Makefile\n")

        # Force TemplateLock.from_yaml to raise
        with patch("rhiza.commands._sync_helpers.TemplateLock.from_yaml", side_effect=Exception("corrupt lock")):
            files = _read_previously_tracked_files(tmp_path)

        assert Path("Makefile") in files


class TestFilesFromSnapshot:
    """Tests for _files_from_snapshot."""

    def test_returns_files_relative_to_snapshot(self, tmp_path):
        """Files are returned relative to the snapshot root."""
        (tmp_path / "Makefile").write_text("all:")
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".github" / "workflows" / "ci.yml").write_text("on: push")

        files = _files_from_snapshot(tmp_path)

        assert all(isinstance(f, Path) for f in files), "all entries must be Path objects"
        assert Path("Makefile") in files
        assert Path(".github/workflows/ci.yml") in files
        assert len(files) == 2

    def test_empty_snapshot_returns_empty_set(self, tmp_path):
        """An empty snapshot directory returns an empty set."""
        files = _files_from_snapshot(tmp_path)
        assert files == set()


class TestReadPreviouslyTrackedFilesWithBaseSnapshot:
    """Tests for _read_previously_tracked_files with base_snapshot fallback."""

    def test_uses_base_snapshot_when_lock_has_no_files(self, tmp_path):
        """Falls back to base_snapshot when lock exists but has no files."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        # Lock file without files
        (rhiza_dir / "template.lock").write_text(
            "sha: abc123\nrepo: owner/repo\nhost: github\nref: main\ninclude: []\nexclude: []\ntemplates: []\n",
        )

        base_snapshot = tmp_path / "snapshot"
        base_snapshot.mkdir()
        (base_snapshot / "Makefile").write_text("all:")
        (base_snapshot / ".github").mkdir()
        (base_snapshot / ".github" / "ci.yml").write_text("on: push")

        files = _read_previously_tracked_files(tmp_path, base_snapshot=base_snapshot)

        assert Path("Makefile") in files
        assert Path(".github/ci.yml") in files

    def test_lock_files_take_priority_over_base_snapshot(self, tmp_path):
        """Lock files field takes priority over base_snapshot."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        (rhiza_dir / "template.lock").write_text(
            "sha: abc123\nrepo: owner/repo\nfiles:\n  - from-lock.txt\n",
        )

        base_snapshot = tmp_path / "snapshot"
        base_snapshot.mkdir()
        (base_snapshot / "from-snapshot.txt").write_text("ignored")

        files = _read_previously_tracked_files(tmp_path, base_snapshot=base_snapshot)

        assert Path("from-lock.txt") in files
        assert Path("from-snapshot.txt") not in files

    def test_ignores_empty_base_snapshot(self, tmp_path):
        """An empty base_snapshot does not override fallback to history."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        (rhiza_dir / "template.lock").write_text(
            "sha: abc123\nrepo: owner/repo\nhost: github\nref: main\n",
        )
        (rhiza_dir / "history").write_text("from-history.txt\n")

        empty_snapshot = tmp_path / "empty_snapshot"
        empty_snapshot.mkdir()

        files = _read_previously_tracked_files(tmp_path, base_snapshot=empty_snapshot)

        assert Path("from-history.txt") in files

    def test_clean_orphaned_files_passes_base_snapshot_through(self, tmp_path):
        """_clean_orphaned_files passes base_snapshot to _read_previously_tracked_files."""
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        # Lock without files
        (rhiza_dir / "template.lock").write_text(
            "sha: abc123\nrepo: owner/repo\nhost: github\nref: main\ninclude: []\nexclude: []\ntemplates: []\n",
        )

        # Create the "previously tracked" file on disk so orphan deletion can happen
        old_file = tmp_path / "old-template-file.txt"
        old_file.write_text("old content")

        # base_snapshot contains the previously tracked file
        base_snapshot = tmp_path / "snapshot"
        base_snapshot.mkdir()
        (base_snapshot / "old-template-file.txt").write_text("old content")

        # Materialize does NOT include old-template-file.txt → it's an orphan
        _clean_orphaned_files(tmp_path, [Path("Makefile")], base_snapshot=base_snapshot)

        assert not old_file.exists(), "orphaned file should have been deleted via base_snapshot reconstruction"


class TestMergeFileFallbackEdgeCases:
    """Tests for edge cases in _merge_file_fallback."""

    def _make_diff(self, filename: str) -> str:
        """Make a minimal 'modified file' diff string for the given filename."""
        return (
            f"diff --git upstream-template-old/{filename} upstream-template-new/{filename}\n"
            f"--- upstream-template-old/{filename}\n"
            f"+++ upstream-template-new/{filename}\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )

    def test_missing_target_file_copied_from_upstream(self, tmp_path, git_ctx):
        """Modified file missing from target is copied from upstream."""
        diff = self._make_diff("file.txt")

        base = tmp_path / "base"
        base.mkdir()
        (base / "file.txt").write_text("old\n")

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "file.txt").write_text("new\n")

        target = tmp_path / "target"
        target.mkdir()
        # file.txt does NOT exist in target

        result = git_ctx._merge_file_fallback(diff, target, base, upstream)

        assert result is True
        assert (target / "file.txt").read_text() == "new\n"

    def test_missing_base_file_overwrites_with_upstream(self, tmp_path, git_ctx):
        """When base file is missing, target is overwritten with upstream."""
        diff = self._make_diff("file.txt")

        base = tmp_path / "base"
        base.mkdir()
        # base/file.txt does NOT exist

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "file.txt").write_text("new\n")

        target = tmp_path / "target"
        target.mkdir()
        (target / "file.txt").write_text("local\n")

        result = git_ctx._merge_file_fallback(diff, target, base, upstream)

        assert result is True
        assert (target / "file.txt").read_text() == "new\n"

    def test_negative_returncode_from_merge_file(self, tmp_path, git_ctx):
        """Negative returncode from git merge-file marks result as unclean."""
        diff = self._make_diff("file.txt")

        base = tmp_path / "base"
        base.mkdir()
        (base / "file.txt").write_text("old\n")

        upstream = tmp_path / "upstream"
        upstream.mkdir()
        (upstream / "file.txt").write_text("new\n")

        target = tmp_path / "target"
        target.mkdir()
        (target / "file.txt").write_text("local\n")

        mock_result = MagicMock()
        mock_result.returncode = -9  # killed by signal
        mock_result.stderr = b"process killed"

        with patch("rhiza.models._git_utils.subprocess.run", return_value=mock_result):
            result = git_ctx._merge_file_fallback(diff, target, base, upstream)

        assert result is False


class TestApplyDiffBlobFallback:
    """Tests for the blob-fallback path in _apply_diff."""

    @patch("rhiza.models._git_utils.GitContext._merge_file_fallback")
    def test_blob_fallback_triggered(self, mock_fallback, git_project, git_ctx):
        """When git apply -3 fails with 'lacks the necessary blob', _merge_file_fallback is used (909-910)."""
        mock_fallback.return_value = True

        diff = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"

        err = subprocess.CalledProcessError(1, ["git", "apply", "-3"])
        err.stderr = b"error: sha1 information is lacking or useless (file.txt). lacks the necessary blob"

        with patch("rhiza.models._git_utils.subprocess.run", side_effect=err):
            base_snapshot = git_project / "base"
            base_snapshot.mkdir()
            upstream_snapshot = git_project / "upstream"
            upstream_snapshot.mkdir()

            result = git_ctx._apply_diff(
                diff,
                git_project,
                base_snapshot=base_snapshot,
                upstream_snapshot=upstream_snapshot,
            )

        mock_fallback.assert_called_once()
        assert result is True


# ---------------------------------------------------------------------------
