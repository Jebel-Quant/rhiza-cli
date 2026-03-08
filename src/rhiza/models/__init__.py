"""Data models for Rhiza configuration.

This package re-exports all public symbols from the sub-modules so that
existing code importing from ``rhiza.models`` continues to work unchanged.

Sub-modules
-----------
- :mod:`rhiza.models._git_utils` - git helpers and ``_normalize_to_list``
- :mod:`rhiza.models.bundle`     - :class:`BundleDefinition`, :class:`RhizaBundles`
- :mod:`rhiza.models.template`   - :class:`GitHost`, :class:`RhizaTemplate`
- :mod:`rhiza.models.lock`       - :class:`TemplateLock`
"""

from rhiza.models._git_utils import get_git_executable
from rhiza.models.bundle import BundleDefinition, RhizaBundles
from rhiza.models.lock import TemplateLock
from rhiza.models.template import GitHost, RhizaTemplate

__all__ = [
    "BundleDefinition",
    "GitHost",
    "RhizaBundles",
    "RhizaTemplate",
    "TemplateLock",
    "get_git_executable",
]
