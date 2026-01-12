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

### materialize

Inject Rhiza configuration templates into a target repository.

Materializes template files from the configured template repository into
your target project by performing a sparse clone of the template repository,
copying specified files/directories, and respecting exclusion patterns.
Files that already exist will not be overwritten unless the `--force` flag
is used.

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

    $ rhiza materialize             # Apply templates to project

    $ rhiza validate                # Validate template configuration
    ```

For more detailed usage examples and workflows, see the USAGE.md guide
or try rhiza <command> --help
"""

from .init import init  # noqa: F401
from .materialize import materialize  # noqa: F401
from .validate import validate  # noqa: F401
