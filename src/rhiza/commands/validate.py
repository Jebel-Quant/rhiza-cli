"""Command for validating Rhiza template configuration.

This module provides functionality to validate template.yml files in the
.rhiza/template.yml location (new standard location after migration).
"""

from pathlib import Path

import yaml
from loguru import logger


def _check_git_repository(target: Path) -> bool:
    """Check if target is a git repository.

    Args:
        target: Path to check.

    Returns:
        True if valid git repository, False otherwise.
    """
    if not (target / ".git").is_dir():
        logger.error(f"Target directory is not a git repository: {target}")
        logger.error("Initialize a git repository with 'git init' first")
        return False
    return True


def _check_project_structure(target: Path) -> None:
    """Check for standard project structure.

    Args:
        target: Path to project.
    """
    logger.debug("Validating project structure")
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


def _check_pyproject_toml(target: Path) -> bool:
    """Check for pyproject.toml file.

    Args:
        target: Path to project.

    Returns:
        True if pyproject.toml exists, False otherwise.
    """
    logger.debug("Validating pyproject.toml")
    pyproject_file = target / "pyproject.toml"

    if not pyproject_file.exists():
        logger.error(f"pyproject.toml not found: {pyproject_file}")
        logger.error("pyproject.toml is required for Python projects")
        logger.info("Run 'rhiza init' to create a default pyproject.toml")
        return False
    else:
        logger.success(f"pyproject.toml exists: {pyproject_file}")
        return True


def _check_template_file_exists(target: Path) -> tuple[bool, Path]:
    """Check if template file exists.

    Args:
        target: Path to project.

    Returns:
        Tuple of (exists, template_file_path).
    """
    template_file = target / ".rhiza" / "template.yml"

    if not template_file.exists():
        logger.error(f"No template file found at: {template_file.relative_to(target)}")
        logger.error("The template configuration must be in the .rhiza folder.")
        logger.info("")
        logger.info("To fix this:")
        logger.info("  • If you're starting fresh, run: rhiza init")
        logger.info("  • If you have an existing configuration, run: rhiza migrate")
        logger.info("")
        logger.info("The 'rhiza migrate' command will move your configuration from")
        logger.info("  the old location → .rhiza/template.yml")
        return False, template_file

    logger.success(f"Template file exists: {template_file.relative_to(target)}")
    return True, template_file


def _parse_yaml_file(template_file: Path) -> tuple[bool, dict | None]:
    """Parse YAML file and return configuration.

    Args:
        template_file: Path to template file.

    Returns:
        Tuple of (success, config_dict).
    """
    logger.debug(f"Parsing YAML file: {template_file}")
    try:
        with open(template_file) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML syntax in template.yml: {e}")
        logger.error("Fix the YAML syntax errors and try again")
        return False, None

    if config is None:
        logger.error("template.yml is empty")
        logger.error("Add configuration to template.yml or run 'rhiza init' to generate defaults")
        return False, None

    logger.success("YAML syntax is valid")
    return True, config


def _validate_required_fields(config: dict) -> bool:
    """Validate required fields exist and have correct types.

    Args:
        config: Configuration dictionary.

    Returns:
        True if all validations pass, False otherwise.
    """
    logger.debug("Validating required fields")
    required_fields = {
        "template-repository": str,
        "include": list,
    }

    validation_passed = True

    for field, expected_type in required_fields.items():
        if field not in config:
            logger.error(f"Missing required field: {field}")
            logger.error(f"Add '{field}' to your template.yml")
            validation_passed = False
        elif not isinstance(config[field], expected_type):
            logger.error(
                f"Field '{field}' must be of type {expected_type.__name__}, got {type(config[field]).__name__}"
            )
            logger.error(f"Fix the type of '{field}' in template.yml")
            validation_passed = False
        else:
            logger.success(f"Field '{field}' is present and valid")

    return validation_passed


def _validate_repository_format(config: dict) -> bool:
    """Validate template-repository format.

    Args:
        config: Configuration dictionary.

    Returns:
        True if valid, False otherwise.
    """
    logger.debug("Validating template-repository format")
    if "template-repository" not in config:
        return True

    repo = config["template-repository"]
    if not isinstance(repo, str):
        logger.error(f"template-repository must be a string, got {type(repo).__name__}")
        logger.error("Example: 'owner/repository'")
        return False
    elif "/" not in repo:
        logger.error(f"template-repository must be in format 'owner/repo', got: {repo}")
        logger.error("Example: 'jebel-quant/rhiza'")
        return False
    else:
        logger.success(f"template-repository format is valid: {repo}")
        return True


