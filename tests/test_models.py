"""Tests for the RhizaTemplate dataclass and related models.

This module verifies that the RhizaTemplate dataclass correctly represents
and handles .rhiza/template.yml configuration.
"""

import pytest
import yaml

from rhiza.models import RhizaTemplate, TemplateLock


class TestRhizaTemplate:
    """Tests for the RhizaTemplate dataclass."""

    def test_rhiza_template_from_yaml(self, tmp_path):
        """Test loading RhizaTemplate from YAML with various field combinations."""
        # 1. Standard loading with 'template-repository', 'template-branch', and 'exclude'
        template_file = tmp_path / "template_std.yml"
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
        assert template.template_host == "github"  # Default
        assert template.language == "python"  # Default

        # 2. Loading with aliases 'repository' and 'ref', and custom host/language
        template_file = tmp_path / "template_alt.yml"
        config = {
            "repository": "owner/repo",
            "ref": "v1.0.0",
            "template-host": "gitlab",
            "language": "go",
            "templates": ["core", "tests"],
        }
        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.template_repository == "owner/repo"
        assert template.template_branch == "v1.0.0"
        assert template.template_host == "gitlab"
        assert template.language == "go"
        assert template.templates == ["core", "tests"]

        # 3. Precedence: 'repository' over 'template-repository', 'ref' over 'template-branch'
        template_file = tmp_path / "template_precedence.yml"
        config = {
            "repository": "correct/repo",
            "template-repository": "wrong/repo",
            "ref": "correct-branch",
            "template-branch": "wrong-branch",
        }
        with open(template_file, "w") as f:
            yaml.dump(config, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.template_repository == "correct/repo"
        assert template.template_branch == "correct-branch"

        # 4. Fallback: null/empty primary fields use alternative fields
        template_file = tmp_path / "template_fallback.yml"
        template_file.write_text(
            "repository: null\ntemplate-repository: fallback/repo\nref: ''\ntemplate-branch: fallback-branch\n"
        )
        template = RhizaTemplate.from_yaml(template_file)
        assert template.template_repository == "fallback/repo"
        assert template.template_branch == "fallback-branch"

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
        """Test that to_yaml omits default fields and handles None/empty values."""
        # 1. Defaults (host=github, language=python) are excluded
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
        assert "template-host" not in config
        assert "language" not in config

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

        # 3. Optional fields (templates, include, exclude) are only included if non-empty
        template = RhizaTemplate(template_repository="owner/repo", include=["only"])
        template_file = tmp_path / "template_optional.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert "include" in config
        assert "templates" not in config
        assert "exclude" not in config

        # 4. None values (repository, branch) are excluded
        template = RhizaTemplate(template_repository=None, template_branch=None)
        template_file = tmp_path / "template_none.yml"
        template.to_yaml(template_file)
        with open(template_file) as f:
            config = yaml.safe_load(f)
        assert "repository" not in config
        assert "ref" not in config

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

    def test_rhiza_hybrid_mode(self, tmp_path):
        """Test template.yml with both templates and include fields (loading and saving)."""
        # 1. Loading
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

        # 2. Saving
        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)
        with open(output_file) as f:
            config = yaml.safe_load(f)
        assert config["templates"] == ["core", "tests"]
        assert config["include"] == [".custom", "extra/"]


class TestTemplateLock:
    """Tests for the TemplateLock dataclass."""

    def test_template_lock_to_yaml(self, tmp_path):
        """Test TemplateLock serialization: defaults, omissions, parent dir, and formatting."""
        # 1. Defaults and parent directory creation
        lock = TemplateLock(sha="abc123")
        lock_path = tmp_path / ".rhiza" / "template.lock"
        lock.to_yaml(lock_path)
        assert lock_path.exists()

        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["sha"] == "abc123"
        assert data["repo"] == ""
        assert data["host"] == "github"
        assert data["ref"] == "main"
        assert data["include"] == []
        assert data["exclude"] == []
        assert data["templates"] == []
        assert data["files"] == []
        assert "synced_at" not in data
        assert "strategy" not in data

        # 2. Professional formatting (header comment, document separator)
        raw = lock_path.read_text(encoding="utf-8")
        assert raw.startswith("# This file is automatically generated by rhiza. Do not edit it manually.\n---\n")

        # 3. Non-defaults: all fields including synced_at and strategy
        lock = TemplateLock(
            sha="abc123def456",
            repo="jebel-quant/rhiza",
            host="gitlab",
            ref="develop",
            include=[".github/", ".rhiza/"],
            exclude=["README.md"],
            templates=["core"],
            files=[".github/workflows/ci.yml"],
            synced_at="2026-02-26T12:00:00Z",
            strategy="merge",
        )
        lock.to_yaml(lock_path)
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert data["sha"] == "abc123def456"
        assert data["repo"] == "jebel-quant/rhiza"
        assert data["host"] == "gitlab"
        assert data["ref"] == "develop"
        assert data["include"] == [".github/", ".rhiza/"]
        assert data["exclude"] == ["README.md"]
        assert data["templates"] == ["core"]
        assert data["files"] == [".github/workflows/ci.yml"]
        assert data["synced_at"] == "2026-02-26T12:00:00Z"
        assert data["strategy"] == "merge"

    def test_template_lock_from_yaml(self, tmp_path):
        """Test TemplateLock deserialization: structured, legacy SHA, and missing fields."""
        lock_path = tmp_path / "template.lock"

        # 1. Structured format (full)
        lock_path.write_text(
            "sha: abc123def456\nrepo: jebel-quant/rhiza\nhost: github\nref: main\n"
            "include:\n- .github/\n- .rhiza/\nexclude: []\ntemplates: []\n"
            "files:\n- .github/workflows/ci.yml\n",
            encoding="utf-8",
        )
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.sha == "abc123def456"
        assert lock.repo == "jebel-quant/rhiza"
        assert lock.include == [".github/", ".rhiza/"]
        assert lock.files == [".github/workflows/ci.yml"]

        # 2. Legacy plain-SHA format
        lock_path.write_text("abc123def456\n", encoding="utf-8")
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.sha == "abc123def456"
        assert lock.repo == ""
        assert lock.host == "github"  # default
        assert lock.ref == "main"  # default

        # 3. Missing optional fields in structured format
        lock_path.write_text("sha: abc789\nhost: gitlab\n", encoding="utf-8")
        lock = TemplateLock.from_yaml(lock_path)
        assert lock.sha == "abc789"
        assert lock.host == "gitlab"
        assert lock.ref == "main"  # default fallback
        assert lock.files == []
        assert lock.synced_at == ""

    def test_template_lock_round_trip(self, tmp_path):
        """Test that to_yaml then from_yaml preserves all fields."""
        original = TemplateLock(
            sha="abc123def456",
            repo="jebel-quant/rhiza",
            host="gitlab",
            ref="develop",
            include=[".github/", ".rhiza/"],
            exclude=["README.md"],
            templates=["core"],
            files=[".github/workflows/ci.yml"],
            synced_at="2026-02-26T12:00:00Z",
            strategy="merge",
        )
        lock_path = tmp_path / "template.lock"
        original.to_yaml(lock_path)
        loaded = TemplateLock.from_yaml(lock_path)
        assert loaded == original

    def test_template_lock_from_yaml_invalid_format(self, tmp_path):
        """from_yaml raises TypeError when the lock data is neither str nor dict."""
        lock_path = tmp_path / "template.lock"
        lock_path.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(TypeError, match=r"Invalid template\.lock format"):
            TemplateLock.from_yaml(lock_path)
