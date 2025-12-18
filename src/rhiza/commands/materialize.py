"""Command for materializing Rhiza template files into a repository.

This module implements the `materialize` command. It performs a sparse
checkout of the configured template repository, copies the selected files
into the target Git repository, and records managed files in
`.rhiza.history`. Use this to take a one-shot snapshot of template files.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger

from rhiza.commands import init
from rhiza.models import RhizaTemplate


def expand_paths(base_dir: Path, paths: list[str]) -> list[Path]:
    """Expand files/directories relative to base_dir into a flat list of files.

    Given a list of paths relative to ``base_dir``, return a flat list of all
    individual files.
    """
    all_files = []
    for p in paths:
        full_path = base_dir / p
        if full_path.is_file():
            all_files.append(full_path)
        elif full_path.is_dir():
            all_files.extend([f for f in full_path.rglob("*") if f.is_file()])
        else:
            # Path does not exist — could log a warning
            continue
    return all_files


def materialize(target: Path, branch: str, target_branch: str | None, force: bool) -> None:
    """Materialize Rhiza templates into the target repository.

    This performs a sparse checkout of the template repository and copies
    the selected files into the target repository, recording all files
    under template control in `.rhiza.history`.

    Parameters
    ----------
    target:
        Path to the target repository.
    branch:
        The Rhiza template branch to use.
    target_branch:
        Optional branch name to create/checkout in target repository.
    force:
        Whether to overwrite existing files.
    """
    target = target.resolve()

    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")

    # -----------------------
    # Handle target branch creation/checkout if specified
    # -----------------------
    if target_branch:
        logger.info(f"Creating/checking out target branch: {target_branch}")
        try:
            # Check if branch already exists
            result = subprocess.run(
                ["git", "rev-parse", "--verify", target_branch],
                cwd=target,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Branch exists, checkout
                logger.info(f"Branch '{target_branch}' exists, checking out...")
                subprocess.run(
                    ["git", "checkout", target_branch],
                    cwd=target,
                    check=True,
                )
            else:
                # Branch doesn't exist, create and checkout
                logger.info(f"Creating new branch '{target_branch}'...")
                subprocess.run(
                    ["git", "checkout", "-b", target_branch],
                    cwd=target,
                    check=True,
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create/checkout branch '{target_branch}': {e}")
            sys.exit(1)

    # -----------------------
    # Ensure Rhiza is initialized
    # -----------------------
    valid = init(target)

    if not valid:
        logger.error(f"Rhiza template is invalid. {target}")
        sys.exit(1)

    template_file = target / ".github" / "template.yml"
    template = RhizaTemplate.from_yaml(template_file)

    rhiza_repo = template.template_repository
    rhiza_branch = template.template_branch or branch
    rhiza_host = template.template_host or "github"
    include_paths = template.include
    excluded_paths = template.exclude

    if not include_paths:
        raise RuntimeError("No include paths found in template.yml")

    logger.info("Include paths:")
    for p in include_paths:
        logger.info(f"  - {p}")

    # -----------------------
    # Construct git clone URL based on host
    # -----------------------
    if rhiza_host == "gitlab":
        git_url = f"https://gitlab.com/{rhiza_repo}.git"
    elif rhiza_host == "github":
        git_url = f"https://github.com/{rhiza_repo}.git"
    else:
        raise ValueError(f"Unsupported template-host: {rhiza_host}. Must be 'github' or 'gitlab'.")

    # -----------------------
    # Sparse clone template repo
    # -----------------------
    tmp_dir = Path(tempfile.mkdtemp())
    materialized_files: list[Path] = []

    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} from {rhiza_host} into temporary directory")

    try:
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
            stdout=subprocess.DEVNULL,
        )

        subprocess.run(
            ["git", "sparse-checkout", "init", "--cone"],
            cwd=tmp_dir,
            check=True,
        )

        subprocess.run(
            ["git", "sparse-checkout", "set", "--skip-checks", *include_paths],
            cwd=tmp_dir,
            check=True,
        )

        # -----------------------
        # Expand include/exclude paths
        # -----------------------
        all_files = expand_paths(tmp_dir, include_paths)

        excluded_files = {f.resolve() for f in expand_paths(tmp_dir, excluded_paths)}

        files_to_copy = [f for f in all_files if f.resolve() not in excluded_files]

        # -----------------------
        # Copy files into target repo
        # -----------------------
        for src_file in files_to_copy:
            dst_file = target / src_file.relative_to(tmp_dir)
            relative_path = dst_file.relative_to(target)

            materialized_files.append(relative_path)

            if dst_file.exists() and not force:
                logger.warning(f"{relative_path} already exists — use --force to overwrite")
                continue

            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            logger.success(f"[ADD] {relative_path}")

    finally:
        shutil.rmtree(tmp_dir)

    # -----------------------
    # Warn about workflow files
    # -----------------------
    workflow_files = [p for p in materialized_files if p.parts[:2] == (".github", "workflows")]

    if workflow_files:
        logger.warning(
            "Workflow files were materialized. Updating these files requires "
            "a token with the 'workflow' permission in GitHub Actions."
        )

    # -----------------------
    # Write .rhiza.history
    # -----------------------
    history_file = target / ".rhiza.history"
    with history_file.open("w", encoding="utf-8") as f:
        f.write("# Rhiza Template History\n")
        f.write("# This file lists all files managed by the Rhiza template.\n")
        f.write(f"# Template repository: {rhiza_repo}\n")
        f.write(f"# Template branch: {rhiza_branch}\n")
        f.write("#\n")
        f.write("# Files under template control:\n")
        for file_path in sorted(materialized_files):
            f.write(f"{file_path}\n")

    logger.info(f"Created {history_file.relative_to(target)} with {len(materialized_files)} files")

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
