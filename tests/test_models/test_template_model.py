"""Tests for the RhizaTemplate dataclass.

This module verifies that the RhizaTemplate dataclass correctly represents
and handles .rhiza/template.yml configuration, including serialisation,
git URL construction, cloning, and snapshotting.
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from rhiza.commands.sync import _clone_template, _load_template_from_project
from rhiza.models import GitContext
from rhiza.models._base import YamlSerializable, load_model
from rhiza.models._git_utils import _excluded_set, _expand_paths, _prepare_snapshot
from rhiza.models.template import RhizaTemplate


class TestRhizaTemplate:
    """Tests for the RhizaTemplate dataclass."""

    def test_rhiza_template_from_config(self):
        """Test loading RhizaTemplate from config dict with various field combinations."""
        # 1. Standard keys with 'template-repository', 'template-branch', and 'exclude'
        template = RhizaTemplate.from_config(
            {
                "template-repository": "custom/repo",
                "template-branch": "dev",
                "include": [".github", "Makefile"],
                "exclude": [".github/workflows/docker.yml"],
            }
        )
        assert template.template_repository == "custom/repo"
        assert template.template_branch == "dev"
        assert template.include == [".github", "Makefile"]
        assert template.exclude == [".github/workflows/docker.yml"]
        assert template.template_host == "github"  # Default
        assert template.language == "python"  # Default

        # 2. Canonical aliases 'repository' and 'ref', with custom host/language
        template = RhizaTemplate.from_config(
            {
                "repository": "owner/repo",
                "ref": "v1.0.0",
                "template-host": "gitlab",
                "language": "go",
                "templates": ["core", "tests"],
            }
        )
        assert template.template_repository == "owner/repo"
        assert template.template_branch == "v1.0.0"
        assert template.template_host == "gitlab"
        assert template.language == "go"
        assert template.templates == ["core", "tests"]

        # 3. Precedence: 'repository' over 'template-repository', 'ref' over 'template-branch'
        template = RhizaTemplate.from_config(
            {
                "repository": "correct/repo",
                "template-repository": "wrong/repo",
                "ref": "correct-branch",
                "template-branch": "wrong-branch",
            }
        )
        assert template.template_repository == "correct/repo"
        assert template.template_branch == "correct-branch"

        # 4. Fallback: null/empty primary fields use alternative fields
        template = RhizaTemplate.from_config(
            {
                "repository": None,
                "template-repository": "fallback/repo",
                "ref": "",
                "template-branch": "fallback-branch",
            }
        )
        assert template.template_repository == "fallback/repo"
        assert template.template_branch == "fallback-branch"

    def test_rhiza_template_from_yaml_empty_file(self, tmp_path):
        """Test that loading fails when file is empty."""
        template_file = tmp_path / "template.yml"
        template_file.write_text("")

        with pytest.raises(ValueError, match="is empty"):
            RhizaTemplate.from_yaml(template_file)

    def test_rhiza_template_from_yaml_invalid_yaml(self, tmp_path):
        """Test that loading fails when YAML is malformed."""
        template_file = tmp_path / "template.yml"
        template_file.write_text("invalid: yaml: content: [[[")

        with pytest.raises(yaml.YAMLError):
            RhizaTemplate.from_yaml(template_file)

    def test_rhiza_template_from_yaml_file_not_found(self, tmp_path):
        """Test that loading fails when file doesn't exist."""
        template_file = tmp_path / "nonexistent.yml"

        with pytest.raises(FileNotFoundError):
            RhizaTemplate.from_yaml(template_file)

    def test_rhiza_template_round_trip(self, tmp_path):
        """Test that loading and saving preserves all RhizaTemplate fields."""
        # 1. Basic round-trip
        original = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[".github", ".editorconfig", "Makefile"],
            exclude=[".github/workflows/docker.yml"],
        )
        template_file = tmp_path / "template_basic.yml"
        original.to_yaml(template_file)
        loaded = RhizaTemplate.from_yaml(template_file)
        assert loaded == original

        # 2. Round-trip with non-default host and language
        original = RhizaTemplate(
            template_repository="mygroup/myproject",
            template_branch="main",
            template_host="gitlab",
            language="go",
            templates=["core", "tests"],
            include=[".gitlab-ci.yml"],
        )
        template_file = tmp_path / "template_gitlab.yml"
        original.to_yaml(template_file)
        loaded = RhizaTemplate.from_yaml(template_file)
        assert loaded == original

        # 3. Round-trip ensures canonical key names (repository, ref)
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
        )
        template_file = tmp_path / "template_keys.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert "repository" in config
        assert "ref" in config
        assert "template-repository" not in config
        assert "template-branch" not in config

    def test_rhiza_template_to_yaml_conditional_serialization(self, tmp_path):
        """Test that to_yaml includes all fields."""
        # 1. Defaults (host=github, language=python) are included
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            template_host="github",
            language="python",
        )
        template_file = tmp_path / "template_defaults.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["template-host"] == "github"
        assert config["language"] == "python"

        # 2. Non-defaults (host=gitlab, language=go) are included
        template = RhizaTemplate(
            template_repository="mygroup/myproject",
            template_branch="main",
            template_host="gitlab",
            language="go",
        )
        template_file = tmp_path / "template_non_defaults.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["template-host"] == "gitlab"
        assert config["language"] == "go"

        # 3. Optional fields (templates, include, exclude) are always included
        template = RhizaTemplate(template_repository="owner/repo", include=["only"])
        template_file = tmp_path / "template_optional.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["include"] == ["only"]
        assert config["templates"] == []
        assert config["exclude"] == []

        # 4. Empty values (repository, branch) are included
        template = RhizaTemplate(template_repository="", template_branch="")
        template_file = tmp_path / "template_empty.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert config["repository"] == ""
        assert config["ref"] == ""

    def test_normalize_to_list_with_unexpected_type(self, tmp_path):
        """Test that _normalize_to_list handles unexpected types gracefully."""
        from rhiza.models._git_utils import _normalize_to_list

        # Test with None
        assert _normalize_to_list(None) == []

        # Test with list
        assert _normalize_to_list(["a", "b"]) == ["a", "b"]

        # Test with string
        assert _normalize_to_list("a\nb\nc") == ["a", "b", "c"]

        # Test with unexpected type (e.g., integer) - should return []
        assert _normalize_to_list(123) == []  # type: ignore[arg-type]

        # Test with dict - should return []
        assert _normalize_to_list({"key": "value"}) == []  # type: ignore[arg-type]

    def test_rhiza_hybrid_mode(self, tmp_path):
        """Test template with both templates and include fields (loading and saving)."""
        # 1. Loading via from_config
        template = RhizaTemplate.from_config(
            {
                "template-repository": "jebel-quant/rhiza",
                "template-branch": "main",
                "templates": ["core", "tests"],
                "include": [".custom", "extra/"],
            }
        )
        assert template.templates == ["core", "tests"]
        assert template.include == [".custom", "extra/"]

        # 2. Saving
        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert config["templates"] == ["core", "tests"]
        assert config["include"] == [".custom", "extra/"]

    def test_default_template_bundles_path(self):
        """template_bundles_path defaults to .rhiza/template-bundles.yml."""
        template = RhizaTemplate.from_config({"template-repository": "owner/repo", "templates": ["core"]})
        assert template.template_bundles_path == ".rhiza/template-bundles.yml"

    def test_custom_template_bundles_path_round_trips(self, tmp_path):
        """A custom template-bundles-path is loaded, preserved, and serialised."""
        template = RhizaTemplate.from_config(
            {
                "template-repository": "owner/repo",
                "templates": ["core"],
                "template-bundles-path": "tooling/my-bundles.yml",
            }
        )
        assert template.template_bundles_path == "tooling/my-bundles.yml"

        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert config["template-bundles-path"] == "tooling/my-bundles.yml"

    def test_default_template_bundles_path_not_serialised(self, tmp_path):
        """The default template-bundles-path is not written to YAML (keeps config minimal)."""
        template = RhizaTemplate.from_config({"template-repository": "owner/repo", "templates": ["core"]})
        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert "template-bundles-path" not in config


