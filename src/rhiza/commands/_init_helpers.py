"""Helper functions backing the ``rhiza init`` command.

This module holds the project-scaffolding helpers used by
:func:`rhiza.commands.init.init` — naming/profile utilities and the
``_create_*`` functions that create individual project files
(package structure, ``pyproject.toml``, ``Makefile``, ``mkdocs.yml``,
``README.md``) and the ``template.yml`` file itself.

These functions are re-exported from :mod:`rhiza.commands.init` so the
public import surface (``rhiza.commands.init._create_*``) stays stable.
"""

import importlib.resources
import keyword
import re
import subprocess  # nosec B404
from pathlib import Path

from jinja2 import Template
from loguru import logger

from rhiza.models import GitHost


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
    # Resolved lazily via sys.modules to avoid a circular import and so that
    # test patches of ``rhiza.commands.init._get_latest_tag`` are honoured at
    # call time. (A ``from rhiza.commands import init`` binding is ambiguous
    # with the re-exported ``init`` function, so we import the module instead.)
    import importlib

    _init_mod = importlib.import_module("rhiza.commands.init")

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
        latest = _init_mod._get_latest_tag(repo, git_host)
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

    # Create test_main.py
    test_file = test_folder / "test_main.py"
    logger.debug(f"Creating {test_file} with example code")
    test_file.touch()

    template_content = importlib.resources.files("rhiza").joinpath("_templates/basic/test_main.py.jinja2").read_text()
    template = Template(template_content, keep_trailing_newline=True)
    code = template.render(project_name=package_name)
    test_file.write_text(code)


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
