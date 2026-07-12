"""Command for syncing Rhiza template files using diff/merge.

This module implements the ``sync`` command. It uses a cruft-style diff/patch
approach so that local customisations are preserved and upstream changes
are applied safely.

The approach:
1. Read the last-synced commit SHA from ``.rhiza/template.lock``.
2. Clone the template repository and obtain two tree snapshots:
   - **base**: the template at the previously synced commit (the common ancestor).
   - **upstream**: the template at the current HEAD of the configured branch.
3. Compute a diff between base and upstream using ``git diff --no-index``.
4. Apply the diff to the project using ``git apply -3`` for a 3-way merge.
5. Update the lock file.

When no lock file exists (first sync), the command falls back to a simple
copy and records the commit SHA.
"""

import dataclasses
import datetime
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from loguru import logger

from rhiza.models import GitContext, RhizaTemplate, TemplateLock
from rhiza.models._git.snapshot import _excluded_set, _prepare_snapshot

if TYPE_CHECKING:
    from rhiza.models.bundle import RhizaBundles

__all__ = ["sync"]

_DEFAULT_BUNDLES_PATH = ".rhiza/template-bundles.yml"


def _log_list(header: str, items: list[str]) -> None:
    """Log a labelled list of items, if non-empty.

    Args:
        header: Label printed before the list.
        items: Items to log; nothing is printed when the list is empty.
    """
    if items:
        logger.info(f"{header}:")
        for item in items:
            logger.info(f"  - {item}")


def _load_template_from_project(target: Path, template_file: Path | None = None) -> RhizaTemplate:
    """Load a :class:`RhizaTemplate` from a project directory.

    Loads the configuration with :meth:`~rhiza.models.RhizaTemplate.from_yaml`
    and checks that the required fields are present.

    Args:
        target: Path to the target repository (must contain ``.git`` and
            ``.rhiza/template.yml``).
        template_file: Optional explicit path to the template file.  When
            ``None`` the default ``<target>/.rhiza/template.yml`` is used.

    Returns:
        The loaded :class:`RhizaTemplate`.

    Raises:
        RuntimeError: If the template file is missing, malformed, or missing
            required fields.
    """
    if template_file is None:
        template_file = target / ".rhiza" / "template.yml"

    try:
        template = RhizaTemplate.from_yaml(template_file)
    except (FileNotFoundError, yaml.YAMLError, ValueError, TypeError) as exc:
        logger.error(f"Rhiza template is invalid in: {target}")
        logger.error(f"{exc}")
        logger.error("Fix the errors above and run 'rhiza sync' again")
        raise RuntimeError("Rhiza template validation failed") from exc  # noqa: TRY003

    # When template_bundles_path is at its default and the template file is not at
    # the default location, derive the bundles path from the template file's directory
    # relative to the project root so that --path-to-template works consistently.
    if template.template_bundles_path == _DEFAULT_BUNDLES_PATH:
        try:
            relative_dir = template_file.resolve().parent.relative_to(target)
            derived = (relative_dir / "template-bundles.yml").as_posix()
            if derived != _DEFAULT_BUNDLES_PATH:
                template = dataclasses.replace(template, template_bundles_path=derived)
        except ValueError:
            pass  # template_file is outside target root; keep default

    if not template.template_repository:
        logger.error("template-repository is not configured in template.yml")
        raise RuntimeError("template-repository is required")  # noqa: TRY003

    if not template.templates and not template.include and not template.profiles:
        logger.error("No templates, profiles, or include paths found in template.yml")
        logger.error("Add 'templates', 'profiles', or 'include' to template.yml")
        raise RuntimeError("No templates, profile, or include paths found in template.yml")  # noqa: TRY003

    _log_list("Profiles", template.profiles)
    _log_list("Templates", template.templates)
    _log_list("Include paths", template.include)
    _log_list("Exclude paths", template.exclude)

    return template


def _validate_clone_config(template: RhizaTemplate) -> None:
    """Validate that *template* carries enough configuration to clone.

    Args:
        template: The template configuration.

    Raises:
        ValueError: If ``template_repository`` is not set, or no templates,
            profile, or include paths are configured.
    """
    if not template.template_repository:
        raise ValueError("template_repository is not configured in template.yml")  # noqa: TRY003
    if not template.templates and not template.include and not template.profiles:
        raise ValueError("No templates, profile, or include paths found in template.yml")  # noqa: TRY003


