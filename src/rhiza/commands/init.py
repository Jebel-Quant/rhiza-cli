"""Command to initialize or validate .github/template.yml.

This module provides the init command that creates or validates the
.github/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

from pathlib import Path

import yaml
from loguru import logger

from rhiza.models import RhizaTemplate


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

    if template_file.exists():
        # Validate existing template.yml
        logger.info("Found existing .github/template.yml")
        try:
            template = RhizaTemplate.from_yaml(template_file)

            # Validate required fields
            if not template.template_repository:
                logger.warning("Missing 'template-repository' field in .github/template.yml")

            if not template.include:
                logger.warning("Missing or empty 'include' field in .github/template.yml")

            logger.success("✓ .github/template.yml is valid")
            logger.info(f"  Template repository: {template.template_repository or 'NOT SET'}")
            logger.info(f"  Template branch: {template.template_branch or 'NOT SET'}")
            logger.info(f"  Include paths: {len(template.include)} path(s)")
            if template.exclude:
                logger.info(f"  Exclude paths: {len(template.exclude)} path(s)")

        except (yaml.YAMLError, ValueError) as e:
            logger.error(f"Failed to parse .github/template.yml: {e}")
            raise SystemExit(1)
        except Exception as e:
            logger.error(f"Error validating .github/template.yml: {e}")
            raise SystemExit(1)
    else:
        # Create default template.yml
        logger.info("Creating default .github/template.yml")

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
            ],
        )

        default_template.to_yaml(template_file)

        logger.success("✓ Created .github/template.yml")
        logger.info("""
Next steps:
  1. Review and customize .github/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
""")