class TestRhizaTemplateGitUrl:
    """Tests for the RhizaTemplate.git_url property."""

    def test_github_url(self):
        """GitHub host produces the correct HTTPS URL."""
        template = RhizaTemplate(template_repository="owner/repo", template_host="github")
        assert template.git_url == "https://github.com/owner/repo.git"

    def test_gitlab_url(self):
        """GitLab host produces the correct HTTPS URL."""
        template = RhizaTemplate(template_repository="mygroup/myproject", template_host="gitlab")
        assert template.git_url == "https://gitlab.com/mygroup/myproject.git"

    def test_default_host_is_github(self):
        """Default host (github) is used when template_host is not specified."""
        template = RhizaTemplate(template_repository="owner/repo")
        assert template.git_url == "https://github.com/owner/repo.git"

    def test_invalid_host_raises(self):
        """An unsupported template_host raises ValueError."""
        template = RhizaTemplate(template_repository="owner/repo", template_host="bitbucket")
        with pytest.raises(ValueError, match="Unsupported template-host"):
            _ = template.git_url

    def test_missing_repository_raises(self):
        """git_url raises ValueError when template_repository is not set."""
        template = RhizaTemplate()
        with pytest.raises(ValueError, match="template_repository is not configured"):
            _ = template.git_url


class TestRhizaTemplateClone:
    """Tests for the _clone_template function."""

    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    def test_clone_returns_upstream_dir_and_sha(self, mock_clone, mock_head_sha):
        """_clone_template returns (upstream_dir, upstream_sha, include) for a plain include-list template."""
        mock_head_sha.return_value = "abc123def456"

        template = RhizaTemplate(
            template_repository="owner/repo",
            template_branch="main",
            template_host="github",
            include=["Makefile", ".github"],
        )

        upstream_dir, upstream_sha, resolved_include = _clone_template(template, GitContext.default(), branch="main")

        assert upstream_dir.is_dir()
        assert upstream_sha == "abc123def456"
        assert resolved_include == ["Makefile", ".github"]
        mock_clone.assert_called_once()
        shutil.rmtree(upstream_dir, ignore_errors=True)

    def test_clone_raises_when_no_repository(self):
        """_clone_template raises ValueError when template_repository is not set."""
        template = RhizaTemplate(include=["Makefile"])
        with pytest.raises(ValueError, match="template_repository is not configured"):
            _clone_template(template, GitContext.default())

    def test_clone_raises_when_no_include_or_templates(self):
        """_clone_template raises ValueError when neither include nor templates are set."""
        template = RhizaTemplate(template_repository="owner/repo")
        with pytest.raises(ValueError, match="No templates or include paths"):
            _clone_template(template, GitContext.default())

    @patch("rhiza.models._git_utils.GitContext.get_head_sha")
    @patch("rhiza.models._git_utils.GitContext.clone_repository")
    def test_clone_uses_template_branch_over_default(self, mock_clone, mock_head_sha):
        """_clone_template uses template_branch when set, ignoring the branch argument."""
        mock_head_sha.return_value = "sha_from_develop"

        template = RhizaTemplate(
            template_repository="owner/repo",
            template_branch="develop",
            include=["Makefile"],
        )

        upstream_dir, upstream_sha, _resolved = _clone_template(template, GitContext.default(), branch="main")

        # The clone should use 'develop' (template_branch), not 'main' (default arg).
        mock_clone.assert_called_once()
        # The second positional argument to clone_repository should be tmp_dir,
        # the third should be the branch
        _args, _kwargs = mock_clone.call_args
        assert _args[2] == "develop"
        assert upstream_sha == "sha_from_develop"
        shutil.rmtree(upstream_dir, ignore_errors=True)


