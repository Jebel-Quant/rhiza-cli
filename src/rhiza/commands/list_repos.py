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

# Description column width used by init command for display truncation
_DESC_WIDTH = 56


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


def list_repos(topic: str = _DEFAULT_TOPIC) -> bool:
    """List GitHub repositories tagged with the given topic.

    Queries the GitHub Search API for repositories with the specified topic
    and prints them in plain-text format.

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

    for repo in repos:
        date = repo.updated_at[:10] if repo.updated_at else ""
        print(f"{repo.full_name}  -  {repo.description}  ({date})")
    return True
