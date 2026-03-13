"""Tests for the validate command and CLI wiring.

This module verifies that `validate` checks `.rhiza/template.yml` and that
the Typer CLI entry `rhiza validate` behaves as expected across scenarios.
"""

import tempfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.validate import (
    _validate_include_paths,
    _validate_language_field,
    _validate_repository_format,
    _validate_required_fields,
    _validate_templates,
    validate,
)


@pytest.fixture
def git_path(tmp_path):
    """Create a temporary git repository."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    return tmp_path


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_fails_on_non_git_directory(self, tmp_path):
        """Test that validate fails when target is not a git repository."""
        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_missing_pyproject_toml(self, git_path):
        """Test that validate fails when pyproject.toml doesn't exist."""
        # Create git directory
        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_invalid_yaml_syntax(self, git_path):
        """Test that validate fails when template.yml has invalid YAML syntax."""
        (git_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        (rhiza_dir / "template.yml").write_text("key: [unclosed bracket\n")

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_empty_template(self, git_path):
        """Test that validate fails on empty template.yml."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create empty template
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("")

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_missing_required_fields(self, git_path):
        """Test that validate fails when required fields are missing."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template without required fields
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"some-field": "value"}, f)

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_invalid_repository_format(self, git_path):
        """Test that validate fails on invalid repository format."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with invalid repository format
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "invalid-repo-format",
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_empty_include_list(self, git_path):
        """Test that validate fails when include list is empty."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with empty include
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_succeeds_on_valid_template(self, git_path):
        """Test that validate succeeds on a valid template.yml."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "include": [".github", "Makefile"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_succeeds_with_exclude(self, git_path):
        """Test that validate succeeds with exclude list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template with exclude
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "template-branch": "dev",
                    "include": [".github"],
                    "exclude": ["tests"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_succeeds_with_migrated_location(self, git_path):
        """Test that validate succeeds when template.yml is in migrated .rhiza location."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template in migrated location (.rhiza/template.yml)
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "template-branch": "main",
                    "include": [".github", "Makefile"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_cli_validate_command(self, git_path):
        """Test the CLI validate command via Typer runner."""
        runner = CliRunner()

        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                },
                f,
            )

        result = runner.invoke(cli.app, ["validate", str(git_path)])
        assert result.exit_code == 0

    def test_validate_warns_on_missing_src_folder(self, git_path):
        """Test that validate warns when src folder doesn't exist."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                },
                f,
            )

        # Should still pass with warning (warnings don't fail validation)
        result = validate(git_path)
        assert result is True

    def test_validate_warns_on_missing_tests_folder(self, git_path):
        """Test that validate warns when tests folder doesn't exist."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create src folder but not tests folder
        src_dir = git_path / "src"
        src_dir.mkdir()

        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                },
                f,
            )

        # Should still pass with warning (warnings don't fail validation)
        result = validate(git_path)
        assert result is True

    def test_validate_succeeds_with_src_and_tests_folders(self, git_path):
        """Test that validate succeeds when both src and tests folders exist."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create src and tests folders
        src_dir = git_path / "src"
        src_dir.mkdir()
        tests_dir = git_path / "tests"
        tests_dir.mkdir()

        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_cli_validate_command_fails(self, git_path):
        """Test the CLI validate command fails on invalid template."""
        runner = CliRunner()

        # Setup git repo with invalid template (missing required fields)
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("{}")

        result = runner.invoke(cli.app, ["validate", str(git_path)])
        assert result.exit_code == 1

    def test_validate_fails_on_wrong_type_template_repository(self, git_path):
        """Test that validate fails when template-repository is not a string."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-repository
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": 12345,  # Should be string
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_wrong_type_include(self, git_path):
        """Test that validate fails when include is not a list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for include
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": "should-be-a-list",  # Should be list
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_warns_on_non_string_include_items(self, git_path):
        """Test that validate warns about non-string items in include list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with non-string items in include
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github", 123, "Makefile"],  # 123 is not a string
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_wrong_type_template_branch(self, git_path):
        """Test that validate warns when template-branch is not a string."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-branch
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                    "template-branch": 123,  # Should be string
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_wrong_type_exclude(self, git_path):
        """Test that validate warns when exclude is not a list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for exclude
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                    "exclude": "should-be-a-list",  # Should be list
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_non_string_exclude_items(self, git_path):
        """Test that validate warns about non-string items in exclude list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with non-string items in exclude
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "include": [".github"],
                    "exclude": ["tests", 456],  # 456 is not a string
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_gitlab_host(self, git_path):
        """Test that validate accepts gitlab as template-host."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with gitlab host
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "mygroup/myproject",
                    "template-host": "gitlab",
                    "include": [".gitlab-ci.yml"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_warns_on_invalid_host(self, git_path):
        """Test that validate warns about invalid template-host values."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with invalid host
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "template-host": "bitbucket",
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        # Should still pass with warning since template-host is optional
        assert result is True

    def test_validate_warns_on_wrong_type_template_host(self, git_path):
        """Test that validate warns about wrong type for template-host."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-host
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "template-host": 123,  # Should be string
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        # Should still pass with warning since template-host is optional
        assert result is True

    def test_validate_fails_when_template_missing(self, git_path):
        """Test that validate fails when template.yml is missing."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Don't create template.yml

        result = validate(git_path)
        assert result is False

    def test_validate_fails_with_old_bundles_field(self, git_path):
        """Test that validate fails when deprecated 'bundles' field is used."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with old "bundles" field
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "bundles": ["core", "tests"],  # Old field name
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_hybrid_mode_logging(self, git_path):
        """Test that validate logs 'hybrid mode' when both templates and include present."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with both templates and include
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "templates": ["core"],
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_template_only_mode_logging(self, git_path):
        """Test that validate logs 'template-based mode' when only templates present."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with only templates
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "templates": ["core"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_fails_on_empty_templates_list(self, git_path):
        """Test that validate fails when templates list is empty."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with empty templates list
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "templates": [],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_fails_on_templates_wrong_type(self, git_path):
        """Test that validate fails when templates is not a list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with templates as a string instead of list
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "templates": "core",  # Should be a list
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_warns_on_non_string_template_items(self, git_path):
        """Test that validate warns about non-string items in templates list."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with non-string template items
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "jebel-quant/rhiza",
                    "template-branch": "main",
                    "templates": ["core", 123, "tests"],  # 123 is not a string
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warning
        assert result is True

    def test_validate_accepts_repository_field(self, git_path):
        """Test that validate accepts 'repository' as alias for 'template-repository'."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with 'repository' instead of 'template-repository'
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "repository": "owner/repo",  # Alternative field name
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_accepts_ref_field(self, git_path):
        """Test that validate accepts 'ref' as alias for 'template-branch'."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with 'ref' instead of 'template-branch'
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "ref": "develop",  # Alternative field name
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_accepts_repository_and_ref_together(self, git_path):
        """Test that validate accepts both 'repository' and 'ref' together."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with both alternative field names
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "repository": "owner/repo",  # Alternative field name
                    "ref": "main",  # Alternative field name
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_prefers_template_repository_over_repository(self, git_path):
        """Test that 'template-repository' takes precedence over 'repository'."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with both field names (template-repository should win)
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "correct/repo",
                    "repository": "wrong/repo",  # This should be ignored
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_prefers_template_branch_over_ref(self, git_path):
        """Test that 'template-branch' takes precedence over 'ref'."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with both field names (template-branch should win)
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "template-repository": "owner/repo",
                    "template-branch": "correct",
                    "ref": "wrong",  # This should be ignored
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is True

    def test_validate_repository_field_invalid_format(self, git_path):
        """Test that validate fails when 'repository' has invalid format."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with invalid repository format
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "repository": "invalid-format",  # Missing slash
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        assert result is False

    def test_validate_ref_field_wrong_type(self, git_path):
        """Test that validate warns when 'ref' has wrong type."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for ref
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump(
                {
                    "repository": "owner/repo",
                    "ref": 123,  # Should be string
                    "include": [".github"],
                },
                f,
            )

        result = validate(git_path)
        # Should still pass but with warning
        assert result is True


class TestValidateHelperFunctions:
    """Tests that directly exercise private helper function edge-case branches."""

    def test_validate_templates_without_templates_key(self):
        """_validate_templates returns True when config has no 'templates' key (line 162)."""
        result = _validate_templates({"include": [".github"]})
        assert result is True

    def test_validate_templates_empty_list(self):
        """_validate_templates returns False for an empty templates list (lines 170-172)."""
        result = _validate_templates({"templates": []})
        assert result is False

    def test_validate_required_fields_missing_repo(self):
        """_validate_required_fields returns False when no repo field present (lines 203-205)."""
        result = _validate_required_fields({"include": [".github"]})
        assert result is False

    def test_validate_repository_format_no_repo_field(self):
        """_validate_repository_format returns True when no repo field present (line 239)."""
        result = _validate_repository_format({})
        assert result is True

    def test_validate_include_paths_without_include_key(self):
        """_validate_include_paths returns True when config has no 'include' key (line 266)."""
        result = _validate_include_paths({})
        assert result is True

    def test_validate_include_paths_empty_list(self):
        """_validate_include_paths returns False for an empty include list (lines 274-276)."""
        result = _validate_include_paths({"include": []})
        assert result is False

    def test_validate_language_non_string(self):
        """_validate_language_field warns when language is not a string (lines 339-340)."""
        # Should not raise — just logs a warning
        _validate_language_field({"language": 42})

    def test_validate_go_project_succeeds(self, git_path):
        """Test validation succeeds for Go project."""
        # Create go.mod
        go_mod_file = git_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        # Create template.yml with go language
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        result = validate(git_path)
        assert result is True

    def test_validate_go_project_fails_without_go_mod(self, git_path):
        """Test validation fails for Go project without go.mod."""
        # Create template.yml with go language but no go.mod
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "go", "include": [".github"]}, f)

        result = validate(git_path)
        assert result is False

    def test_validate_python_project_with_explicit_language(self, git_path):
        """Test validation succeeds for Python project with explicit language."""
        # Create pyproject.toml
        pyproject_file = git_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template.yml with explicit python language
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "python", "include": [".github"]}, f)

        result = validate(git_path)
        assert result is True

    def test_validate_with_unknown_language_succeeds(self, git_path):
        """Test validation with unknown language shows warning but doesn't fail."""
        # Create template.yml with unknown language
        rhiza_dir = git_path / ".rhiza"
        rhiza_dir.mkdir()
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"template-repository": "owner/repo", "language": "rust", "include": [".github"]}, f)

        # Should succeed but with warnings
        result = validate(git_path)
        assert result is True


