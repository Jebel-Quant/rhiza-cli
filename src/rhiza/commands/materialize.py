"""Command for materializing Rhiza template files into a repository.

This module implements the `materialize` command. It performs a sparse
checkout of the configured template repository, copies the selected files
into the target Git repository, and records managed files in
`.rhiza.history`. Use this to take a one-shot snapshot of template files.
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


def __resolve_symlinks(base_dir: Path, paths: list[str]) -> tuple[list[str], dict[str, str]]:
    """Resolve symlinks in the given paths and return targets to checkout.

    Given a list of paths, detect any symlinks and return both the original paths
    and a mapping of symlinks to their targets for sparse checkout resolution.

    Args:
        base_dir: The base directory to resolve paths against.
        paths: List of relative path strings (files or directories).

    Returns:
        A tuple of (paths_to_checkout, symlink_mapping) where:
        - paths_to_checkout: All paths including resolved symlink targets
        - symlink_mapping: Dict mapping symlink path to target path
    """
    additional_paths = []
    symlink_mapping = {}

    for p in paths:
        full_path = base_dir / p
        # Check if this path is a symlink
        if full_path.is_symlink():
            # Get the target of the symlink (relative to the symlink location)
            try:
                target = full_path.readlink()
                # Resolve to absolute path, then make relative to base_dir
                if target.is_absolute():
                    resolved_target = target
                else:
                    # Resolve relative to the symlink's parent directory
                    resolved_target = (full_path.parent / target).resolve()

                # Make it relative to base_dir for sparse checkout
                try:
                    relative_target = resolved_target.relative_to(base_dir)
                    target_str = str(relative_target)
                    if target_str not in paths and target_str not in additional_paths:
                        additional_paths.append(target_str)
                        symlink_mapping[p] = target_str
                        logger.info(f"Symlink detected: {p} -> {target_str}")
                except ValueError:
                    # Target is outside base_dir, we'll handle this in expand_paths
                    logger.warning(f"Symlink {p} points outside repository: {target}")
            except Exception as e:
                logger.warning(f"Failed to resolve symlink {p}: {e}")

    return additional_paths, symlink_mapping


def __expand_paths(base_dir: Path, paths: list[str], symlink_mapping: dict[str, str] | None = None) -> list[tuple[Path, Path]]:
    """Expand files/directories relative to base_dir into a flat list of files.

    Given a list of paths relative to ``base_dir``, return a flat list of all
    individual files. Handles symlinks by resolving them to their targets.

    Args:
        base_dir: The base directory to resolve paths against.
        paths: List of relative path strings (files or directories).
        symlink_mapping: Optional dict mapping symlink paths to their target paths.

    Returns:
        A list of tuples (source_path, dest_path) where source_path is the actual
        file to copy and dest_path is where it should be placed in the target.
    """
    if symlink_mapping is None:
        symlink_mapping = {}

    all_files = []
    for p in paths:
        full_path = base_dir / p

        # If this path was a symlink, we need to resolve it to its target
        if p in symlink_mapping:
            target_path = base_dir / symlink_mapping[p]
            logger.debug(f"Processing symlink {p} via target {symlink_mapping[p]}")

            # Process the target instead, but map files back to symlink path
            if target_path.is_file():
                # For file symlinks, add with the symlink's path
                all_files.append((target_path, base_dir / p))
            elif target_path.is_dir():
                # For directory symlinks, map all files to be under symlink path
                for f in target_path.rglob("*"):
                    if f.is_file():
                        # Calculate relative path from target and map to symlink location
                        rel_from_target = f.relative_to(target_path)
                        symlink_dest = base_dir / p / rel_from_target
                        all_files.append((f, symlink_dest))
            else:
                logger.warning(f"Symlink target not found: {p} -> {symlink_mapping[p]}")
            continue

        # Check if the path is a symlink (should have been handled above, but check anyway)
        if full_path.is_symlink():
            # Try to resolve it
            try:
                resolved = full_path.resolve()
                if resolved.is_file():
                    all_files.append((resolved, full_path))
                elif resolved.is_dir():
                    for f in resolved.rglob("*"):
                        if f.is_file():
                            rel_path = f.relative_to(resolved)
                            all_files.append((f, full_path / rel_path))
            except Exception as e:
                logger.warning(f"Failed to resolve symlink {p}: {e}")
            continue

        # Check if the path is a regular file
        if full_path.is_file():
            all_files.append((full_path, full_path))
        # If it's a directory, recursively find all files within it
        elif full_path.is_dir():
            for f in full_path.rglob("*"):
                if f.is_file():
                    all_files.append((f, f))
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
    template control in `.rhiza.history`.

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
    template_file = target / ".github" / "rhiza" / "template.yml"
    logger.debug(f"Loading template configuration from: {template_file}")
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
        # Resolve symlinks and checkout targets
        # -----------------------
        # Check for symlinks and resolve them to their targets
        logger.debug("Checking for symlinks in included paths")
        additional_paths, symlink_mapping = __resolve_symlinks(tmp_dir, include_paths)

        # If we found symlink targets, add them to sparse checkout
        if additional_paths:
            logger.info(f"Detected {len(additional_paths)} symlink target(s), adding to sparse checkout")
            all_checkout_paths = include_paths + additional_paths
            try:
                subprocess.run(
                    ["git", "sparse-checkout", "set", "--skip-checks", *all_checkout_paths],
                    cwd=tmp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=git_env,
                )
                logger.debug("Updated sparse checkout with symlink targets")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to update sparse checkout with symlink targets: {e}")
                if e.stderr:
                    logger.error(f"Git error: {e.stderr.strip()}")
                raise

        # -----------------------
        # Expand include/exclude paths
        # -----------------------
        # Convert directory paths to individual file paths for precise control
        logger.debug("Expanding included paths to individual files")
        all_files = __expand_paths(tmp_dir, include_paths, symlink_mapping)
        logger.info(f"Found {len(all_files)} file(s) in included paths")

        # Create a set of excluded files for fast lookup
        logger.debug("Expanding excluded paths to individual files")
        excluded_files = {f[1].resolve() for f in __expand_paths(tmp_dir, excluded_paths, symlink_mapping)}
        if excluded_files:
            logger.info(f"Excluding {len(excluded_files)} file(s) based on exclude patterns")

        # Filter out excluded files from the list of files to copy
        files_to_copy = [f for f in all_files if f[1].resolve() not in excluded_files]
        logger.info(f"Will materialize {len(files_to_copy)} file(s) to target repository")

        # -----------------------
        # Copy files into target repo
        # -----------------------
        # Copy each file from the temporary clone to the target repository
        # Preserve file metadata (timestamps, permissions) with copy2
        logger.info("Copying files to target repository...")
        for src_file, dst_path in files_to_copy:
            # Calculate destination path maintaining relative structure
            dst_file = target / dst_path.relative_to(tmp_dir)
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
    # Read the old .rhiza.history file to find files that are no longer
    # part of the current materialization and should be deleted
    history_file = target / ".rhiza.history"
    previously_tracked_files: set[Path] = set()

    if history_file.exists():
        logger.debug("Reading existing .rhiza.history file")
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#"):
                    previously_tracked_files.add(Path(line))

        logger.debug(f"Found {len(previously_tracked_files)} file(s) in previous .rhiza.history")

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
    # Write .rhiza.history
    # -----------------------
    # This file tracks which files were materialized by Rhiza
    # Useful for understanding which files came from the template
    logger.debug("Writing .rhiza.history file")
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