class TestRhizaTemplateSnapshot:
    """Tests for the _excluded_set and _prepare_snapshot module-level functions."""

    def test_snapshot_copies_included_files(self, tmp_path):
        """_prepare_snapshot copies included files into snapshot_dir and returns them as materialized."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()
        (upstream_dir / "a.txt").write_text("content-a")
        (upstream_dir / "b.txt").write_text("content-b")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        template = RhizaTemplate(
            template_repository="owner/repo",
            include=["a.txt", "b.txt"],
        )

        excludes = _excluded_set(upstream_dir, template.exclude)
        materialized = _prepare_snapshot(upstream_dir, template.include, excludes, snapshot_dir)

        assert len(materialized) == 2
        assert (snapshot_dir / "a.txt").read_text() == "content-a"
        assert (snapshot_dir / "b.txt").read_text() == "content-b"

    def test_snapshot_excludes_user_paths_and_rhiza_defaults(self, tmp_path):
        """_excluded_set + _prepare_snapshot exclude user-configured paths and rhiza internals."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()
        (upstream_dir / "keep.txt").write_text("keep")
        (upstream_dir / "skip.txt").write_text("skip")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        template = RhizaTemplate(
            template_repository="owner/repo",
            include=["keep.txt", "skip.txt"],
            exclude=["skip.txt"],
        )

        excludes = _excluded_set(upstream_dir, template.exclude)
        materialized = _prepare_snapshot(upstream_dir, template.include, excludes, snapshot_dir)

        assert len(materialized) == 1
        assert (snapshot_dir / "keep.txt").exists()
        assert not (snapshot_dir / "skip.txt").exists()
        assert "skip.txt" in excludes
        assert ".rhiza/template.yml" in excludes
        assert ".rhiza/history" in excludes

    def test_snapshot_returns_excludes_for_downstream_use(self, tmp_path):
        """_excluded_set returns the excludes set so callers can pass it to merge helpers."""
        upstream_dir = tmp_path / "upstream"
        upstream_dir.mkdir()
        (upstream_dir / "secrets.env").write_text("API_KEY=secret")

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        template = RhizaTemplate(
            template_repository="owner/repo",
            include=["secrets.env"],
            exclude=["secrets.env"],
        )

        excludes = _excluded_set(upstream_dir, template.exclude)
        _prepare_snapshot(upstream_dir, template.include, excludes, snapshot_dir)

        assert "secrets.env" in excludes
        assert ".rhiza/template.yml" in excludes


