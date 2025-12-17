"""Command to show differences between rhiza templates and target repository.

This module provides functionality to preview what changes would be made by
the materialize command without actually applying them.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from loguru import logger

from rhiza.commands.inject import expand_paths


def diff(target: Path, branch: str):
    """Show differences between rhiza templates and TARGET repository."""
    # Convert to absolute path to avoid surprises
    target = target.resolve()

    # Validate target is a git repository
    if not (target / ".git").is_dir():
        logger.error(f"Target directory is not a git repository: {target}")
        sys.exit(1)

    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")

    # -----------------------
    # Ensure template.yml
    # -----------------------
    template_file = target / ".github" / "template.yml"

    if not template_file.exists():
        logger.warning("No .github/template.yml found")
        logger.info("Run 'rhiza materialize' first to create a default template.yml")
        sys.exit(1)

    # -----------------------
    # Load template.yml
    # -----------------------
    with open(template_file) as f:
        config = yaml.safe_load(f)

    rhiza_repo = config.get("template-repository")
    rhiza_branch = config.get("template-branch", branch)
    include_paths = config.get("include", [])
    excluded_paths = config.get("exclude", [])

    if not include_paths:
        logger.error("No include paths found in template.yml")
        sys.exit(1)

    logger.info("Include paths:")
    for p in include_paths:
        logger.info(f"  - {p}")

    # -----------------------
    # Sparse clone rhiza
    # -----------------------
    tmp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Cloning {rhiza_repo}@{rhiza_branch} into temporary directory")

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
                f"https://github.com/{rhiza_repo}.git",
                str(tmp_dir),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        subprocess.run(["git", "sparse-checkout", "init"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "sparse-checkout", "set", "--skip-checks", *include_paths], cwd=tmp_dir, check=True)

        # After sparse-checkout
        all_files = expand_paths(tmp_dir, include_paths)

        # Filter out excluded files
        excluded_files = expand_paths(tmp_dir, excluded_paths)

        files_to_compare = [f for f in all_files if f not in excluded_files]

        # Show differences
        has_differences = False
        new_files = []
        modified_files = []
        identical_files = []

        for src_file in files_to_compare:
            dst_file = target / src_file.relative_to(tmp_dir)
            rel_path = dst_file.relative_to(target)

            if not dst_file.exists():
                new_files.append(rel_path)
                has_differences = True
            else:
                # Compare file contents
                try:
                    src_content = src_file.read_bytes()
                    dst_content = dst_file.read_bytes()

                    if src_content != dst_content:
                        modified_files.append(rel_path)
                        has_differences = True
                    else:
                        identical_files.append(rel_path)
                except Exception as e:
                    logger.error(f"Error comparing {rel_path}: {e}")

        # Report results
        logger.info("\n" + "=" * 60)
        logger.info("DIFF SUMMARY")
        logger.info("=" * 60)

        if new_files:
            logger.info(f"\nNew files ({len(new_files)}):")
            for f in new_files:
                logger.info(f"  [NEW] {f}")

        if modified_files:
            logger.info(f"\nModified files ({len(modified_files)}):")
            for f in modified_files:
                logger.info(f"  [MODIFIED] {f}")

        if identical_files:
            logger.info(f"\nIdentical files ({len(identical_files)}):")
            for f in identical_files:
                logger.info(f"  [UNCHANGED] {f}")

        logger.info("\n" + "=" * 60)

        if has_differences:
            logger.warning("Differences found! Run 'rhiza materialize --force' to apply changes.")
        else:
            logger.success("No differences found. Repository is up to date with rhiza templates.")

    finally:
        shutil.rmtree(tmp_dir)
