"""Template model for Rhiza configuration."""

import logging
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from rhiza.models._base import read_yaml
from rhiza.models._git_utils import GitContext, _log_git_stderr_errors, _normalize_to_list
from rhiza.models.bundle import RhizaBundles


class GitHost(StrEnum):
    """Supported git hosting platforms."""

    GITHUB = "github"
    GITLAB = "gitlab"


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

    template_repository: str = ""
    template_branch: str = ""
    template_host: GitHost | str = GitHost.GITHUB
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
        return cls.from_config(read_yaml(file_path))

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RhizaTemplate":
        """Create a RhizaTemplate instance from a configuration dictionary.

        Args:
            config: Dictionary containing template configuration.

        Returns:
            A new RhizaTemplate instance.
        """
        # Support both 'repository' and 'template-repository' (repository takes precedence)
        # Empty or None values fall back to the alternative field
        template_repository = config.get("repository") or config.get("template-repository")

        # Support both 'ref' and 'template-branch' (ref takes precedence)
        # Empty or None values fall back to the alternative field
        template_branch = config.get("ref") or config.get("template-branch")

        return cls(
            template_repository=template_repository or "",
            template_branch=template_branch or "",
            template_host=config.get("template-host", GitHost.GITHUB),
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
        if self.template_host and self.template_host != GitHost.GITHUB:
            config["template-host"] = str(self.template_host)

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
        host = self.template_host or GitHost.GITHUB
        if host == GitHost.GITHUB:
            return f"https://github.com/{self.template_repository}.git"
        if host == GitHost.GITLAB:
            return f"https://gitlab.com/{self.template_repository}.git"
        raise ValueError(f"Unsupported template-host: {host}. Must be 'github' or 'gitlab'.")  # noqa: TRY003

    # ------------------------------------------------------------------
    # Private template helpers (migrated from _sync_helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def _expand_paths(base_dir: Path, paths: list[str], logger=None) -> list[Path]:
        """Expand file/directory paths relative to *base_dir* into individual files.

        Args:
            base_dir: Root directory to resolve against.
            paths: Relative path strings.
            logger: Optional logger; defaults to module logger.

        Returns:
            Flat list of file paths.
        """
        logger = logger or logging.getLogger(__name__)

        all_files: list[Path] = []
        for p in paths:
            full = base_dir / p
            if full.is_file():
                all_files.append(full)
            elif full.is_dir():
                all_files.extend(f for f in full.rglob("*") if f.is_file())
            else:
                logger.debug(f"Path not found in template repository: {p}")
        return all_files

    @staticmethod
    def _excluded_set(base_dir: Path, excluded_paths: list[str]) -> set[str]:
        """Build a set of relative path strings that should be excluded.

        Args:
            base_dir: Root of the template clone.
            excluded_paths: User-configured exclude list.

        Returns:
            Set of relative path strings (always includes rhiza internals).
        """
        result: set[str] = set()
        for f in RhizaTemplate._expand_paths(base_dir, excluded_paths):
            result.add(str(f.relative_to(base_dir)))
        result.add(".rhiza/template.yml")
        result.add(".rhiza/history")
        return result

    @staticmethod
    def _prepare_snapshot(
        clone_dir: Path,
        include_paths: list[str],
        excludes: set[str],
        snapshot_dir: Path,
    ) -> list[Path]:
        """Copy included (non-excluded) files from a clone into a snapshot directory.

        Args:
            clone_dir: Root of the template clone.
            include_paths: Paths to include.
            excludes: Set of relative paths to exclude.
            snapshot_dir: Destination directory for the snapshot.

        Returns:
            List of relative file paths that were copied.
        """
        materialized: list[Path] = []
        for f in RhizaTemplate._expand_paths(clone_dir, include_paths):
            rel = str(f.relative_to(clone_dir))
            if rel not in excludes:
                dst = snapshot_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                materialized.append(Path(rel))
        return materialized

    @staticmethod
    def _update_sparse_checkout(
        tmp_dir: Path,
        include_paths: list[str],
        git_ctx: GitContext,
        logger=None,
    ) -> None:
        """Update sparse-checkout paths in an already-cloned repository.

        Args:
            tmp_dir: Temporary directory with cloned repository.
            include_paths: Paths to include in sparse checkout.
            git_ctx: Git context.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)

        try:
            logger.debug(f"Updating sparse checkout paths: {include_paths}")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
            logger.debug("Sparse checkout paths updated")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to update sparse checkout paths")
            _log_git_stderr_errors(e.stderr)
            raise

    @staticmethod
    def _get_head_sha(repo_dir: Path, git_ctx: GitContext) -> str:
        """Return the HEAD commit SHA of a cloned repository.

        Args:
            repo_dir: Path to the git repository.
            git_ctx: Git context.

        Returns:
            The full HEAD SHA.
        """
        result = subprocess.run(  # nosec B603  # noqa: S603
            [git_ctx.executable, "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
            env=git_ctx.env,
        )
        return result.stdout.strip()

    def _clone_template_repository(
        self,
        tmp_dir: Path,
        rhiza_branch: str,
        include_paths: list[str],
        git_ctx: GitContext,
        logger=None,
    ) -> None:
        """Clone template repository with sparse checkout.

        Args:
            tmp_dir: Temporary directory for cloning.
            rhiza_branch: Branch to clone.
            include_paths: Initial paths to include in sparse checkout.
            git_ctx: Git context.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)

        git_url = self.git_url
        try:
            logger.debug("Executing git clone with sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    git_ctx.executable,
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
                env=git_ctx.env,
            )
            logger.debug("Git clone completed successfully")
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to clone repository from {git_url}")
            _log_git_stderr_errors(e.stderr)
            logger.exception("Please check that:")
            logger.exception("  - The repository exists and is accessible")
            logger.exception(f"  - Branch '{rhiza_branch}' exists in the repository")
            logger.exception("  - You have network access to the git hosting service")
            raise

        try:
            logger.debug("Initializing sparse checkout")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "sparse-checkout", "init", "--cone"],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
            logger.debug("Sparse checkout initialized")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to initialize sparse checkout")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            logger.debug(f"Setting sparse checkout paths: {include_paths}")
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=tmp_dir,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
            logger.debug("Sparse checkout paths configured")
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to configure sparse checkout paths")
            _log_git_stderr_errors(e.stderr)
            raise

    def _clone_at_sha(
        self,
        sha: str,
        dest: Path,
        include_paths: list[str],
        git_ctx: GitContext,
        logger=None,
    ) -> None:
        """Clone the template repository and checkout a specific commit.

        Args:
            sha: Commit SHA to check out.
            dest: Target directory for the clone.
            include_paths: Paths for sparse checkout.
            git_ctx: Git context.
            logger: Optional logger; defaults to module logger.
        """
        logger = logger or logging.getLogger(__name__)
        git_url = self.git_url
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [
                    git_ctx.executable,
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
                env=git_ctx.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to clone repository for base snapshot: {git_url}")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "sparse-checkout", "init", "--cone"],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "sparse-checkout", "set", "--skip-checks", *include_paths],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception("Failed to configure sparse checkout for base snapshot")
            _log_git_stderr_errors(e.stderr)
            raise

        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [git_ctx.executable, "checkout", sha],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
                env=git_ctx.env,
            )
        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to checkout base commit {sha[:12]}")
            _log_git_stderr_errors(e.stderr)
            raise

    @classmethod
    def from_project(cls, target: Path, branch: str = "main", logger=None) -> "RhizaTemplate":
        """Validate and load a :class:`RhizaTemplate` from a project directory.

        Validates the project's ``template.yml`` via :func:`~rhiza.commands.validate.validate`,
        then loads the configuration with :meth:`from_yaml` and checks that
        the required fields are present.

        Args:
            target: Path to the target repository (must contain ``.git`` and
                ``.rhiza/template.yml``).
            branch: The Rhiza template branch to use as a fallback when
                ``template-branch`` is not set in ``template.yml``.
            logger: Optional logger; defaults to module logger.

        Returns:
            The loaded and validated :class:`RhizaTemplate`.
        """
        from rhiza.commands.validate import validate

        logger = logger or logging.getLogger(__name__)

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

    def resolve_include_paths(self, bundles_config: "RhizaBundles | None") -> list[str]:
        """Resolve template configuration to file paths.

        Supports:
        - Template-based mode (templates field)
        - Path-based mode (include field)
        - Hybrid mode (both templates and include)

        Args:
            bundles_config: The loaded bundles configuration, or None if not available.

        Returns:
            List of file paths to materialize.

        Raises:
            ValueError: If configuration is invalid or bundles.yml is missing.
        """
        paths: list[str] = []
        if self.templates:
            if not bundles_config:
                msg = "Template uses templates but template-bundles.yml not found in template repository"
                raise ValueError(msg)
            paths.extend(bundles_config.resolve_to_paths(self.templates))
        if self.include:
            paths.extend(self.include)
        if not paths:
            msg = "Template configuration must specify either 'templates' or 'include'"
            raise ValueError(msg)
        seen: set[str] = set()
        deduplicated: list[str] = []
        for path in paths:
            if path not in seen:
                deduplicated.append(path)
                seen.add(path)
        return deduplicated

    def clone(self, git_ctx: GitContext, branch: str = "main", logger=None) -> tuple[Path, str]:
        """Clone the upstream template repository and resolve include paths.

        Clones the template repository using sparse checkout.  When
        ``templates`` are configured the corresponding bundle names are resolved
        to file paths and ``self.include`` is updated with the result.

        Args:
            git_ctx: Git context.
            branch: Default branch to use when ``template_branch`` is not set
                on the template.
            logger: Optional logger; defaults to module logger.

        Returns:
            Tuple of ``(upstream_dir, upstream_sha)`` where *upstream_dir* is a
            temporary directory containing the cloned repository tree.  The
            caller is responsible for removing *upstream_dir* when done.

        Raises:
            ValueError: If ``template_repository`` is not set, the host is
                unsupported, or no include paths / templates are configured.
            subprocess.CalledProcessError: If a git operation fails.
        """
        logger = logger or logging.getLogger(__name__)

        if not self.template_repository:
            raise ValueError("template_repository is not configured in template.yml")  # noqa: TRY003
        if not self.templates and not self.include:
            raise ValueError("No templates or include paths found in template.yml")  # noqa: TRY003

        rhiza_branch = self.template_branch or branch
        include_paths = self.include

        upstream_dir = Path(tempfile.mkdtemp())
        initial_paths = [".rhiza"] if self.templates else include_paths
        self._clone_template_repository(upstream_dir, rhiza_branch, initial_paths, git_ctx)

        if self.templates:
            bundles_config = RhizaBundles.from_clone(upstream_dir)
            resolved_paths = self.resolve_include_paths(bundles_config)
            self._update_sparse_checkout(upstream_dir, resolved_paths, git_ctx)
            self.include = resolved_paths

        upstream_sha = self._get_head_sha(upstream_dir, git_ctx)
        logger.info(f"Upstream HEAD: {upstream_sha[:12]}")

        return upstream_dir, upstream_sha

    def snapshot(
        self,
        upstream_dir: Path,
        snapshot_dir: Path,
    ) -> tuple[list[Path], set[str]]:
        """Build a clean snapshot of the included template files.

        Computes the set of excluded paths from ``self.exclude`` and copies
        all included (non-excluded) files from *upstream_dir* into
        *snapshot_dir*, producing a flat tree suitable for
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
        excludes = self._excluded_set(upstream_dir, self.exclude)
        materialized = self._prepare_snapshot(upstream_dir, self.include, excludes, snapshot_dir)
        return materialized, excludes
