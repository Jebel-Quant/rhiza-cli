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
from typing import TYPE_CHECKING

import questionary
from jinja2 import Template
from loguru import logger

from rhiza.commands.list_repos import _fetch_repos
from rhiza.commands.validate import validate
from rhiza.models import GitContext, GitHost, RhizaTemplate

if TYPE_CHECKING:
    from rhiza.models.bundle import RhizaBundles

# ---------------------------------------------------------------------------
# Rhiza brand style — cyan on dark terminals
# ---------------------------------------------------------------------------

_RHIZA_STYLE = questionary.Style(
    [
        ("qmark", "fg:#00BCD4 bold"),  # the ? marker
        ("question", "bold"),  # question text
        ("answer", "fg:#00BCD4 bold"),  # confirmed answer
        ("pointer", "fg:#00BCD4 bold"),  # > cursor in select
        ("highlighted", "fg:#00BCD4 bold"),  # hovered item in select
        ("selected", "fg:#00ff00 bold"),  # checked checkbox item (green dot)
        ("separator", "fg:#444444"),  # separator lines
        ("instruction", "fg:#666666 italic"),  # hint text
        ("text", "fg:#aaaaaa"),  # unchecked items (dimmed)
    ]
)


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


def _check_template_repository_reachable(template_repository: str, git_host: GitHost | str = GitHost.GITHUB) -> bool:
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


def _prompt_git_host() -> GitHost:
    """Prompt user for git hosting platform using an interactive menu.

    Returns:
        Git hosting platform choice as a GitHost enum value.
    """
    if sys.stdin.isatty():
        choice = questionary.select(
            "Where will your project be hosted?",
            choices=[
                questionary.Choice("GitHub", value="github"),
                questionary.Choice("GitLab", value="gitlab"),
            ],
            default="github",
            style=_RHIZA_STYLE,
        ).ask()
        if choice is None:
            # User cancelled (Ctrl-C / Escape) — fall back to github
            choice = "github"
    else:
        choice = "github"
        logger.debug("Non-interactive mode detected, defaulting to github")

    return GitHost(choice)


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

    import shutil

    term_width = shutil.get_terminal_size((80, 24)).columns
    # 4 = questionary pointer/indicator prefix, 30 = repo name col, 2 = spacing, 1 = ellipsis
    menu_desc_width = max(10, term_width - 4 - 30 - 2 - 1)

    default_label = "Use the default repository"
    choices = [questionary.Choice(title=default_label, value=None)]
    for repo in repos:
        if repo.description:
            raw = repo.description[:menu_desc_width]
            desc = raw + "…" if len(repo.description) > menu_desc_width else raw
        else:
            desc = ""
        label = f"{repo.full_name:<30}  {desc}".rstrip()
        choices.append(questionary.Choice(title=label, value=repo.full_name))

    chosen = questionary.select(
        "Select a template repository:",
        choices=choices,
        style=_RHIZA_STYLE,
    ).ask()

    if chosen is None:
        # Either user picked the default option or cancelled (Ctrl-C)
        return None

    logger.info(f"Selected template repository: {chosen}")
    return chosen


def _get_default_templates_for_host(git_host: GitHost | str) -> list[str]:
    """Get default templates based on git hosting platform.

    Args:
        git_host: Git hosting platform.

    Returns:
        List of template names.

    .. deprecated::
        Use :func:`_prompt_profile` instead.  This function is retained for
        backward compatibility when profile selection is not available
        (e.g. offline, non-interactive, or the upstream bundle file has no
        profiles section).
    """
    common = ["core", "tests", "book", "marimo", "presentation"]
    if git_host == GitHost.GITLAB:
        return [*common, "gitlab"]
    else:
        return [*common, "github"]


