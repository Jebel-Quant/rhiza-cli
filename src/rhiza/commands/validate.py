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


def _check_pyproject_toml(target: Path, lenient: bool = False) -> bool:
    """Check for pyproject.toml file.

    Args:
        target: Path to project.
        lenient: If True, missing pyproject.toml is a warning, not an error.
            Used during materialize when template will provide the file.

    Returns:
        True if pyproject.toml exists or lenient mode is enabled, False otherwise.
    """
    logger.debug("Validating pyproject.toml")
    pyproject_file = target / "pyproject.toml"

    if not pyproject_file.exists():
        if lenient:
            logger.warning(f"pyproject.toml not found: {pyproject_file}")
            logger.warning("pyproject.toml will be provided by the template")
            return True
        else:
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
        logger.info("  .github/rhiza/template.yml → .rhiza/template.yml")
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

    In exclude-only mode (exclude present but no include), the include field is not required.

    Args:
        config: Configuration dictionary.

    Returns:
        True if all validations pass, False otherwise.
    """
    logger.debug("Validating required fields")

    # Check if we're in exclude-only mode
    has_exclude = "exclude" in config and config["exclude"]
    is_exclude_only = has_exclude and ("include" not in config or not config.get("include"))

    validation_passed = True

    # template-repository is always required
    if "template-repository" not in config:
        logger.error("Missing required field: template-repository")
        logger.error("Add 'template-repository' to your template.yml")
        validation_passed = False
    elif not isinstance(config["template-repository"], str):
        logger.error(
            f"Field 'template-repository' must be of type str, got {type(config['template-repository']).__name__}"
        )
        logger.error("Fix the type of 'template-repository' in template.yml")
        validation_passed = False
    else:
        logger.success("Field 'template-repository' is present and valid")

    # include is required unless we're in exclude-only mode
    if not is_exclude_only:
        if "include" not in config:
            logger.error("Missing required field: include")
            logger.error("Add 'include' to your template.yml or use 'exclude' for exclude-only mode")
            validation_passed = False
        elif not isinstance(config["include"], list):
            logger.error(f"Field 'include' must be of type list, got {type(config['include']).__name__}")
            logger.error("Fix the type of 'include' in template.yml")
            validation_passed = False
        else:
            logger.success("Field 'include' is present and valid")
    else:
        logger.info("Using exclude-only mode (include field not required)")

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

    # Check if we have either include or exclude (at least one required)
    has_include = "include" in config and config["include"]
    has_exclude = "exclude" in config and config["exclude"]

    if not has_include and not has_exclude:
        logger.error("Must have either 'include' or 'exclude' paths in template.yml")
        logger.error("Add 'include' to specify which paths to materialize")
        logger.error("Or add 'exclude' to include all files except specified ones")
        return False

    if not has_include and has_exclude:
        # Exclude-only mode - valid
        logger.success("Using exclude-only mode (all files except excluded will be materialized)")
        return True

    if "include" not in config:
        return True

    include = config["include"]
    if not isinstance(include, list):
        logger.error(f"include must be a list, got {type(include).__name__}")
        logger.error("Example: include: ['.github', '.gitignore']")
        return False
    elif len(include) == 0 and not has_exclude:
        logger.error("include list cannot be empty (unless using exclude-only mode)")
        logger.error("Add at least one path to materialize or use exclude-only mode")
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


def validate(target: Path, lenient: bool = False) -> bool:
    """Validate template.yml configuration in the target repository.

    Performs authoritative validation of the template configuration:
    - Checks if target is a git repository
    - Checks for standard project structure (src and tests folders)
    - Checks for pyproject.toml (required, unless lenient mode)
    - Checks if template.yml exists
    - Validates YAML syntax
    - Validates required fields
    - Validates field values are appropriate

    Args:
        target: Path to the target Git repository directory.
        lenient: If True, missing project files (pyproject.toml) are warnings,
            not errors. Used during materialize when template will provide files.

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

    # Check for pyproject.toml (lenient mode makes this a warning)
    if not _check_pyproject_toml(target, lenient=lenient):
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
