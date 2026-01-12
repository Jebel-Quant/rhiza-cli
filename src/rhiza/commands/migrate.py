"""Command for migrating to the new .rhiza folder structure.

This module implements the `migrate` command. It helps transition projects to use
the new `.rhiza/` folder structure for storing Rhiza state and configuration files,
separate from `.github/` which contains GitHub-specific configurations.
"""

import shutil
from pathlib import Path

from loguru import logger

from rhiza.models import RhizaTemplate


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


def _ensure_rhiza_in_include(template_file: Path) -> None:
    """Ensure .rhiza folder is in template.yml include list.

    Args:
        template_file: Path to template.yml file.
    """
    if not template_file.exists():
        logger.debug("No template.yml present in .rhiza; skipping include update")
        return

    template = RhizaTemplate.from_yaml(template_file)
    template_include = template.include or []
    if ".rhiza" not in template_include:
        logger.warning("The .rhiza folder is not included in your template.yml")
        template_include.append(".rhiza")
        logger.info("The .rhiza folder is added to your template.yml to ensure it's included in your repository")
        template.include = template_include
        template.to_yaml(template_file)


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
    4. Provides instructions for next steps

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

    # Ensure .rhiza is in include list
    if template_exists:
        _ensure_rhiza_in_include(rhiza_dir / "template.yml")

    # Migrate history file
    history_migrations = _migrate_history_file(target, rhiza_dir)

    # Print summary
    all_migrations = template_migrations + history_migrations
    _print_migration_summary(all_migrations)