def _fetch_profiles_from_upstream(
    repo: str,
    branch: str = "main",
    git_host: GitHost | str = GitHost.GITHUB,
    bundles_path: str = ".rhiza/template-bundles.yml",
) -> tuple[dict[str, str], "RhizaBundles"] | None:
    """Fetch available profiles from the upstream template-bundles.yml.

    Args:
        repo: Template repository in 'owner/repo' format.
        branch: Branch to fetch from. Defaults to 'main'.
        git_host: Git host. Defaults to GitHub.
        bundles_path: Path to bundle definitions inside the repo.

    Returns:
        Tuple of (profiles map, full RhizaBundles object), or ``None`` if the
        file could not be fetched or contains no profiles section.
    """
    import tempfile

    from rhiza.models.bundle import RhizaBundles

    try:
        git_ctx = GitContext.default()
        host_urls = {
            GitHost.GITHUB: "https://github.com",
            GitHost.GITLAB: "https://gitlab.com",
        }
        base_url = host_urls.get(git_host, "https://github.com")  # type: ignore[call-overload]
        repo_url = f"{base_url}/{repo}.git"

        tmpdir = Path(tempfile.mkdtemp())
        try:
            git_ctx.clone_repository(repo_url, tmpdir, branch, [bundles_path])
            bundles_file = tmpdir / bundles_path
            if not bundles_file.exists():
                return None
            rb = RhizaBundles.from_yaml(bundles_file)
            if not rb.profiles:
                return None
            return {name: profile.description for name, profile in rb.profiles.items()}, rb
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as exc:
        logger.debug(f"Could not fetch profiles from upstream: {exc}")
        return None


def _prompt_profile(
    profiles: dict[str, str],
    git_host: GitHost | str = GitHost.GITHUB,
    available_bundles: "RhizaBundles | None" = None,
) -> tuple[list[str], list[str]]:
    """Prompt the user to select a profile or hand-pick individual bundles.

    Args:
        profiles: Mapping of profile name → description.
        git_host: Current git host (used for advanced fallback).
        available_bundles: Full bundle definitions for advanced selection. When
            provided, advanced mode shows a checkbox list of all bundles instead
            of falling back to a hard-coded default list.

    Returns:
        Tuple of ``(selected_profiles, selected_templates)`` where exactly
        one of the two lists will be non-empty.  In profile mode
        ``selected_templates`` is empty; in advanced mode
        ``selected_profiles`` is empty.
    """
    if not sys.stdin.isatty():
        # Non-interactive: pick a sensible default profile
        default = "github-project" if git_host == GitHost.GITHUB else "gitlab-project"
        chosen = default if default in profiles else next(iter(profiles), None)
        if chosen:
            logger.debug(f"Non-interactive mode: using profile '{chosen}'")
            return [chosen], []
        return [], _get_default_templates_for_host(git_host)

    # Build choices: one per profile + a separator + advanced option
    choices: list[questionary.Choice | questionary.Separator] = []
    for name, desc in profiles.items():
        first_line = desc.strip().split("\n")[0].strip()
        choices.append(questionary.Choice(title=f"{name}  —  {first_line}", value=name))
    choices.append(questionary.Separator())
    choices.append(questionary.Choice(title="Advanced — hand-pick individual bundles", value="__advanced__"))

    selection = questionary.select(
        "Select a setup profile:",
        choices=choices,
        style=_RHIZA_STYLE,
    ).ask()

    if selection is None:
        # Cancelled — fall back to sensible default
        default = "github-project" if git_host == GitHost.GITHUB else "gitlab-project"
        chosen = default if default in profiles else next(iter(profiles), None)
        return ([chosen], []) if chosen else ([], _get_default_templates_for_host(git_host))

    if selection == "__advanced__":
        return _prompt_advanced_bundles(git_host, available_bundles)

    logger.info(f"Selected profile: {selection}")
    return [selection], []


