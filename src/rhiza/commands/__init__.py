"""Command implementations for the Rhiza CLI.

This package contains the core implementation functions that back the Typer
commands exposed by `rhiza.cli`. These commands help you manage reusable
configuration templates for Python projects.

## Available Commands

### init

Initialize or validate `.rhiza/template.yml` in a target directory.

Creates a default configuration file if it doesn't exist, or validates
an existing one. The default configuration includes common Python project
files like `.github`, `.editorconfig`, `.gitignore`,
`.pre-commit-config.yaml`, `Makefile`, and `pytest.ini`.

### materialize (deprecated)

This command is deprecated. Use ``rhiza sync`` instead.

Retained as a backward-compatibility shim; it delegates to :func:`sync`
with the ``"merge"`` strategy.

### sync

Sync templates using diff/merge instead of overwriting.

Uses cruft's diff utilities (``git diff --no-index``) and 3-way patch
application (``git apply -3``) so that local customisations are preserved
while upstream changes are applied safely.  Tracks the last-synced
template commit in ``.rhiza/template.lock``.

### validate

Validate Rhiza template configuration.

Validates the `.rhiza/template.yml` file to ensure it is syntactically
correct and semantically valid. Performs comprehensive validation including
YAML syntax checking, required field verification, field type validation,
and repository format verification.

## Usage Example

These functions are typically invoked through the CLI:

    ```bash
    $ rhiza init                    # Initialize configuration

    $ rhiza sync                    # Sync templates (primary command)

    $ rhiza validate                # Validate template configuration

    $ rhiza materialize             # Deprecated — use rhiza sync
    ```

For more detailed usage examples and workflows, see the USAGE.md guide
or try rhiza <command> --help
"""

from .init import init
from .materialize import materialize
from .sync import sync
from .tree import tree
from .validate import validate

__all__ = ["init", "materialize", "sync", "tree", "validate"]
