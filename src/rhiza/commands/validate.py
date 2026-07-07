"""Command for validating Rhiza template configuration.

This module provides functionality to validate template.yml files in the
.rhiza/template.yml location (new standard location after migration).
"""

from pathlib import Path
from typing import Any

from loguru import logger

from rhiza.commands._validate_helpers import (
    _check_git_repository,
    _check_project_structure,
    _check_template_file_exists,
    _parse_yaml_file,
    _validate_configuration_mode,
    _validate_include_paths,
    _validate_language_field,
    _validate_optional_fields,
    _validate_repository_format,
    _validate_required_fields,
    _validate_templates,
)

# ``_validate_language_field`` is re-exported for the test suite, which imports the
# individual field validators from this module's historical location.
__all__ = [
    "_validate_configuration_mode",
    "_validate_include_paths",
    "_validate_language_field",
    "_validate_repository_format",
    "_validate_required_fields",
    "validate",
]


def validate(target: Path, template_file: Path | None = None) -> bool:
    """Validate template.yml configuration in the target repository.

    Performs authoritative validation of the template configuration:
    - Checks if target is a git repository
    - Checks for language-specific project structure
    - Checks if template.yml exists
    - Validates YAML syntax
    - Validates required fields
    - Validates field values are appropriate

    Args:
        target: Path to the target Git repository directory.
        template_file: Optional explicit path to the template file.  When
            ``None`` the default ``<target>/.rhiza/template.yml`` is used.

    Returns:
        True if validation passes, False otherwise.
    """
    target = target.resolve()
    logger.info(f"Validating template configuration in: {target}")

    config = _run_preflight_checks(target, template_file)
    if config is None:
        return False

    validation_passed = _validate_config_fields(config)

    # Final verdict
    logger.debug("Validation complete, determining final result")
    if validation_passed:
        logger.success("✓ Validation passed: template.yml is valid")
        return True
    logger.error("✗ Validation failed: template.yml has errors")
    logger.error("Fix the errors above and run 'rhiza validate' again")
    return False


def _run_preflight_checks(target: Path, template_file: Path | None) -> dict[str, Any] | None:
    """Run early-exit structural checks; return the parsed config, or None on failure."""
    # Check if target is a git repository
    if not _check_git_repository(target):
        return None

    # Check for template file first to get the language
    exists, template_file = _check_template_file_exists(target, template_file)
    if not exists:
        return None

    # Parse YAML file
    success, config = _parse_yaml_file(template_file)
    if not success or config is None:
        return None

    # Get the language from config (default to "python" for backward compatibility)
    language = config.get("language", "python")
    logger.info(f"Project language: {language}")

    # Check for language-specific project structure
    if not _check_project_structure(target, language):
        return None

    # Validate configuration mode (templates OR include)
    if not _validate_configuration_mode(config):
        return None

    return config


def _validate_config_fields(config: dict[str, Any]) -> bool:
    """Validate all fields (non-short-circuiting so every error surfaces); True when all pass."""
    # Validate required fields
    validation_passed = _validate_required_fields(config)

    # Validate specific field formats
    if not _validate_repository_format(config):
        validation_passed = False

    # Validate templates if present
    if config.get("templates") and not _validate_templates(config):
        validation_passed = False

    # Validate include if present
    if config.get("include") and not _validate_include_paths(config):
        validation_passed = False

    # Validate optional fields
    _validate_optional_fields(config)

    return validation_passed
