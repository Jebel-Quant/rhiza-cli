"""Command for extracting supported Python versions from pyproject.toml.

This module provides functionality to read a pyproject.toml file and determine
which Python versions are supported based on the requires-python field.
"""

import json
import re
import tomllib
from pathlib import Path

from loguru import logger


class RhizaError(Exception):
    """Base exception for Rhiza-related errors."""


class VersionSpecifierError(RhizaError):
    """Raised when a version string or specifier is invalid."""


class PyProjectError(RhizaError):
    """Raised when there are issues with pyproject.toml configuration."""


CANDIDATES = ["3.11", "3.12", "3.13", "3.14"]  # extend as needed


def parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    This is intentionally simple and only supports numeric components.
    If a component contains non-numeric suffixes (e.g. '3.11.0rc1'),
    the leading numeric portion will be used (e.g. '0rc1' -> 0). If a
    component has no leading digits at all, a VersionSpecifierError is raised.

    Args:
        v: Version string to parse (e.g., "3.11", "3.11.0rc1").

    Returns:
        Tuple of integers representing the version.

    Raises:
        VersionSpecifierError: If a version component has no numeric prefix.
    """
    parts: list[int] = []
    for part in v.split("."):
        match = re.match(r"\d+", part)
        if not match:
            msg = f"Invalid version component {part!r} in version {v!r}; expected a numeric prefix."
            raise VersionSpecifierError(msg)
        parts.append(int(match.group(0)))
    return tuple(parts)


def _check_operator(version_tuple: tuple[int, ...], op: str, spec_v_tuple: tuple[int, ...]) -> bool:
    """Check if a version tuple satisfies an operator constraint."""
    operators = {
        ">=": lambda v, s: v >= s,
        "<=": lambda v, s: v <= s,
        ">": lambda v, s: v > s,
        "<": lambda v, s: v < s,
        "==": lambda v, s: v == s,
        "!=": lambda v, s: v != s,
    }
    return operators[op](version_tuple, spec_v_tuple)


def satisfies(version: str, specifier: str) -> bool:
    """Check if a version satisfies a comma-separated list of specifiers.

    This is a simplified version of packaging.specifiers.SpecifierSet.
    Supported operators: >=, <=, >, <, ==, !=

    Args:
        version: Version string to check (e.g., "3.11").
        specifier: Comma-separated specifier string (e.g., ">=3.11,<3.14").

    Returns:
        True if the version satisfies all specifiers, False otherwise.

    Raises:
        VersionSpecifierError: If the specifier format is invalid.
    """
    version_tuple = parse_version(version)

    # Split by comma for multiple constraints
    for spec in specifier.split(","):
        spec = spec.strip()
        # Match operator and version part
        match = re.match(r"(>=|<=|>|<|==|!=)\s*([\d.]+)", spec)
        if not match:
            # If no operator, assume ==
            if re.match(r"[\d.]+", spec):
                if version_tuple != parse_version(spec):
                    return False
                continue
            msg = f"Invalid specifier {spec!r}; expected format like '>=3.11' or '3.11'"
            raise VersionSpecifierError(msg)

        op, spec_v = match.groups()
        spec_v_tuple = parse_version(spec_v)

        if not _check_operator(version_tuple, op, spec_v_tuple):
            return False

    return True


def supported_versions(pyproject_path: Path) -> list[str]:
    """Return all supported Python versions declared in pyproject.toml.

    Reads project.requires-python, evaluates candidate versions against the
    specifier, and returns the subset that satisfy the constraint, in ascending order.

    Args:
        pyproject_path: Path to the pyproject.toml file.

    Returns:
        list[str]: The supported versions (e.g., ["3.11", "3.12"]).

    Raises:
        PyProjectError: If requires-python is missing or no candidates match.
        FileNotFoundError: If pyproject.toml does not exist.
    """
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at: {pyproject_path}")

    # Load pyproject.toml using the tomllib standard library (Python 3.11+)
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    # Extract the requires-python field from project metadata
    # This specifies the Python version constraint (e.g., ">=3.11")
    spec_str = data.get("project", {}).get("requires-python")
    if not spec_str:
        msg = "pyproject.toml: missing 'project.requires-python'"
        raise PyProjectError(msg)

    # Filter candidate versions to find which ones satisfy the constraint
    versions: list[str] = []
    for v in CANDIDATES:
        if satisfies(v, spec_str):
            versions.append(v)

    if not versions:
        msg = f"pyproject.toml: no supported Python versions match '{spec_str}'. Evaluated candidates: {CANDIDATES}"
        raise PyProjectError(msg)

    return versions


def versions(target: Path) -> None:
    """Extract and print supported Python versions from pyproject.toml.

    Args:
        target: Path to pyproject.toml file or directory containing it.
    """
    target = target.resolve()

    # Determine the pyproject.toml path
    if target.is_file() and target.name == "pyproject.toml":
        pyproject_path = target
    elif target.is_dir():
        pyproject_path = target / "pyproject.toml"
    else:
        logger.error(f"Invalid target: {target}")
        logger.error("Target must be a directory or pyproject.toml file")
        raise ValueError(f"Invalid target: {target}")

    logger.info(f"Reading Python version requirements from: {pyproject_path}")

    try:
        versions_list = supported_versions(pyproject_path)
        logger.success(f"Supported Python versions: {versions_list}")
        print(json.dumps(versions_list))
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("Ensure pyproject.toml exists in the target location")
        raise
    except PyProjectError as e:
        logger.error(str(e))
        raise
    except VersionSpecifierError as e:
        logger.error(f"Invalid version specifier: {e}")
        raise
