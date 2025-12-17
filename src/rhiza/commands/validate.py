"""Command for validating Rhiza template configuration.

This module provides functionality to validate .github/template.yml files
to ensure they are syntactically correct and semantically valid.
"""

from pathlib import Path

import yaml
from loguru import logger


def validate(target: Path) -> bool:
    """Validate template.yml configuration in the target repository.

    Performs authoritative validation of the template configuration:
    - Checks if template.yml exists
    - Validates YAML syntax
    - Validates required fields
    - Validates field values are appropriate

    Parameters
    ----------
    target:
        Path to the target Git repository directory.

    Returns:
    -------
    bool
        True if validation passes, False otherwise.
    """
    # Convert to absolute path
    target = target.resolve()

    # Check if target is a git repository
    if not (target / ".git").is_dir():
        logger.error(f"Target directory is not a git repository: {target}")
        return False

    logger.info(f"Validating template configuration in: {target}")

    # Check if template.yml exists
    template_file = target / ".github" / "template.yml"
    if not template_file.exists():
        logger.error(f"Template file not found: {template_file}")
        logger.info("Run 'rhiza materialize' or 'rhiza inject' to create a default template.yml")
        return False

    logger.success(f"Found template file: {template_file}")

    # Validate YAML syntax
    try:
        with open(template_file) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML syntax in template.yml: {e}")
        return False

    if config is None:
        logger.error("template.yml is empty")
        return False

    logger.success("YAML syntax is valid")

    # Validate required fields
    required_fields = {
        "template-repository": str,
        "include": list,
    }

    validation_passed = True

    for field, expected_type in required_fields.items():
        if field not in config:
            logger.error(f"Missing required field: {field}")
            validation_passed = False
        elif not isinstance(config[field], expected_type):
            logger.error(
                f"Field '{field}' must be of type {expected_type.__name__}, got {type(config[field]).__name__}"
            )
            validation_passed = False
        else:
            logger.success(f"Field '{field}' is present and valid")

    # Validate template-repository format
    if "template-repository" in config:
        repo = config["template-repository"]
        if not isinstance(repo, str):
            logger.error(f"template-repository must be a string, got {type(repo).__name__}")
            validation_passed = False
        elif "/" not in repo:
            logger.error(f"template-repository must be in format 'owner/repo', got: {repo}")
            validation_passed = False
        else:
            logger.success(f"template-repository format is valid: {repo}")

    # Validate include paths
    if "include" in config:
        include = config["include"]
        if not isinstance(include, list):
            logger.error(f"include must be a list, got {type(include).__name__}")
            validation_passed = False
        elif len(include) == 0:
            logger.error("include list cannot be empty")
            validation_passed = False
        else:
            logger.success(f"include list has {len(include)} path(s)")
            for path in include:
                if not isinstance(path, str):
                    logger.warning(f"include path should be a string, got {type(path).__name__}: {path}")
                else:
                    logger.info(f"  - {path}")

    # Validate optional fields
    if "template-branch" in config:
        branch = config["template-branch"]
        if not isinstance(branch, str):
            logger.warning(f"template-branch should be a string, got {type(branch).__name__}: {branch}")
        else:
            logger.success(f"template-branch is valid: {branch}")

    if "exclude" in config:
        exclude = config["exclude"]
        if not isinstance(exclude, list):
            logger.warning(f"exclude should be a list, got {type(exclude).__name__}")
        else:
            logger.success(f"exclude list has {len(exclude)} path(s)")
            for path in exclude:
                if not isinstance(path, str):
                    logger.warning(f"exclude path should be a string, got {type(path).__name__}: {path}")
                else:
                    logger.info(f"  - {path}")

    # Final verdict
    if validation_passed:
        logger.success("✓ Validation passed: template.yml is valid")
        return True
    else:
        logger.error("✗ Validation failed: template.yml has errors")
        return False
