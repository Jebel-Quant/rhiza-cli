"""Tests for the validate command and CLI wiring.

This module verifies that `validate` checks `.rhiza/template.yml` and that
the Typer CLI entry `rhiza validate` behaves as expected across scenarios.
"""

import yaml
from typer.testing import CliRunner

from rhiza import cli
from rhiza.commands.validate import validate


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_fails_on_non_git_directory(self, tmp_path):
        """Test that validate fails when target is not a git repository."""
        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_missing_pyproject_toml(self, tmp_path):
        """Test that validate fails when pyproject.toml doesn't exist."""
        # Create git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_missing_template_yml(self, tmp_path):
        """Test that validate fails when template.yml doesn't exist."""
        # Create git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_invalid_yaml(self, tmp_path):
        """Test that validate fails on invalid YAML syntax."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create invalid YAML
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("invalid: yaml: syntax: :")

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_empty_template(self, tmp_path):
        """Test that validate fails on empty template.yml."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create empty template
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("")

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_missing_required_fields(self, tmp_path):
        """Test that validate fails when required fields are missing."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template without required fields
        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"some-field": "value"}, f)

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_invalid_repository_format(self, tmp_path):
        """Test that validate fails on invalid repository format."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with invalid repository format
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_empty_include_list(self, tmp_path):
        """Test that validate fails when include list is empty."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with empty include
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is False

    def test_validate_succeeds_on_valid_template(self, tmp_path):
        """Test that validate succeeds on a valid template.yml."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is True

    def test_validate_succeeds_with_exclude(self, tmp_path):
        """Test that validate succeeds with exclude list."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template with exclude
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is True

    def test_validate_succeeds_with_migrated_location(self, tmp_path):
        """Test that validate succeeds when template.yml is in migrated .rhiza location."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create valid template in migrated location (.rhiza/template.yml)
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is True

    def test_cli_validate_command(self, tmp_path):
        """Test the CLI validate command via Typer runner."""
        runner = CliRunner()

        # Setup git repo with valid template
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        rhiza_dir = tmp_path / ".rhiza"
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

        result = runner.invoke(cli.app, ["validate", str(tmp_path)])
        assert result.exit_code == 0

    def test_validate_warns_on_missing_src_folder(self, tmp_path):
        """Test that validate warns when src folder doesn't exist."""
        # Setup git repo with valid template but no src folder
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        rhiza_dir = tmp_path / ".rhiza"
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
        result = validate(tmp_path)
        assert result is True

    def test_validate_warns_on_missing_tests_folder(self, tmp_path):
        """Test that validate warns when tests folder doesn't exist."""
        # Setup git repo with valid template but no tests folder
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create src folder but not tests folder
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        rhiza_dir = tmp_path / ".rhiza"
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
        result = validate(tmp_path)
        assert result is True

    def test_validate_succeeds_with_src_and_tests_folders(self, tmp_path):
        """Test that validate succeeds when both src and tests folders exist."""
        # Setup git repo with valid template and proper structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create src and tests folders
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is True

    def test_cli_validate_command_fails(self, tmp_path):
        """Test the CLI validate command fails on invalid template."""
        runner = CliRunner()

        # Setup git repo with invalid template (missing required fields)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        rhiza_dir = tmp_path / ".rhiza"
        rhiza_dir.mkdir(parents=True)
        template_file = rhiza_dir / "template.yml"
        template_file.write_text("{}")

        result = runner.invoke(cli.app, ["validate", str(tmp_path)])
        assert result.exit_code == 1

    def test_validate_fails_on_wrong_type_template_repository(self, tmp_path):
        """Test that validate fails when template-repository is not a string."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-repository
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_wrong_type_include(self, tmp_path):
        """Test that validate fails when include is not a list."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for include
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is False

    def test_validate_warns_on_non_string_include_items(self, tmp_path):
        """Test that validate warns about non-string items in include list."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with non-string items in include
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_wrong_type_template_branch(self, tmp_path):
        """Test that validate warns when template-branch is not a string."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-branch
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_wrong_type_exclude(self, tmp_path):
        """Test that validate warns when exclude is not a list."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for exclude
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_warns_on_non_string_exclude_items(self, tmp_path):
        """Test that validate warns about non-string items in exclude list."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with non-string items in exclude
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass but with warnings
        assert result is True

    def test_validate_gitlab_host(self, tmp_path):
        """Test that validate accepts gitlab as template-host."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with gitlab host
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        assert result is True

    def test_validate_warns_on_invalid_host(self, tmp_path):
        """Test that validate warns about invalid template-host values."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with invalid host
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass with warning since template-host is optional
        assert result is True

    def test_validate_warns_on_wrong_type_template_host(self, tmp_path):
        """Test that validate warns about wrong type for template-host."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Create template with wrong type for template-host
        rhiza_dir = tmp_path / ".rhiza"
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

        result = validate(tmp_path)
        # Should still pass with warning since template-host is optional
        assert result is True

    def test_validate_fails_when_template_missing(self, tmp_path):
        """Test that validate fails when template.yml is missing."""
        # Setup git repo with pyproject.toml but no template.yml
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create pyproject.toml
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        # Don't create template.yml

        result = validate(tmp_path)
        assert result is False
