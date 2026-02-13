"""Tests for the RhizaTemplate dataclass and related models.

This module verifies that the RhizaTemplate dataclass correctly represents
and handles .rhiza/template.yml configuration.
"""

import pytest
import yaml

from rhiza.models import RhizaBundles, RhizaTemplate


class TestRhizaTemplate:
    """Tests for the RhizaTemplate dataclass."""

    def test_rhiza_template_from_yaml_basic(self, tmp_path):
        """Test loading a basic template.yml file."""
        rhiza_dir = tmp_path / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": [".github", "Makefile"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "jebel-quant/rhiza"
        assert template.template_branch == "main"
        assert template.include == [".github", "Makefile"]
        assert template.exclude == []

    def test_rhiza_template_from_yaml_with_exclude(self, tmp_path):
        """Test loading a template.yml file with exclude field."""
        rhiza_dir = tmp_path / "rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        config = {
            "template-repository": "custom/repo",
            "template-branch": "dev",
            "include": [".github", "Makefile"],
            "exclude": [".github/workflows/docker.yml"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "custom/repo"
        assert template.template_branch == "dev"
        assert template.include == [".github", "Makefile"]
        assert template.exclude == [".github/workflows/docker.yml"]

    def test_rhiza_template_from_yaml_default_branch(self, tmp_path):
        """Test that template-branch is None if not provided."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "jebel-quant/rhiza",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_branch is None

    def test_rhiza_template_from_yaml_missing_repository(self, tmp_path):
        """Test that loading succeeds when template-repository is missing (returns None)."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-branch": "main",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.template_repository is None
        assert template.template_branch == "main"
        assert template.include == [".github"]

    def test_rhiza_template_from_yaml_empty_file(self, tmp_path):
        """Test that loading fails when file is empty."""
        template_file = tmp_path / "template.yml"
        template_file.write_text("")

        with pytest.raises(ValueError, match="Template file is empty"):
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

    def test_rhiza_template_to_yaml_basic(self, tmp_path):
        """Test saving a basic RhizaTemplate to YAML."""
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[".github", "Makefile"],
        )

        template_file = tmp_path / ".github" / "rhiza" / "template.yml"
        template.to_yaml(template_file)

        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"
        assert config["template-branch"] == "main"
        assert config["include"] == [".github", "Makefile"]
        assert "exclude" not in config  # Should not be present when empty

    def test_rhiza_template_to_yaml_with_exclude(self, tmp_path):
        """Test saving a RhizaTemplate with exclude to YAML."""
        template = RhizaTemplate(
            template_repository="custom/repo",
            template_branch="dev",
            include=[".github", "Makefile"],
            exclude=[".github/workflows/docker.yml"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "custom/repo"
        assert config["template-branch"] == "dev"
        assert config["include"] == [".github", "Makefile"]
        assert config["exclude"] == [".github/workflows/docker.yml"]

    def test_rhiza_template_round_trip(self, tmp_path):
        """Test that loading and saving preserves data."""
        original = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[".github", ".editorconfig", "Makefile"],
            exclude=[".github/workflows/docker.yml", ".github/workflows/devcontainer.yml"],
        )

        template_file = tmp_path / "template.yml"
        original.to_yaml(template_file)

        loaded = RhizaTemplate.from_yaml(template_file)

        assert loaded.template_repository == original.template_repository
        assert loaded.template_branch == original.template_branch
        assert loaded.include == original.include
        assert loaded.exclude == original.exclude

    def test_rhiza_template_creates_parent_directory(self, tmp_path):
        """Test that to_yaml creates parent directories if they don't exist."""
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[".github"],
        )

        # Create a nested path that doesn't exist
        template_file = tmp_path / "nested" / "path" / "template.yml"

        template.to_yaml(template_file)

        assert template_file.exists()
        assert template_file.parent.exists()

    def test_rhiza_template_defaults_to_github(self, tmp_path):
        """Test that template-host defaults to github when not specified."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_host == "github"

    def test_rhiza_template_gitlab_host(self, tmp_path):
        """Test loading a template.yml with gitlab as template-host."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "mygroup/myproject",
            "template-branch": "main",
            "template-host": "gitlab",
            "include": [".gitlab-ci.yml", "Makefile"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "mygroup/myproject"
        assert template.template_branch == "main"
        assert template.template_host == "gitlab"
        assert template.include == [".gitlab-ci.yml", "Makefile"]

    def test_rhiza_template_to_yaml_github_not_included(self, tmp_path):
        """Test that template-host is not saved when it's 'github' (default)."""
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            template_host="github",
            include=[".github"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # GitHub is default, should not appear in the file
        assert "template-host" not in config

    def test_rhiza_template_to_yaml_gitlab_included(self, tmp_path):
        """Test that template-host is saved when it's 'gitlab'."""
        template = RhizaTemplate(
            template_repository="mygroup/myproject",
            template_branch="main",
            template_host="gitlab",
            include=[".gitlab-ci.yml"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-host"] == "gitlab"

    def test_rhiza_template_round_trip_with_gitlab(self, tmp_path):
        """Test that loading and saving preserves gitlab host."""
        original = RhizaTemplate(
            template_repository="mygroup/myproject",
            template_branch="main",
            template_host="gitlab",
            include=[".gitlab-ci.yml", "Makefile"],
        )

        template_file = tmp_path / "template.yml"
        original.to_yaml(template_file)

        loaded = RhizaTemplate.from_yaml(template_file)

        assert loaded.template_repository == original.template_repository
        assert loaded.template_branch == original.template_branch
        assert loaded.template_host == original.template_host
        assert loaded.include == original.include

    def test_rhiza_template_from_yaml_with_multiline_exclude(self, tmp_path):
        """Test loading a template.yml with multi-line string exclude field (using |)."""
        template_file = tmp_path / "template.yml"
        # This is the format users might write in YAML with the literal block scalar (|)
        template_file.write_text("""template-repository: ".tschm/.config-templates"
template-branch: "main"
exclude: |
  LICENSE
  README.md
  .github/CODEOWNERS
""")

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == ".tschm/.config-templates"
        assert template.template_branch == "main"
        assert template.exclude == ["LICENSE", "README.md", ".github/CODEOWNERS"]

    def test_rhiza_template_from_yaml_with_multiline_include(self, tmp_path):
        """Test loading a template.yml with multi-line string include field (using |)."""
        template_file = tmp_path / "template.yml"
        template_file.write_text("""template-repository: "test/repo"
template-branch: "main"
include: |
  .github
  Makefile
  src
""")

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "test/repo"
        assert template.include == [".github", "Makefile", "src"]

    def test_rhiza_template_round_trip_multiline_exclude(self, tmp_path):
        """Test that multi-line exclude is properly saved as a YAML list."""
        template_file = tmp_path / "template.yml"
        # Write with multi-line string format
        template_file.write_text("""template-repository: ".tschm/.config-templates"
template-branch: "main"
exclude: |
  LICENSE
  README.md
  .github/CODEOWNERS
""")

        # Load and save
        template = RhizaTemplate.from_yaml(template_file)
        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)

        # Reload and verify
        reloaded = RhizaTemplate.from_yaml(output_file)
        assert reloaded.exclude == ["LICENSE", "README.md", ".github/CODEOWNERS"]

        # Verify the saved file uses proper YAML list format
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert config["exclude"] == ["LICENSE", "README.md", ".github/CODEOWNERS"]
        assert isinstance(config["exclude"], list)

    def test_normalize_to_list_with_unexpected_type(self, tmp_path):
        """Test that _normalize_to_list handles unexpected types gracefully."""
        from rhiza.models import _normalize_to_list

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

    def test_rhiza_template_to_yaml_without_repository(self, tmp_path):
        """Test that to_yaml works when template_repository is None."""
        template = RhizaTemplate(
            template_repository=None,
            template_branch="main",
            include=[".github"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        # template-repository should not be present when None
        assert "template-repository" not in config
        assert config["template-branch"] == "main"

    def test_rhiza_template_with_templates(self, tmp_path):
        """Test loading template.yml with templates field."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "templates": ["core", "tests", "github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "jebel-quant/rhiza"
        assert template.template_branch == "main"
        assert template.templates == ["core", "tests", "github"]
        assert template.include == []

    def test_rhiza_template_to_yaml_with_templates(self, tmp_path):
        """Test saving a RhizaTemplate with templates field."""
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            templates=["core", "tests", "docs"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"
        assert config["template-branch"] == "main"
        assert config["templates"] == ["core", "tests", "docs"]
        assert "include" not in config

    def test_rhiza_template_hybrid_mode(self, tmp_path):
        """Test template.yml with both templates and include fields."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "templates": ["core", "tests"],
            "include": [".custom", "extra/"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.templates == ["core", "tests"]
        assert template.include == [".custom", "extra/"]

    def test_rhiza_template_to_yaml_hybrid_mode(self, tmp_path):
        """Test saving a RhizaTemplate with both templates and include."""
        template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            templates=["core", "tests"],
            include=[".custom", "extra/"],
        )

        template_file = tmp_path / "template.yml"
        template.to_yaml(template_file)

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["templates"] == ["core", "tests"]
        assert config["include"] == [".custom", "extra/"]

    def test_rhiza_template_accepts_repository_field(self, tmp_path):
        """Test that RhizaTemplate.from_yaml accepts 'repository' field."""
        template_file = tmp_path / "template.yml"
        config = {
            "repository": "owner/repo",  # Alternative field name
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "owner/repo"
        assert template.include == [".github"]

    def test_rhiza_template_accepts_ref_field(self, tmp_path):
        """Test that RhizaTemplate.from_yaml accepts 'ref' field."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "owner/repo",
            "ref": "develop",  # Alternative field name
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "owner/repo"
        assert template.template_branch == "develop"
        assert template.include == [".github"]

    def test_rhiza_template_accepts_repository_and_ref(self, tmp_path):
        """Test that RhizaTemplate.from_yaml accepts both 'repository' and 'ref' fields."""
        template_file = tmp_path / "template.yml"
        config = {
            "repository": "owner/repo",  # Alternative field name
            "ref": "main",  # Alternative field name
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "owner/repo"
        assert template.template_branch == "main"
        assert template.include == [".github"]

    def test_rhiza_template_prefers_template_repository_over_repository(self, tmp_path):
        """Test that 'template-repository' takes precedence over 'repository'."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "correct/repo",
            "repository": "wrong/repo",  # Should be ignored
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        # Should use template-repository, not repository
        assert template.template_repository == "correct/repo"

    def test_rhiza_template_prefers_template_branch_over_ref(self, tmp_path):
        """Test that 'template-branch' takes precedence over 'ref'."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "owner/repo",
            "template-branch": "correct",
            "ref": "wrong",  # Should be ignored
            "include": [".github"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        # Should use template-branch, not ref
        assert template.template_branch == "correct"

    def test_rhiza_template_repository_field_only(self, tmp_path):
        """Test using only 'repository' field without 'template-repository'."""
        template_file = tmp_path / "template.yml"
        config = {
            "repository": "owner/repo",
            "templates": ["core"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "owner/repo"
        assert template.templates == ["core"]

    def test_rhiza_template_ref_field_only(self, tmp_path):
        """Test using only 'ref' field without 'template-branch'."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "owner/repo",
            "ref": "v1.0.0",
            "templates": ["core"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        assert template.template_repository == "owner/repo"
        assert template.template_branch == "v1.0.0"

    def test_rhiza_template_empty_string_uses_default(self, tmp_path):
        """Test that empty string values are preserved (not falling back to alternative)."""
        template_file = tmp_path / "template.yml"
        config = {
            "template-repository": "",  # Empty string should be preserved
            "repository": "should-not-use-this",
            "templates": ["core"],
        }

        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)

        # Should preserve the empty string from template-repository, not fall back to repository
        assert template.template_repository == ""


class TestRhizaBundles:
    """Tests for the RhizaBundles dataclass."""

    def test_rhiza_bundles_invalid_bundle_type(self, tmp_path):
        """Test that RhizaBundles raises TypeError for non-dict bundle."""
        bundles_file = tmp_path / "template-bundles.yml"
        config = {
            "version": "1.0",
            "bundles": {
                "core": ["file1.yml", "file2.yml"],
            },
        }

        with open(bundles_file, "w") as f:
            yaml.dump(config, f)

        with pytest.raises(TypeError, match="Bundle 'core' must be a dictionary"):
            RhizaBundles.from_yaml(bundles_file)
