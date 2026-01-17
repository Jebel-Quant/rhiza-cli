#!/usr/bin/env python3
"""Generate PR description for rhiza sync operations.

This script analyzes the changes made by rhiza materialize and generates
a comprehensive PR description including:
- Summary of changes (files added/modified/deleted)
- Commit history from template repository since last sync
- Categorization of changes by type (workflows, config, docs, etc.)
"""

import argparse
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return the output.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command

    Returns:
        Command output as string
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git {' '.join(args)}: {e.stderr}", file=sys.stderr)
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


def categorize_files(files: list[str]) -> dict[str, list[str]]:
    """Categorize files by type.

    Args:
        files: List of file paths

    Returns:
        Dictionary mapping category names to file lists
    """
    categories = defaultdict(list)

    for filepath in files:
        path_parts = Path(filepath).parts

        if not path_parts:
            continue

        # Categorize based on path
        if path_parts[0] == ".github":
            if len(path_parts) > 1 and path_parts[1] == "workflows":
                categories["GitHub Actions Workflows"].append(filepath)
            else:
                categories["GitHub Configuration"].append(filepath)
        elif path_parts[0] == ".rhiza":
            if "script" in filepath.lower():
                categories["Rhiza Scripts"].append(filepath)
            elif "Makefile" in filepath:
                categories["Makefiles"].append(filepath)
            else:
                categories["Rhiza Configuration"].append(filepath)
        elif path_parts[0] == "tests":
            categories["Tests"].append(filepath)
        elif path_parts[0] == "book":
            categories["Documentation"].append(filepath)
        elif filepath.endswith(".md"):
            categories["Documentation"].append(filepath)
        elif filepath in [
            "Makefile",
            "ruff.toml",
            "pytest.ini",
            ".editorconfig",
            ".gitignore",
            ".pre-commit-config.yaml",
            "renovate.json",
            ".python-version",
        ]:
            categories["Configuration Files"].append(filepath)
        else:
            categories["Other"].append(filepath)

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

    # Start building the description
    lines = []
    lines.append("## 🔄 Template Synchronization")
    lines.append("")
    lines.append(
        f"This PR synchronizes the repository with the [{template_repo}](https://github.com/{template_repo}) template."
    )
    lines.append("")

    # Add summary statistics
    total_changes = sum(len(files) for files in changes.values())
    if total_changes == 0:
        lines.append("No changes detected.")
        return "\n".join(lines)

    lines.append("### 📊 Change Summary")
    lines.append("")
    lines.append(f"- **{len(changes['added'])}** files added")
    lines.append(f"- **{len(changes['modified'])}** files modified")
    lines.append(f"- **{len(changes['deleted'])}** files deleted")
    lines.append("")

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

            if category_added:
                lines.append("<details>")
                lines.append(f"<summary>Added ({len(category_added)})</summary>")
                lines.append("")
                for f in sorted(category_added):
                    lines.append(f"- ✅ `{f}`")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            if category_modified:
                lines.append("<details>")
                lines.append(f"<summary>Modified ({len(category_modified)})</summary>")
                lines.append("")
                for f in sorted(category_modified):
                    lines.append(f"- 📝 `{f}`")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            if category_deleted:
                lines.append("<details>")
                lines.append(f"<summary>Deleted ({len(category_deleted)})</summary>")
                lines.append("")
                for f in sorted(category_deleted):
                    lines.append(f"- ❌ `{f}`")
                lines.append("")
                lines.append("</details>")
                lines.append("")

    # Add metadata footer
    lines.append("---")
    lines.append("")
    lines.append("**🤖 Generated by [rhiza](https://github.com/jebel-quant/rhiza-cli)**")
    lines.append("")
    lines.append(f"- Template: `{template_repo}@{template_branch}`")
    if last_sync:
        lines.append(f"- Last sync: {last_sync}")
    lines.append(f"- Sync date: {datetime.now().astimezone().isoformat()}")

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate PR description for rhiza sync")
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()

    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    description = generate_pr_description(repo_path)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(description)
        print(f"PR description written to {output_path}")
    else:
        print(description)


if __name__ == "__main__":
    main()
