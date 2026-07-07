"""Command to initialize or validate .rhiza/template.yml.

This module provides the init command that creates or validates the
.rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.

The project-scaffolding helpers (the ``_create_*`` functions plus the
naming/profile utilities) live in :mod:`rhiza.commands._init_helpers` and
are re-exported here so the import surface (``rhiza.commands.init._create_*``)
stays stable.
"""

import re
import subprocess  # nosec B404
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import typer
from loguru import logger

from rhiza.commands._init_helpers import (
    _create_makefile,
    _create_mkdocs_yml,
    _create_pyproject_toml,
    _create_python_package,
    _create_readme,
    _create_template_file,
    _create_uv_lock,
    _display_path,
    _get_default_profile_for_host,
    _normalize_package_name,
)
from rhiza.commands._init_host import _parse_version_tags, _prompt_git_host, _validate_git_host
from rhiza.commands.list_repos import _DESC_WIDTH, _fetch_repos
from rhiza.commands.validate import validate
from rhiza.models import GitContext, GitHost

__all__ = [
    "_check_template_repository_reachable",
    "_create_makefile",
    "_create_mkdocs_yml",
    "_create_pyproject_toml",
    "_create_python_package",
    "_create_readme",
    "_create_template_file",
    "_create_uv_lock",
    "_detect_git_host",
    "_display_path",
    "_get_default_profile_for_host",
    "_get_github_username",
    "_get_latest_tag",
    "_normalize_package_name",
    "_prompt_git_host",
    "_prompt_template_repository",
    "_validate_git_host",
    "init",
]


def _check_template_repository_reachable(template_repository: str, git_host: GitHost = GitHost.GITHUB) -> bool:
    """Check if the template repository is reachable via git ls-remote.

    Args:
        template_repository: Repository in 'owner/repo' format.
        git_host: Git hosting platform ('github' or 'gitlab'). Defaults to 'github'.

    Returns:
        True if the repository is reachable, False otherwise.
    """
    host_urls = {
        GitHost.GITHUB: "https://github.com",
        GitHost.GITLAB: "https://gitlab.com",
    }
    base_url = host_urls.get(git_host, "https://github.com")
    repo_url = f"{base_url}/{template_repository}"

    logger.debug(f"Checking reachability of template repository: {repo_url}")
    try:
        git_ctx = GitContext.default()
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "ls-remote", "--exit-code", repo_url],
            capture_output=True,
            timeout=30,
            env=git_ctx.env,
        )
        if result.returncode == 0:
            logger.success(f"Template repository is reachable: {template_repository}")
            return True
        else:
            stderr_output = (result.stderr or b"").decode(errors="replace").strip()
            logger.error(
                f"Template repository '{template_repository}' is not accessible at {repo_url} "
                f"(git exit code: {result.returncode})."
            )
            if stderr_output:
                logger.error(f"git ls-remote stderr: {stderr_output}")
            else:
                logger.error("git ls-remote returned no stderr output.")
            logger.error(
                "Please check that the repository exists, your network connection, and your access permissions."
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timed out while checking repository reachability: {repo_url}")
        logger.error("Please check your network connection and try again.")
        return False
    except RuntimeError as e:
        logger.warning(f"Could not verify template repository reachability: {e}")
        return True  # Don't block init if git is unavailable


def _get_latest_tag(template_repository: str, git_host: GitHost | str = GitHost.GITHUB) -> str | None:
    """Fetch the latest version tag from the template repository via git ls-remote.

    Args:
        template_repository: Repository in 'owner/repo' format.
        git_host: Git hosting platform.

    Returns:
        Latest version tag (e.g. ``'v0.18.4'``), or ``None`` on error or when no
        version tags exist.
    """
    if git_host == GitHost.GITLAB:
        repo_url = f"https://gitlab.com/{template_repository}"
    else:
        repo_url = f"https://github.com/{template_repository}"

    logger.debug(f"Fetching latest tag from {repo_url}")
    try:
        git_ctx = GitContext.default()
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "ls-remote", "--tags", repo_url],
            capture_output=True,
            text=True,
            timeout=30,
            env=git_ctx.env,
        )
        if result.returncode != 0:
            logger.debug(f"git ls-remote --tags failed for {repo_url}")
            return None

        version_tags = _parse_version_tags(result.stdout)
        if not version_tags:
            logger.debug(f"No version tags found in {repo_url}")
            return None

        latest = max(version_tags, key=lambda t: tuple(int(x) for x in re.findall(r"\d+", t)))
        logger.debug(f"Latest tag: {latest}")

    except (subprocess.TimeoutExpired, RuntimeError, OSError) as exc:
        logger.debug(f"Could not fetch latest tag from {repo_url}: {exc}")
        return None
    else:
        return latest