# ---------------------------------------------------------------------------
# YamlSerializable Protocol — template-related checks
# ---------------------------------------------------------------------------


class TestYamlSerializableProtocol:
    """Tests for the YamlSerializable Protocol as it applies to RhizaTemplate."""

    def test_rhiza_template_satisfies_protocol(self):
        """RhizaTemplate is a runtime-checkable instance of YamlSerializable."""
        template = RhizaTemplate(template_repository="owner/repo")
        assert isinstance(template, YamlSerializable)

    def test_plain_class_does_not_satisfy_protocol(self):
        """A class without from_yaml / to_yaml does not satisfy YamlSerializable."""

        class NotSerializable:
            pass

        assert not isinstance(NotSerializable(), YamlSerializable)


# ---------------------------------------------------------------------------
# load_model helper — template-related checks
# ---------------------------------------------------------------------------


class TestLoadModel:
    """Tests for the load_model generic helper as it applies to RhizaTemplate."""

    def test_load_model_returns_rhiza_template(self, tmp_path):
        """load_model loads a RhizaTemplate and returns the correct type/values."""
        import yaml

        template_file = tmp_path / "template.yml"
        template_file.write_text(yaml.dump({"repository": "owner/repo", "ref": "main"}))

        result = load_model(RhizaTemplate, template_file)

        assert isinstance(result, RhizaTemplate)
        assert result.template_repository == "owner/repo"
        assert result.template_branch == "main"

    def test_load_model_raises_for_class_without_from_config(self):
        """load_model raises TypeError when the class lacks from_config."""

        class NoConfig:
            pass

        with pytest.raises(TypeError, match="NoConfig does not implement from_config"):
            load_model(NoConfig, Path("irrelevant.yml"))


# ---------------------------------------------------------------------------
# Module-level helper functions — direct coverage
# ---------------------------------------------------------------------------


