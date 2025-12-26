"""Command for materializing Rhiza template files into a repository.

This module implements the `materialize` command. It performs a sparse
checkout of the configured template repository, copies the selected files
into the target Git repository, and records managed files in
`.rhiza/history`. Use this to take a one-shot snapshot of template files.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger

from rhiza.commands import init
from rhiza.models import RhizaTemplate


def __expand_paths(base_dir: Path, paths: list[str]) -> list[Path]:
    """Expand files/directories relative to base_dir into a flat list of files.

    Given a list of paths relative to ``base_dir``, return a flat list of all
    individual files.

    Args:
        base_dir: The base directory to resolve paths against.
        paths: List of relative path strings (files or directories).

    Returns:
        A flat list of Path objects representing all individual files found.
    """
    all_files = []
    for p in paths:
        full_path = base_dir / p
        # Check if the path is a regular file
        if full_path.is_file():
            all_files.append(full_path)
        # If it's a directory, recursively find all files within it
        elif full_path.is_dir():
            all_files.extend([f for f in full_path.rglob("*") if f.is_file()])
        else:
            # Path does not exist in the cloned repository - skip it silently
            # This can happen if the template repo doesn't have certain paths
            logger.debug(f"Path not found in template repository: {p}")
            continue
    return all_files


def materialize(target: Path, branch: str, target_branch: str | None, force: bool) -> None:
    """Materialize Rhiza templates into the target repository.

    This performs a sparse checkout of the template repository and copies the
    selected files into the target repository, recording all files under
    template control in `.rhiza/history`.

    Args:
        target (Path): Path to the target repository.
        branch (str): The Rhiza template branch to use.
        target_branch (str | None): Optional branch name to create/checkout in
            the target repository.
        force (bool): Whether to overwrite existing files.
    """
    # Resolve to absolute path to avoid any ambiguity
    target = target.resolve()

    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")

    # Set environment to prevent git from prompting for credentials
    # This ensures non-interactive behavior during git operations
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    # -----------------------
    # Handle target branch creation/checkout if specified
    # -----------------------
    # When a target branch is specified, we either checkout an existing branch
    # or create a new one. This allows users to materialize templates onto a
    # separate branch for review before merging to main.
    if target_branch:
        logger.info(f"Creating/checking out target branch: {target_branch}")
        try:
            # Check if branch already exists using git rev-parse
            # Returns 0 if the branch exists, non-zero otherwise
            result = subprocess.run(
                ["git", "rev-parse", "--verify", target_branch],
                cwd=target,
                capture_output=True,
                text=True,
                env=git_env,
            )

            if result.returncode == 0:
                # Branch exists, switch to it
                logger.info(f"Branch '{target_branch}' exists, checking out...")
                subprocess.run(
                    ["git", "checkout", target_branch],
                    cwd=target,
                    check=True,
                    env=git_env,
                )
            else:
                # Branch doesn't exist, create it from current HEAD
                logger.info(f"Creating new branch '{target_branch}'...")
                subprocess.run(
                    ["git", "checkout", "-b", target_branch],
                    cwd=target,
                    check=True,
                    env=git_env,
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create/checkout branch '{target_branch}': {e}")
            sys.exit(1)

    # -----------------------
    # Ensure Rhiza is initialized
    # -----------------------
    # The init function creates template.yml if missing and validates it
    # Returns True if valid, False otherwise
    valid = init(target)

    if not valid:
        logger.error(f"Rhiza template is invalid in: {target}")
        logger.error("Please fix validation errors and try again")
        sys.exit(1)

    # Load the template configuration from the validated file
    # Check for template in new location first, then fall back to old location
    migrated_template_file = target / ".rhiza" / "template.yml"
    standard_template_file = target / ".github" / "rhiza" / "template.yml"

    if migrated_template_file.exists():
        template_file = migrated_template_file
        logger.debug(f"Loading template configuration from migrated location: {template_file}")
    elif standard_template_file.exists():
        template_file = standard_template_file
        logger.debug(f"Loading template configuration from standard location: {template_file}")
    else:
        logger.error("No template.yml file found")
        logger.error("Run 'rhiza init' or 'rhiza migrate' to create one")
        sys.exit(1)

    template = RhizaTemplate.from_yaml(template_file)

    # Extract template configuration settings
    # These define where to clone from and what to materialize
    rhiza_repo = template.template_repository
    # Use CLI arg if template doesn't specify a branch
    rhiza_branch = template.template_branch or branch
    # Default to GitHub if not specified
    rhiza_host = template.template_host or "github"
    include_paths = template.include
    excluded_paths = template.exclude

    # Validate that we have paths to include
    if not include_paths:
        logger.error("No include paths found in template.yml")
        logger.error("Add at least one path to the 'include' list in template.yml")
        raise RuntimeError("No include paths found in template.yml")

    # Log the paths we'll be including for transparency
    logger.info("Include paths:")
    for p in include_paths:
        logger.info(f"  - {p}")

    # Log excluded paths if any are defined
    if excluded_paths:
        logger.info("Exclude paths:")
        for p in excluded_paths:
            logger.info(f"  - {p}")

    # -----------------------
    # Construct git clone URL based on host
    # -----------------------
    # Support both GitHub and GitLab template repositories
    if rhiza_host == "gitlab":
        git_url = f"https://gitlab.com/{rhiza_repo}.git"
        logger.debug(f"Using GitLab repository: {git_url}")
    elif rhiza_host == "github":
        git_url = f"https://github.com/{rhiza_repo}.git"
        logger.debug(f"Using GitHub repository: {git_url}")
    else:
        logger.error(f"Unsupported template-host: {rhiza_host}")
        logger.error("template-host must be 'github' or 'gitlab'")
        raise ValueError(f"Unsupported template-host: {rhiza_host}. Must be 'github' or 'gitlab'.")

    # -----------------------
    # Sparse clone template repo
    # -----------------------
    # Create a temporary directory for the sparse clone
    # This will be cleaned up in the finally block
    tmp_dir = Path(tempfile.mkdtemp())
    materialized_files: list[Path] = []

    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} from {rhiza_host} into temporary directory")
    logger.debug(f"Temporary directory: {tmp_dir}")

    try:
        # Clone the repository using sparse checkout for efficiency
        # --depth 1: Only fetch the latest commit (shallow clone)
        # --filter=blob:none: Don't download file contents initially
        # --sparse: Enable sparse checkout mode
        # This combination allows us to clone only the paths we need
        try:
            logger.debug("Executing git clone with sparse checkout")
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    "--branch",
                    rhiza_branch,
                    git_url,
                    str(tmp_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Git clone completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e}")
            if e.stderr:
                logger.error(f"Git error: {e.stderr.strip()}")
            logger.error(f"Check that the repository '{rhiza_repo}' exists and branch '{rhiza_branch}' is valid")
            raise

        # Initialize sparse checkout in cone mode
        # Cone mode is more efficient and uses pattern matching
        try:
            logger.debug("Initializing sparse checkout")
            subprocess.run(
                ["git", "sparse-checkout", "init", "--cone"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Sparse checkout initialized")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize sparse checkout: {e}")
            if e.stderr:
                logger.error(f"Git error: {e.stderr.strip()}")
            raise

        # Set sparse checkout paths to only checkout the files/directories we need
        # --skip-checks: Don't validate that patterns match existing files
        try:
            logger.debug(f"Setting sparse checkout paths: {include_paths}")
            subprocess.run(
                ["git", "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Sparse checkout paths configured")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set sparse checkout paths: {e}")
            if e.stderr:
                logger.error(f"Git error: {e.stderr.strip()}")
            raise

        # -----------------------
        # Expand include/exclude paths
        # -----------------------
        # Convert directory paths to individual file paths for precise control
        logger.debug("Expanding included paths to individual files")
        all_files = __expand_paths(tmp_dir, include_paths)
        logger.info(f"Found {len(all_files)} file(s) in included paths")

        # Create a set of excluded files for fast lookup
        logger.debug("Expanding excluded paths to individual files")
        excluded_files = {f.resolve() for f in __expand_paths(tmp_dir, excluded_paths)}
        if excluded_files:
            logger.info(f"Excluding {len(excluded_files)} file(s) based on exclude patterns")

        # Filter out excluded files from the list of files to copy
        files_to_copy = [f for f in all_files if f.resolve() not in excluded_files]
        logger.info(f"Will materialize {len(files_to_copy)} file(s) to target repository")

        # -----------------------
        # Copy files into target repo
        # -----------------------
        # Copy each file from the temporary clone to the target repository
        # Preserve file metadata (timestamps, permissions) with copy2
        logger.info("Copying files to target repository...")
        for src_file in files_to_copy:
            # Calculate destination path maintaining relative structure
            dst_file = target / src_file.relative_to(tmp_dir)
            relative_path = dst_file.relative_to(target)

            # Track this file for .rhiza.history
            materialized_files.append(relative_path)

            # Check if file already exists and handle based on force flag
            if dst_file.exists() and not force:
                logger.warning(f"{relative_path} already exists — use --force to overwrite")
                continue

            # Create parent directories if they don't exist
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file with metadata preservation
            shutil.copy2(src_file, dst_file)
            logger.success(f"[ADD] {relative_path}")

    finally:
        # Clean up the temporary directory
        logger.debug(f"Cleaning up temporary directory: {tmp_dir}")
        shutil.rmtree(tmp_dir)

    # -----------------------
    # Warn about workflow files
    # -----------------------
    # GitHub Actions workflow files require special permissions to modify
    # Check if any of the materialized files are workflow files
    workflow_files = [p for p in materialized_files if p.parts[:2] == (".github", "workflows")]

    if workflow_files:
        logger.warning(
            "Workflow files were materialized. Updating these files requires "
            "a token with the 'workflow' permission in GitHub Actions."
        )
        logger.info(f"Workflow files affected: {len(workflow_files)}")

    # -----------------------
    # Clean up orphaned files
    # -----------------------
    # Read the old history file to find files that are no longer
    # part of the current materialization and should be deleted
    # Check both new and old locations for backward compatibility
    new_history_file = target / ".rhiza" / "history"
    old_history_file = target / ".rhiza.history"

    # Prefer new location, but check old location for migration
    if new_history_file.exists():
        history_file = new_history_file
        logger.debug(f"Reading existing history file from new location: {history_file.relative_to(target)}")
    elif old_history_file.exists():
        history_file = old_history_file
        logger.debug(f"Reading existing history file from old location: {history_file.relative_to(target)}")
    else:
        history_file = new_history_file  # Default to new location for creation
        logger.debug("No existing history file found, will create new one")

    previously_tracked_files: set[Path] = set()

    if history_file.exists():
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#"):
                    previously_tracked_files.add(Path(line))

        logger.debug(f"Found {len(previously_tracked_files)} file(s) in previous history")

    # Convert materialized_files list to a set for comparison
    currently_materialized_files = set(materialized_files)

    # Find orphaned files (in old history but not in new materialization)
    orphaned_files = previously_tracked_files - currently_materialized_files

    if orphaned_files:
        logger.info(f"Found {len(orphaned_files)} orphaned file(s) no longer maintained by template")
        for file_path in sorted(orphaned_files):
            full_path = target / file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                    logger.success(f"[DEL] {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            else:
                logger.debug(f"Skipping {file_path} (already deleted)")
    else:
        logger.debug("No orphaned files to clean up")

    # -----------------------
    # Write history file
    # -----------------------
    # This file tracks which files were materialized by Rhiza
    # Useful for understanding which files came from the template
    # Always write to new location (.rhiza/history)
    history_file = target / ".rhiza" / "history"

    # Ensure .rhiza directory exists
    history_file.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Writing history file: {history_file.relative_to(target)}")
    with history_file.open("w", encoding="utf-8") as f:
        f.write("# Rhiza Template History\n")
        f.write("# This file lists all files managed by the Rhiza template.\n")
        f.write(f"# Template repository: {rhiza_repo}\n")
        f.write(f"# Template branch: {rhiza_branch}\n")
        f.write("#\n")
        f.write("# Files under template control:\n")
        # Sort files for consistent ordering
        for file_path in sorted(materialized_files):
            f.write(f"{file_path}\n")

    logger.info(f"Updated {history_file.relative_to(target)} with {len(materialized_files)} file(s)")

    # Clean up old history file if it exists (migration)
    old_history_file = target / ".rhiza.history"
    if old_history_file.exists() and old_history_file != history_file:
        try:
            old_history_file.unlink()
            logger.debug(f"Removed old history file: {old_history_file.relative_to(target)}")
        except Exception as e:
            logger.warning(f"Could not remove old history file: {e}")

    logger.success("Rhiza templates materialized successfully")

    logger.info(
        "Next steps:\n"
        "  1. Review changes:\n"
        "       git status\n"
        "       git diff\n\n"
        "  2. Commit:\n"
        "       git add .\n"
        '       git commit -m "chore: import rhiza templates"\n\n'
        "This is a one-shot snapshot.\n"
        "Re-run this command to update templates explicitly."
    )
