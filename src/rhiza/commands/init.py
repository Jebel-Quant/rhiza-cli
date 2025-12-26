"""Command to initialize or validate .github/rhiza/template.yml.

This module provides the init command that creates or validates the
.github/rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

import importlib.resources
import keyword
import re
from pathlib import Path

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
    # Replace any character that is not a letter, number, or underscore with an underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Ensure it doesn't start with a number
    if name[0].isdigit():
        name = f"_{name}"

    # Ensure it's not a Python keyword
    if keyword.iskeyword(name):
        name = f"{name}_"

    return name


def init(
    target: Path,
    project_name: str | None = None,
    package_name: str | None = None,
    with_dev_dependencies: bool = False,
):
    """Initialize or validate .github/rhiza/template.yml in the target repository.

    Creates a default .github/rhiza/template.yml file if it doesn't exist,
    or validates an existing one.

    Args:
        target: Path to the target directory. Defaults to the current working directory.
        project_name: Custom project name. Defaults to target directory name.
        package_name: Custom package name. Defaults to normalized project name.
        with_dev_dependencies: Include development dependencies in pyproject.toml.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    # Convert to absolute path to avoid surprises
    target = target.resolve()

    logger.info(f"Initializing Rhiza configuration in: {target}")

    # Create .rhiza directory structure if it doesn't exist
    # This is where Rhiza stores its configuration
    rhiza_dir = target / ".rhiza"
    logger.debug(f"Ensuring directory exists: {rhiza_dir}")
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # Define the template file path
    template_file = rhiza_dir / "template.yml"

    if not template_file.exists():
        # Create default template.yml with sensible defaults
        logger.info("Creating default .rhiza/template.yml")
        logger.debug("Using default template configuration")

        # Default template points to the jebel-quant/rhiza repository
        # and includes common Python project configuration files
        default_template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[
                ".github",  # GitHub configuration and workflows
                ".editorconfig",  # Editor configuration
                ".gitignore",  # Git ignore patterns
                ".pre-commit-config.yaml",  # Pre-commit hooks
                "ruff.toml",  # Ruff linter configuration
                "Makefile",  # Build and development tasks
                "pytest.ini",  # Pytest configuration
                "book",  # Documentation book
                "presentation",  # Presentation materials
                "tests",  # Test structure
            ],
        )

        # Write the default template to the file
        logger.debug(f"Writing default template to: {template_file}")
        default_template.to_yaml(template_file)

        logger.success("✓ Created .rhiza/template.yml")
        logger.info("""
Next steps:
  1. Review and customize .rhiza/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")

    # Bootstrap basic Python project structure if it doesn't exist
    # Get the name of the parent directory to use as package name
    if project_name is None:
        project_name = target.name

    if package_name is None:
        package_name = _normalize_package_name(project_name)

    logger.debug(f"Project name: {project_name}")
    logger.debug(f"Package name: {package_name}")

    # Create src/{package_name} directory structure following src-layout
    src_folder = target / "src" / package_name
    if not (target / "src").exists():
        logger.info(f"Creating Python package structure: {src_folder}")
        src_folder.mkdir(parents=True)

        # Create __init__.py to make it a proper Python package
        init_file = src_folder / "__init__.py"
        logger.debug(f"Creating {init_file}")
        init_file.touch()

        template_content = (
            importlib.resources.files("rhiza").joinpath("_templates/basic/__init__.py.jinja2").read_text()
        )
        template = Template(template_content)
        code = template.render(project_name=project_name)
        init_file.write_text(code)

        # Create main.py with a simple "Hello World" example
        main_file = src_folder / "main.py"
        logger.debug(f"Creating {main_file} with example code")
        main_file.touch()

        # Write example code to main.py
        template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/main.py.jinja2").read_text()
        template = Template(template_content)
        code = template.render(project_name=project_name)
        main_file.write_text(code)
        logger.success(f"Created Python package structure in {src_folder}")

    # Create pyproject.toml if it doesn't exist
    # This is the standard Python package metadata file (PEP 621)
    pyproject_file = target / "pyproject.toml"
    if not pyproject_file.exists():
        logger.info("Creating pyproject.toml with basic project metadata")
        pyproject_file.touch()

        # Write minimal pyproject.toml content
        template_content = (
            importlib.resources.files("rhiza").joinpath("_templates/basic/pyproject.toml.jinja2").read_text()
        )
        template = Template(template_content)
        code = template.render(
            project_name=project_name,
            package_name=package_name,
            with_dev_dependencies=with_dev_dependencies,
        )
        pyproject_file.write_text(code)
        logger.success("Created pyproject.toml")

    # Create README.md if it doesn't exist
    # Every project should have a README
    readme_file = target / "README.md"
    if not readme_file.exists():
        logger.info("Creating README.md")
        readme_file.touch()
        logger.success("Created README.md")

    # Validate the template file to ensure it's correct
    # This will catch any issues early
    logger.debug("Validating template configuration")
    return validate(target)
