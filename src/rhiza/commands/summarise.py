"""Command for generating PR descriptions from staged changes.

This module provides functionality to analyze staged git changes and generate
structured PR descriptions for rhiza sync operations.
"""

import subprocess  # nosec B404
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from loguru import logger


def run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return the output.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command

    Returns:
        Command output as string
    """
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running git {' '.join(args)}: {e.stderr}")
        return ""


def get_staged_changes(repo_path: Path) -> dict[str, list[str]]:
    """Get list of staged changes categorized by type.

    Args:
        repo_path: Path to the repository

    Returns:
        Dictionary with keys 'added', 'modified', 'deleted' containing file lists
    """
    changes = {
        "added": [],
        "modified": [],
        "deleted": [],
    }

    # Get staged changes
    output = run_git_command(["diff", "--cached", "--name-status"], cwd=repo_path)

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


def _get_config_files() -> set[str]:
    """Get set of known configuration files.

    Returns:
        Set of configuration file names
    """
    return {
        "Makefile",
        "ruff.toml",
        "pytest.ini",
        ".editorconfig",
        ".gitignore",
        ".pre-commit-config.yaml",
        "renovate.json",
        ".python-version",
    }


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

    if first_dir == "tests":
        return "Tests"

    if first_dir == "book":
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

    if filepath in _get_config_files():
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
    """Get template repository and branch from template.yml.

    Args:
        repo_path: Path to the repository

    Returns:
        Tuple of (template_repo, template_branch)
    """
    template_file = repo_path / ".rhiza" / "template.yml"

    if not template_file.exists():
        return ("jebel-quant/rhiza", "main")

    template_repo = "jebel-quant/rhiza"
    template_branch = "main"

    with open(template_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("template-repository:"):
                template_repo = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("template-branch:"):
                template_branch = line.split(":", 1)[1].strip().strip('"')

    return template_repo, template_branch


def get_last_sync_date(repo_path: Path) -> str | None:
    """Get the date of the last sync commit.

    Args:
        repo_path: Path to the repository

    Returns:
        ISO format date string or None if not found
    """
    # Look for the most recent commit with "rhiza" in the message
    output = run_git_command(
        ["log", "--grep=rhiza", "--grep=Sync", "--grep=template", "-i", "--format=%cI", "-1"], cwd=repo_path
    )

    if output:
        return output

    # Fallback: try to get date from history file if it exists
    history_file = repo_path / ".rhiza" / "history"
    if history_file.exists():
        # Get the file modification time
        stat = history_file.stat()
        return datetime.fromtimestamp(stat.st_mtime).isoformat()

    return None


def _format_file_list(files: list[str], status_emoji: str) -> list[str]:
    """Format a list of files with the given status emoji.

    Args:
        files: List of file paths
        status_emoji: Emoji to use (✅ for added, 📝 for modified, ❌ for deleted)

    Returns:
        List of formatted lines
    """
    lines = []
    for f in sorted(files):
        lines.append(f"- {status_emoji} `{f}`")
    return lines


def _add_category_section(lines: list[str], title: str, count: int, files: list[str], emoji: str) -> None:
    """Add a collapsible section for a category and change type.

    Args:
        lines: List to append lines to
        title: Section title (e.g., "Added", "Modified")
        count: Number of files
        files: List of file paths
        emoji: Status emoji
    """
    if not files:
        return

    lines.append("<details>")
    lines.append(f"<summary>{title} ({count})</summary>")
    lines.append("")
    lines.extend(_format_file_list(files, emoji))
    lines.append("")
    lines.append("</details>")
    lines.append("")


def _build_header(template_repo: str) -> list[str]:
    """Build the PR description header.

    Args:
        template_repo: Template repository name

    Returns:
        List of header lines
    """
    return [
        "## 🔄 Template Synchronization",
        "",
        f"This PR synchronizes the repository with the [{template_repo}](https://github.com/{template_repo}) template.",
        "",
    ]


def _build_summary(changes: dict[str, list[str]]) -> list[str]:
    """Build the change summary section.

    Args:
        changes: Dictionary of changes by type

    Returns:
        List of summary lines
    """
    return [
        "### 📊 Change Summary",
        "",
        f"- **{len(changes['added'])}** files added",
        f"- **{len(changes['modified'])}** files modified",
        f"- **{len(changes['deleted'])}** files deleted",
        "",
    ]


def _build_footer(template_repo: str, template_branch: str, last_sync: str | None) -> list[str]:
    """Build the PR description footer with metadata.

    Args:
        template_repo: Template repository name
        template_branch: Template branch name
        last_sync: Last sync date string or None

    Returns:
        List of footer lines
    """
    lines = [
        "---",
        "",
        "**🤖 Generated by [rhiza](https://github.com/jebel-quant/rhiza-cli)**",
        "",
        f"- Template: `{template_repo}@{template_branch}`",
    ]
    if last_sync:
        lines.append(f"- Last sync: {last_sync}")
    lines.append(f"- Sync date: {datetime.now().astimezone().isoformat()}")
    return lines


def generate_pr_description(repo_path: Path) -> str:
    """Generate PR description based on staged changes.

    Args:
        repo_path: Path to the repository

    Returns:
        Formatted PR description
    """
    changes = get_staged_changes(repo_path)
    template_repo, template_branch = get_template_info(repo_path)
    last_sync = get_last_sync_date(repo_path)

    # Build header
    lines = _build_header(template_repo)

    # Check if there are any changes
    total_changes = sum(len(files) for files in changes.values())
    if total_changes == 0:
        lines.append("No changes detected.")
        return "\n".join(lines)

    # Add summary
    lines.extend(_build_summary(changes))

    # Add detailed changes by category
    all_changed_files = changes["added"] + changes["modified"] + changes["deleted"]
    categories = categorize_files(all_changed_files)

    if categories:
        lines.append("### 📁 Changes by Category")
        lines.append("")

        for category, files in sorted(categories.items()):
            lines.append(f"#### {category}")
            lines.append("")

            # Group files by change type
            category_added = [f for f in files if f in changes["added"]]
            category_modified = [f for f in files if f in changes["modified"]]
            category_deleted = [f for f in files if f in changes["deleted"]]

            _add_category_section(lines, "Added", len(category_added), category_added, "✅")
            _add_category_section(lines, "Modified", len(category_modified), category_modified, "📝")
            _add_category_section(lines, "Deleted", len(category_deleted), category_deleted, "❌")

    # Add footer
    lines.extend(_build_footer(template_repo, template_branch, last_sync))

    return "\n".join(lines)


def summarise(target: Path, output: Path | None = None) -> None:
    """Generate a summary of staged changes for rhiza sync operations.

    This command analyzes staged git changes and generates a structured
    PR description with:
    - Summary statistics (files added/modified/deleted)
    - Changes categorized by type (workflows, configs, docs, tests, etc.)
    - Template repository information
    - Last sync date

    Args:
        target: Path to the target repository.
        output: Optional output file path. If not provided, prints to stdout.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")

    # Check if target is a git repository
    if not (target / ".git").is_dir():
        logger.error(f"Target directory is not a git repository: {target}")
        logger.error("Initialize a git repository with 'git init' first")
        sys.exit(1)

    # Generate the PR description
    description = generate_pr_description(target)

    # Output the description
    if output:
        output_path = output.resolve()
        output_path.write_text(description)
        logger.success(f"PR description written to {output_path}")
    else:
        # Print to stdout
        print(description)

    logger.success("Summary generated successfully")
