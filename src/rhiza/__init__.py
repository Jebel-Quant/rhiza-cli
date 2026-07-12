"""Rhiza — Manage reusable configuration templates for Python projects.

Rhiza is a command-line interface (CLI) that helps you maintain consistent
configuration across multiple Python projects using templates stored in a
central repository. It syncs (injects) template files into a target repository,
loading and validating the template configuration each time it runs.

## Key features

- Template sync with selective include/exclude support.
- Configuration loaded and validated on every sync.
- Validating dry-run preview via ``rhiza sync --strategy diff``.
- Multi-host support (GitHub and GitLab).

## Quick start

Create a `.rhiza/template.yml` file in your project by hand — it must specify a
`template-repository` and one of `include`, `templates`, or `profiles`. Then
sync templates into your project:

```bash
rhiza sync
```

Preview what would change first with a validating dry-run:

```bash
rhiza sync --strategy diff
```

## Main modules

- `rhiza.commands` — Core command implementations (sync, summarise).
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