def _get_github_username(target: Path) -> str:
    """Extract the GitHub/GitLab username (or org) from the origin remote URL.

    Args:
        target: Repository root directory.

    Returns:
        Username string, or ``"your-org"`` when detection fails.
    """
    try:
        git_ctx = GitContext.default()
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=target,
            env=git_ctx.env,
        )
        if result.returncode != 0:
            return "your-org"
        url = result.stdout.strip()
        # ssh: git@github.com:username/repo.git
        ssh_match = re.match(r"git@[^:]+:([^/]+)/", url)
        if ssh_match:
            return ssh_match.group(1)
        # https: https://github.com/username/repo.git
        https_match = re.match(r"https?://[^/]+/([^/]+)/", url)
        if https_match:
            return https_match.group(1)
    except (RuntimeError, OSError):
        pass
    return "your-org"


def _detect_git_host(target: Path) -> GitHost | None:
    """Infer the git hosting platform from the repository's origin remote URL.

    Args:
        target: Repository root directory.

    Returns:
        Detected :class:`GitHost`, or ``None`` when detection is not possible
        (no git repo, no origin remote, or unrecognised host).
    """
    try:
        git_ctx = GitContext.default()
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=target,
            env=git_ctx.env,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()

        host: str | None = None
        if "://" in url:
            host = urllib.parse.urlparse(url).hostname
        else:
            # Handle SCP-like git remotes, e.g. git@github.com:org/repo.git
            match = re.match(r"^(?:[^@]+@)?([^:]+):.+$", url)
            if match:
                host = match.group(1)

        host = host.lower() if host else None
        if host == "github.com":
            logger.debug(f"Detected git host: github (from {url})")
            return GitHost.GITHUB
        if host == "gitlab.com":
            logger.debug(f"Detected git host: gitlab (from {url})")
            return GitHost.GITLAB
    except (RuntimeError, OSError):
        return None
    else:
        return None


def _prompt_template_repository() -> str | None:
    """Prompt the user to select a template repository from a list of rhiza-tagged repos.

    Fetches repositories tagged with 'rhiza' from the GitHub API and presents
    them as a numbered list. In non-interactive or offline scenarios the function
    returns None so the caller falls back to the language default.

    Returns:
        The selected repository in 'owner/repo' format, or None if the user
        accepts the default or selection is not possible.
    """
    if not sys.stdin.isatty():
        logger.debug("Non-interactive mode detected, skipping template repository selection")
        return None

    try:
        repos = _fetch_repos()
    except urllib.error.URLError as exc:
        logger.debug(f"Could not fetch repository list: {exc}")
        return None

    if not repos:
        return None

    # Display a compact numbered list
    typer.echo("\nAvailable template repositories:")
    for i, repo in enumerate(repos, start=1):
        desc = repo.description[:_DESC_WIDTH] if repo.description else ""
        typer.echo(f"  {i:>2}  {repo.full_name:<30}  {desc}")

    typer.echo("")
    selection = typer.prompt(
        "Select a template repository by number",
        default="1",
    ).strip()

    try:
        idx = int(selection)
        if 1 <= idx <= len(repos):
            chosen = repos[idx - 1].full_name
            logger.info(f"Selected template repository: {chosen}")
            return chosen
        else:
            logger.warning(f"Invalid selection '{idx}', using default repository")
            return None
    except ValueError:
        logger.warning(f"Invalid input '{selection}', using default repository")
        return None


