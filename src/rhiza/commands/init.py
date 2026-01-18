"""Command to initialize or validate .rhiza/template.yml.

This module provides the init command that creates or validates the
.rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

import importlib.resources
import keyword
import re
import sys
from pathlib import Path

import typer
from jinja2 import Template
from loguru import logger

from rhiza.commands.validate import validate
from rhiza.models import RhizaTemplate


def _normalize_package_name(name: str) -> str:
    """Normalize a string into a valid Python package name.

    Args:
        name: The input string (e.g., project name).

    Returns:
        A valid Python identifier safe for use as a package name.
    """
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name[0].isdigit():
        name = f"_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _validate_git_host(git_host: str | None) -> str | None:
    """Validate git_host parameter.

    Args:
        git_host: Git hosting platform.

    Returns:
        Validated git_host or None.

    Raises:
        ValueError: If git_host is invalid.
    """
    if git_host is not None:
        git_host = git_host.lower()
        if git_host not in ["github", "gitlab"]:
            logger.error(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'")
            raise ValueError(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'")  # noqa: TRY003
    return git_host


def _prompt_git_host() -> str:
    """Prompt user for git hosting platform.

    Returns:
        Git hosting platform choice.
    """
    if sys.stdin.isatty():
        logger.info("Where will your project be hosted?")
        git_host = typer.prompt(
            "Target Git hosting platform (github/gitlab)",
            type=str,
            default="github",
        ).lower()

        while git_host not in ["github", "gitlab"]:
            logger.warning(f"Invalid choice: {git_host}. Please choose 'github' or 'gitlab'")
            git_host = typer.prompt(
                "Target Git hosting platform (github/gitlab)",
                type=str,
                default="github",
            ).lower()
    else:
        git_host = "github"
        logger.debug("Non-interactive mode detected, defaulting to github")

    return git_host


def _get_include_paths_for_host(git_host: str) -> list[str]:
    """Get include paths based on git hosting platform.

    Args:
        git_host: Git hosting platform.

    Returns:
        List of include paths.
    """
    if git_host == "gitlab":
        return [
            ".rhiza",
            ".gitlab",
            ".gitlab-ci.yml",
            ".editorconfig",
            ".gitignore",
            ".pre-commit-config.yaml",
            "ruff.toml",
            "Makefile",
            "pytest.ini",
            "book",
            "presentation",
            "tests",
        ]
    else:
        return [
            ".rhiza",
            ".github",
            ".editorconfig",
            ".gitignore",
            ".pre-commit-config.yaml",
            "ruff.toml",
            "Makefile",
            "pytest.ini",
            "book",
            "presentation",
            "tests",
        ]


def _create_template_file(
    target: Path,
    git_host: str,
    template_repository: str | None = None,
    template_branch: str | None = None,
) -> None:
    """Create default template.yml file.

    Args:
        target: Target repository path.
        git_host: Git hosting platform.
        template_repository: Custom template repository (format: owner/repo).
        template_branch: Custom template branch.
    """
    rhiza_dir = target / ".rhiza"
    template_file = rhiza_dir / "template.yml"

    if template_file.exists():
        return

    logger.info("Creating default .rhiza/template.yml")
    logger.debug("Using default template configuration")

    include_paths = _get_include_paths_for_host(git_host)

    # Use custom template repository/branch if provided, otherwise use defaults
    repo = template_repository or "jebel-quant/rhiza"
    branch = template_branch or "main"

    # Log when custom values are used
    if template_repository:
        logger.info(f"Using custom template repository: {repo}")
    if template_branch:
        logger.info(f"Using custom template branch: {branch}")

    default_template = RhizaTemplate(
        template_repository=repo,
        template_branch=branch,
        include=include_paths,
    )

    logger.debug(f"Writing default template to: {template_file}")
    default_template.to_yaml(template_file)

    logger.success("✓ Created .rhiza/template.yml")
    logger.info("""
Next steps:
  1. Review and customize .rhiza/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")


