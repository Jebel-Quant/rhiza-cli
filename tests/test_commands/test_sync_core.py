"""Core tests for the sync() function in rhiza.commands.sync.

Covers the five fundamental scenarios:
1. Already up to date  — early exit when lock SHA matches upstream AND template.yml unchanged
2. First merge sync    — files copied, lock written
3. Diff strategy       — no files modified, no lock written
4. Subsequent merge    — lock SHA updated to new upstream SHA
5. template.yml changed with same upstream SHA — re-sync triggered, files copied
6. templates: mode — include: in lock contains original names, not resolved paths
7. hybrid mode — templates: resolved paths merged with explicit include: paths
8. custom template-bundles-path — bundle definitions file fetched from custom location
9. path-to-template bundles derivation — template_bundles_path derived from template_file location
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


def _setup_project_base(target: Path) -> None:
    """Create the minimal git project structure (.git dir and pyproject.toml)."""
    (target / ".git").mkdir(exist_ok=True)
    (target / "pyproject.toml").write_text('[project]\nname = "test"\n')


def _write_template_yml(tmp_path: Path, config: dict) -> None:
    """Write a template.yml config file to .rhiza/."""
    _setup_project_base(tmp_path)
    rhiza_dir = tmp_path / ".rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)
    with open(rhiza_dir / "template.yml", "w") as f:
        yaml.dump(config, f)


def _write_template_yml_at(target: Path, template_file: Path, config: dict) -> None:
    """Write a template.yml config file to an explicit path, creating the project structure."""
    _setup_project_base(target)
    template_file.parent.mkdir(parents=True, exist_ok=True)
    with open(template_file, "w") as f:
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
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
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
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
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
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
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
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
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

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_hybrid_mode_merges_bundle_and_include_paths(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """Hybrid mode: resolved bundle paths and explicit include: paths are both synced."""
        _write_template_yml(
            tmp_path,
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core"],
                "include": ["extra.txt"],
            },
        )
        mock_sha.return_value = "hybrid1"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(
            tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n", "extra.txt": "extra\n"}
        )
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        # update_sparse_checkout must have received both the resolved bundle path and the
        # explicit include: path — i.e. hybrid mode is correctly merged.
        call_args = mock_update_sparse.call_args
        merged = call_args[0][1]  # second positional arg is the paths list
        assert "Makefile" in merged
        assert "extra.txt" in merged

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_custom_template_bundles_path_is_used(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """When template-bundles-path is set, the custom path is fetched instead of the default."""
        custom_bundles_path = "tooling/my-bundles.yml"
        _write_template_yml(
            tmp_path,
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core"],
                "template-bundles-path": custom_bundles_path,
            },
        )
        mock_sha.return_value = "custom1"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        # clone_repository must have been called with the custom bundles path, not the default
        first_clone_call = mock_clone.call_args_list[0]
        sparse_paths_arg = first_clone_call[0][3]  # fourth positional arg is sparse paths
        assert sparse_paths_arg == [custom_bundles_path]
        # from_yaml must have been called with a path ending in the custom bundles path
        from_yaml_path = mock_from_yaml.call_args[0][0]
        assert str(from_yaml_path).endswith(custom_bundles_path)


# ---------------------------------------------------------------------------
# 9. path-to-template bundles derivation
# ---------------------------------------------------------------------------


class TestSyncPathToTemplateBundlesDerived:
    """Tests that template_bundles_path is derived from the template_file location.

    When --path-to-template specifies a non-default directory, the default
    ``template_bundles_path`` must mirror that directory (e.g., ``custom/template-bundles.yml``
    instead of ``.rhiza/template-bundles.yml``).  Explicitly set ``template-bundles-path``
    values in template.yml must always be respected unchanged.
    """

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_bundles_path_derived_from_custom_template_file_directory(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """When template_file is in a custom dir, bundles path uses that dir by default."""
        custom_dir = tmp_path / "my-rhiza"
        template_file = custom_dir / "template.yml"
        _write_template_yml_at(
            tmp_path,
            template_file,
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core"],
            },
        )
        mock_sha.return_value = "derived1"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge", template_file=template_file)

        # clone_repository must have been called with the derived bundles path, not .rhiza/
        first_clone_call = mock_clone.call_args_list[0]
        sparse_paths_arg = first_clone_call[0][3]
        assert sparse_paths_arg == ["my-rhiza/template-bundles.yml"]
        # from_yaml must have been called with a path ending in the derived bundles path
        from_yaml_path = mock_from_yaml.call_args[0][0]
        assert str(from_yaml_path).endswith("my-rhiza/template-bundles.yml")

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_bundles_path_derived_from_project_root_template_file(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """When template_file is in the project root, bundles path is template-bundles.yml."""
        template_file = tmp_path / "template.yml"
        _write_template_yml_at(
            tmp_path,
            template_file,
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core"],
            },
        )
        mock_sha.return_value = "rootderived"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge", template_file=template_file)

        # When template_file is at the project root, bundles path should be "template-bundles.yml"
        first_clone_call = mock_clone.call_args_list[0]
        sparse_paths_arg = first_clone_call[0][3]
        assert sparse_paths_arg == ["template-bundles.yml"]

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_explicit_bundles_path_not_overridden_by_template_file_location(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """An explicit template-bundles-path in template.yml is never overridden."""
        custom_dir = tmp_path / "my-rhiza"
        template_file = custom_dir / "template.yml"
        explicit_bundles_path = "tooling/custom-bundles.yml"
        _write_template_yml_at(
            tmp_path,
            template_file,
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core"],
                "template-bundles-path": explicit_bundles_path,
            },
        )
        mock_sha.return_value = "explicit1"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge", template_file=template_file)

        # Explicit template-bundles-path must be respected; the custom dir must NOT override it
        first_clone_call = mock_clone.call_args_list[0]
        sparse_paths_arg = first_clone_call[0][3]
        assert sparse_paths_arg == [explicit_bundles_path]

    @patch("rhiza.commands.sync.shutil.rmtree")
    @patch("rhiza.models._git_utils.GitContext.update_sparse_checkout")
    @patch("rhiza.models.bundle.RhizaBundles.from_yaml")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    @patch("rhiza.commands.sync.tempfile.mkdtemp")
    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    def test_default_rhiza_dir_keeps_default_bundles_path(
        self,
        mock_sha,
        mock_mkdtemp,
        mock_clone,
        mock_from_yaml,
        mock_update_sparse,
        mock_rmtree,
        tmp_path,
    ):
        """When template_file is in the default .rhiza/ dir, bundles path stays at default."""
        _setup_project_with_templates(tmp_path, templates=["core"])
        mock_sha.return_value = "default1"

        from rhiza.models.bundle import RhizaBundles

        mock_from_yaml.return_value = RhizaBundles.from_config(
            {"bundles": {"core": {"description": "Core", "files": ["Makefile"]}}}
        )

        clone_dir = _make_clone_dir(tmp_path, "upstream_clone", {"Makefile": "all:\n\techo ok\n"})
        snapshot_dir = _make_clone_dir(tmp_path, "upstream_snapshot", {})
        base_snapshot_dir = _make_clone_dir(tmp_path, "base_snapshot", {})

        mock_mkdtemp.side_effect = [str(clone_dir), str(snapshot_dir), str(base_snapshot_dir)]

        sync(tmp_path, "main", None, "merge")

        # Default .rhiza/ directory keeps the default .rhiza/template-bundles.yml path
        first_clone_call = mock_clone.call_args_list[0]
        sparse_paths_arg = first_clone_call[0][3]
        assert sparse_paths_arg == [".rhiza/template-bundles.yml"]
