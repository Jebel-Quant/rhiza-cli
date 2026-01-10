"""Command for migrating to the new .rhiza folder structure.

This module implements the `migrate` command. It helps transition projects to use
the new `.rhiza/` folder structure for storing Rhiza state and configuration files,
separate from `.github/rhiza/` which contains template configuration.
"""

import shutil
import sys
import warnings
from pathlib import Path

import questionary
from loguru import logger

from rhiza.models import DEPRECATED_REPOSITORY, NEW_REPOSITORY, RhizaTemplate


def _create_rhiza_directory(target: Path) -> Path:
    """Create .rhiza directory if it doesn't exist.

    Args:
        target: Target repository path.

    Returns:
        Path to .rhiza directory.
    """
    rhiza_dir = target / ".rhiza"
    if not rhiza_dir.exists():
        logger.info(f"Creating .rhiza directory at: {rhiza_dir.relative_to(target)}")
        rhiza_dir.mkdir(exist_ok=True)
        logger.success(f"✓ Created {rhiza_dir.relative_to(target)}")
    else:
        logger.debug(f".rhiza directory already exists at: {rhiza_dir.relative_to(target)}")
    return rhiza_dir


def _migrate_template_file(target: Path, rhiza_dir: Path) -> tuple[bool, list[str]]:
    """Migrate template.yml from .github to .rhiza.

    Args:
        target: Target repository path.
        rhiza_dir: Path to .rhiza directory.

    Returns:
        Tuple of (migration_performed, migrations_list).
    """
    github_dir = target / ".github"
    new_template_file = rhiza_dir / "template.yml"

    possible_template_locations = [
        github_dir / "rhiza" / "template.yml",
        github_dir / "template.yml",
    ]

    migrations_performed = []
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
                shutil.move(str(old_template_file), str(new_template_file))
                # Normalize the template file (convert multiline strings to lists, etc.)
                _normalize_template_file(new_template_file)
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

    return template_migrated or new_template_file.exists(), migrations_performed


def _normalize_template_file(template_file: Path) -> None:
    """Normalize template file by re-parsing and re-saving it.

    This ensures that multiline YAML strings are converted to proper lists
    and the file format is consistent.

    Args:
        template_file: Path to template.yml file.
    """
    template = RhizaTemplate.from_yaml(template_file)
    template.to_yaml(template_file)
    logger.debug("Template file normalized")


def _ensure_rhiza_in_include(template_file: Path) -> None:
    """Ensure .rhiza folder is in template.yml include list.

    If user has an include list and .rhiza is not in there, prompt the user to add it.
    If .rhiza is in the exclude list, show a warning.

    Args:
        template_file: Path to template.yml file.
    """
    if not template_file.exists():
        logger.debug("No template.yml present in .rhiza; skipping include update")
        return

    template = RhizaTemplate.from_yaml(template_file)

    # Check if .rhiza is in exclude list
    if template.has_rhiza_folder_in_exclude():
        warnings.warn(
            "The .rhiza folder is in the exclude list. "
            "Excluding .rhiza may cause issues with Rhiza functionality. "
            "Consider removing .rhiza from your exclude list.",
            UserWarning,
            stacklevel=2,
        )

    # Check if user has an include list (not exclude-only mode)
    if template.include:
        # Check if .rhiza is already in include
        if not template.has_rhiza_folder_in_include():
            logger.warning("The .rhiza folder is not included in your template.yml")
            logger.info("Rhiza needs the .rhiza folder to store configuration and history.")
            logger.info("Without it, some Rhiza functionality may be restricted.")

            # Prompt user to add .rhiza to include if interactive
            if sys.stdin.isatty():
                add_rhiza = questionary.confirm(
                    "Would you like to add .rhiza to your include list?", default=True
                ).ask()
            else:
                # Non-interactive mode, add it automatically
                add_rhiza = True
                logger.info("Non-interactive mode: automatically adding .rhiza to include list")

            if add_rhiza:
                template.include.append(".rhiza")
                template.to_yaml(template_file)
                logger.success("✓ Added .rhiza to include list in template.yml")
            else:
                logger.warning("Skipping .rhiza addition. Some Rhiza features may not work correctly.")