class TestExpandPaths:
    """Tests for _expand_paths module-level function."""

    def test_expand_paths_with_directory(self, tmp_path):
        """When a path points to a directory, all files within are returned."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "a.txt").write_text("a")
        (sub / "b.txt").write_text("b")

        result = _expand_paths(tmp_path, ["subdir"])

        assert len(result) == 2
        assert all(f.is_file() for f in result)


class TestUpdateSparseCheckout:
    """Tests for GitContext.update_sparse_checkout."""

    def test_success(self, tmp_path):
        """Success path calls subprocess and logs completion."""
        git_ctx = GitContext.default()
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch("rhiza.models._git_utils.subprocess.run", return_value=ok) as mock_run:
            git_ctx.update_sparse_checkout(tmp_path, [".github"])
        mock_run.assert_called_once()

    def test_failure_reraises(self, tmp_path):
        """CalledProcessError is logged and re-raised."""
        git_ctx = GitContext.default()
        err = subprocess.CalledProcessError(1, ["git"])
        err.stderr = "error output"
        with (
            patch("rhiza.models._git_utils.subprocess.run", side_effect=err),
            pytest.raises(subprocess.CalledProcessError),
        ):
            git_ctx.update_sparse_checkout(tmp_path, [".github"])


class TestGetHeadSha:
    """Tests for GitContext.get_head_sha."""

    def test_returns_sha(self, tmp_path):
        """Returns the stdout stripped from git rev-parse HEAD."""
        git_ctx = GitContext.default()
        ok = MagicMock(returncode=0, stdout="abc123def456\n", stderr="")
        with patch("rhiza.models._git_utils.subprocess.run", return_value=ok):
            sha = git_ctx.get_head_sha(tmp_path)
        assert sha == "abc123def456"


class TestCloneRepositorySuccess:
    """Tests for the success path of GitContext.clone_repository."""

    def test_all_subprocess_calls_succeed(self, tmp_path):
        """When all three subprocess calls succeed, no exception is raised."""
        git_ctx = GitContext.default()
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch("rhiza.models._git_utils.subprocess.run", return_value=ok):
            git_ctx.clone_repository("https://github.com/owner/repo.git", tmp_path, "main", [".github"])


class TestCloneAtShaErrors:
    """Tests for GitContext.clone_at_sha error paths."""

    def test_clone_failure_reraises(self, tmp_path):
        """CalledProcessError from the clone step is logged and re-raised."""
        git_ctx = GitContext.default()
        err = subprocess.CalledProcessError(128, ["git", "clone"])
        err.stderr = "fatal: not found"
        with (
            patch("rhiza.models._git_utils.subprocess.run", side_effect=err),
            pytest.raises(subprocess.CalledProcessError),
        ):
            git_ctx.clone_at_sha("https://github.com/owner/repo.git", "abc123", tmp_path / "dest", [".github"])

    def test_sparse_checkout_failure_reraises(self, tmp_path):
        """CalledProcessError from the sparse-checkout step is logged and re-raised."""
        git_ctx = GitContext.default()
        ok = MagicMock(returncode=0, stdout="", stderr="")
        err = subprocess.CalledProcessError(1, ["git", "sparse-checkout"])
        err.stderr = "error"
        with (
            patch("rhiza.models._git_utils.subprocess.run", side_effect=[ok, err]),
            pytest.raises(subprocess.CalledProcessError),
        ):
            git_ctx.clone_at_sha("https://github.com/owner/repo.git", "abc123", tmp_path / "dest", [".github"])


# ---------------------------------------------------------------------------
# _load_template_from_project — branch coverage
# ---------------------------------------------------------------------------


def _write_template_yml(target: Path, config: dict) -> None:
    rhiza_dir = target / ".rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)
    with open(rhiza_dir / "template.yml", "w") as f:
        yaml.dump(config, f)


class TestFromProject:
    """Tests for _load_template_from_project branch coverage."""

    def test_validation_failure_raises(self, tmp_path):
        """RuntimeError is raised when validate() returns False."""
        _write_template_yml(tmp_path, {"template-repository": "owner/repo", "include": ["Makefile"]})
        with (
            patch("rhiza.commands.validate.validate", return_value=False),
            pytest.raises(RuntimeError, match="validation failed"),
        ):
            _load_template_from_project(tmp_path)

    def test_missing_template_repository_raises(self, tmp_path):
        """RuntimeError is raised when template_repository is not set."""
        _write_template_yml(tmp_path, {"include": ["Makefile"]})
        with (
            patch("rhiza.commands.validate.validate", return_value=True),
            pytest.raises(RuntimeError, match="template-repository is required"),
        ):
            _load_template_from_project(tmp_path)

    def test_missing_template_branch_uses_fallback(self, tmp_path):
        """template_branch is set from the branch argument when not in template.yml."""
        _write_template_yml(
            tmp_path, {"template-repository": "owner/repo", "template-branch": "develop", "include": ["Makefile"]}
        )
        with patch("rhiza.commands.validate.validate", return_value=True):
            template = _load_template_from_project(tmp_path)
        assert template.template_branch == "develop"

    def test_no_include_or_templates_raises(self, tmp_path):
        """RuntimeError is raised when neither include nor templates are configured."""
        _write_template_yml(tmp_path, {"template-repository": "owner/repo", "template-branch": "main"})
        with (
            patch("rhiza.commands.validate.validate", return_value=True),
            pytest.raises(RuntimeError, match="No templates or include paths"),
        ):
            _load_template_from_project(tmp_path)

    def test_templates_list_is_logged(self, tmp_path):
        """_load_template_from_project succeeds and returns template when templates are configured."""
        _write_template_yml(
            tmp_path,
            {"template-repository": "owner/repo", "template-branch": "main", "templates": ["core"]},
        )
        with patch("rhiza.commands.validate.validate", return_value=True):
            template = _load_template_from_project(tmp_path)
        assert template.templates == ["core"]

    def test_exclude_list_is_logged(self, tmp_path):
        """_load_template_from_project succeeds and returns template when exclude paths are configured."""
        _write_template_yml(
            tmp_path,
            {
                "template-repository": "owner/repo",
                "template-branch": "main",
                "include": ["Makefile"],
                "exclude": ["secret.txt"],
            },
        )
        with patch("rhiza.commands.validate.validate", return_value=True):
            template = _load_template_from_project(tmp_path)
        assert template.exclude == ["secret.txt"]