def _create_python_package(target: Path, project_name: str, package_name: str) -> None:
    """Create basic Python package structure.

    Args:
        target: Target repository path.
        project_name: Project name.
        package_name: Package name.
    """
    src_folder = target / "src" / package_name
    if (target / "src").exists():
        return

    logger.info(f"Creating Python package structure: {src_folder}")
    src_folder.mkdir(parents=True)

    # Create __init__.py
    init_file = src_folder / "__init__.py"
    logger.debug(f"Creating {init_file}")
    init_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/__init__.py.jinja2").read_text()
    template = Template(template_content)
    code = template.render(project_name=project_name)
    init_file.write_text(code)

    # Create main.py
    main_file = src_folder / "main.py"
    logger.debug(f"Creating {main_file} with example code")
    main_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/main.py.jinja2").read_text()
    template = Template(template_content)
    code = template.render(project_name=project_name)
    main_file.write_text(code)
    logger.success(f"Created Python package structure in {src_folder}")


def _create_pyproject_toml(target: Path, project_name: str, package_name: str, with_dev_dependencies: bool) -> None:
    """Create pyproject.toml file.

    Args:
        target: Target repository path.
        project_name: Project name.
        package_name: Package name.
        with_dev_dependencies: Whether to include dev dependencies.
    """
    pyproject_file = target / "pyproject.toml"
    if pyproject_file.exists():
        return

    logger.info("Creating pyproject.toml with basic project metadata")
    pyproject_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/pyproject.toml.jinja2").read_text()
    template = Template(template_content)
    code = template.render(
        project_name=project_name,
        package_name=package_name,
        with_dev_dependencies=with_dev_dependencies,
    )
    pyproject_file.write_text(code)
    logger.success("Created pyproject.toml")


def _create_readme(target: Path) -> None:
    """Create README.md file.

    Args:
        target: Target repository path.
    """
    readme_file = target / "README.md"
    if readme_file.exists():
        return

    logger.info("Creating README.md")
    readme_file.touch()
    logger.success("Created README.md")


def init(
    target: Path,
    project_name: str | None = None,
    package_name: str | None = None,
    with_dev_dependencies: bool = False,
    git_host: str | None = None,
    template_repository: str | None = None,
    template_branch: str | None = None,
):
    """Initialize or validate .rhiza/template.yml in the target repository.

    Creates a default .rhiza/template.yml file if it doesn't exist,
    or validates an existing one.

    Args:
        target: Path to the target directory. Defaults to the current working directory.
        project_name: Custom project name. Defaults to target directory name.
        package_name: Custom package name. Defaults to normalized project name.
        with_dev_dependencies: Include development dependencies in pyproject.toml.
        git_host: Target Git hosting platform ("github" or "gitlab"). Determines which
            CI/CD configuration files to include. If None, will prompt user interactively.
        template_repository: Custom template repository (format: owner/repo).
            Defaults to 'jebel-quant/rhiza'.
        template_branch: Custom template branch. Defaults to 'main'.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    target = target.resolve()
    git_host = _validate_git_host(git_host)

    logger.info(f"Initializing Rhiza configuration in: {target}")

    # Create .rhiza directory
    rhiza_dir = target / ".rhiza"
    logger.debug(f"Ensuring directory exists: {rhiza_dir}")
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # Determine git host
    if git_host is None:
        git_host = _prompt_git_host()

    # Create template file
    _create_template_file(target, git_host, template_repository, template_branch)

    # Bootstrap Python project structure
    if project_name is None:
        project_name = target.name
    if package_name is None:
        package_name = _normalize_package_name(project_name)

    logger.debug(f"Project name: {project_name}")
    logger.debug(f"Package name: {package_name}")

    _create_python_package(target, project_name, package_name)
    _create_pyproject_toml(target, project_name, package_name, with_dev_dependencies)
    _create_readme(target)

    # Validate the template file
    logger.debug("Validating template configuration")
    return validate(target)
