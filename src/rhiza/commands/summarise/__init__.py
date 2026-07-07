"""Command for generating PR descriptions from staged changes.

This package analyses staged git changes and generates structured PR
descriptions for rhiza sync operations.  Responsibilities are split across two
private modules:

* :mod:`._gather` — collects staged changes and reads template metadata.
* :mod:`._render` — formats the gathered data into markdown, plain text, JSON,
  or a custom Jinja2 template.

The orchestration (:func:`generate_pr_description` and :func:`summarise`) lives
here and wires the two together.
"""

from datetime import datetime
from pathlib import Path

from loguru import logger

from ._gather import (
    _categorize_single_file,
    _TemplateInfo,
    categorize_files,
    get_last_sync_date,
    get_staged_changes,
    get_template_info,
    run_git_command,
)
from ._render import (
    SummariseOptions,
    _generate_jinja2_output,
    _generate_json_output,
    _generate_plain_output,
    _markdown_body,
)

__all__ = [
    "SummariseOptions",
    "_TemplateInfo",
    "_categorize_single_file",
    "categorize_files",
    "generate_pr_description",
    "get_last_sync_date",
    "get_staged_changes",
    "get_template_info",
    "run_git_command",
    "summarise",
]


def generate_pr_description(repo_path: Path, options: SummariseOptions | None = None) -> str:
    """Generate PR description based on staged changes.

    Args:
        repo_path: Path to the repository
        options: Output customisation options.  Defaults to :class:`SummariseOptions`
            with all fields at their defaults (markdown format, with header / footer /
            categories, no custom title, staged-index diff).

    Returns:
        Formatted PR description
    """
    opts = options or SummariseOptions()

    changes = get_staged_changes(repo_path, compare_ref=opts.compare_ref)
    template_repo, template_branch = get_template_info(repo_path)
    last_sync = get_last_sync_date(repo_path, template_repo=template_repo)

    all_changed_files = changes["added"] + changes["modified"] + changes["deleted"]
    categories = categorize_files(all_changed_files) if all_changed_files else {}

    tmpl = _TemplateInfo(repo=template_repo, branch=template_branch, last_sync=last_sync)

    # Custom Jinja2 template takes full precedence over all other options
    if opts.jinja2_template:
        context = {
            "template_repo": tmpl.repo,
            "template_branch": tmpl.branch,
            "last_sync": tmpl.last_sync,
            "sync_date": datetime.now().astimezone().isoformat(),
            "changes": changes,
            "categories": categories,
            "title": opts.title,
        }
        return _generate_jinja2_output(opts.jinja2_template, context)

    if opts.output_format == "json":
        return _generate_json_output(changes, categories, tmpl)

    if opts.output_format == "plain":
        return _generate_plain_output(changes, categories, tmpl, opts)

    return _markdown_body(changes, categories, tmpl, opts)


def summarise(
    target: Path,
    output: Path | None = None,
    *,
    options: SummariseOptions | None = None,
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
        options: Output customisation options.  Defaults to :class:`SummariseOptions`
            with all fields at their defaults.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")

    # Check if target is a git repository
    if not (target / ".git").is_dir():
        err_msg = f"Target directory is not a git repository: {target}"
        logger.error(err_msg)
        logger.error("Initialize a git repository with 'git init' first")
        raise RuntimeError(err_msg)

    description = generate_pr_description(target, options)

    if output:
        output_path = output.resolve()
        output_path.write_text(description, encoding="utf-8")
        logger.success(f"PR description written to {output_path}")
    else:
        print(description)

    logger.success("Summary generated successfully")
