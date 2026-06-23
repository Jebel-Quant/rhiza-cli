"""Backwards-compatible re-exports for the split git engine.

The git engine now lives in the :mod:`rhiza.models._git` subpackage (see
ADR-0005, which supersedes ADR-0004). This module re-exports the public and
previously module-private names so that existing imports — and the test suite's
``patch("rhiza.models._git_utils.…")`` targets — keep resolving.

The bare ``subprocess`` and ``shutil`` imports are intentional: tests patch
``rhiza.models._git_utils.subprocess.run`` and
``rhiza.models._git_utils.shutil.which``, which require those module objects to
be attributes of this module.  Because they are the same global module objects
the engine submodules use, patching them here affects the real call sites.
"""

import shutil  # noqa: F401  # re-exported for patch("rhiza.models._git_utils.shutil.which")
import subprocess  # nosec B404  # noqa: F401  # re-exported for patch("rhiza.models._git_utils.subprocess.run")

from rhiza.models._git.context import GitContext
from rhiza.models._git.helpers import _log_git_stderr_errors, _normalize_to_list, get_git_executable
from rhiza.models._git.snapshot import _excluded_set, _expand_paths, _prepare_snapshot, _remap_path

__all__ = [
    "GitContext",
    "_excluded_set",
    "_expand_paths",
    "_log_git_stderr_errors",
    "_normalize_to_list",
    "_prepare_snapshot",
    "_remap_path",
    "get_git_executable",
]
