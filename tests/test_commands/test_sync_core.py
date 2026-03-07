"""Core tests for the sync() function in rhiza.commands.sync.

Covers the five fundamental scenarios:
1. Always resync    — sync always proceeds even when lock SHA matches upstream AND template.yml unchanged
2. First merge sync — files copied, lock written
3. Diff strategy    — no files modified, no lock written
4. Subsequent merge — lock SHA updated to new upstream SHA
5. template.yml changed with same upstream SHA — normal merge path taken (no forced copy)
"""

from pathlib import Path
from unittest.mock import patch

import yaml

from rhiza.commands._sync_helpers import _read_lock, _write_lock
from rhiza.commands.sync import sync
from rhiza.models import TemplateLock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path: Path, include: list[str] | None = None) -> None:
    """Create a minimal project with .git, pyproject.toml, and .rhiza/template.yml."""
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


def _make_clone_dir(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    """Create a directory with the given files and return its path."""
    d = tmp_path / name
    d.mkdir()
    for filename, content in files.items():
        (d / filename).write_text(content)
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncCore:
    """Core scenario tests for sync()."""

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_at_sha")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_unchanged_sha_unchanged_template_yml_still_runs_merge(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, tmp_path
    ):
        """When lock SHA matches upstream HEAD and template.yml is unchanged, sync still proceeds."""
        _setup_project(tmp_path)
        # Write a lock with matching settings; the exact match no longer causes an early exit —
        # sync always proceeds regardless.
        _write_lock(
            tmp_path,
            TemplateLock(
                sha="abc123",
                repo="jebel-quant/rhiza",
                host="github",
                ref="main",
                include=["test.txt"],
            ),
        )
        mock_sha.return_value = "abc123"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})
        # Pre-populate base_clone with same content so the diff is empty (no changes to apply).
        base_clone_dir = _make_clone_dir(tmp_path, "base_clone", {"test.txt": "content\n"})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        # Sync must proceed and attempt to clone the base, even though SHA and template.yml are unchanged.
        mock_clone_base.assert_called_once()

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_first_merge_sync_copies_files_and_writes_lock(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path
    ):
        """First sync (no lock) copies upstream files and records the SHA."""
        _setup_project(tmp_path)
        mock_sha.return_value = "first111"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "template content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        assert (tmp_path / "test.txt").read_text() == "template content\n"
        assert _read_lock(tmp_path) == "first111"

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_diff_strategy_does_not_modify_files_or_write_lock(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path
    ):
        """Diff strategy leaves local files untouched and writes no lock."""
        _setup_project(tmp_path)
        (tmp_path / "test.txt").write_text("local content")
        mock_sha.return_value = "def456"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "upstream content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir)]

        sync(tmp_path, "main", None, "diff")

        assert (tmp_path / "test.txt").read_text() == "local content"
        assert _read_lock(tmp_path) is None

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_subsequent_merge_updates_lock_sha(self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path):
        """When upstream has a newer SHA, merge updates the lock to the new SHA."""
        _setup_project(tmp_path)
        _write_lock(tmp_path, TemplateLock(sha="old111"))
        mock_sha.return_value = "new222"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "updated content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})
        # _merge_with_base creates a 4th tempdir for the base_clone
        base_clone_dir = _make_clone_dir(tmp_path, "base_clone", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        assert _read_lock(tmp_path) == "new222"

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_template_yml_changed_same_sha_runs_normal_merge(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_rmtree, tmp_path
    ):
        """When template.yml changes but upstream SHA is unchanged, the normal merge path is taken."""
        # Project previously synced with include: ["old.txt"]
        _setup_project(tmp_path, include=["test.txt"])
        _write_lock(
            tmp_path,
            TemplateLock(
                sha="abc123",
                repo="jebel-quant/rhiza",
                host="github",
                ref="main",
                include=["old.txt"],  # differs from current template.yml
                files=["old.txt"],
            ),
        )
        # Upstream SHA is the same as the lock — no new template commits.
        mock_sha.return_value = "abc123"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "new content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})
        # Empty base_clone_dir simulates first-time merge of newly included file.
        base_clone_dir = _make_clone_dir(tmp_path, "base_clone", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        # File from updated include list is merged (not copied) into target.
        assert (tmp_path / "test.txt").read_text() == "new content\n"
        # Lock must be updated with the upstream SHA.
        assert _read_lock(tmp_path) == "abc123"

    @patch("rhiza.commands._sync_helpers.shutil.rmtree")
    @patch("rhiza.commands._sync_helpers._clone_at_sha")
    @patch("rhiza.commands._sync_helpers._clone_template_repository")
    @patch("rhiza.commands._sync_helpers.tempfile.mkdtemp")
    @patch("rhiza.commands._sync_helpers._get_head_sha")
    def test_unchanged_sha_unchanged_template_yml_writes_lock(
        self, mock_sha, mock_mkdtemp, mock_clone, mock_clone_base, mock_rmtree, tmp_path
    ):
        """When SHA matches AND template.yml is unchanged, sync still completes and writes the lock."""
        _setup_project(tmp_path, include=["test.txt"])
        _write_lock(
            tmp_path,
            TemplateLock(
                sha="abc123",
                repo="jebel-quant/rhiza",
                host="github",
                ref="main",
                include=["test.txt"],
            ),
        )
        mock_sha.return_value = "abc123"

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"test.txt": "content\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})
        # Pre-populate base_clone with same content so the diff is empty (no changes to apply).
        base_clone_dir = _make_clone_dir(tmp_path, "base_clone", {"test.txt": "content\n"})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir), str(base_clone_dir)]

        sync(tmp_path, "main", None, "merge")

        # Lock must be written even though nothing changed.
        assert _read_lock(tmp_path) == "abc123"