def _validate_include_paths(config: dict) -> bool:
    """Validate include paths.

    Args:
        config: Configuration dictionary.

    Returns:
        True if valid, False otherwise.
    """
    logger.debug("Validating include paths")
    if "include" not in config:
        return True

    include = config["include"]
    if not isinstance(include, list):
        logger.error(f"include must be a list, got {type(include).__name__}")
        logger.error("Example: include: ['.github', '.gitignore']")
        return False
    elif len(include) == 0:
        logger.error("include list cannot be empty")
        logger.error("Add at least one path to materialize")
        return False
    else:
        logger.success(f"include list has {len(include)} path(s)")
        for path in include:
            if not isinstance(path, str):
                logger.warning(f"include path should be a string, got {type(path).__name__}: {path}")
            else:
                logger.info(f"  - {path}")
        return True


def _validate_optional_fields(config: dict) -> None:
    """Validate optional fields if present.

    Args:
        config: Configuration dictionary.
    """
    logger.debug("Validating optional fields")

    # template-branch
    if "template-branch" in config:
        branch = config["template-branch"]
        if not isinstance(branch, str):
            logger.warning(f"template-branch should be a string, got {type(branch).__name__}: {branch}")
            logger.warning("Example: 'main' or 'develop'")
        else:
            logger.success(f"template-branch is valid: {branch}")

    # template-host
    if "template-host" in config:
        host = config["template-host"]
        if not isinstance(host, str):
            logger.warning(f"template-host should be a string, got {type(host).__name__}: {host}")
            logger.warning("Must be 'github' or 'gitlab'")
        elif host not in ("github", "gitlab"):
            logger.warning(f"template-host should be 'github' or 'gitlab', got: {host}")
            logger.warning("Other hosts are not currently supported")
        else:
            logger.success(f"template-host is valid: {host}")

    # exclude
    if "exclude" in config:
        exclude = config["exclude"]
        if not isinstance(exclude, list):
            logger.warning(f"exclude should be a list, got {type(exclude).__name__}")
            logger.warning("Example: exclude: ['.github/workflows/ci.yml']")
        else:
            logger.success(f"exclude list has {len(exclude)} path(s)")
            for path in exclude:
                if not isinstance(path, str):
                    logger.warning(f"exclude path should be a string, got {type(path).__name__}: {path}")
                else:
                    logger.info(f"  - {path}")


def validate(target: Path) -> bool:
    """Validate template.yml configuration in the target repository.

    Performs authoritative validation of the template configuration:
    - Checks if target is a git repository
    - Checks for standard project structure (src and tests folders)
    - Checks for pyproject.toml (required)
    - Checks if template.yml exists
    - Validates YAML syntax
    - Validates required fields
    - Validates field values are appropriate

    Args:
        target: Path to the target Git repository directory.

    Returns:
        True if validation passes, False otherwise.
    """
    target = target.resolve()
    logger.info(f"Validating template configuration in: {target}")

    # Check if target is a git repository
    if not _check_git_repository(target):
        return False

    # Check for standard project structure
    _check_project_structure(target)

    # Check for pyproject.toml
    if not _check_pyproject_toml(target):
        return False

    # Check for template file
    exists, template_file = _check_template_file_exists(target)
    if not exists:
        return False

    # Parse YAML file
    success, config = _parse_yaml_file(template_file)
    if not success or config is None:
        return False

    # Validate required fields
    validation_passed = _validate_required_fields(config)

    # Validate specific field formats
    if not _validate_repository_format(config):
        validation_passed = False

    if not _validate_include_paths(config):
        validation_passed = False

    # Validate optional fields
    _validate_optional_fields(config)

    # Final verdict
    logger.debug("Validation complete, determining final result")
    if validation_passed:
        logger.success("✓ Validation passed: template.yml is valid")
        return True
    else:
        logger.error("✗ Validation failed: template.yml has errors")
        logger.error("Fix the errors above and run 'rhiza validate' again")
        return False
