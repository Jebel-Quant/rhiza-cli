"""Tests for template.yml language field support."""

import yaml

from rhiza.commands.validate import validate
from rhiza.models import RhizaTemplate


class TestLanguageFieldInTemplate:
    """Tests for language field in template.yml."""

    def test_template_with_python_language(self, tmp_path):
        """Test template with explicit python language."""
        template_file = tmp_path / "template.yml"
        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "python", "include": [".github"]}, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.language == "python"

    def test_template_with_go_language(self, tmp_path):
        """Test template with go language."""
        template_file = tmp_path / "template.yml"
        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.language == "go"

    def test_template_defaults_to_python(self, tmp_path):
        """Test template defaults to python when language not specified."""
        template_file = tmp_path / "template.yml"
        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "include": [".github"]}, f)

        template = RhizaTemplate.from_yaml(template_file)
        assert template.language == "python"

    def test_template_to_yaml_excludes_default_python(self, tmp_path):
        """Test template.to_yaml excludes default python language."""
        template = RhizaTemplate(template_repository="owner/repo", language="python", include=[".github"])

        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)

        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Should not include "python" since it's the default
        assert "language" not in config

    def test_template_to_yaml_includes_non_default_language(self, tmp_path):
        """Test template.to_yaml includes non-default language."""
        template = RhizaTemplate(template_repository="owner/repo", language="go", include=[".github"])

        output_file = tmp_path / "output.yml"
        template.to_yaml(output_file)

        with open(output_file) as f:
            config = yaml.safe_load(f)

        assert config["language"] == "go"

    def test_template_roundtrip_with_go_language(self, tmp_path):
        """Test roundtrip conversion with go language."""
        input_file = tmp_path / "input.yml"
        output_file = tmp_path / "output.yml"

        with open(input_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        template = RhizaTemplate.from_yaml(input_file)
        template.to_yaml(output_file)

        with open(output_file) as f:
            config = yaml.safe_load(f)

        assert config["language"] == "go"


class TestValidateWithLanguageField:
    """Tests for validation with language field."""

    def test_validate_go_project_succeeds(self, tmp_path):
        """Test validation succeeds for Go project."""
        # Setup git repository
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create go.mod
        go_mod_file = tmp_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        # Create template.yml with go language
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        result = validate(tmp_path)
        assert result is True

    def test_validate_go_project_fails_without_go_mod(self, tmp_path):
        """Test validation fails for Go project without go.mod."""
        # Setup git repository
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with go language but no go.mod
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        result = validate(tmp_path)
        assert result is False

    def test_validate_python_project_with_explicit_language(self, tmp_path):
        """Test validation succeeds for Python project with explicit language."""
        # Setup git repository
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with explicit python language
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "python", "include": [".github"]}, f)

        result = validate(tmp_path)
        assert result is True

    def test_validate_with_unknown_language(self, tmp_path):
        """Test validation with unknown language shows warning but doesn't fail."""
        # Setup git repository
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template.yml with unknown language
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "rust", "include": [".github"]}, f)

        # Should succeed but with warnings
        result = validate(tmp_path)
        assert result is True

    def test_validate_backward_compatible_without_language(self, tmp_path):
        """Test validation is backward compatible (defaults to Python)."""
        # Setup git repository
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml for Python
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml WITHOUT language field
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "include": [".github"]}, f)

        result = validate(tmp_path)
        assert result is True
