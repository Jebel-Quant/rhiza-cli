"""Rhiza - Manage reusable configuration templates for Python projects.

Rhiza is a command-line interface (CLI) tool that helps you maintain consistent
configuration across multiple Python projects by using templates stored in a
central repository. It enables you to initialize projects with standard
configuration templates, materialize (inject) templates into target repositories,
validate template configurations, and keep project configurations synchronized
with template repositories.

Key Features
------------
- **Template Initialization**: Create default configuration templates for new
  or existing Python projects with a single command.

- **Template Materialization**: Fetch and apply configuration files from a
  central template repository to your projects, with support for selective
  inclusion/exclusion of files.

- **Configuration Validation**: Validate template configurations to ensure
  they are syntactically correct and semantically valid before use.

- **Multi-Host Support**: Work with templates from both GitHub and GitLab
  repositories.

- **Non-Destructive Updates**: Preserve existing files by default, with
  explicit `--force` flag for intentional overwrites.

Quick Start
-----------
Initialize a project with Rhiza templates:

    $ cd your-project
    $ rhiza init

Customize the template configuration in `.github/template.yml`, then
materialize templates into your project:

    $ rhiza materialize

Validate your configuration:

    $ rhiza validate

Main Modules
------------
commands : module
    Core command implementations for init, materialize, and validate operations.

models : module
    Data models and schemas for template configuration.

cli : module
    Typer-based command-line interface and entry points.

Documentation
-------------
For comprehensive documentation, see:

- README.md : Project overview and installation instructions
- USAGE.md : Practical examples, workflows, and best practices
- CLI.md : Command syntax reference and quick examples

For the latest version and updates, visit:
https://github.com/jebel-quant/rhiza-cli
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rhiza")
except PackageNotFoundError:
    # Package is not installed, use a fallback version
    __version__ = "0.0.0+dev"

__all__ = ["commands", "models"]