def _prompt_advanced_bundles(
    git_host: GitHost | str = GitHost.GITHUB,
    available_bundles: "RhizaBundles | None" = None,
) -> tuple[list[str], list[str]]:
    """Prompt the user to hand-pick individual bundles via a checkbox list.

    Args:
        git_host: Current git host (used for default selection hints).
        available_bundles: Full bundle definitions. When ``None`` falls back to
            the hard-coded default list for the host.

    Returns:
        Tuple of ``([], selected_templates)`` — profiles list is always empty
        in advanced mode.
    """
    if available_bundles and available_bundles.bundles:
        default_names = set(_get_default_templates_for_host(git_host))
        choices = [
            questionary.Choice(
                title=f"{name}  —  {(bundle.description or '').splitlines()[0].split('.')[0].strip()}".rstrip(),
                value=name,
                checked=name in default_names,
            )
            for name, bundle in available_bundles.bundles.items()
        ]
        selected = questionary.checkbox(
            "Select bundles:",
            choices=choices,
            style=_RHIZA_STYLE,
        ).ask()
        if selected is None or not selected:
            # Cancelled or nothing chosen — fall back to defaults
            logger.debug("Advanced bundle selection cancelled, using defaults")
            return [], _get_default_templates_for_host(git_host)
        logger.info(f"Advanced mode: selected bundles: {', '.join(selected)}")
        return [], selected

    # No bundle metadata available — fall back to defaults silently
    logger.info("Advanced mode: using default bundle set for your git host")
    return [], _get_default_templates_for_host(git_host)


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

    branch = template_branch or "main"

    # Log when custom values are used
    if template_branch:
        logger.info(f"Using custom template branch: {branch}")

    # Attempt profile-first selection: fetch upstream profiles and prompt user.
    # TODO: remove feat/bundle-profiles fallback once that branch is merged to main.
    fetch_result = _fetch_profiles_from_upstream(repo, branch, git_host)
    if not fetch_result:
        fetch_result = _fetch_profiles_from_upstream(repo, "feat/bundle-profiles", git_host)

    selected_profiles: list[str] = []
    selected_templates: list[str] = []

    if fetch_result:
        profiles_map, available_bundles = fetch_result
        selected_profiles, selected_templates = _prompt_profile(profiles_map, git_host, available_bundles)
    else:
        # Fallback to legacy template list (offline or pre-profile upstream)
        selected_templates = _get_default_templates_for_host(git_host)
        logger.info(f"Using template-based configuration with templates: {', '.join(selected_templates)}")

    if selected_profiles:
        logger.info(f"Using profile-based configuration with profiles: {', '.join(selected_profiles)}")

    default_template = RhizaTemplate(
        template_repository=repo,
        template_branch=branch,
        language=language,
        profiles=selected_profiles,
        templates=selected_templates,
    )

    logger.debug(f"Writing default template to: {template_file}")
    default_template.to_yaml(template_file)

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
    template = Template(template_content)
    code = template.render(project_name=project_name)
    init_file.write_text(code)

    # Create main.py
    main_file = src_folder / "main.py"
    logger.debug(f"Creating {main_file} with example code")
    main_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/main.py.jinja2").read_text()
    template = Template(template_content)
    code = template.render(project_name=project_name)
    main_file.write_text(code)
    logger.success(f"Created Python package structure in {src_folder}")

    # Create main.py
    test_file = test_folder / "test_main.py"
    logger.debug(f"Creating {test_file} with example code")
    test_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/test_main.py.jinja2").read_text()
    template = Template(template_content)
    code = template.render(project_name=project_name)
    test_file.write_text(code)
    # logger.success(f"Created Python package structure in {src_folder}")


def _create_pyproject_toml(target: Path, project_name: str, package_name: str, with_dev_dependencies: bool) -> None:
    """Create pyproject.toml file.

    Args:
        target: Target repository path.
        project_name: Project name.
        package_name: Package name.
        with_dev_dependencies: Whether to include dev dependencies.
    """
    pyproject_file = target / "pyproject.toml"
    if pyproject_file.exists():
        return

    logger.info("Creating pyproject.toml with basic project metadata")
    pyproject_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/pyproject.toml.jinja2").read_text()
    template = Template(template_content)
    code = template.render(
        project_name=project_name,
        package_name=package_name,
        with_dev_dependencies=with_dev_dependencies,
    )
    pyproject_file.write_text(code)
    logger.success("Created pyproject.toml")


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

    logger.info(f"Initializing Rhiza configuration in: {target}")
    logger.info(f"Project language: {language}")

    # Create .rhiza directory (always; project structure lives there regardless of
    # where template.yml is placed)
    rhiza_dir = target / ".rhiza"
    logger.debug(f"Ensuring directory exists: {rhiza_dir}")
    rhiza_dir.mkdir(parents=True, exist_ok=True)

    # Determine git host
    if git_host is None:
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

        _create_python_package(target, project_name, package_name)
        _create_pyproject_toml(target, project_name, package_name, with_dev_dependencies)
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
