"""Command for materializing Rhiza template files into a repository.

This module implements the `materialize` command. It performs a sparse
checkout of the configured template repository, copies the selected files
into the target Git repository, and records managed files in
`.rhiza/history`. Use this to take a one-shot snapshot of template files.
"""

import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from loguru import logger

from rhiza.bundle_resolver import load_bundles_from_clone, resolve_include_paths
from rhiza.models import RhizaTemplate
from rhiza.subprocess_utils import get_git_executable


def _log_git_stderr_errors(stderr: str | None) -> None:
    """Extract and log only relevant error messages from git stderr.

    Args:
        stderr: Git command stderr output.
    """
    if stderr:
        # Extract relevant error message from git stderr
        stderr_lines = stderr.strip().split("\n")
        # Show only the most relevant error lines, skip verbose git output
        for line in stderr_lines:
            line = line.strip()
            if line and (line.startswith("fatal:") or line.startswith("error:")):
                logger.error(line)


def _handle_target_branch(
    target: Path, target_branch: str | None, git_executable: str, git_env: dict[str, str]
) -> None:
    """Handle target branch creation or checkout if specified.

    Args:
        target: Path to the target repository.
        target_branch: Optional branch name to create/checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    if not target_branch:
        return

    logger.info(f"Creating/checking out target branch: {target_branch}")
    try:
        # Check if branch already exists using git rev-parse
        result = subprocess.run(  # nosec B603
            [git_executable, "rev-parse", "--verify", target_branch],
            cwd=target,
            capture_output=True,
            text=True,
            env=git_env,
        )

        if result.returncode == 0:
            # Branch exists, switch to it
            logger.info(f"Branch '{target_branch}' exists, checking out...")
            subprocess.run(  # nosec B603
                [git_executable, "checkout", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
        else:
            # Branch doesn't exist, create it from current HEAD
            logger.info(f"Creating new branch '{target_branch}'...")
            subprocess.run(  # nosec B603
                [git_executable, "checkout", "-b", target_branch],
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create/checkout branch '{target_branch}'")
        _log_git_stderr_errors(e.stderr)
        logger.error("Please ensure you have no uncommitted changes or conflicts")
        sys.exit(1)


def _load_template(target: Path, branch: str) -> tuple[RhizaTemplate, str, str, list[str], list[str]]:
    """Load template configuration.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use (CLI argument).

    Returns:
        Tuple of (template, rhiza_repo, rhiza_branch, include_paths, excluded_paths).
    """
    # Load the template configuration
    template_file = target / ".rhiza" / "template.yml"
    
    if not template_file.exists():
        logger.error(f"Template file not found: {template_file}")
        logger.error("Run 'rhiza init' to create a template configuration")
        sys.exit(1)
    
    template = RhizaTemplate.from_yaml(template_file)

    # Extract template configuration settings
    rhiza_repo = template.template_repository
    if not rhiza_repo:
        logger.error("template-repository is not configured in template.yml")
        raise RuntimeError("template-repository is required")  # noqa: TRY003
    rhiza_branch = template.template_branch or branch
    excluded_paths = template.exclude

    # Note: We'll resolve bundles to paths after cloning the template repo,
    # since we need access to bundles.yml from the template
    include_paths = template.include

    # Validate that we have either bundles or include paths
    if not template.bundles and not include_paths:
        logger.error("No bundles or include paths found in template.yml")
        logger.error("Add either 'bundles' (new) or 'include' (legacy) list in template.yml")
        raise RuntimeError("No bundles or include paths found in template.yml")  # noqa: TRY003

    # Log what we'll be using
    if template.bundles:
        logger.info("Bundles:")
        for b in template.bundles:
            logger.info(f"  - {b}")
    else:
        logger.info("Include paths:")
        for p in include_paths:
            logger.info(f"  - {p}")

    if excluded_paths:
        logger.info("Exclude paths:")
        for p in excluded_paths:
            logger.info(f"  - {p}")

    return template, rhiza_repo, rhiza_branch, include_paths, excluded_paths


def _construct_git_url(rhiza_repo: str, rhiza_host: str) -> str:
    """Construct git clone URL based on host.

    Args:
        rhiza_repo: Repository name in 'owner/repo' format.
        rhiza_host: Git hosting platform ('github' or 'gitlab').

    Returns:
        Git URL for cloning.

    Raises:
        ValueError: If rhiza_host is not supported.
    """
    if rhiza_host == "gitlab":
        git_url = f"https://gitlab.com/{rhiza_repo}.git"
        logger.debug(f"Using GitLab repository: {git_url}")
    elif rhiza_host == "github":
        git_url = f"https://github.com/{rhiza_repo}.git"
        logger.debug(f"Using GitHub repository: {git_url}")
    else:
        logger.error(f"Unsupported template-host: {rhiza_host}")
        logger.error("template-host must be 'github' or 'gitlab'")
        raise ValueError(f"Unsupported template-host: {rhiza_host}. Must be 'github' or 'gitlab'.")  # noqa: TRY003
    return git_url


def _update_sparse_checkout(
    tmp_dir: Path,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> None:
    """Update sparse checkout paths in an already-cloned repository.

    Args:
        tmp_dir: Temporary directory with cloned repository.
        include_paths: Paths to include in sparse checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    try:
        logger.debug(f"Updating sparse checkout paths: {include_paths}")
        subprocess.run(  # nosec B603
            [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout paths updated")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to update sparse checkout paths")
        _log_git_stderr_errors(e.stderr)
        sys.exit(1)


def _clone_template_repository(
    tmp_dir: Path,
    git_url: str,
    rhiza_branch: str,
    include_paths: list[str],
    git_executable: str,
    git_env: dict[str, str],
) -> None:
    """Clone template repository with sparse checkout.

    Args:
        tmp_dir: Temporary directory for cloning.
        git_url: Git repository URL.
        rhiza_branch: Branch to clone.
        include_paths: Initial paths to include in sparse checkout.
        git_executable: Path to git executable.
        git_env: Environment variables for git commands.
    """
    # Clone the repository using sparse checkout
    try:
        logger.debug("Executing git clone with sparse checkout")
        subprocess.run(  # nosec B603
            [
                git_executable,
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
        logger.error(f"Failed to clone repository from {git_url}")
        _log_git_stderr_errors(e.stderr)
        logger.error("Please check that:")
        logger.error("  - The repository exists and is accessible")
        logger.error(f"  - Branch '{rhiza_branch}' exists in the repository")
        logger.error("  - You have network access to the git hosting service")
        sys.exit(1)

    # Initialize sparse checkout in cone mode
    try:
        logger.debug("Initializing sparse checkout")
        subprocess.run(  # nosec B603
            [git_executable, "sparse-checkout", "init", "--cone"],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout initialized")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to initialize sparse checkout")
        _log_git_stderr_errors(e.stderr)
        sys.exit(1)

    # Set sparse checkout paths
    try:
        logger.debug(f"Setting sparse checkout paths: {include_paths}")
        subprocess.run(  # nosec B603
            [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            text=True,
            env=git_env,
        )
        logger.debug("Sparse checkout paths configured")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to configure sparse checkout paths")
        _log_git_stderr_errors(e.stderr)
        sys.exit(1)


def _copy_files_to_target(
    tmp_dir: Path,
    target: Path,
    include_paths: list[str],
    excluded_paths: list[str],
    force: bool,
) -> list[Path]:
    """Copy files from temporary clone to target repository.

    Args:
        tmp_dir: Temporary directory with cloned files.
        target: Target repository path.
        include_paths: Paths to include.
        excluded_paths: Paths to exclude.
        force: Whether to overwrite existing files.

    Returns:
        List of materialized file paths (relative to target).
    """
    # Expand paths to individual files
    logger.debug("Expanding included paths to individual files")
    all_files = __expand_paths(tmp_dir, include_paths)
    logger.info(f"Found {len(all_files)} file(s) in included paths")

    # Create set of excluded files
    logger.debug("Expanding excluded paths to individual files")
    excluded_files = {f.resolve() for f in __expand_paths(tmp_dir, excluded_paths)}

    # Always exclude .rhiza/template.yml to prevent overwriting local configuration
    # Also exclude .rhiza/history to prevent overwriting local history with template history
    rhiza_dir = tmp_dir / ".rhiza"
    template_config = (rhiza_dir / "template.yml").resolve()
    upstream_history = (rhiza_dir / "history").resolve()

    if template_config.is_file():
        excluded_files.add(template_config)

    if upstream_history.is_file():
        excluded_files.add(upstream_history)

    if excluded_files:
        logger.info(f"Excluding {len(excluded_files)} file(s) based on exclude patterns")

    # Filter out excluded files
    files_to_copy = [f for f in all_files if f.resolve() not in excluded_files]
    logger.info(f"Will materialize {len(files_to_copy)} file(s) to target repository")

    # Copy files to target repository
    logger.info("Copying files to target repository...")
    materialized_files: list[Path] = []

    for src_file in files_to_copy:
        # Calculate destination path maintaining relative structure
        dst_file = target / src_file.relative_to(tmp_dir)
        relative_path = dst_file.relative_to(target)

        # Track this file for history
        materialized_files.append(relative_path)

        # Check if file exists and handle based on force flag
        if dst_file.exists() and not force:
            logger.warning(f"{relative_path} already exists — use --force to overwrite")
            continue

        # Create parent directories if needed
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        # Copy file with metadata preservation
        shutil.copy2(src_file, dst_file)
        logger.success(f"[ADD] {relative_path}")

    return materialized_files


def _warn_about_workflow_files(materialized_files: list[Path]) -> None:
    """Warn if workflow files were materialized.

    Args:
        materialized_files: List of materialized file paths.
    """
    workflow_files = [p for p in materialized_files if p.parts[:2] == (".github", "workflows")]

    if workflow_files:
        logger.warning(
            "Workflow files were materialized. Updating these files requires "
            "a token with the 'workflow' permission in GitHub Actions."
        )
        logger.info(f"Workflow files affected: {len(workflow_files)}")


def _clean_orphaned_files(target: Path, materialized_files: list[Path]) -> None:
    """Clean up files that are no longer maintained by template.

    Args:
        target: Target repository path.
        materialized_files: List of currently materialized files.
    """
    # Read old history file
    new_history_file = target / ".rhiza" / "history"
    old_history_file = target / ".rhiza.history"

    # Prefer new location, check old for migration
    if new_history_file.exists():
        history_file = new_history_file
        logger.debug(f"Reading existing history file from new location: {history_file.relative_to(target)}")
    elif old_history_file.exists():
        history_file = old_history_file
        logger.debug(f"Reading existing history file from old location: {history_file.relative_to(target)}")
    else:
        logger.debug("No existing history file found")
        return

    previously_tracked_files: set[Path] = set()
    with history_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                previously_tracked_files.add(Path(line))

    logger.debug(f"Found {len(previously_tracked_files)} file(s) in previous history")

    # Find orphaned files
    currently_materialized_files = set(materialized_files)
    orphaned_files = previously_tracked_files - currently_materialized_files

    # Protected files that should never be deleted automatically
    # even if they are orphaned (e.g. user chose to stop tracking them)
    protected_files = {Path(".rhiza/template.yml")}

    if orphaned_files:
        logger.info(f"Found {len(orphaned_files)} orphaned file(s) no longer maintained by template")
        for file_path in sorted(orphaned_files):
            if file_path in protected_files:
                logger.info(f"Skipping protected file: {file_path}")
                continue

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


def _write_history_file(target: Path, materialized_files: list[Path], rhiza_repo: str, rhiza_branch: str) -> None:
    """Write history file tracking materialized files.

    Args:
        target: Target repository path.
        materialized_files: List of materialized files.
        rhiza_repo: Template repository name.
        rhiza_branch: Template branch name.
    """
    # Always write to new location
    history_file = target / ".rhiza" / "history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Writing history file: {history_file.relative_to(target)}")
    with history_file.open("w", encoding="utf-8") as f:
        f.write("# Rhiza Template History\n")
        f.write("# This file lists all files managed by the Rhiza template.\n")
        f.write(f"# Template repository: {rhiza_repo}\n")
        f.write(f"# Template branch: {rhiza_branch}\n")
        f.write("#\n")
        f.write("# Files under template control:\n")
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
    target = target.resolve()
    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")

    # Setup git environment
    git_executable = get_git_executable()
    logger.debug(f"Using git executable: {git_executable}")
    git_env = os.environ.copy()
    git_env["GIT_TERMINAL_PROMPT"] = "0"

    # Handle target branch if specified
    _handle_target_branch(target, target_branch, git_executable, git_env)

    # Load template configuration
    template, rhiza_repo, rhiza_branch, include_paths, excluded_paths = _load_template(target, branch)
    rhiza_host = template.template_host or "github"

    # Construct git URL
    git_url = _construct_git_url(rhiza_repo, rhiza_host)

    # Clone template repository
    tmp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} from {rhiza_host} into temporary directory")
    logger.debug(f"Temporary directory: {tmp_dir}")

    try:
        # Clone with initial minimal checkout to load bundles.yml if needed
        initial_paths = [".rhiza"] if template.bundles else include_paths
        _clone_template_repository(tmp_dir, git_url, rhiza_branch, initial_paths, git_executable, git_env)

        # Load bundles.yml and resolve bundles to paths if using bundle mode
        if template.bundles:
            logger.info("Resolving bundles to file paths...")
            try:
                bundles_config = load_bundles_from_clone(tmp_dir)
                resolved_paths = resolve_include_paths(template, bundles_config)
                logger.info(f"Resolved {len(template.bundles)} bundle(s) to {len(resolved_paths)} path(s)")
                logger.debug(f"Resolved paths: {resolved_paths}")
                # Update sparse checkout with resolved paths
                _update_sparse_checkout(tmp_dir, resolved_paths, git_executable, git_env)
                include_paths = resolved_paths
            except ValueError as e:
                logger.error(f"Failed to resolve bundles: {e}")
                sys.exit(1)

        materialized_files = _copy_files_to_target(tmp_dir, target, include_paths, excluded_paths, force)
    finally:
        logger.debug(f"Cleaning up temporary directory: {tmp_dir}")
        shutil.rmtree(tmp_dir)

    # Post-processing
    _warn_about_workflow_files(materialized_files)
    _clean_orphaned_files(target, materialized_files)
    _write_history_file(target, materialized_files, rhiza_repo, rhiza_branch)

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
