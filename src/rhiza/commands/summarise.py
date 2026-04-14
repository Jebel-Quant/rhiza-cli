"""Command for generating PR descriptions from staged changes.

This module provides functionality to analyze staged git changes and generate
structured PR descriptions for rhiza sync operations.
"""

import json as _json
import subprocess  # nosec B404
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import jinja2
import yaml
from loguru import logger

from rhiza.models.lock import TemplateLock
from rhiza.models.template import RhizaTemplate


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

    if first_dir in {"book", "docs"}:
        return "Documentation"

    if first_dir == "src":
        return "Source Code"

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
    else:
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
    template_short_name = template_repo.split("/")[-1] if template_repo else ""

    grep_args = ["log", "--format=%cI", "-1"]
    if template_short_name:
        grep_args.extend(["--grep", template_short_name])
    grep_args.extend(["--grep=Sync", "--grep=template", "-i"])

    output = run_git_command(grep_args, cwd=repo_path)
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


def _build_header(template_repo: str, title: str | None = None) -> list[str]:
    """Build the PR description header.

    Args:
        template_repo: Template repository name
        title: Optional override for the section heading

    Returns:
        List of header lines
    """
    header_title = title if title else "## 🔄 Template Synchronization"
    lines = [header_title, ""]
    if template_repo:
        url = f"https://github.com/{template_repo}"
        lines.append(f"This PR synchronizes the repository with the [{template_repo}]({url}) template.")
    else:
        lines.append("This PR synchronizes the repository with the upstream template.")
    lines.append("")
    return lines


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
    ]
    if template_repo:
        lines.append(f"- Template: `{template_repo}@{template_branch}`")
    if last_sync:
        lines.append(f"- Last sync: {last_sync}")
    lines.append(f"- Sync date: {datetime.now().astimezone().isoformat()}")
    return lines


def _generate_json_output(
    changes: dict[str, list[str]],
    categories: dict[str, list[str]],
    template_repo: str,
    template_branch: str,
    last_sync: str | None,
) -> str:
    """Generate a JSON representation of the change data.

    Args:
        changes: Dictionary of changes by type
        categories: Files grouped by category
        template_repo: Template repository name
        template_branch: Template branch name
        last_sync: Last sync date string or None

    Returns:
        JSON-formatted string
    """
    data = {
        "template_repo": template_repo,
        "template_branch": template_branch,
        "last_sync": last_sync,
        "sync_date": datetime.now().astimezone().isoformat(),
        "changes": changes,
        "categories": categories,
    }
    return _json.dumps(data, indent=2)


def _generate_plain_output(
    changes: dict[str, list[str]],
    categories: dict[str, list[str]],
    template_repo: str,
    template_branch: str,
    last_sync: str | None,
    title: str | None = None,
    include_header: bool = True,
    include_footer: bool = True,
    include_categories: bool = True,
) -> str:
    """Generate plain-text output from change data.

    Args:
        changes: Dictionary of changes by type
        categories: Files grouped by category
        template_repo: Template repository name
        template_branch: Template branch name
        last_sync: Last sync date string or None
        title: Optional title override
        include_header: Whether to include the header block
        include_footer: Whether to include the footer block
        include_categories: Whether to group files by category

    Returns:
        Plain-text formatted string
    """
    lines: list[str] = []

    if include_header:
        heading = title if title else "Template Synchronization"
        lines.extend([heading, "=" * len(heading), ""])
        if template_repo:
            lines.append(f"Template: {template_repo}@{template_branch}")
            lines.append("")

    total = sum(len(v) for v in changes.values())
    if total == 0:
        lines.append("No changes detected.")
        return "\n".join(lines)

    lines.append(
        f"Changes: {len(changes['added'])} added, "
        f"{len(changes['modified'])} modified, "
        f"{len(changes['deleted'])} deleted"
    )
    lines.append("")

    if include_categories:
        for category, files in sorted(categories.items()):
            lines.append(f"{category}:")
            for f in sorted(files):
                lines.append(f"  {f}")
            lines.append("")
    else:
        for label, files in [
            ("Added", changes["added"]),
            ("Modified", changes["modified"]),
            ("Deleted", changes["deleted"]),
        ]:
            if files:
                lines.append(f"{label}:")
                for f in sorted(files):
                    lines.append(f"  {f}")
                lines.append("")

    if include_footer:
        if last_sync:
            lines.append(f"Last sync: {last_sync}")
        lines.append(f"Sync date: {datetime.now().astimezone().isoformat()}")

    return "\n".join(lines)


def _generate_jinja2_output(
    template_path: Path,
    changes: dict[str, list[str]],
    categories: dict[str, list[str]],
    template_repo: str,
    template_branch: str,
    last_sync: str | None,
    title: str | None = None,
) -> str:
    """Render output using a custom Jinja2 template file.

    The template receives the following context variables:

    - ``template_repo`` (str): Template repository name.
    - ``template_branch`` (str): Template branch name.
    - ``last_sync`` (str | None): ISO timestamp of last sync, or ``None``.
    - ``sync_date`` (str): ISO timestamp for the current run.
    - ``changes`` (dict): Files grouped by ``"added"``, ``"modified"``, ``"deleted"``.
    - ``categories`` (dict): Files grouped by category name.
    - ``title`` (str | None): User-supplied title, or ``None``.

    Note:
        Autoescape is disabled because this function generates plain text / Markdown,
        not HTML.  Do **not** use the rendered output directly in a web context without
        first escaping it, as the template content is not sanitised for HTML.

    Args:
        template_path: Path to the Jinja2 template file
        changes: Dictionary of changes by type
        categories: Files grouped by category
        template_repo: Template repository name
        template_branch: Template branch name
        last_sync: Last sync date string or None
        title: Optional title override

    Returns:
        Rendered template string
    """
    template_text = template_path.read_text(encoding="utf-8")
    env = jinja2.Environment(autoescape=False, loader=jinja2.BaseLoader())  # nosec B701  # noqa: S701
    tmpl = env.from_string(template_text)
    context = {
        "template_repo": template_repo,
        "template_branch": template_branch,
        "last_sync": last_sync,
        "sync_date": datetime.now().astimezone().isoformat(),
        "changes": changes,
        "categories": categories,
        "title": title,
    }
    return tmpl.render(**context)