class TestValidateCustomTemplatePath:
    """Tests for the validate() template_file parameter."""

    def test_validate_with_custom_template_file_outside_target(self, git_path, tmp_path):
        """validate() accepts a template file path outside the target directory.

        When the template file is at a path that cannot be made relative to
        *target*, validate() still displays and uses it correctly.
        """
        # Create a valid Python project structure.
        (git_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        # Write the template file *outside* git_path.
        external_config = tmp_path / "external" / "template.yml"
        external_config.parent.mkdir(parents=True)
        external_config.write_text("template-repository: owner/repo\ninclude:\n  - .github\n")

        result = validate(git_path, template_file=external_config)
        assert result is True

    def test_validate_fails_when_custom_template_file_missing_and_outside_target(self, git_path):
        """validate() reports the correct path when a custom template file is missing.

        When the template file lies outside *target* the ValueError branch in
        the path display logic (lines 75-76 in validate.py) is exercised.
        """
        # Create a valid Python project structure.
        (git_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        # Use a path in a completely unrelated temp directory (not a subpath of
        # git_path) so that Path.relative_to() raises ValueError, which exercises
        # lines 75-76 in validate.py.
        with tempfile.TemporaryDirectory() as unrelated_dir:
            external_missing = Path(unrelated_dir) / "nonexistent" / "template.yml"
            result = validate(git_path, template_file=external_missing)
        assert result is False
