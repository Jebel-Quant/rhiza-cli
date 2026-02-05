"""Bundle resolution logic for template configuration.

This module provides functions to load and resolve bundle configurations
from the template repository's bundles.yml file.
"""

from pathlib import Path

from rhiza.models import RhizaBundles, RhizaTemplate


def load_bundles_from_clone(tmp_dir: Path) -> RhizaBundles | None:
    """Load .rhiza/bundles.yml from cloned template repo.

    Args:
        tmp_dir: Path to the cloned template repository.

    Returns:
        RhizaBundles if bundles.yml exists, None otherwise.

    Raises:
        yaml.YAMLError: If bundles.yml is malformed.
        ValueError: If bundles.yml is invalid.
    """
    bundles_file = tmp_dir / ".rhiza" / "bundles.yml"
    if not bundles_file.exists():
        return None
    return RhizaBundles.from_yaml(bundles_file)


def resolve_include_paths(
    template: RhizaTemplate,
    bundles_config: RhizaBundles | None,
) -> list[str]:
    """Resolve template configuration to file paths.

    Supports:
    - Template-based mode (templates field)
    - Path-based mode (include field)
    - Hybrid mode (both templates and include)

    Args:
        template: The template configuration.
        bundles_config: The loaded bundles configuration, or None if not available.

    Returns:
        List of file paths to materialize.

    Raises:
        ValueError: If configuration is invalid or bundles.yml is missing.
    """
    paths = []

    # Resolve templates to paths if specified
    if template.templates:
        if not bundles_config:
            msg = "Template uses templates but bundles.yml not found in template repository"
            raise ValueError(msg)
        paths.extend(bundles_config.resolve_to_paths(template.templates))

    # Add include paths if specified
    if template.include:
        paths.extend(template.include)

    # At least one must be specified
    if not paths:
        msg = "Template configuration must specify either 'templates' or 'include'"
        raise ValueError(msg)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for path in paths:
        if path not in seen:
            deduplicated.append(path)
            seen.add(path)

    return deduplicated