def generate_pr_description(
    repo_path: Path,
    *,
    include_header: bool = True,
    include_footer: bool = True,
    include_categories: bool = True,
    output_format: str = "markdown",
    title: str | None = None,
    compare_ref: str | None = None,
    jinja2_template: Path | None = None,
) -> str:
    """Generate PR description based on staged changes.

    Args:
        repo_path: Path to the repository
        include_header: Whether to include the header section (markdown only)
        include_footer: Whether to include the footer section (markdown / plain)
        include_categories: Whether to group changes by category
        output_format: Output format - ``"markdown"`` (default), ``"plain"``, or ``"json"``
        title: Optional override for the PR description title
        compare_ref: Optional git ref to compare against instead of staged changes
        jinja2_template: Optional path to a Jinja2 template for fully custom output

    Returns:
        Formatted PR description
    """
    changes = get_staged_changes(repo_path, compare_ref=compare_ref)
    template_repo, template_branch = get_template_info(repo_path)
    last_sync = get_last_sync_date(repo_path, template_repo=template_repo)

    all_changed_files = changes["added"] + changes["modified"] + changes["deleted"]
    categories = categorize_files(all_changed_files) if all_changed_files else {}

    # Custom Jinja2 template takes full precedence over all other options
    if jinja2_template:
        return _generate_jinja2_output(
            jinja2_template,
            changes,
            categories,
            template_repo,
            template_branch,
            last_sync,
            title=title,
        )

    if output_format == "json":
        return _generate_json_output(changes, categories, template_repo, template_branch, last_sync)

    if output_format == "plain":
        return _generate_plain_output(
            changes,
            categories,
            template_repo,
            template_branch,
            last_sync,
            title=title,
            include_header=include_header,
            include_footer=include_footer,
            include_categories=include_categories,
        )

    # --- Markdown format (default) ---
    lines: list[str] = []

    if include_header:
        lines.extend(_build_header(template_repo, title=title))

    total_changes = sum(len(files) for files in changes.values())
    if total_changes == 0:
        lines.append("No changes detected.")
        if include_footer:
            lines.append("")
            lines.extend(_build_footer(template_repo, template_branch, last_sync))
        return "\n".join(lines)

    lines.extend(_build_summary(changes))

    if include_categories and categories:
        lines.append("### 📁 Changes by Category")
        lines.append("")

        for category, files in sorted(categories.items()):
            lines.append(f"#### {category}")
            lines.append("")

            # Group files by change type within this category
            category_added = [f for f in files if f in changes["added"]]
            category_modified = [f for f in files if f in changes["modified"]]
            category_deleted = [f for f in files if f in changes["deleted"]]

            _add_category_section(lines, "Added", len(category_added), category_added, "✅")
            _add_category_section(lines, "Modified", len(category_modified), category_modified, "📝")
            _add_category_section(lines, "Deleted", len(category_deleted), category_deleted, "❌")

    elif not include_categories:
        # Flat file list when categories are suppressed
        lines.append("### 📁 Changed Files")
        lines.append("")
        _add_category_section(lines, "Added", len(changes["added"]), changes["added"], "✅")
        _add_category_section(lines, "Modified", len(changes["modified"]), changes["modified"], "📝")
        _add_category_section(lines, "Deleted", len(changes["deleted"]), changes["deleted"], "❌")

    if include_footer:
        lines.extend(_build_footer(template_repo, template_branch, last_sync))

    return "\n".join(lines)


def summarise(
    target: Path,
    output: Path | None = None,
    *,
    include_header: bool = True,
    include_footer: bool = True,
    include_categories: bool = True,
    output_format: str = "markdown",
    title: str | None = None,
    compare_ref: str | None = None,
    jinja2_template: Path | None = None,
) -> None:
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
        include_header: Whether to include the header section.
        include_footer: Whether to include the footer section.
        include_categories: Whether to group changes by category.
        output_format: Output format - ``"markdown"`` (default), ``"plain"``, or ``"json"``.
        title: Optional override for the PR description title.
        compare_ref: Optional git ref to compare against (instead of staged changes).
        jinja2_template: Optional path to a Jinja2 template for custom output.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")

    # Check if target is a git repository
    if not (target / ".git").is_dir():
        logger.error(f"Target directory is not a git repository: {target}")
        logger.error("Initialize a git repository with 'git init' first")
        raise RuntimeError(f"Target directory is not a git repository: {target}")  # noqa: TRY003

    # Generate the PR description
    description = generate_pr_description(
        target,
        include_header=include_header,
        include_footer=include_footer,
        include_categories=include_categories,
        output_format=output_format,
        title=title,
        compare_ref=compare_ref,
        jinja2_template=jinja2_template,
    )

    # Output the description
    if output:
        output_path = output.resolve()
        output_path.write_text(description, encoding="utf-8")
        logger.success(f"PR description written to {output_path}")
    else:
        # Print to stdout
        print(description)

    logger.success("Summary generated successfully")