def _raise_unknown_profile(profile_name: str, bundles_path: str, available_profiles: Mapping[str, object]) -> None:
    """Raise a ``ValueError`` describing a profile that is not defined.

    Args:
        profile_name: The profile that could not be found.
        bundles_path: Path to the bundle definitions file (used in the message).
        available_profiles: Mapping of the profiles that *are* defined.

    Raises:
        ValueError: Always — lists the available profiles when any exist.
    """
    sorted_available = sorted(available_profiles)
    if sorted_available:
        available_text = ", ".join(sorted_available)
        raise ValueError(  # noqa: TRY003
            f"Profile '{profile_name}' was not found in {bundles_path}. Available profiles: {available_text}"
        )
    raise ValueError(  # noqa: TRY003
        f"Profile '{profile_name}' was not found in {bundles_path}. No profiles are defined."
    )


def _resolve_bundle_names(template: RhizaTemplate, bundles: "RhizaBundles", bundles_path: str) -> list[str]:
    """Resolve configured profiles and templates to a deduplicated bundle-name list.

    Profiles are expanded to their constituent bundle names (preserving order and
    dropping duplicates) and then merged with any explicitly configured
    ``templates``.  When no profiles are configured, the explicit ``templates``
    list is returned unchanged.

    Args:
        template: The template configuration.
        bundles: Parsed bundle definitions from the template repository.
        bundles_path: Path to the bundle definitions file (used in error messages).

    Returns:
        The ordered, deduplicated list of bundle names to check out.

    Raises:
        ValueError: If a configured profile is not defined in *bundles*.
    """
    if not template.profiles:
        return template.templates

    available_profiles = bundles.profiles or {}
    profile_bundle_names: list[str] = []
    for profile_name in template.profiles:
        if profile_name not in available_profiles:
            _raise_unknown_profile(profile_name, bundles_path, available_profiles)
        for bundle in available_profiles[profile_name].bundles:
            if bundle not in profile_bundle_names:
                profile_bundle_names.append(bundle)
    return list(dict.fromkeys(profile_bundle_names + template.templates))


def _clone_template(
    template: RhizaTemplate,
    git_ctx: GitContext,
    branch: str = "main",
) -> tuple[Path, str, list[str], dict[str, str]]:
    """Clone the upstream template repository and resolve include paths.

    Clones the template repository using sparse checkout.  When
    ``templates`` are configured the corresponding bundle names are resolved
    to file paths via :meth:`~rhiza.models.RhizaTemplate.resolve_include_paths`.

    Args:
        template: The template configuration.
        git_ctx: Git context.
        branch: Default branch to use when ``template_branch`` is not set
            on the template.

    Returns:
        Tuple of ``(upstream_dir, upstream_sha, resolved_include, path_map)`` where
        *upstream_dir* is a temporary directory containing the cloned repository
        tree and *path_map* maps source paths to destination paths for remapped
        entries.  The caller is responsible for removing *upstream_dir* when done.

    Raises:
        ValueError: If ``template_repository`` is not set, the host is
            unsupported, or no include paths / templates are configured.
        subprocess.CalledProcessError: If a git operation fails.
    """
    from rhiza.models.bundle import RhizaBundles

    _validate_clone_config(template)

    rhiza_branch = template.template_branch or branch
    include_paths = list(template.include)
    upstream_dir = Path(tempfile.mkdtemp())

    if template.profiles or template.templates:
        # Checkout the bundle definitions file from template_repository @ template_branch
        bundles_path = template.template_bundles_path
        git_ctx.clone_repository(template.git_url, upstream_dir, rhiza_branch, [bundles_path])

        # Load bundle definitions
        bundles = RhizaBundles.from_yaml(upstream_dir / bundles_path)

        # Resolve profiles → bundle names, then merge with explicit templates list
        all_bundle_names = _resolve_bundle_names(template, bundles, bundles_path)

        resolved_paths = bundles.resolve_to_paths(all_bundle_names)
        path_map = bundles.resolve_to_path_map(all_bundle_names)
        # Merge resolved bundle paths with any explicit include: paths (hybrid mode)
        merged_paths = list(dict.fromkeys(resolved_paths + include_paths))
        git_ctx.update_sparse_checkout(upstream_dir, merged_paths)
        include_paths = merged_paths
    else:
        path_map = {}
        git_ctx.clone_repository(template.git_url, upstream_dir, rhiza_branch, include_paths)

    upstream_sha = git_ctx.get_head_sha(upstream_dir)
    logger.info(f"Upstream HEAD: {upstream_sha[:12]}")

    return upstream_dir, upstream_sha, include_paths, path_map


