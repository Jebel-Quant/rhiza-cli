"""Data models for Rhiza configuration.

This module defines dataclasses that represent the structure of Rhiza
configuration files, making it easier to work with them without frequent
YAML parsing.
"""

import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

__all__ = [
    "BundleDefinition",
    "RhizaBundles",
    "RhizaTemplate",
    "TemplateLock",
]


def _log_git_stderr_errors(stderr: str | None) -> None:
    """Extract and log only relevant error messages from git stderr."""
    if stderr:
        for line in stderr.strip().split("\n"):
            line = line.strip()
            if line and (line.startswith("fatal:") or line.startswith("error:")):
                logger.error(line)


def _is_excluded(rel_path: Path, excludes: set[str]) -> bool:
    """Check if a relative path (or any of its parents) is in the excludes set.

    Args:
        rel_path: Relative path to check.
        excludes: Set of excluded path strings.

    Returns:
        True if the path or a parent is excluded, False otherwise.
    """
    path_str = str(rel_path)
    if path_str in excludes:
        return True
    return any(str(parent) in excludes for parent in rel_path.parents)


def _normalize_to_list(value: str | list[str] | None) -> list[str]:
    r"""Convert a value to a list of strings.

    Handles the case where YAML multi-line strings (using |) are parsed as
    a single string instead of a list. Splits the string by newlines and
    strips whitespace from each item.

    Args:
        value: A string, list of strings, or None.

    Returns:
        A list of strings. Empty list if value is None or empty.

    Examples:
        >>> _normalize_to_list(None)
        []
        >>> _normalize_to_list([])
        []
        >>> _normalize_to_list(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> _normalize_to_list('single line')
        ['single line']
        >>> _normalize_to_list('line1\\n' + 'line2\\n' + 'line3')
        ['line1', 'line2', 'line3']
        >>> _normalize_to_list('  item1  \\n' + '  item2  ')
        ['item1', 'item2']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Split by newlines and filter out empty strings
        # Handle both actual newlines (\n) and literal backslash-n (\\n)
        items = value.split("\\n") if "\\n" in value and "\n" not in value else value.split("\n")
        return [item.strip() for item in items if item.strip()]
    return []


@dataclass
class BundleDefinition:
    """Represents a single bundle from template-bundles.yml.

    Attributes:
        name: The bundle identifier (e.g., "core", "tests", "github").
        description: Human-readable description of the bundle.
        files: List of file paths included in this bundle.
        workflows: List of workflow file paths included in this bundle.
        depends_on: List of bundle names that this bundle depends on.
    """

    name: str
    description: str
    files: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def all_paths(self) -> list[str]:
        """Return combined files and workflows."""
        return self.files + self.workflows


@dataclass
class RhizaBundles:
    """Represents the structure of template-bundles.yml.

    Attributes:
        version: Optional version string of the bundles configuration format.
        bundles: Dictionary mapping bundle names to their definitions.
    """

    version: str | None = None
    bundles: dict[str, BundleDefinition] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, file_path: Path) -> "RhizaBundles":
        """Load RhizaBundles from a YAML file.

        Args:
            file_path: Path to the template-bundles.yml file.

        Returns:
            The loaded bundles configuration.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file is empty or invalid.
            TypeError: If bundle data has invalid types.
        """
        with open(file_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Bundles file is empty")  # noqa: TRY003

        version = config.get("version")

        bundles_config = config.get("bundles", {})
        if not isinstance(bundles_config, dict):
            msg = "Bundles must be a dictionary"
            raise TypeError(msg)

        bundles: dict[str, BundleDefinition] = {}
        for bundle_name, bundle_data in bundles_config.items():
            if not isinstance(bundle_data, dict):
                msg = f"Bundle '{bundle_name}' must be a dictionary"
                raise TypeError(msg)

            files = _normalize_to_list(bundle_data.get("files"))
            workflows = _normalize_to_list(bundle_data.get("workflows"))
            depends_on = _normalize_to_list(bundle_data.get("depends-on"))

            bundles[bundle_name] = BundleDefinition(
                name=bundle_name,
                description=bundle_data.get("description", ""),
                files=files,
                workflows=workflows,
                depends_on=depends_on,
            )

        return cls(version=version, bundles=bundles)

    def resolve_dependencies(self, bundle_names: list[str]) -> list[str]:
        """Resolve bundle dependencies using topological sort.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Ordered list of bundle names with dependencies first, no duplicates.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        # Validate all bundles exist
        for name in bundle_names:
            if name not in self.bundles:
                raise ValueError(f"Bundle '{name}' not found in template-bundles.yml")  # noqa: TRY003

        resolved: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(bundle_name: str) -> None:
            if bundle_name in visited:
                return
            if bundle_name in visiting:
                raise ValueError(f"Circular dependency detected involving '{bundle_name}'")  # noqa: TRY003

            visiting.add(bundle_name)
            bundle = self.bundles[bundle_name]

            for dep in bundle.depends_on:
                if dep not in self.bundles:
                    raise ValueError(f"Bundle '{bundle_name}' depends on unknown bundle '{dep}'")  # noqa: TRY003
                visit(dep)

            visiting.remove(bundle_name)
            visited.add(bundle_name)
            resolved.append(bundle_name)

        for name in bundle_names:
            visit(name)

        return resolved

    def resolve_to_paths(self, bundle_names: list[str]) -> list[str]:
        """Convert bundle names to deduplicated file paths.

        Args:
            bundle_names: List of bundle names to resolve.

        Returns:
            Deduplicated list of file paths from all bundles and their dependencies.

        Raises:
            ValueError: If a bundle doesn't exist or circular dependency detected.
        """
        resolved_bundles = self.resolve_dependencies(bundle_names)
        paths: list[str] = []
        seen: set[str] = set()

        for bundle_name in resolved_bundles:
            bundle = self.bundles[bundle_name]
            for path in bundle.all_paths():
                if path not in seen:
                    paths.append(path)
                    seen.add(path)

        return paths


