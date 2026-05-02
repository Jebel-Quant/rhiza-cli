"""Profile resolution logic for Rhiza templates.

This module provides :func:`resolve_bundles`, which expands any ``profiles``
listed in a :class:`~rhiza.models.template.RhizaTemplate` into their
constituent bundle names (as defined in the upstream
``template-bundles.yml``) and merges them with any explicit ``templates``
entries.

The resolution rules are:

1. For each name in ``template.profiles``, look up the corresponding
   :class:`~rhiza.models.bundle.ProfileDefinition` in
   ``available_bundles.profiles`` and collect its ``bundles`` list.
2. Append any explicit names from ``template.templates``.
3. Deduplicate preserving order (profile-derived bundles first, then
   explicit).
4. Raise :exc:`ValueError` for unknown profile names or unknown bundle
   names.

Old ``template.yml`` files that have neither a ``profiles`` key nor a
``templates`` key (i.e. both lists are empty) are passed through unchanged
— an empty list is returned so the caller can decide whether to error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rhiza.models.bundle import RhizaBundles
    from rhiza.models.template import RhizaTemplate

__all__ = ["resolve_bundles"]


def resolve_bundles(template: "RhizaTemplate", available_bundles: "RhizaBundles") -> list[str]:
    """Resolve a template's profiles and explicit bundle list to a deduplicated list of bundle names.

    Profiles are expanded first (in declaration order), then any explicit
    ``templates`` entries are appended.  The final list is deduplicated
    preserving first-seen order.

    Args:
        template: The loaded :class:`~rhiza.models.template.RhizaTemplate`.
        available_bundles: The upstream :class:`~rhiza.models.bundle.RhizaBundles`
            (loaded from ``template-bundles.yml``).

    Returns:
        Ordered, deduplicated list of bundle names that should be synced.

    Raises:
        ValueError: If a profile name is not found in ``available_bundles.profiles``.
        ValueError: If a bundle name (from a profile expansion or explicit
            ``templates`` list) is not found in ``available_bundles.bundles``.
    """
    resolved: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        if name not in seen:
            resolved.append(name)
            seen.add(name)

    # Expand profiles
    for profile_name in template.profiles:
        if profile_name not in available_bundles.profiles:
            known = ", ".join(sorted(available_bundles.profiles.keys())) or "(none)"
            msg = f"Unknown profile '{profile_name}'. Known profiles: {known}"
            raise ValueError(msg)
        for bundle_name in available_bundles.profiles[profile_name].bundles:
            if bundle_name not in available_bundles.bundles:
                msg = (
                    f"Profile '{profile_name}' references unknown bundle '{bundle_name}'. "
                    f"Check template-bundles.yml for available bundles."
                )
                raise ValueError(msg)
            _add(bundle_name)

    # Merge explicit templates
    for bundle_name in template.templates:
        if bundle_name not in available_bundles.bundles:
            known = ", ".join(sorted(available_bundles.bundles.keys())) or "(none)"
            msg = f"Unknown bundle '{bundle_name}'. Known bundles: {known}"
            raise ValueError(msg)
        _add(bundle_name)

    return resolved
