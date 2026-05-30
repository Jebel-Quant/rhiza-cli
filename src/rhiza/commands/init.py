"""Command to initialize or validate .rhiza/template.yml.

This module provides the init command that creates or validates the
.rhiza/template.yml file, which defines where templates come from
and what paths are governed by Rhiza.
"""

import importlib.resources
import keyword
import re
import subprocess  # nosec B404
import sys
import urllib.error
from pathlib import Path

import typer
from jinja2 import Template
from loguru import logger

from rhiza.commands.list_repos import _DESC_WIDTH, _fetch_repos
from rhiza.commands.validate import validate
from rhiza.models import GitContext, GitHost


def _normalize_package_name(name: str) -> str:
    """Normalize a string into a valid Python package name.

    Args:
        name: The input string (e.g., project name).

    Returns:
        A valid Python identifier safe for use as a package name.
    """
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name[0].isdigit():
        name = f"_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _validate_git_host(git_host: str | None) -> GitHost | None:
    """Validate git_host parameter.

    Args:
        git_host: Git hosting platform.

    Returns:
        Validated GitHost enum value or None.

    Raises:
        ValueError: If git_host is invalid.
    """
    if git_host is None:
        return None
    try:
        return GitHost(git_host.lower())
    except ValueError:
        logger.error(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'")
        raise ValueError(f"Invalid git-host: {git_host}. Must be 'github' or 'gitlab'") from None  # noqa: TRY003


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
            logger.error(f"Template repository '{template_repository}' is not accessible at {repo_url}")
            logger.error("Please check that the repository exists and you have access to it.")
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

        version_tags = []
        for line in result.stdout.splitlines():
            if "^{}" in line:  # skip dereferenced annotated-tag objects
                continue
            parts = line.split("\t")
            if len(parts) == 2 and parts[1].startswith("refs/tags/"):
                tag = parts[1][len("refs/tags/") :]
                if re.match(r"^v?\d+\.\d+", tag):
                    version_tags.append(tag)

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
        if "github.com" in url:
            logger.debug(f"Detected git host: github (from {url})")
            return GitHost.GITHUB
        if "gitlab.com" in url:
            logger.debug(f"Detected git host: gitlab (from {url})")
            return GitHost.GITLAB
    except (RuntimeError, OSError):
        return None
    else:
        return None


def _prompt_git_host() -> GitHost:
    """Prompt user for git hosting platform.

    Returns:
        Git hosting platform choice as a GitHost enum value.
    """
    if sys.stdin.isatty():
        logger.info("Where will your project be hosted?")
        git_host = typer.prompt(
            "Target Git hosting platform (github/gitlab)",
            type=str,
            default="github",
        ).lower()

        while git_host not in GitHost._value2member_map_:
            logger.warning(f"Invalid choice: {git_host}. Please choose 'github' or 'gitlab'")
            git_host = typer.prompt(
                "Target Git hosting platform (github/gitlab)",
                type=str,
                default="github",
            ).lower()
    else:
        git_host = "github"
        logger.debug("Non-interactive mode detected, defaulting to github")

    return GitHost(git_host)


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


def _get_default_profile_for_host(git_host: GitHost | str) -> str:
    """Return the profile name that matches the git hosting platform.

    Args:
        git_host: Git hosting platform.

    Returns:
        Profile name (e.g. ``"gitlab-project"`` or ``"github-project"``).
    """
    if git_host == GitHost.GITLAB:
        return "gitlab-project"
    return "github-project"


def _display_path(path: Path, target: Path) -> Path:
    """Return *path* relative to *target* when possible, otherwise the absolute path.

    Args:
        path: Path to display.
        target: Base directory used as the reference point.

    Returns:
        A relative or absolute Path suitable for log messages.
    """
    return path.relative_to(target) if path.is_relative_to(target) else path


def _create_template_file(
    target: Path,
    git_host: GitHost | str,
    language: str = "python",
    template_repository: str | None = None,
    template_branch: str | None = None,
    template_file: Path | None = None,
) -> None:
    """Create default template.yml file.

    Args:
        target: Target repository path.
        git_host: Git hosting platform.
        language: Programming language for the project (default: python).
        template_repository: Custom template repository (format: owner/repo).
        template_branch: Custom template branch.
        template_file: Optional explicit path to write template.yml.  When
            ``None`` the default ``<target>/.rhiza/template.yml`` is used.
    """
    if template_file is None:
        rhiza_dir = target / ".rhiza"
        template_file = rhiza_dir / "template.yml"

    if template_file.exists():
        return

    template_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Creating default {_display_path(template_file, target)}")
    logger.debug("Using default template configuration")

    # Use custom template repository/branch if provided, otherwise use language defaults
    if template_repository:
        repo = template_repository
        logger.info(f"Using custom template repository: {repo}")
    else:
        # Default repositories by language
        repo = "jebel-quant/rhiza-go" if language == "go" else "jebel-quant/rhiza"
        logger.debug(f"Using default repository for {language}: {repo}")

    if template_branch:
        branch = template_branch
        logger.info(f"Using custom template branch: {branch}")
    else:
        latest = _get_latest_tag(repo, git_host)
        if latest:
            branch = latest
            logger.info(f"Using latest tag: {branch}")
        else:
            branch = "main"
            logger.warning("Could not determine latest tag, falling back to 'main'")

    profile = _get_default_profile_for_host(git_host)
    logger.info(f"Using profile: {profile}")

    jinja_src = importlib.resources.files("rhiza").joinpath("_templates/basic/template.yml.jinja2").read_text()
    rendered = Template(jinja_src, keep_trailing_newline=True).render(
        template_repository=repo,
        template_branch=branch,
        git_host=str(git_host),
        language=language,
        profile=profile,
    )

    logger.debug(f"Writing default template to: {template_file}")
    template_file.write_text(rendered)

    logger.success(f"✓ Created {_display_path(template_file, target)}")
    logger.info("""
Next steps:
  1. Review and customize .rhiza/template.yml to match your project needs
  2. Run 'uvx rhiza sync' to inject templates into your repository
""")


def _create_python_package(target: Path, project_name: str, package_name: str) -> None:
    """Create basic Python package structure.

    Args:
        target: Target repository path.
        project_name: Project name.
        package_name: Package name.
    """
    src_folder = target / "src" / package_name
    test_folder = target / "tests"

    if (target / "src").exists():
        return

    logger.info(f"Creating Python package structure: {src_folder}")
    src_folder.mkdir(parents=True)

    logger.info(f"Creating test folder: {test_folder}")
    test_folder.mkdir(parents=True)

    # Create __init__.py
    init_file = src_folder / "__init__.py"
    logger.debug(f"Creating {init_file}")
    init_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/__init__.py.jinja2").read_text()
    template = Template(template_content, keep_trailing_newline=True)
    code = template.render(project_name=project_name)
    init_file.write_text(code)

    # Create main.py
    main_file = src_folder / "main.py"
    logger.debug(f"Creating {main_file} with example code")
    main_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/main.py.jinja2").read_text()
    template = Template(template_content, keep_trailing_newline=True)
    code = template.render(project_name=project_name)
    main_file.write_text(code)
    logger.success(f"Created Python package structure in {src_folder}")

    # Create main.py
    test_file = test_folder / "test_main.py"
    logger.debug(f"Creating {test_file} with example code")
    test_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/test_main.py.jinja2").read_text()
    template = Template(template_content, keep_trailing_newline=True)
    code = template.render(project_name=package_name)
    test_file.write_text(code)
    # logger.success(f"Created Python package structure in {src_folder}")


def _create_pyproject_toml(
    target: Path,
    project_name: str,
    package_name: str,
    with_dev_dependencies: bool,
    github_username: str = "your-org",
) -> None:
    """Create pyproject.toml file.

    Args:
        target: Target repository path.
        project_name: Project name.
        package_name: Package name.
        with_dev_dependencies: Whether to include dev dependencies.
        github_username: GitHub/GitLab username or org extracted from the origin remote.
    """
    pyproject_file = target / "pyproject.toml"
    if pyproject_file.exists():
        return

    logger.info("Creating pyproject.toml with basic project metadata")
    pyproject_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/pyproject.toml.jinja2").read_text()
    template = Template(template_content, keep_trailing_newline=True)
    code = template.render(
        project_name=project_name,
        package_name=package_name,
        with_dev_dependencies=with_dev_dependencies,
        github_username=github_username,
    )
    pyproject_file.write_text(code)
    logger.success("Created pyproject.toml")


def _create_uv_lock(target: Path) -> None:
    """Run ``uv lock`` to generate the initial uv.lock file.

    Args:
        target: Repository root directory.
    """
    lock_file = target / "uv.lock"
    if lock_file.exists():
        return

    logger.info("Generating uv.lock")
    try:
        result = subprocess.run(  # nosec B603 B607
            ["uv", "lock"],  # noqa: S607
            cwd=target,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.success("Created uv.lock")
        else:
            logger.warning(f"uv lock failed (exit {result.returncode}): {result.stderr.strip()}")
    except (OSError, FileNotFoundError):
        logger.warning("uv not found — skipping uv.lock generation. Run 'uv lock' manually.")


def _create_makefile(target: Path) -> None:
    """Create a minimal Makefile that bootstraps ``make sync`` before rhiza.mk exists.

    Args:
        target: Target repository path.
    """
    makefile = target / "Makefile"
    if makefile.exists():
        return

    logger.info("Creating Makefile")
    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/Makefile.jinja2").read_text()
    makefile.write_text(Template(template_content, keep_trailing_newline=True).render())
    logger.success("Created Makefile")


def _create_mkdocs_yml(target: Path, project_name: str, username: str, git_host: GitHost | None = None) -> None:
    """Create mkdocs.yml file.

    Args:
        target: Target repository path.
        project_name: Project name.
        username: GitHub/GitLab username or org extracted from the origin remote.
        git_host: Git hosting platform; controls repo and pages URLs.
    """
    mkdocs_file = target / "mkdocs.yml"
    if mkdocs_file.exists():
        return

    if git_host == GitHost.GITLAB:
        repo_host = "gitlab.com"
        pages_host = "gitlab.io"
    else:
        repo_host = "github.com"
        pages_host = "github.io"

    logger.info("Creating mkdocs.yml")
    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/mkdocs.yml.jinja2").read_text()
    mkdocs_file.write_text(
        Template(template_content, keep_trailing_newline=True).render(
            project_name=project_name,
            username=username,
            repo_host=repo_host,
            pages_host=pages_host,
        )
    )
    logger.success("Created mkdocs.yml")


def _create_readme(target: Path) -> None:
    """Create README.md file.

    Args:
        target: Target repository path.
    """
    readme_file = target / "README.md"
    if readme_file.exists():
        return

    logger.info("Creating README.md")
    readme_file.touch()
    logger.success("Created README.md")


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
    if git_host is None:
        git_host = _detect_git_host(target)
        if git_host is not None:
            logger.info(f"Detected git host from remote URL: {git_host}")
        else:
            git_host = _prompt_git_host()

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
    if language == "python":
        # Python-specific setup
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
    elif language == "go":
        # Go-specific setup - just create README, user should run go mod init
        _create_readme(target)
        logger.info("For Go projects, run 'go mod init <module-name>' to initialize the module")
    else:
        # Unknown language - just create README
        logger.warning(f"Unknown language '{language}', creating minimal structure")
        _create_readme(target)

    # Validate the template file
    logger.debug("Validating template configuration")
    return validate(target, template_file=template_file)
