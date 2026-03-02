"""Tests for template-repository-based init functionality."""

from unittest.mock import patch

import yaml

from rhiza.commands.init import init


class TestInitWithTemplateRepository:
    """Tests for init command with template repository selection."""

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_with_go_template_repository(self, mock_check, tmp_path):
        """Test that init with go template repository creates correct config."""
        init(tmp_path, git_host="github", template_repository="jebel-quant/rhiza-go")

        # Verify template.yml was created with go repository
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        # The language parameter defaults to "python" internally; RhizaTemplate.to_yaml()
        # omits the language field when it equals the default "python" value.
        assert "language" not in config

    def test_init_with_python_template_repository(self, tmp_path):
        """Test that init with default python template repository creates Python structure."""
        init(tmp_path, git_host="github")

        # Verify template.yml was created WITHOUT language field (it's default)
        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza"
        # RhizaTemplate.to_yaml() omits the language field when it equals the
        # default "python" value, so no language key is written to the file.
        assert "language" not in config

        # Verify Python-specific structure
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src" / tmp_path.name).is_dir()
        assert (tmp_path / "README.md").exists()

    def test_init_defaults_to_python(self, tmp_path):
        """Test that init defaults to python when no template repository specified."""
        init(tmp_path, git_host="github")

        # Verify Python structure was created
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src").is_dir()

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_with_custom_template_repository(self, mock_check, tmp_path):
        """Test that custom template repository is stored correctly."""
        init(
            tmp_path,
            git_host="github",
            template_repository="custom/go-templates",
        )

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Custom repository should be set
        assert config["repository"] == "custom/go-templates"

    @patch("rhiza.commands.init._check_template_repository_reachable", return_value=True)
    def test_init_go_template_repository_with_gitlab(self, mock_check, tmp_path):
        """Test go template repository with GitLab hosting."""
        init(tmp_path, git_host="gitlab", template_repository="jebel-quant/rhiza-go")

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["repository"] == "jebel-quant/rhiza-go"
        # Should include gitlab in templates
        assert "gitlab" in config["templates"]
        assert "github" not in config["templates"]
