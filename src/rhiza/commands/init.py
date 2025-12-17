"""Command to initialize or validate .github/template.yml.

This module provides the init command that creates or validates the
.github/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

from pathlib import Path

import yaml
from loguru import logger

from rhiza.commands.validate import validate


def init(target: Path):
    """Initialize or validate .github/template.yml in the target repository.

    Creates a default .github/template.yml file if it doesn't exist,
    or validates an existing one.

    Parameters
    ----------
    target:
        Path to the target directory. Defaults to the current working directory.
    """
    # Convert to absolute path to avoid surprises
    target = target.resolve()

    logger.info(f"Initializing Rhiza configuration in: {target}")

    # Create .github directory if it doesn't exist
    github_dir = target / ".github"
    github_dir.mkdir(parents=True, exist_ok=True)

    # Define the template file path
    template_file = github_dir / "template.yml"

    if not template_file.exists():
        # Create default template.yml
        logger.info("Creating default .github/template.yml")

        default_config = {
            "template-repository": "jebel-quant/rhiza",
            "template-branch": "main",
            "include": [
                ".github",
                ".editorconfig",
                ".gitignore",
                ".pre-commit-config.yaml",
                "Makefile",
                "pytest.ini",
            ],
        }

        with open(template_file, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        logger.success("✓ Created .github/template.yml")
        logger.info("""
Next steps:
  1. Review and customize .github/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")

    # the template file exists, so validate it
    validate(target)
