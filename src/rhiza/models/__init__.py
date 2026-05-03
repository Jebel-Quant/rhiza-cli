"""Data models for Rhiza configuration.

This package re-exports all public symbols from the sub-modules so that
existing code importing from ``rhiza.models`` continues to work unchanged.

Sub-modules
-----------
- :mod:`rhiza.models._base`             - :class:`YamlSerializable` protocol, :func:`load_model`
- :mod:`rhiza.models._git_utils`        - git helpers and ``_normalize_to_list``
- :mod:`rhiza.models._profile_resolver` - :func:`resolve_bundles`
- :mod:`rhiza.models.bundle`            - :class:`BundleDefinition`, :class:`ProfileDefinition`, :class:`RhizaBundles`
- :mod:`rhiza.models.template`          - :class:`GitHost`, :class:`RhizaTemplate`
- :mod:`rhiza.models.lock`              - :class:`TemplateLock`
"""

from rhiza.models._base import YamlSerializable, load_model
from rhiza.models._git_utils import GitContext, get_git_executable
from rhiza.models._profile_resolver import resolve_bundles
from rhiza.models.bundle import BundleDefinition, ProfileDefinition, RhizaBundles
from rhiza.models.lock import TemplateLock
from rhiza.models.template import GitHost, RhizaTemplate

__all__ = [
    "BundleDefinition",
    "GitContext",
    "GitHost",
    "ProfileDefinition",
    "RhizaBundles",
    "RhizaTemplate",
    "TemplateLock",
    "YamlSerializable",
    "get_git_executable",
    "load_model",
    "resolve_bundles",
]
