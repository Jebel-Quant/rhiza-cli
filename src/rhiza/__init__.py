"""Utility tools and command-line helpers for the Rhiza project.

This package groups small, user-facing utilities that can be invoked from
the command line or other automation scripts.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rhiza")
except PackageNotFoundError:
    # Package is not installed, use a fallback version
    __version__ = "0.0.0+dev"

__all__ = ["commands", "models"]
