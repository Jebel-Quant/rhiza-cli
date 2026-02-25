"""Shared lock-file helpers for Rhiza template sync state.

This module provides the single source of truth for reading and writing
``.rhiza/template.lock``.  Both ``materialize`` and ``sync`` import from here
to avoid the circular-import that would arise if either imported the other.
"""

import subprocess  # nosec B404
from pathlib import Path

import yaml
from loguru import logger

LOCK_FILE = ".rhiza/template.lock"


def _read_lock(target: Path) -> str | None:
    """Read the last-synced commit SHA from the lock file.

    Supports both the current YAML format and the legacy plain-text format
    (a bare SHA string) for backward compatibility.

    Args:
        target: Path to the target repository.

    Returns:
        The commit SHA string or ``None`` when no lock exists.
    """
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return None
    content = lock_path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "sha" in data:
            return data["sha"]
    except yaml.YAMLError:
        pass
    # Legacy format: plain-text SHA
    return content


def _read_lock_files(target: Path) -> list[Path]:
    """Return the list of managed files recorded in the lock file.

    Falls back to reading ``.rhiza/history`` when the lock file does not exist
    or does not contain a ``files`` list (projects not yet on the new format).

    Args:
        target: Path to the target repository.

    Returns:
        List of relative file paths managed by the template.
    """
    lock_path = target / LOCK_FILE
    if lock_path.exists():
        content = lock_path.read_text(encoding="utf-8").strip()
        if content:
            try:
                data = yaml.safe_load(content)
                if isinstance(data, dict) and "files" in data:
                    return [Path(f) for f in data["files"]]
            except yaml.YAMLError:
                pass

    # Legacy fallback: .rhiza/history plain-text file
    for history_path in (target / ".rhiza" / "history", target / ".rhiza.history"):
        if history_path.exists():
            logger.debug(f"Reading managed files from legacy history: {history_path.relative_to(target)}")
            files: list[Path] = []
            with history_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        files.append(Path(line))
            return files

    return []


def _write_lock(
    target: Path,
    sha: str,
    repo: str,
    host: str,
    ref: str,
    include: list[str],
    exclude: list[str],
    templates: list[str],
    files: list[Path],
) -> None:
    """Persist the synced commit SHA, template metadata, and managed file list.

    The lock file is written in YAML format so the sync state is fully
    self-describing and the ``.rhiza/history`` plain-text file is no longer
    needed.

    Args:
        target: Path to the target repository.
        sha: The commit SHA to record.
        repo: Template repository name (e.g. ``"owner/repo"``).
        host: Git hosting platform (``"github"`` or ``"gitlab"``).
        ref: Template branch or tag ref.
        include: Include paths from the template configuration.
        exclude: Exclude paths from the template configuration.
        templates: Template bundle names from the template configuration.
        files: Relative paths of all files currently managed by the template.
    """
    lock_path = target / LOCK_FILE
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "sha": sha,
        "repo": repo,
        "host": host,
        "ref": ref,
        "include": include,
        "exclude": exclude,
        "templates": templates,
        "files": [str(f) for f in sorted(files)],
    }
    lock_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    logger.info(f"Updated {LOCK_FILE} → {sha[:12]}")


def _get_head_sha(repo_dir: Path, git_executable: str, git_env: dict[str, str]) -> str:
    """Return the HEAD commit SHA of a cloned repository.

    Args:
        repo_dir: Path to the git repository.
        git_executable: Absolute path to git.
        git_env: Environment variables for git commands.

    Returns:
        The full HEAD SHA.
    """
    result = subprocess.run(  # nosec B603  # noqa: S603
        [git_executable, "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
        env=git_env,
    )
    return result.stdout.strip()
