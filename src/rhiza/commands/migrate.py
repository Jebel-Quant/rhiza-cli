"""Command for migrating to the new .rhiza folder structure.

This module implements the `migrate` command. It helps transition projects to use
the new `.rhiza/` folder structure for storing Rhiza state and configuration files,
separate from `.github/rhiza/` which contains template configuration.
"""

import shutil
from pathlib import Path

from loguru import logger

from rhiza.models import RhizaTemplate


def migrate(target: Path) -> None:
    """Migrate project to use the new .rhiza folder structure.

    This command performs the following actions:
    1. Creates the `.rhiza/` directory in the project root
    2. Moves template.yml from `.github/rhiza/` or `.github/` to `.rhiza/template.yml`
    3. Moves `.rhiza.history` to `.rhiza/history` if it exists
    4. Provides instructions for next steps

    The `.rhiza/` folder will contain:
    - `template.yml` - Template configuration (replaces `.github/rhiza/template.yml`)
    - `history` - List of files managed by Rhiza templates (replaces `.rhiza.history`)
    - Future: Additional state, cache, or metadata files

    Args:
        target (Path): Path to the target repository.
    """
    # Resolve to absolute path
    target = target.resolve()

    logger.info(f"Migrating Rhiza structure in: {target}")
    logger.info("This will create the .rhiza folder and migrate configuration files")

    # Create .rhiza directory
    rhiza_dir = target / ".rhiza"
    if not rhiza_dir.exists():
        logger.info(f"Creating .rhiza directory at: {rhiza_dir.relative_to(target)}")
        rhiza_dir.mkdir(exist_ok=True)
        logger.success(f"✓ Created {rhiza_dir.relative_to(target)}")
    else:
        logger.debug(f".rhiza directory already exists at: {rhiza_dir.relative_to(target)}")

    # Track what was migrated for summary
    migrations_performed = []

    # Migrate template.yml from .github to .rhiza if it exists
    github_dir = target / ".github"
    new_template_file = rhiza_dir / "template.yml"

    # Check possible locations for template.yml in .github
    possible_template_locations = [
        github_dir / "rhiza" / "template.yml",
        github_dir / "template.yml",
    ]

    template_migrated = False
    for old_template_file in possible_template_locations:
        if old_template_file.exists():
            if new_template_file.exists():
                logger.info(".rhiza/template.yml already exists")
                logger.info(f"Skipping migration of {old_template_file.relative_to(target)}")
                logger.info(f"Note: Old file at {old_template_file.relative_to(target)} still exists")
            else:
                logger.info(f"Found template.yml at: {old_template_file.relative_to(target)}")
                logger.info(f"Moving to new location: {new_template_file.relative_to(target)}")

                # Move the template file to new location (not copy)
                shutil.move(str(old_template_file), str(new_template_file))
                logger.success("✓ Moved template.yml to .rhiza/template.yml")
                migrations_performed.append("Moved template.yml to .rhiza/template.yml")
                template_migrated = True
            break

    if not template_migrated:
        if new_template_file.exists():
            logger.info(".rhiza/template.yml already exists (no migration needed)")
        else:
            logger.warning("No existing template.yml file found in .github")
            logger.info("You may need to run 'rhiza init' to create a template configuration")

    # Ensure the .rhiza folder is included in template.yml include list (if template exists)
    template_file = new_template_file
    if template_file.exists():
        # Load existing template configuration
        template = RhizaTemplate.from_yaml(template_file)
        template_include = template.include or []
        if ".rhiza" not in template_include:
            logger.warning("The .rhiza folder is not included in your template.yml")
            template_include.append(".rhiza")
            logger.info("The .rhiza folder is added to your template.yml to ensure it's included in your repository")

            # Save the updated template.yml
            template.include = template_include
            template.to_yaml(template_file)
    else:
        logger.debug("No template.yml present in .rhiza; skipping include update")

    # Migrate .rhiza.history to .rhiza/history if it exists
    old_history_file = target / ".rhiza.history"
    new_history_file = rhiza_dir / "history"

    if old_history_file.exists():
        if new_history_file.exists():
            logger.info(".rhiza/history already exists")
            logger.info(f"Skipping migration of {old_history_file.relative_to(target)}")
            logger.info(f"Note: Old file at {old_history_file.relative_to(target)} still exists")
        else:
            logger.info("Found existing .rhiza.history file")
            logger.info(f"Moving to new location: {new_history_file.relative_to(target)}")

            # Move the history file to new location
            shutil.move(str(old_history_file), str(new_history_file))
            logger.success("✓ Moved history file to .rhiza/history")
            migrations_performed.append("Moved history tracking to .rhiza/history")
    else:
        if new_history_file.exists():
            logger.debug(".rhiza/history already exists (no migration needed)")
        else:
            logger.debug("No existing .rhiza.history file to migrate")

    # Summary
    logger.success("✓ Migration completed successfully")

    if migrations_performed:
        logger.info("\nMigration Summary:")
        logger.info("  - Created .rhiza/ folder")
        for migration in migrations_performed:
            logger.info(f"  - {migration}")
    else:
        logger.info("\nNo files needed migration (already using .rhiza structure)")

    logger.info(
        "\nNext steps:\n"
        "  1. Review changes:\n"
        "       git status\n"
        "       git diff\n\n"
        "  2. Update other commands to use new .rhiza/ location\n"
        "     (Future rhiza versions will automatically use .rhiza/)\n\n"
        "  3. Commit the migration:\n"
        "       git add .\n"
        '       git commit -m "chore: migrate to .rhiza folder structure"\n'
    )