def _migrate_deprecated_repository(template_file: Path) -> list[str]:
    """Check for deprecated repository and offer to migrate.

    Args:
        template_file: Path to template.yml file.

    Returns:
        List of migrations performed.
    """
    migrations_performed = []

    if not template_file.exists():
        return migrations_performed

    template = RhizaTemplate.from_yaml(template_file)

    if template.is_deprecated_repository():
        warnings.warn(
            f"The repository '{DEPRECATED_REPOSITORY}' is deprecated. "
            f"The new official repository is '{NEW_REPOSITORY}'.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Prompt user to migrate
        if sys.stdin.isatty():
            migrate_repo = questionary.confirm(f"Would you like to switch to '{NEW_REPOSITORY}'?", default=True).ask()
        else:
            # Non-interactive mode, don't change automatically but warn
            migrate_repo = False
            logger.warning("Non-interactive mode: cannot migrate repository automatically")
            logger.warning(f"Please manually update template-repository to '{NEW_REPOSITORY}'")

        if migrate_repo:
            template.template_repository = NEW_REPOSITORY
            template.to_yaml(template_file)
            logger.success(f"✓ Updated template-repository to '{NEW_REPOSITORY}'")
            migrations_performed.append(
                f"Updated template-repository from '{DEPRECATED_REPOSITORY}' to '{NEW_REPOSITORY}'"
            )
        else:
            logger.warning(f"Keeping deprecated repository. Please migrate to '{NEW_REPOSITORY}' soon.")

    return migrations_performed


def _migrate_history_file(target: Path, rhiza_dir: Path) -> list[str]:
    """Migrate .rhiza.history to .rhiza/history.

    Args:
        target: Target repository path.
        rhiza_dir: Path to .rhiza directory.

    Returns:
        List of migrations performed.
    """
    old_history_file = target / ".rhiza.history"
    new_history_file = rhiza_dir / "history"
    migrations_performed = []

    if old_history_file.exists():
        if new_history_file.exists():
            logger.info(".rhiza/history already exists")
            logger.info(f"Skipping migration of {old_history_file.relative_to(target)}")
            logger.info(f"Note: Old file at {old_history_file.relative_to(target)} still exists")
        else:
            logger.info("Found existing .rhiza.history file")
            logger.info(f"Moving to new location: {new_history_file.relative_to(target)}")
            shutil.move(str(old_history_file), str(new_history_file))
            logger.success("✓ Moved history file to .rhiza/history")
            migrations_performed.append("Moved history tracking to .rhiza/history")
    else:
        if new_history_file.exists():
            logger.debug(".rhiza/history already exists (no migration needed)")
        else:
            logger.debug("No existing .rhiza.history file to migrate")

    return migrations_performed


def _print_migration_summary(migrations_performed: list[str]) -> None:
    """Print migration summary.

    Args:
        migrations_performed: List of migrations performed.
    """
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


def migrate(target: Path) -> None:
    """Migrate project to use the new .rhiza folder structure.

    This command performs the following actions:
    1. Creates the `.rhiza/` directory in the project root
    2. Moves template.yml from `.github/rhiza/` or `.github/` to `.rhiza/template.yml`
    3. Moves `.rhiza.history` to `.rhiza/history` if it exists
    4. Checks for deprecated repository and offers to migrate
    5. Ensures .rhiza folder is included in the template
    6. Provides instructions for next steps

    The `.rhiza/` folder will contain:
    - `template.yml` - Template configuration (replaces `.github/rhiza/template.yml`)
    - `history` - List of files managed by Rhiza templates (replaces `.rhiza.history`)
    - Future: Additional state, cache, or metadata files

    Args:
        target (Path): Path to the target repository.
    """
    target = target.resolve()
    logger.info(f"Migrating Rhiza structure in: {target}")
    logger.info("This will create the .rhiza folder and migrate configuration files")

    # Create .rhiza directory
    rhiza_dir = _create_rhiza_directory(target)

    # Migrate template file
    template_exists, template_migrations = _migrate_template_file(target, rhiza_dir)

    # Check for deprecated repository and offer to migrate
    deprecated_migrations = []
    if template_exists:
        deprecated_migrations = _migrate_deprecated_repository(rhiza_dir / "template.yml")

    # Ensure .rhiza is in include list (with proper handling)
    if template_exists:
        _ensure_rhiza_in_include(rhiza_dir / "template.yml")

    # Migrate history file
    history_migrations = _migrate_history_file(target, rhiza_dir)

    # Print summary
    all_migrations = template_migrations + deprecated_migrations + history_migrations
    _print_migration_summary(all_migrations)
