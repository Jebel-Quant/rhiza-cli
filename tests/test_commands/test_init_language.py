"""Tests for language-specific init functionality."""

import yaml

from rhiza.commands.init import init


class TestInitWithLanguage:
    """Tests for init command with language parameter."""

    def test_init_with_go_language(self, tmp_path):
        """Test that init with go language creates Go-specific structure."""
        init(tmp_path, git_host="github", language="go")

        # Verify template.yml was created with go language
        template_file = tmp_path / ".rhiza" / "template.yml"
        assert template_file.exists()

        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"

        # Verify Go-specific structure was NOT created (user should run go mod init)
        assert not (tmp_path / "go.mod").exists()
        assert not (tmp_path / "src").exists()
        assert not (tmp_path / "pyproject.toml").exists()

        # Only README should be created
        assert (tmp_path / "README.md").exists()

    def test_init_with_python_language_explicit(self, tmp_path):
        """Test that init with explicit python language creates Python structure."""
        init(tmp_path, git_host="github", language="python")

        # Verify template.yml was created WITHOUT language field (it's default)
        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza"
        # Language field should not be in config (it's the default)
        assert "language" not in config

        # Verify Python-specific structure
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src" / tmp_path.name).is_dir()
        assert (tmp_path / "README.md").exists()

    def test_init_defaults_to_python(self, tmp_path):
        """Test that init defaults to python when no language specified."""
        init(tmp_path, git_host="github")

        # Verify Python structure was created
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src").is_dir()

    def test_init_go_with_custom_template_repository(self, tmp_path):
        """Test that custom template repository works with Go language."""
        init(
            tmp_path,
            git_host="github",
            language="go",
            template_repository="custom/go-templates",
        )

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        # Custom repository should override default
        assert config["template-repository"] == "custom/go-templates"
        assert config["language"] == "go"

    def test_init_unknown_language(self, tmp_path):
        """Test that init handles unknown languages gracefully."""
        init(tmp_path, git_host="github", language="rust")

        # Should create minimal structure
        assert (tmp_path / ".rhiza" / "template.yml").exists()
        assert (tmp_path / "README.md").exists()

        # Should not create language-specific files
        assert not (tmp_path / "pyproject.toml").exists()
        assert not (tmp_path / "go.mod").exists()

        # Verify template.yml
        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["language"] == "rust"
        # Should use default Python repository since no mapping exists
        assert config["template-repository"] == "jebel-quant/rhiza"

    def test_init_go_language_with_gitlab(self, tmp_path):
        """Test Go init with GitLab hosting."""
        init(tmp_path, git_host="gitlab", language="go")

        template_file = tmp_path / ".rhiza" / "template.yml"
        with open(template_file) as f:
            config = yaml.safe_load(f)

        assert config["template-repository"] == "jebel-quant/rhiza-go"
        assert config["language"] == "go"
        # Should include gitlab in templates
        assert "gitlab" in config["templates"]
        assert "github" not in config["templates"]
