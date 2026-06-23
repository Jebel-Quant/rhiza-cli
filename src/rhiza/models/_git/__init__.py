"""The git engine for Rhiza's template sync.

This package decomposes what was historically a single ~1000-LOC
``_git_utils.py`` module into focused submodules (see ADR-0005):

- :mod:`rhiza.models._git.remote` — clone / sparse-checkout / HEAD resolution
- :mod:`rhiza.models._git.diff` — diff computation and parsing
- :mod:`rhiza.models._git.merge` — the 3-way merge strategy
- :mod:`rhiza.models._git.snapshot` — snapshot materialization helpers
- :mod:`rhiza.models._git.helpers` — module-level git/text helpers
- :mod:`rhiza.models._git.context` — the public :class:`GitContext` facade
"""

from rhiza.models._git.context import GitContext
from rhiza.models._git.helpers import get_git_executable

__all__ = ["GitContext", "get_git_executable"]