def sync(
    target: Path,
    branch: str,
    target_branch: str | None,
    strategy: str,
    template_file: Path | None = None,
    lock_file: Path | None = None,
) -> None:
    """Sync Rhiza templates using cruft-style diff/merge.

    Uses diff utilities to compute the diff between the base
    (last-synced) and upstream (latest) template snapshots, then applies
    the diff to the project using ``git apply -3`` for a 3-way merge.

    Args:
        target: Path to the target repository.
        branch: The Rhiza template branch to use.
        target_branch: Optional branch name to create/checkout in the target.
        strategy: Sync strategy -- ``"merge"`` for 3-way merge,
            or ``"diff"`` for dry-run showing what would change.
        template_file: Optional explicit path to the ``template.yml`` file.
            When ``None`` the default ``<target>/.rhiza/template.yml`` is used.
        lock_file: Optional explicit path for the output lock file.  When
            ``None`` the default ``<target>/.rhiza/template.lock`` is used.
    """
    target = target.resolve()
    logger.info(f"Target repository: {target}")
    logger.info(f"Rhiza branch: {branch}")
    logger.info(f"Sync strategy: {strategy}")

    git_ctx = GitContext.default()

    git_ctx.assert_status_clean(target)
    git_ctx.handle_target_branch(target, target_branch)

    template = _load_template_from_project(target, template_file=template_file)

    # Capture original include before resolving bundles (templates: mode)
    original_include = list(template.include)

    logger.info(f"Cloning {template.template_repository}@{template.template_branch} (upstream)")
    upstream_dir, upstream_sha, resolved_include, path_map = _clone_template(template, git_ctx, branch=branch)

    # Synchronizes target with upstream template snapshot transactionally; cleans up resources
    try:
        lock_path = lock_file if lock_file is not None else target / ".rhiza" / "template.lock"
        base_sha = TemplateLock.from_yaml(lock_path).config["sha"] if lock_path.exists() else None

        upstream_snapshot = Path(tempfile.mkdtemp())
        try:
            excludes = _excluded_set(upstream_dir, template.exclude)
            template_files = _prepare_snapshot(
                upstream_dir, resolved_include, excludes, upstream_snapshot, path_map=path_map
            )
            logger.info(f"Upstream: {len(template_files)} file(s) to consider")
            lock = TemplateLock(
                sha=upstream_sha,
                repo=template.template_repository,
                host=template.template_host,
                ref=template.template_branch,
                include=original_include,
                exclude=template.exclude,
                templates=template.templates,
                profiles=template.profiles,
                files=[str(p) for p in template_files],
                synced_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                strategy=strategy,
            )

            # Build a resolved template view for merge operations (bundles → concrete paths)
            resolved_template = dataclasses.replace(template, include=resolved_include, templates=[])

            if strategy == "diff":
                git_ctx.sync_diff(
                    target=target,
                    upstream_snapshot=upstream_snapshot,
                )
            else:
                clean = git_ctx.sync_merge(
                    target=target,
                    upstream_snapshot=upstream_snapshot,
                    upstream_sha=upstream_sha,
                    base_sha=base_sha,
                    template_files=template_files,
                    template=resolved_template,
                    excludes=excludes,
                    lock=lock,
                    lock_file=lock_file,
                    path_map=path_map,
                )
                if not clean:
                    logger.error("Sync completed with conflicts — see the file list above for details")
                    logger.error(
                        "Resolve all conflicts locally (remove *.rej files and conflict markers),\n"
                        "  then commit the result."
                    )
                    msg = "Sync completed with merge conflicts"
                    raise RuntimeError(msg)
        finally:
            if upstream_snapshot.exists():
                shutil.rmtree(upstream_snapshot)
    finally:
        if upstream_dir.exists():
            shutil.rmtree(upstream_dir)
