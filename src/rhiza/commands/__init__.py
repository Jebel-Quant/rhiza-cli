"""Command implementations for the Rhiza CLI.

This package contains the core implementation functions that back the Typer
commands exposed by `rhiza.cli`. These commands help you manage reusable
configuration templates for Python projects.

## Available Commands

### init

Initialize `.rhiza/template.yml` in a target directory.

Creates a default configuration file if it doesn't exist. The default 
configuration includes common Python project files like `.github`, 
`.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `Makefile`, 
and `pytest.ini`.

### materialize

Inject Rhiza configuration templates into a target repository.

Materializes template files from the configured template repository into
your target project by performing a sparse clone of the template repository,
copying specified files/directories, and respecting exclusion patterns.
Files that already exist will not be overwritten unless the `--force` flag
is used.

## Usage Example

These functions are typically invoked through the CLI:

    ```bash
    $ rhiza init                    # Initialize configuration

    $ rhiza materialize             # Apply templates to project
    ```

For more detailed usage examples and workflows, see the USAGE.md guide
or try rhiza <command> --help
"""

from .init import init
from .materialize import materialize

__all__ = ["init", "materialize"]