def init(
    target: Path,
    project_name: str | None = None,
    package_name: str | None = None,
    with_dev_dependencies: bool = False,
    git_host: str | None = None,
    language: str = "python",
    template_repository: str | None = None,
    template_branch: str | None = None,
    template_file: Path | None = None,
) -> bool:
    """Initialize or validate .rhiza/template.yml in the target repository.

    Creates a default .rhiza/template.yml file if it doesn't exist,
    or validates an existing one.

    Args:
        target: Path to the target directory. Defaults to the current working directory.
        project_name: Custom project name. Defaults to target directory name.
        package_name: Custom package name. Defaults to normalized project name.
        with_dev_dependencies: Include development dependencies in pyproject.toml.
        git_host: Target Git hosting platform ("github" or "gitlab"). Determines which
            CI/CD configuration files to include. If None, will prompt user interactively.
        language: Programming language for the project (default: python).
            Supported: python, go. Determines which project files to create.
        template_repository: Custom template repository (format: owner/repo).
            Defaults to 'jebel-quant/rhiza' for Python or 'jebel-quant/rhiza-go' for Go.
        template_branch: Custom template branch. Defaults to 'main'.
        template_file: Optional explicit path to write template.yml.  When
            ``None`` the default ``<target>/.rhiza/template.yml`` is used.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    target = target.resolve()
    git_host = _validate_git_host(git_host)

    git_ctx = GitContext.default()
    result = subprocess.run(  # nosec B603  # noqa: S603
        [git_ctx.executable, "rev-parse", "--git-dir"],
        capture_output=True,
        cwd=target,
        env=git_ctx.env,
    )
    if result.returncode != 0:
        logger.error(f"{target} is not a git repository. Run 'git init' first.")
        return False

    logger.info(f"Initializing Rhiza configuration in: {target}")
    logger.info(f"Project language: {language}")

    # Create .rhiza directory (always; project structure lives there regardless of
    # where template.yml is placed)
    rhiza_dir = target / ".rhiza"
    logger.debug(f"Ensuring directory exists: {rhiza_dir}")
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # Determine git host: explicit arg > remote URL detection > interactive prompt
    git_host = _resolve_git_host(target, git_host)

    # When no template repository is specified and no config file exists yet,
    # offer the user an interactive selection from discovered rhiza repos.
    resolved_template_file = template_file if template_file is not None else target / ".rhiza" / "template.yml"
    if template_repository is None and not resolved_template_file.exists():
        template_repository = _prompt_template_repository()

    # Validate template repository reachability early if a custom one is specified
    if template_repository is not None and not _check_template_repository_reachable(template_repository, git_host):
        return False

    # Create template file with language
    _create_template_file(target, git_host, language, template_repository, template_branch, template_file)

    # Bootstrap project structure based on language
    _bootstrap_project_structure(
        target,
        language,
        project_name,
        package_name,
        with_dev_dependencies=with_dev_dependencies,
        git_host=git_host,
    )

    # Validate the template file
    logger.debug("Validating template configuration")
    return validate(target, template_file=template_file)


def _resolve_git_host(target: Path, git_host: GitHost | None) -> GitHost:
    """Resolve the git host: keep an explicit value, else detect from remote, else prompt."""
    if git_host is not None:
        return git_host
    detected = _detect_git_host(target)
    if detected is not None:
        logger.info(f"Detected git host from remote URL: {detected}")
        return detected
    return _prompt_git_host()


def _bootstrap_project_structure(
    target: Path,
    language: str,
    project_name: str | None,
    package_name: str | None,
    *,
    with_dev_dependencies: bool,
    git_host: GitHost | None,
) -> None:
    """Create the initial project files for *language* (python, go, or minimal fallback)."""
    if language == "python":
        _bootstrap_python_project(
            target, project_name, package_name, with_dev_dependencies=with_dev_dependencies, git_host=git_host
        )
    elif language == "go":
        # Go-specific setup - just create README, user should run go mod init
        _create_readme(target)
        logger.info("For Go projects, run 'go mod init <module-name>' to initialize the module")
    else:
        # Unknown language - just create README
        logger.warning(f"Unknown language '{language}', creating minimal structure")
        _create_readme(target)


def _bootstrap_python_project(
    target: Path,
    project_name: str | None,
    package_name: str | None,
    *,
    with_dev_dependencies: bool,
    git_host: GitHost | None,
) -> None:
    """Create the Python project scaffolding (package, pyproject, lock, Makefile, docs, README)."""
    if project_name is None:
        project_name = target.name
    if package_name is None:
        package_name = _normalize_package_name(project_name)

    logger.debug(f"Project name: {project_name}")
    logger.debug(f"Package name: {package_name}")

    github_username = _get_github_username(target)
    _create_python_package(target, project_name, package_name)
    _create_pyproject_toml(target, project_name, package_name, with_dev_dependencies, github_username)
    _create_uv_lock(target)
    _create_makefile(target)
    _create_mkdocs_yml(target, project_name, github_username, git_host)
    _create_readme(target)
