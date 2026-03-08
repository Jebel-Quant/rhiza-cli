"""Base abstractions for YAML-serializable Rhiza models.

This module defines the :class:`YamlSerializable` :class:`~typing.Protocol` that all
YAML-capable Rhiza model classes satisfy, plus the :func:`load_model` generic
helper that can load any such model from a file path.

Example usage::

    from rhiza.models._base import load_model
    from rhiza.models.template import RhizaTemplate

    template = load_model(RhizaTemplate, Path(".rhiza/template.yml"))
"""

from pathlib import Path
from typing import Protocol, Self, TypeVar, runtime_checkable


@runtime_checkable
class YamlSerializable(Protocol):
    """Structural protocol for Rhiza models with YAML round-trip support.

    Any class that implements ``from_yaml`` and ``to_yaml`` with these
    signatures automatically satisfies this protocol (structural typing).

    Implementors
    ------------
    - :class:`rhiza.models.template.RhizaTemplate`
    - :class:`rhiza.models.lock.TemplateLock`
    """

    @classmethod
    def from_yaml(cls, file_path: Path) -> Self:
        """Load the model from a YAML file.

        Args:
            file_path: Path to the YAML file to load.

        Returns:
            A new instance populated from the file.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            ValueError: If the file content is not recognised.
        """
        ...

    def to_yaml(self, file_path: Path) -> None:
        """Save the model to a YAML file.

        Args:
            file_path: Destination path.  Parent directories are created
                automatically if they do not exist.
        """
        ...


_T = TypeVar("_T")


def load_model(cls: type[_T], path: Path) -> _T:
    """Load a YAML-serializable model from *path*.

    This is a thin generic wrapper around ``cls.from_yaml(path)`` that
    preserves the concrete return type so callers do not need a cast.

    Args:
        cls: A class that exposes a ``from_yaml(Path)`` classmethod,
            such as :class:`~rhiza.models.template.RhizaTemplate`,
            :class:`~rhiza.models.lock.TemplateLock`, or
            :class:`~rhiza.models.bundle.RhizaBundles`.
        path: Path to the YAML file to load.

    Returns:
        An instance of *cls* populated from *path*.

    Raises:
        TypeError: If *cls* does not implement ``from_yaml``.

    Example::

        from rhiza.models._base import load_model
        from rhiza.models.lock import TemplateLock

        lock = load_model(TemplateLock, Path(".rhiza/template.lock"))
    """
    from_yaml = getattr(cls, "from_yaml", None)
    if not callable(from_yaml):
        raise TypeError(f"{cls.__name__} does not implement from_yaml")  # noqa: TRY003
    return cls.from_yaml(path)  # type: ignore[attr-defined]
