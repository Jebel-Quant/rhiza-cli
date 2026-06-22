"""Shared attribute declarations for the :class:`GitContext` mixins.

The git engine is split across focused mixin modules (:mod:`remote`,
:mod:`diff`, :mod:`merge`) that are composed into the concrete
:class:`~rhiza.models._git.context.GitContext` dataclass.  Each mixin needs to
reference ``self.executable`` and ``self.env``; declaring them once here gives
the type checker a single source of truth while the real fields live on the
concrete dataclass.
"""


class GitContextBase:
    """Declares the attributes every git mixin relies on.

    Attributes:
        executable: Absolute path to the git binary.
        env: Environment variables passed to every git subprocess.
    """

    executable: str
    env: dict[str, str]
