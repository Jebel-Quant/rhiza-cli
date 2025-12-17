# GitHub Copilot Instructions for rhiza-cli

## Project Overview

Rhiza is a command-line interface (CLI) tool for managing reusable configuration templates for modern Python projects. It provides commands for initializing, validating, and materializing configuration templates across projects.

**Repository:** <https://github.com/jebel-quant/rhiza-cli>

## Technology Stack

- **Language:** Python 3.11+ (supports 3.11, 3.12, 3.13, 3.14)
- **Package Manager:** uv (fast Python package installer and resolver)
- **CLI Framework:** Typer
- **Testing:** pytest with coverage reporting
- **Linting/Formatting:** Ruff
- **Build System:** Hatchling
- **Pre-commit Hooks:** YAML/TOML validation, Ruff, markdownlint, actionlint

## Project Structure

```text
rhiza-cli/
├── src/rhiza/          # Main source code
│   ├── cli.py          # CLI entry points (Typer app)
│   └── commands/       # Command implementations
├── tests/              # Test suite
├── book/               # Documentation and Marimo notebooks
├── .github/            # GitHub workflows and scripts
├── pyproject.toml      # Project configuration
├── ruff.toml           # Linting configuration
└── Makefile            # Development tasks
```

## Coding Standards

### Python Style

- **Line length:** Maximum 120 characters
- **Quotes:** Use double quotes for strings
- **Indentation:** 4 spaces (no tabs)
- **Docstrings:** Google style convention (required for all public modules, classes, and functions)
- **Type hints:** Not strictly enforced but encouraged
- **Import sorting:** Automatic via isort (part of Ruff)

### Linting Rules

The project uses Ruff with the following rule sets:

- **D** (pydocstyle): Docstring style enforcement
- **E** (pycodestyle): PEP 8 style guide errors
- **F** (pyflakes): Logical error detection
- **I** (isort): Import sorting
- **N** (pep8-naming): PEP 8 naming conventions
- **W** (pycodestyle): PEP 8 warnings
- **UP** (pyupgrade): Modern Python syntax

**Exception:** Tests allow assert statements (S101 ignored in tests/)

### Docstring Requirements

- All public modules, classes, functions, and methods must have docstrings
- Use Google docstring convention
- Include magic methods like `__init__` (D105, D107 enforced)
- Use multi-line format with summary line, then blank line, then details

Example:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """Short summary of what the function does.

    Longer description if needed. Explain complex behavior,
    side effects, or important context.

    Parameters
    ----------
    arg1:
        Description of arg1
    arg2:
        Description of arg2

    Returns
    -------
    bool
        Description of return value
    """
    return True
```

## Development Workflow

### Setup

```bash
make install    # Install dependencies with uv
```

### Common Commands

```bash
make fmt        # Run linters and formatters (pre-commit)
make test       # Run tests with coverage
make docs       # Generate documentation with pdoc
make clean      # Clean build artifacts
make help       # Show all available commands
```

### Testing

- Use pytest for all tests
- Place tests in `tests/` directory
- Test files should match pattern `test_*.py`
- Aim for good coverage of new code
- Run tests with `make test` before submitting changes

### Pre-commit Hooks

The project uses pre-commit hooks that run automatically on commit:

- YAML/TOML validation
- Ruff linting and formatting
- Markdown linting (MD013 disabled for long lines)
- GitHub workflow validation
- Renovate config validation
- README.md auto-update with Makefile help

## Architecture Notes

### CLI Structure

The CLI uses Typer for command definitions. Commands are thin wrappers in `cli.py` that delegate to implementations in `rhiza.commands.*`:

- `init`: Initialize or validate `.github/template.yml`
- `materialize` (alias `inject`): Apply templates to a target repository
- `validate`: Validate template configuration

### Command Implementation Pattern

1. Command defined in `src/rhiza/cli.py` using Typer decorators
2. Implementation logic in `src/rhiza/commands/*.py`
3. Commands use `loguru` for logging
4. Use `Path` from `pathlib` for file operations

## Best Practices

1. **Minimal changes:** Make surgical, focused changes
2. **Type hints:** Use when they improve clarity
3. **Error handling:** Use appropriate exceptions, log errors clearly
4. **Documentation:** Update docstrings when changing function signatures
5. **Tests:** Add tests for new functionality
6. **Imports:** Keep imports organized (isort handles this automatically)
7. **File headers:** Include repository attribution comment at top of new files:

   ```python
   # This file is part of the jebel-quant/rhiza repository
   # (https://github.com/jebel-quant/rhiza).
   #
   ```

## Dependencies

### Core Dependencies

- `typer>=0.20.0` - CLI framework
- `loguru>=0.7.3` - Logging
- `PyYAML==6.0.3` - YAML parsing

### Development Dependencies

- `pytest`, `pytest-cov`, `pytest-html` - Testing
- `pre-commit` - Git hooks
- `marimo` - Notebook support
- `pdoc` - Documentation generation

## Common Patterns

### Path Handling

```python
from pathlib import Path

target = Path(".")  # Use Path objects, not strings
if target.exists():
    # Do something
```

### Logging

```python
from loguru import logger

logger.info("Starting operation")
logger.error("Something went wrong")
```

### CLI Arguments

```python
import typer

@app.command()
def my_command(
    target: Path = typer.Argument(
        default=Path("."),
        exists=True,
        help="Description"
    ),
):
    """Command docstring."""
```

## When Making Changes

1. Run `make fmt` to ensure code follows style guidelines
2. Run `make test` to verify tests pass
3. Update docstrings if changing public APIs
4. Add tests for new functionality
5. Keep changes focused and minimal
6. Follow existing code patterns and conventions
