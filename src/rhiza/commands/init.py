"""Command to initialize or validate .github/rhiza/template.yml.

This module provides the init command that creates or validates the
.github/rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

import shutil
import textwrap
from pathlib import Path

from loguru import logger

from rhiza.commands.validate import validate
from rhiza.models import RhizaTemplate


def init(target: Path):
    """Initialize or validate .github/rhiza/template.yml in the target repository.

    Creates a default .github/rhiza/template.yml file if it doesn't exist,
    or validates an existing one.

    Args:
        target: Path to the target directory. Defaults to the current working directory.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    # Convert to absolute path to avoid surprises
    target = target.resolve()

    logger.info(f"Initializing Rhiza configuration in: {target}")

    # Create .github/rhiza directory structure if it doesn't exist
    # This is where Rhiza stores its configuration
    github_dir = target / ".github"
    rhiza_dir = github_dir / "rhiza"
    logger.debug(f"Ensuring directory exists: {rhiza_dir}")
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # Check for old location and migrate if necessary
    # TODO: This migration logic can be removed in a future version
    # after users have had time to migrate
    template_file = github_dir / "template.yml"
    if template_file.exists():
        logger.warning(f"Found template.yml in old location: {template_file}")
        logger.info(f"Copying to new location: {rhiza_dir / 'template.yml'}")
        # Copy the file to the new location (not move, to preserve old one temporarily)
        shutil.copyfile(template_file, rhiza_dir / "template.yml")

    # Define the template file path (new location)
    template_file = rhiza_dir / "template.yml"

    if not template_file.exists():
        # Create default template.yml with sensible defaults
        logger.info("Creating default .github/rhiza/template.yml")
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

        logger.success("✓ Created .github/rhiza/template.yml")
        logger.info("""
Next steps:
  1. Review and customize .github/rhiza/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")

    # Bootstrap basic Python project structure if it doesn't exist
    # Get the name of the parent directory to use as package name
    parent = target.name
    logger.debug(f"Parent directory name: {parent}")

    # Create src/{parent} directory structure following src-layout
    src_folder = target / "src" / parent
    if not (target / "src").exists():
        logger.info(f"Creating Python package structure: {src_folder}")
        src_folder.mkdir(parents=True)

        # Create __init__.py to make it a proper Python package
        init_file = src_folder / "__init__.py"
        logger.debug(f"Creating {init_file}")
        init_file.touch()

        # Create main.py with a simple "Hello World" example
        main_file = src_folder / "main.py"
        logger.debug(f"Creating {main_file} with example code")
        main_file.touch()

        # Write example code to main.py
        code = textwrap.dedent("""\
        def say_hello(name: str) -> str:
            return f"Hello, {name}!"

        def main():
            print(say_hello("World"))

        if __name__ == "__main__":
            main()
        """)
        main_file.write_text(code)
        logger.success(f"Created Python package structure in {src_folder}")

    # Create pyproject.toml if it doesn't exist
    # This is the standard Python package metadata file (PEP 621)
    pyproject_file = target / "pyproject.toml"
    if not pyproject_file.exists():
        logger.info("Creating pyproject.toml with basic project metadata")
        pyproject_file.touch()

        # Write minimal pyproject.toml content
        code = textwrap.dedent(f'''\
        [project]
        name = "{parent}"
        version = "0.1.0"
        description = "Add your description here"
        readme = "README.md"
        requires-python = ">=3.11"
        dependencies = []
        ''')
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
