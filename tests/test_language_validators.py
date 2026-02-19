"""Tests for language-specific validation."""

from rhiza.language_validators import (
    GoValidator,
    LanguageValidatorRegistry,
    PythonValidator,
    get_validator_registry,
)


class TestPythonValidator:
    """Tests for Python project validation."""

    def test_python_validator_name(self):
        """Test Python validator returns correct language name."""
        validator = PythonValidator()
        assert validator.get_language_name() == "python"

    def test_python_validator_with_pyproject_toml(self, tmp_path):
        """Test Python validator succeeds with pyproject.toml."""
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        validator = PythonValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is True

    def test_python_validator_without_pyproject_toml(self, tmp_path):
        """Test Python validator fails without pyproject.toml."""
        validator = PythonValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is False

    def test_python_validator_with_all_directories(self, tmp_path):
        """Test Python validator with all standard directories."""
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        src_dir = tmp_path / "src"
        src_dir.mkdir()

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        validator = PythonValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is True


class TestGoValidator:
    """Tests for Go project validation."""

    def test_go_validator_name(self):
        """Test Go validator returns correct language name."""
        validator = GoValidator()
        assert validator.get_language_name() == "go"

    def test_go_validator_with_go_mod(self, tmp_path):
        """Test Go validator succeeds with go.mod."""
        go_mod_file = tmp_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        validator = GoValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is True

    def test_go_validator_without_go_mod(self, tmp_path):
        """Test Go validator fails without go.mod."""
        validator = GoValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is False

    def test_go_validator_with_all_directories(self, tmp_path):
        """Test Go validator with all standard directories."""
        go_mod_file = tmp_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        cmd_dir = tmp_path / "cmd"
        cmd_dir.mkdir()

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()

        validator = GoValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is True

    def test_go_validator_with_internal_directory(self, tmp_path):
        """Test Go validator with internal directory."""
        go_mod_file = tmp_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        internal_dir = tmp_path / "internal"
        internal_dir.mkdir()

        validator = GoValidator()
        result = validator.validate_project_structure(tmp_path)
        assert result is True


class TestLanguageValidatorRegistry:
    """Tests for language validator registry."""

    def test_registry_has_default_validators(self):
        """Test registry is initialized with default validators."""
        registry = LanguageValidatorRegistry()
        supported = registry.get_supported_languages()

        assert "python" in supported
        assert "go" in supported

    def test_registry_get_python_validator(self):
        """Test getting Python validator from registry."""
        registry = LanguageValidatorRegistry()
        validator = registry.get_validator("python")

        assert validator is not None
        assert isinstance(validator, PythonValidator)

    def test_registry_get_go_validator(self):
        """Test getting Go validator from registry."""
        registry = LanguageValidatorRegistry()
        validator = registry.get_validator("go")

        assert validator is not None
        assert isinstance(validator, GoValidator)

    def test_registry_get_unknown_validator(self):
        """Test getting unknown validator returns None."""
        registry = LanguageValidatorRegistry()
        validator = registry.get_validator("rust")

        assert validator is None

    def test_registry_case_insensitive(self):
        """Test registry is case insensitive."""
        registry = LanguageValidatorRegistry()

        validator_lower = registry.get_validator("python")
        validator_upper = registry.get_validator("PYTHON")
        validator_mixed = registry.get_validator("Python")

        assert validator_lower is not None
        assert validator_upper is not None
        assert validator_mixed is not None

    def test_get_validator_registry_singleton(self):
        """Test get_validator_registry returns singleton instance."""
        registry1 = get_validator_registry()
        registry2 = get_validator_registry()

        assert registry1 is registry2


class TestLanguageIntegration:
    """Integration tests for language validation."""

    def test_validate_python_project(self, tmp_path):
        """Test validating a complete Python project."""
        # Create Python project structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[project]\nname = 'test'\n")

        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Use validator
        registry = get_validator_registry()
        validator = registry.get_validator("python")
        result = validator.validate_project_structure(tmp_path)

        assert result is True

    def test_validate_go_project(self, tmp_path):
        """Test validating a complete Go project."""
        # Create Go project structure
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        go_mod_file = tmp_path / "go.mod"
        go_mod_file.write_text("module example.com/myproject\n\ngo 1.20\n")

        cmd_dir = tmp_path / "cmd"
        cmd_dir.mkdir()

        # Use validator
        registry = get_validator_registry()
        validator = registry.get_validator("go")
        result = validator.validate_project_structure(tmp_path)

        assert result is True
