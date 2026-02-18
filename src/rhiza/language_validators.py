"""Language-specific validation for Rhiza projects.

This module provides a framework for validating project structure based on
the programming language. Different languages have different requirements
(e.g., Python needs pyproject.toml, Go needs go.mod).
"""

from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger


class LanguageValidator(ABC):
    """Abstract base class for language-specific validators."""

    @abstractmethod
    def validate_project_structure(self, target: Path) -> bool:
        """Validate language-specific project structure.

        Args:
            target: Path to the project root.

        Returns:
            True if validation passes, False otherwise.
        """
        pass

    @abstractmethod
    def get_language_name(self) -> str:
        """Get the name of the language this validator handles.

        Returns:
            Language name (e.g., "python", "go").
        """
        pass


class PythonValidator(LanguageValidator):
    """Validator for Python projects."""

    def get_language_name(self) -> str:
        """Get the language name."""
        return "python"

    def validate_project_structure(self, target: Path) -> bool:
        """Validate Python project structure.

        Checks for:
        - pyproject.toml (required)
        - src directory (warning if missing)
        - tests directory (warning if missing)

        Args:
            target: Path to the project root.

        Returns:
            True if validation passes, False otherwise.
        """
        validation_passed = True

        # Check for pyproject.toml (required)
        pyproject_file = target / "pyproject.toml"
        if not pyproject_file.exists():
            logger.error(f"pyproject.toml not found: {pyproject_file}")
            logger.error("pyproject.toml is required for Python projects")
            logger.info("Run 'rhiza init' to create a default pyproject.toml")
            validation_passed = False
        else:
            logger.success(f"pyproject.toml exists: {pyproject_file}")

        # Check for standard directories (warnings only)
        src_dir = target / "src"
        tests_dir = target / "tests"

        if not src_dir.exists():
            logger.warning(f"Standard 'src' folder not found: {src_dir}")
            logger.warning("Consider creating a 'src' directory for source code")
        else:
            logger.success(f"'src' folder exists: {src_dir}")

        if not tests_dir.exists():
            logger.warning(f"Standard 'tests' folder not found: {tests_dir}")
            logger.warning("Consider creating a 'tests' directory for test files")
        else:
            logger.success(f"'tests' folder exists: {tests_dir}")

        return validation_passed


class GoValidator(LanguageValidator):
    """Validator for Go projects."""

    def get_language_name(self) -> str:
        """Get the language name."""
        return "go"

    def validate_project_structure(self, target: Path) -> bool:
        """Validate Go project structure.

        Checks for:
        - go.mod (required)
        - cmd directory (warning if missing)
        - pkg or internal directory (warning if missing)

        Args:
            target: Path to the project root.

        Returns:
            True if validation passes, False otherwise.
        """
        validation_passed = True

        # Check for go.mod (required)
        go_mod_file = target / "go.mod"
        if not go_mod_file.exists():
            logger.error(f"go.mod not found: {go_mod_file}")
            logger.error("go.mod is required for Go projects")
            logger.info("Run 'go mod init <module-name>' to create go.mod")
            validation_passed = False
        else:
            logger.success(f"go.mod exists: {go_mod_file}")

        # Check for standard directories (warnings only)
        cmd_dir = target / "cmd"
        pkg_dir = target / "pkg"
        internal_dir = target / "internal"

        if not cmd_dir.exists():
            logger.warning(f"Standard 'cmd' folder not found: {cmd_dir}")
            logger.warning("Consider creating a 'cmd' directory for main applications")
        else:
            logger.success(f"'cmd' folder exists: {cmd_dir}")

        if not pkg_dir.exists() and not internal_dir.exists():
            logger.warning("Neither 'pkg' nor 'internal' folder found")
            logger.warning("Consider creating 'pkg' for public libraries or 'internal' for private packages")
        else:
            if pkg_dir.exists():
                logger.success(f"'pkg' folder exists: {pkg_dir}")
            if internal_dir.exists():
                logger.success(f"'internal' folder exists: {internal_dir}")

        return validation_passed


class LanguageValidatorRegistry:
    """Registry for language validators."""

    def __init__(self):
        """Initialize the registry with default validators."""
        self._validators: dict[str, LanguageValidator] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default language validators."""
        self.register(PythonValidator())
        self.register(GoValidator())

    def register(self, validator: LanguageValidator) -> None:
        """Register a language validator.

        Args:
            validator: The validator to register.
        """
        language_name = validator.get_language_name()
        self._validators[language_name] = validator
        logger.debug(f"Registered validator for language: {language_name}")

    def get_validator(self, language: str) -> LanguageValidator | None:
        """Get a validator for the specified language.

        Args:
            language: The language name (e.g., "python", "go").

        Returns:
            The validator for the language, or None if not found.
        """
        return self._validators.get(language.lower())

    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages.

        Returns:
            List of supported language names.
        """
        return list(self._validators.keys())


# Global registry instance
_registry = LanguageValidatorRegistry()


def get_validator_registry() -> LanguageValidatorRegistry:
    """Get the global validator registry.

    Returns:
        The global validator registry instance.
    """
    return _registry
