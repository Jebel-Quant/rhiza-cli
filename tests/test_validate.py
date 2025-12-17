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

        # Create invalid YAML
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"
        template_file.write_text("invalid: yaml: syntax: :")

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_empty_template(self, tmp_path):
        """Test that validate fails on empty template.yml."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create empty template
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"
        template_file.write_text("")

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_missing_required_fields(self, tmp_path):
        """Test that validate fails when required fields are missing."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template without required fields
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

        with open(template_file, "w") as f:
            yaml.dump({"some-field": "value"}, f)

        result = validate(tmp_path)
        assert result is False

    def test_validate_fails_on_invalid_repository_format(self, tmp_path):
        """Test that validate fails on invalid repository format."""
        # Setup git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create template with invalid repository format
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

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

        # Create template with empty include
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

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

        # Create valid template
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

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

        # Create valid template with exclude
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

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

    def test_cli_validate_command(self, tmp_path):
        """Test the CLI validate command via Typer runner."""
        runner = CliRunner()

        # Setup git repo with valid template
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"

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

    def test_cli_validate_command_fails(self, tmp_path):
        """Test the CLI validate command fails on invalid template."""
        runner = CliRunner()

        # Setup git repo with invalid template (missing required fields)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "template.yml"
        template_file.write_text("{}")

        result = runner.invoke(cli.app, ["validate", str(tmp_path)])
        assert result.exit_code == 1
