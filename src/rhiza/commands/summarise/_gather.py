"""Data-gathering helpers for the ``summarise`` command.

Collects staged git changes, categorises files by type, and reads template
metadata from ``template.lock`` / ``template.yml``.  This module performs no
rendering — see :mod:`rhiza.commands.summarise._render` for output formatting.
"""

import subprocess  # nosec B404
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import yaml
from loguru import logger

from rhiza.models.lock import TemplateLock
from rhiza.models.template import RhizaTemplate


class _TemplateInfo(NamedTuple):
    """Lightweight container for template metadata used during rendering."""

    repo: str
    branch: str
    last_sync: str | None


def run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return the output.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command

    Returns:
        Command output as string
    """
    try:
        result = subprocess.run(  # nosec B603 B607  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running git {' '.join(args)}: {e.stderr}")
        return ""


def get_staged_changes(repo_path: Path, compare_ref: str | None = None) -> dict[str, list[str]]:
    """Get list of changes categorized by type.

    Args:
        repo_path: Path to the repository
        compare_ref: Optional git ref to compare against.  When provided the
            working tree is diffed against this ref instead of the staged index.

    Returns:
        Dictionary with keys 'added', 'modified', 'deleted' containing file lists
    """
    changes: dict[str, list[str]] = {
        "added": [],
        "modified": [],
        "deleted": [],
    }

    # Compare against a specific ref, or fall back to staged changes
    diff_args = ["diff", compare_ref, "--name-status"] if compare_ref else ["diff", "--cached", "--name-status"]

    output = run_git_command(diff_args, cwd=repo_path)

    for line in output.split("\n"):
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, filepath = parts

        if status == "A":
            changes["added"].append(filepath)
        elif status == "M":
            changes["modified"].append(filepath)
        elif status == "D":
            changes["deleted"].append(filepath)
        elif status.startswith("R"):
            # Renamed file - treat as modified
            changes["modified"].append(filepath)

    return changes


_CONFIG_FILES: frozenset[str] = frozenset(
    {
        "Makefile",
        "ruff.toml",
        "pytest.ini",
        ".editorconfig",
        ".gitignore",
        ".pre-commit-config.yaml",
        "renovate.json",
        ".python-version",
    }
)


_DIR_CATEGORIES: dict[str, str] = {
    "tests": "Tests",
    "src": "Source Code",
}
_DOC_DIRS: frozenset[str] = frozenset({"book", "docs"})


def _categorize_by_directory(first_dir: str, filepath: str) -> str | None:
    """Categorize file based on its first directory.

    Args:
        first_dir: First directory in the path
        filepath: Full file path

    Returns:
        Category name or None if no match
    """
    if first_dir == ".github":
        path_parts = Path(filepath).parts
        if len(path_parts) > 1 and path_parts[1] == "workflows":
            return "GitHub Actions Workflows"
        return "GitHub Configuration"

    if first_dir == ".rhiza":
        if "script" in filepath.lower():
            return "Rhiza Scripts"
        if "Makefile" in filepath:
            return "Makefiles"
        return "Rhiza Configuration"

    if first_dir in _DIR_CATEGORIES:
        return _DIR_CATEGORIES[first_dir]

    if first_dir in _DOC_DIRS:
        return "Documentation"

    return None


def _categorize_single_file(filepath: str) -> str:
    """Categorize a single file path.

    Args:
        filepath: File path to categorize

    Returns:
        Category name
    """
    path_parts = Path(filepath).parts

    if not path_parts:
        return "Other"

    # Try directory-based categorization first
    category = _categorize_by_directory(path_parts[0], filepath)
    if category:
        return category

    # Check file-based categories
    if filepath.endswith(".md"):
        return "Documentation"

    if filepath in _CONFIG_FILES:
        return "Configuration Files"

    return "Other"


def categorize_files(files: list[str]) -> dict[str, list[str]]:
    """Categorize files by type.

    Args:
        files: List of file paths

    Returns:
        Dictionary mapping category names to file lists
    """
    categories = defaultdict(list)

    for filepath in files:
        category = _categorize_single_file(filepath)
        categories[category].append(filepath)

    return dict(categories)


def get_template_info(repo_path: Path) -> tuple[str, str]:
    """Get template repository and branch from template.lock or template.yml.

    Prefers ``template.lock`` as the authoritative record of the last sync.
    Falls back to ``template.yml`` if the lock file is absent or incomplete.
    Returns empty strings when no configuration is found, rather than
    defaulting to any hardcoded repository name.

    Args:
        repo_path: Path to the repository

    Returns:
        Tuple of (template_repo, template_branch)
    """
    # Prefer template.lock - it is the authoritative record of what was synced
    lock_file = repo_path / ".rhiza" / "template.lock"
    if lock_file.exists():
        try:
            lock = TemplateLock.from_yaml(lock_file)
            if lock.repo:
                return lock.repo, lock.ref
        except (yaml.YAMLError, ValueError, TypeError, KeyError):
            logger.warning("Failed to read template.lock; falling back to template.yml")

    # Fall back to template.yml, using the proper model which handles both
    # 'template-repository'/'repository' and 'template-branch'/'ref' key variants
    template_file = repo_path / ".rhiza" / "template.yml"
    if not template_file.exists():
        return ("", "")

    try:
        template = RhizaTemplate.from_yaml(template_file)
    except (yaml.YAMLError, ValueError, TypeError, KeyError):
        logger.warning("Failed to read template.yml")
        return ("", "")

    return template.template_repository, template.template_branch


def get_last_sync_date(repo_path: Path, template_repo: str = "") -> str | None:
    """Get the date of the last sync.

    Checks ``template.lock`` for a recorded sync timestamp first, then falls
    back to searching the git log.  The template repository name (when given)
    is used to build more accurate grep patterns so that projects using a
    non-rhiza template are still matched correctly.

    Args:
        repo_path: Path to the repository
        template_repo: Template repository name (e.g. ``"my-org/my-template"``)
            used to derive the short name for git-log grep patterns.

    Returns:
        ISO format date string or None if not found
    """
    # Prefer template.lock synced_at - it is the most reliable source
    lock_file = repo_path / ".rhiza" / "template.lock"
    if lock_file.exists():
        try:
            lock = TemplateLock.from_yaml(lock_file)
            if lock.synced_at:
                return lock.synced_at
        except (yaml.YAMLError, ValueError, TypeError, KeyError):
            pass

    # Derive the short name from the template repo for targeted grepping
    template_short_name = template_repo.rsplit("/", 1)[-1] if template_repo else ""

    grep_args = ["log", "--format=%cI", "-1"]
    if template_short_name:
        grep_args.extend(["--grep", template_short_name])
    grep_args.extend(["--grep=Sync", "--grep=template", "-i"])

    output = run_git_command(grep_args, cwd=repo_path)
    if output:
        return output

    return None
