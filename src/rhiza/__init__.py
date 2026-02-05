"""Rhiza — Manage reusable configuration templates for Python projects.

Rhiza is a command-line interface (CLI) that helps you maintain consistent
configuration across multiple Python projects using templates stored in a
central repository. It can initialize projects with standard configuration
and materialize (inject) template files into a target repository.

## Key features

- Template initialization for new or existing projects.
- Template materialization with selective include/exclude support.
- Multi-host support (GitHub and GitLab).
- Non-destructive updates by default, with an explicit `--force` flag.
- Validation via pre-commit hooks.

## Quick start

Initialize a project with Rhiza templates:

```bash
cd your-project
rhiza init
```

Customize `.rhiza/template.yml`, then materialize templates into your project:

```bash
rhiza materialize
```

## Main modules

- `rhiza.commands` — Core command implementations (init, materialize).
- `rhiza.models` — Data models and schemas for template configuration.

## Documentation

For an overview and usage guides, see the repository files:

- [README.md](https://github.com/jebel-quant/rhiza-cli/blob/main/README.md) —
Project overview and installation instructions.
- [USAGE.md](https://github.com/jebel-quant/rhiza-cli/blob/main/USAGE.md) —
Practical examples, workflows, and best practices.
- [CLI.md](https://github.com/jebel-quant/rhiza-cli/blob/main/CLI.md) —
Command reference with examples.

Latest version and updates: https://github.com/jebel-quant/rhiza-cli
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rhiza")
except PackageNotFoundError:
    # Package is not installed, use a fallback version
    __version__ = "0.0.0+dev"

__all__ = ["commands", "models"]
