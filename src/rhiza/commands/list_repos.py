"""Command for listing GitHub repositories with the rhiza topic.

This module queries the GitHub Search API for repositories tagged with
the 'rhiza' topic and displays them in a formatted table.
"""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from loguru import logger

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_DEFAULT_TOPIC = "rhiza"
_PER_PAGE = 50

# Fixed column content widths (excluding 1-space padding on each side)
_REPO_WIDTH = 20
_DESC_WIDTH = 56
_DATE_WIDTH = 10


@dataclass
class _RepoInfo:
    full_name: str
    description: str
    updated_at: str


def _fetch_repos(topic: str = _DEFAULT_TOPIC) -> list[_RepoInfo]:
    """Fetch repositories from the GitHub Search API with the given topic.

    Args:
        topic: GitHub topic to search for.

    Returns:
        List of repository info objects.

    Raises:
        urllib.error.URLError: If the API request fails.
    """
    url = f"{_GITHUB_SEARCH_URL}?q=topic:{topic}&per_page={_PER_PAGE}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)  # nosec B310  # noqa: S310
    with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310  # noqa: S310
        data = json.loads(resp.read().decode())

    return [
        _RepoInfo(
            full_name=item["full_name"],
            description=item.get("description") or "",
            updated_at=item.get("updated_at") or "",
        )
        for item in data.get("items", [])
    ]


def _format_date(iso_date: str) -> str:
    """Format an ISO 8601 date string to YYYY-MM-DD.

    Args:
        iso_date: ISO 8601 date string (e.g. '2026-03-02T12:12:02Z').

    Returns:
        Date string in YYYY-MM-DD format, or empty string if input is empty.
    """
    if not iso_date:
        return ""
    return iso_date[:10]


def _wrap_text(text: str, width: int) -> list[str]:
    """Wrap text to fit within a given width, splitting on word boundaries.

    Args:
        text: The text to wrap.
        width: Maximum line width in characters.

    Returns:
        List of lines, each at most *width* characters wide.
    """
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        lines.append(current)
    return lines or [""]


def _render_table(repos: list[_RepoInfo]) -> str:
    """Render a list of repositories as a formatted table.

    Args:
        repos: List of repository info objects to display.

    Returns:
        Formatted table string ready to print.
    """
    if not repos:
        return "No repositories found."

    rw, dw, uw = _REPO_WIDTH, _DESC_WIDTH, _DATE_WIDTH

    top = f"┌{'─' * (rw + 2)}┬{'─' * (dw + 2)}┬{'─' * (uw + 2)}┐"
    sep = f"├{'─' * (rw + 2)}┼{'─' * (dw + 2)}┼{'─' * (uw + 2)}┤"
    bot = f"└{'─' * (rw + 2)}┴{'─' * (dw + 2)}┴{'─' * (uw + 2)}┘"

    def cell_row(r: str, d: str, u: str) -> str:
        return f"│ {r:<{rw}} │ {d:<{dw}} │ {u:<{uw}} │"

    header = f"│ {'Repo':^{rw}} │ {'Description':^{dw}} │ {'Updated':^{uw}} │"

    lines = [top, header, sep]
    for i, repo in enumerate(repos):
        if i > 0:
            lines.append(sep)
        desc_lines = _wrap_text(repo.description, dw)
        date_str = _format_date(repo.updated_at)
        for j, desc_line in enumerate(desc_lines):
            if j == 0:
                lines.append(cell_row(repo.full_name, desc_line, date_str))
            else:
                lines.append(cell_row("", desc_line, ""))
    lines.append(bot)
    return "\n".join(lines)


def list_repos(topic: str = _DEFAULT_TOPIC) -> bool:
    """List GitHub repositories tagged with the given topic.

    Queries the GitHub Search API for repositories with the specified topic
    and prints them in a formatted table.

    Args:
        topic: GitHub topic to search for (default: 'rhiza').

    Returns:
        True on success, False if the API request failed.
    """
    try:
        repos = _fetch_repos(topic)
    except urllib.error.URLError as exc:
        logger.error(f"Failed to fetch repositories: {exc}")
        return False

    if not repos:
        logger.info(f"No repositories found with topic '{topic}'.")
        return True

    print(_render_table(repos))
    return True