@dataclass
class RhizaTemplate:
    """Represents the structure of .rhiza/template.yml.

    Attributes:
        template_repository: The GitHub or GitLab repository containing templates (e.g., "jebel-quant/rhiza").
            Can be None if not specified in the template file.
        template_branch: The branch to use from the template repository.
            Can be None if not specified in the template file (defaults to "main" when creating).
        template_host: The git hosting platform ("github" or "gitlab").
            Defaults to "github" if not specified in the template file.
        language: The programming language of the project ("python", "go", etc.).
            Defaults to "python" if not specified in the template file.
        include: List of paths to include from the template repository (path-based mode).
        exclude: List of paths to exclude from the template repository (default: empty list).
        templates: List of template names to include (template-based mode).
            Can be used together with include to merge paths.
    """

    template_repository: str | None = None
    template_branch: str | None = None
    template_host: str = "github"
    language: str = "python"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, file_path: Path) -> "RhizaTemplate":
        """Load RhizaTemplate from a YAML file.

        Args:
            file_path: Path to the template.yml file.

        Returns:
            The loaded template configuration.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file is empty.
        """
        with open(file_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Template file is empty")  # noqa: TRY003

        # Support both 'repository' and 'template-repository' (repository takes precedence)
        # Empty or None values fall back to the alternative field
        template_repository = config.get("repository") or config.get("template-repository")

        # Support both 'ref' and 'template-branch' (ref takes precedence)
        # Empty or None values fall back to the alternative field
        template_branch = config.get("ref") or config.get("template-branch")

        return cls(
            template_repository=template_repository,
            template_branch=template_branch,
            template_host=config.get("template-host", "github"),
            language=config.get("language", "python"),
            include=_normalize_to_list(config.get("include")),
            exclude=_normalize_to_list(config.get("exclude")),
            templates=_normalize_to_list(config.get("templates")),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save RhizaTemplate to a YAML file.

        Args:
            file_path: Path where the template.yml file should be saved.
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary with YAML-compatible keys
        config: dict[str, Any] = {}

        # Only include repository if it's not None
        if self.template_repository:
            config["repository"] = self.template_repository

        # Only include ref if it's not None
        if self.template_branch:
            config["ref"] = self.template_branch

        # Only include template-host if it's not the default "github"
        if self.template_host and self.template_host != "github":
            config["template-host"] = self.template_host

        # Only include language if it's not the default "python"
        if self.language and self.language != "python":
            config["language"] = self.language

        # Write templates if present
        if self.templates:
            config["templates"] = self.templates

        # Write include if present (can coexist with templates)
        if self.include:
            config["include"] = self.include

        # Only include exclude if it's not empty
        if self.exclude:
            config["exclude"] = self.exclude

        with open(file_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    @property
    def git_url(self) -> str:
        """Construct the HTTPS clone URL for this template repository.

        Returns:
            HTTPS clone URL derived from ``template_repository`` and
            ``template_host``.

        Raises:
            ValueError: If ``template_repository`` is not set or
                ``template_host`` is not ``"github"`` or ``"gitlab"``.
        """
        if not self.template_repository:
            raise ValueError("template_repository is not configured in template.yml")  # noqa: TRY003
        host = self.template_host or "github"
        if host == "github":
            return f"https://github.com/{self.template_repository}.git"
        if host == "gitlab":
            return f"https://gitlab.com/{self.template_repository}.git"
        raise ValueError(f"Unsupported template-host: {host}. Must be 'github' or 'gitlab'.")  # noqa: TRY003

    # ------------------------------------------------------------------
    # Private template helpers (migrated from _sync_helpers)
    # ------------------------------------------------------------------

    @staticmethod
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

    def _clone_template_repository(
        self,
        tmp_dir: Path,
        rhiza_branch: str,
        include_paths: list[str],
        git_executable: str,
        git_env: dict[str, str],
    ) -> None:
        """Clone template repository with sparse checkout.

        Args:
            tmp_dir: Temporary directory for cloning.
            rhiza_branch: Branch to clone.
            include_paths: Initial paths to include in sparse checkout.
            git_executable: Path to git executable.
            git_env: Environment variables for git commands.
        """
        git_url = self.git_url
        try:
            logger.debug("Executing git clone with sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    git_executable,
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    "--branch",
                    rhiza_branch,
                    git_url,
                    str(tmp_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Git clone completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository from {git_url}")
            _log_git_stderr_errors(e.stderr)
            logger.error("Please check that:")
            logger.error("  - The repository exists and is accessible")
            logger.error(f"  - Branch '{rhiza_branch}' exists in the repository")
            logger.error("  - You have network access to the git hosting service")
            raise

        try:
            logger.debug("Initializing sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "sparse-checkout", "init", "--cone"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Sparse checkout initialized")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to initialize sparse checkout")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            logger.debug(f"Setting sparse checkout paths: {include_paths}")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            logger.debug("Sparse checkout paths configured")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to configure sparse checkout paths")
            _log_git_stderr_errors(e.stderr)
            raise

    def _clone_at_sha(
        self,
        sha: str,
        dest: Path,
        include_paths: list[str],
        git_executable: str,
        git_env: dict[str, str],
    ) -> None:
        """Clone the template repository and checkout a specific commit.

        Args:
            sha: Commit SHA to check out.
            dest: Target directory for the clone.
            include_paths: Paths for sparse checkout.
            git_executable: Absolute path to git.
            git_env: Environment variables for git commands.
        """
        git_url = self.git_url
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    git_executable,
                    "clone",
                    "--filter=blob:none",
                    "--sparse",
                    "--no-checkout",
                    git_url,
                    str(dest),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository for base snapshot: {git_url}")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "sparse-checkout", "init", "--cone"],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Failed to configure sparse checkout for base snapshot")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_executable, "checkout", sha],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_env,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to checkout base commit {sha[:12]}")
            _log_git_stderr_errors(e.stderr)
            raise

    @classmethod
    def from_project(cls, target: Path, branch: str = "main") -> "RhizaTemplate":
        """Validate and load a :class:`RhizaTemplate` from a project directory.

        Validates the project's ``template.yml`` via :func:`~rhiza.commands.validate.validate`,
        then loads the configuration with :meth:`from_yaml` and checks that
        the required fields are present.

        Args:
            target: Path to the target repository (must contain ``.git`` and
                ``.rhiza/template.yml``).
            branch: The Rhiza template branch to use as a fallback when
                ``template-branch`` is not set in ``template.yml``.

        Returns:
            The loaded and validated :class:`RhizaTemplate`.
        """
        from rhiza.commands.validate import validate

        valid = validate(target)
        if not valid:
            logger.error(f"Rhiza template is invalid in: {target}")
            logger.error("Please fix validation errors and try again")
            raise RuntimeError("Rhiza template validation failed")  # noqa: TRY003

        template_file = target / ".rhiza" / "template.yml"
        template = cls.from_yaml(template_file)

        if not template.template_repository:
            logger.error("template-repository is not configured in template.yml")
            raise RuntimeError("template-repository is required")  # noqa: TRY003

        if not template.template_branch:
            template.template_branch = branch

        if not template.templates and not template.include:
            logger.error("No templates or include paths found in template.yml")
            logger.error("Add either 'templates' or 'include' list in template.yml")
            raise RuntimeError("No templates or include paths found in template.yml")  # noqa: TRY003

        if template.templates:
            logger.info("Templates:")
            for t in template.templates:
                logger.info(f"  - {t}")

        if template.include:
            logger.info("Include paths:")
            for p in template.include:
                logger.info(f"  - {p}")

        if template.exclude:
            logger.info("Exclude paths:")
            for p in template.exclude:
                logger.info(f"  - {p}")

        return template

    # ------------------------------------------------------------------
    # Public clone / snapshot workflow methods
    # ------------------------------------------------------------------

    def clone(
        self,
        git_executable: str,
        git_env: dict[str, str],
        branch: str = "main",
    ) -> tuple[Path, str, list[str]]:
        """Clone the upstream template repository and resolve include paths.

        Clones the template repository using sparse checkout.  When
        ``templates`` are configured the corresponding bundle names are resolved
        to file paths.

        Args:
            git_executable: Absolute path to the git executable.
            git_env: Environment variables for git commands.
            branch: Default branch to use when ``template_branch`` is not set
                on the template.

        Returns:
            Tuple of ``(upstream_dir, upstream_sha, include_paths)`` where
            *upstream_dir* is a temporary directory containing the cloned
            repository tree and *include_paths* is the resolved list of paths
            to include (from bundle resolution when ``templates`` are
            configured, otherwise ``self.include``).  The caller is
            responsible for removing *upstream_dir* when done.

        Raises:
            ValueError: If ``template_repository`` is not set, the host is
                unsupported, or no include paths / templates are configured.
            subprocess.CalledProcessError: If a git operation fails.
        """
        from rhiza.bundle_resolver import (
            load_bundles_from_clone,
            resolve_include_paths,
        )

        if not self.template_repository:
            raise ValueError("template_repository is not configured in template.yml")  # noqa: TRY003
        if not self.templates and not self.include:
            raise ValueError("No templates or include paths found in template.yml")  # noqa: TRY003

        rhiza_branch = self.template_branch or branch
        include_paths = self.include

        upstream_dir = Path(tempfile.mkdtemp())
        initial_paths = [".rhiza"] if self.templates else include_paths
        self._clone_template_repository(upstream_dir, rhiza_branch, initial_paths, git_executable, git_env)

        if self.templates:
            bundles_config = load_bundles_from_clone(upstream_dir)
            resolved_paths = resolve_include_paths(self, bundles_config)
            try:
                logger.debug(f"Updating sparse checkout paths: {resolved_paths}")
                subprocess.run(  # nosec B603  # noqa: S603
                    [git_executable, "sparse-checkout", "set", "--skip-checks", *resolved_paths],
                    cwd=upstream_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=git_env,
                )
                logger.debug("Sparse checkout paths updated")
            except subprocess.CalledProcessError as e:
                logger.error("Failed to update sparse checkout paths")
                _log_git_stderr_errors(e.stderr)
                raise
            include_paths = resolved_paths

        upstream_sha = self._get_head_sha(upstream_dir, git_executable, git_env)
        logger.info(f"Upstream HEAD: {upstream_sha[:12]}")

        return upstream_dir, upstream_sha, include_paths

    def snapshot(
        self,
        upstream_dir: Path,
        snapshot_dir: Path,
    ) -> tuple[list[Path], set[str]]:
        """Build a clean snapshot of the included template files.

        Computes the set of excluded paths from ``self.exclude`` (adding default
        rhiza exclusions) and copies all included (non-excluded) files from
        *upstream_dir* into *snapshot_dir*, producing a flat tree suitable for
        ``git diff --no-index``.

        Args:
            upstream_dir: Root of the cloned template repository (returned by
                :meth:`clone`).
            snapshot_dir: Destination directory for the snapshot.  Must already
                exist.

        Returns:
            Tuple of ``(materialized, excludes)`` where *materialized* is the
            list of relative file paths that were copied and *excludes* is the
            full set of relative path strings that were skipped.
        """
        excludes = set(self.exclude)
        excludes.add(".rhiza/template.yml")
        excludes.add(".rhiza/history")

        materialized: list[Path] = []
        for f in upstream_dir.rglob("*"):
            if not f.is_file():
                continue

            rel = f.relative_to(upstream_dir)
            if str(rel).startswith(".git/"):
                continue

            if not _is_excluded(rel, excludes):
                dst = snapshot_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                materialized.append(rel)

        return sorted(materialized), excludes


@dataclass
class TemplateLock:
    """Represents the structure of .rhiza/template.lock.

    Attributes:
        sha: The commit SHA of the last-synced template.
        repo: The template repository (e.g., "jebel-quant/rhiza").
        host: The git hosting platform (e.g., "github", "gitlab").
        ref: The branch or ref that was synced (e.g., "main").
        include: List of paths included from the template.
        exclude: List of paths excluded from the template.
        templates: List of template bundle names.
        files: List of file paths that were synced.
        synced_at: ISO 8601 UTC timestamp of when the sync was performed.
        strategy: The sync strategy used (e.g., "merge", "diff", "materialize").
    """

    sha: str
    repo: str = ""
    host: str = "github"
    ref: str = "main"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    synced_at: str = ""
    strategy: str = ""

    @classmethod
    def from_yaml(cls, file_path: Path) -> "TemplateLock":
        """Load TemplateLock from a YAML file.

        Supports both the structured YAML format and the legacy plain-SHA format.

        Args:
            file_path: Path to the template.lock file.

        Returns:
            The loaded lock data.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the YAML is malformed.
            ValueError: If the file format is not recognised.
        """
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        data = yaml.safe_load(content)

        # Legacy plain-SHA format: yaml.safe_load returns the SHA string directly.
        if isinstance(data, str):
            return cls(sha=data.strip())

        if not isinstance(data, dict):
            raise TypeError("Invalid template.lock format")  # noqa: TRY003

        return cls(
            sha=data.get("sha", ""),
            repo=data.get("repo", ""),
            host=data.get("host", "github"),
            ref=data.get("ref", "main"),
            include=_normalize_to_list(data.get("include")),
            exclude=_normalize_to_list(data.get("exclude")),
            templates=_normalize_to_list(data.get("templates")),
            files=_normalize_to_list(data.get("files")),
            synced_at=data.get("synced_at", ""),
            strategy=data.get("strategy", ""),
        )

    def to_yaml(self, file_path: Path) -> None:
        """Save TemplateLock to a YAML file.

        Args:
            file_path: Path where the template.lock file should be saved.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        config: dict[str, Any] = {
            "sha": self.sha,
            "repo": self.repo,
            "host": self.host,
            "ref": self.ref,
            "include": self.include,
            "exclude": self.exclude,
            "templates": self.templates,
            "files": self.files,
        }

        if self.synced_at:
            config["synced_at"] = self.synced_at
        if self.strategy:
            config["strategy"] = self.strategy

        class _IndentedDumper(yaml.Dumper):
            def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
                # Always use indented style for sequences regardless of context.
                return super().increase_indent(flow, indentless=False)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# This file is automatically generated by rhiza. Do not edit it manually.\n")
            yaml.dump(
                config,
                f,
                Dumper=_IndentedDumper,
                default_flow_style=False,
                sort_keys=False,
                explicit_start=True,
            )
