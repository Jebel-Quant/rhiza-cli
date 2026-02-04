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

    Supports both bundle-based mode (new) and include-based mode (legacy).

    Args:
        template: The template configuration.
        bundles_config: The loaded bundles configuration, or None if not available.

    Returns:
        List of file paths to materialize.

    Raises:
        ValueError: If configuration is invalid or bundles.yml is missing.
    """
    if template.bundles:
        # Bundle-based mode
        if not bundles_config:
            msg = "Template uses bundles but bundles.yml not found in template repository"
            raise ValueError(msg)
        return bundles_config.resolve_to_paths(template.bundles)
    elif template.include:
        # Legacy path-based mode
        return template.include
    else:
        msg = "Template configuration must specify either 'bundles' or 'include'"
        raise ValueError(msg)
