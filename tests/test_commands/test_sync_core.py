"""Core tests for the sync() function in rhiza.commands.sync.

Covers the five fundamental scenarios:
1. Already up to date  — early exit when lock SHA matches upstream AND template.yml unchanged
2. First merge sync    — files copied, lock written
3. Diff strategy       — no files modified, no lock written
4. Subsequent merge    — lock SHA updated to new upstream SHA
5. template.yml changed with same upstream SHA — re-sync triggered, files copied
6. templates: mode — include: in lock contains original names, not resolved paths
"""

from pathlib import Path
from unittest.mock import patch

import yaml

from rhiza.commands._sync_helpers import _write_lock
from rhiza.commands.sync import sync
from rhiza.models import TemplateLock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_template_yml(tmp_path: Path, config: dict) -> None:
    """Write a template.yml config file to .rhiza/."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    rhiza_dir = tmp_path / ".rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)
    with open(rhiza_dir / "template.yml", "w") as f:
        yaml.dump(config, f)


def _setup_project(tmp_path: Path, include: list[str] | None = None) -> None:
    """Create a minimal project with .git, pyproject.toml, and .rhiza/template.yml."""
    _write_template_yml(
        tmp_path,
        {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": include or ["test.txt"],
        },
    )


def _setup_project_with_templates(tmp_path: Path, templates: list[str]) -> None:
    """Create a minimal project using templates: mode (bundle names, no include:)."""
    _write_template_yml(
        tmp_path,
        {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "templates": templates,
        },
    )


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

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models.RhizaTemplate._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models.RhizaTemplate._get_head_sha")
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
        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == "first111"

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models.RhizaTemplate._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models.RhizaTemplate._get_head_sha")
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
        assert not (tmp_path / ".rhiza" / "template.lock").exists()

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models.RhizaTemplate._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models.RhizaTemplate._get_head_sha")
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

        assert TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock").config["sha"] == "new222"

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models.RhizaTemplate._update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models.RhizaTemplate._clone_template_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models.RhizaTemplate._get_head_sha")
    def test_templates_mode_lock_include_contains_original_not_resolved(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """When templates: mode is used, include: in lock contains original bundle names, not resolved paths."""
        _setup_project_with_templates(tmp_path, templates=["core"])
        mock_sha.return_value = "abc123"

        # Simulate bundle resolution: "core" resolves to ["Makefile", "pyproject.toml"]
        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile", "pyproject.toml"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        lock = TemplateLock.from_yaml(tmp_path / ".rhiza" / "template.lock")
        # include: must be the original value from template.yml — empty because
        # _setup_project_with_templates writes only templates:, no include: field.
        # clone() resolves "core" to ["Makefile", "pyproject.toml"] and would mutate
        # template.include; those resolved paths must NOT appear here.
        assert lock.include == []
        # The resolved file paths should appear in files: (materialized from snapshot)
        assert "Makefile" in lock.files
