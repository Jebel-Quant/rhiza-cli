"""Command to initialize or validate .github/rhiza/template.yml.

This module provides the init command that creates or validates the
.github/rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

import shutil
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
    """
    # Convert to absolute path to avoid surprises
    target = target.resolve()

    logger.info(f"Initializing Rhiza configuration in: {target}")

    # Create .github/rhiza directory if it doesn't exist
    github_dir = target / ".github"
    rhiza_dir = github_dir / "rhiza"
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # check the old location and copy over if existent
    # todo: remove this logic later
    template_file = github_dir / "template.yml"
    if template_file.exists():
        # move the file into rhiza_dir
        shutil.copyfile(template_file, rhiza_dir / "template.yml")

    # Define the template file path
    template_file = rhiza_dir / "template.yml"

    if not template_file.exists():
        # Create default template.yml
        logger.info("Creating default .github/rhiza/template.yml")

        default_template = RhizaTemplate(
            template_repository="jebel-quant/rhiza",
            template_branch="main",
            include=[
                ".github",
                ".editorconfig",
                ".gitignore",
                ".pre-commit-config.yaml",
                "Makefile",
                "pytest.ini",
                "book",
                "presentation",
                "tests",
            ],
        )

        default_template.to_yaml(template_file)

        logger.success("✓ Created .github/rhiza/template.yml")
        logger.info("""
Next steps:
  1. Review and customize .github/rhiza/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")

    # the template file exists, so validate it
    return validate(target)
