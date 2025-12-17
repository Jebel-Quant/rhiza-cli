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

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value (bool)
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

See `pyproject.toml` for exact versions. Key dependencies:

- `typer` - CLI framework
- `loguru` - Logging
- `PyYAML` - YAML parsing

### Development Dependencies

See `pyproject.toml` for complete list. Key dev dependencies:

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

## Security Considerations

- **No secrets in code:** Never commit API keys, passwords, or sensitive data
- **Path traversal:** Always use `Path.resolve()` to normalize paths and prevent directory traversal attacks
- **Input validation:** Validate all user inputs, especially file paths and command arguments
- **YAML parsing:** Use safe YAML loading (PyYAML uses safe loading by default)
- **File permissions:** Be mindful of file permissions when creating files

## Error Handling Patterns

### Exception Handling

```python
from loguru import logger
from pathlib import Path

def safe_operation(path: Path):
    """Safe operation with proper error handling."""
    try:
        # Normalize path to prevent traversal
        path = path.resolve()
        
        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            raise FileNotFoundError(f"Path not found: {path}")
            
        # Perform operation
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
```

### CLI Exit Codes

Use Typer's `Exit` for non-zero exit codes on errors:

```python
import typer

if not success:
    raise typer.Exit(code=1)
```

## Common Tasks

### Adding a New Command

1. Create a new file in `src/rhiza/commands/` (e.g., `newcommand.py`)
2. Implement the command logic with proper docstrings
3. Add a wrapper in `src/rhiza/cli.py` using Typer decorators
4. Add tests in `tests/` for the new command
5. Update documentation if needed

Example:

```python
# In src/rhiza/commands/newcommand.py
from pathlib import Path
from loguru import logger

def my_new_command(target: Path):
    """Execute the new command.
    
    Parameters
    ----------
    target:
        Path to the target directory.
    """
    target = target.resolve()
    logger.info(f"Running new command on: {target}")
    # Implementation here
```

```python
# In src/rhiza/cli.py
from rhiza.commands.newcommand import my_new_command

@app.command()
def newcommand(
    target: Path = typer.Argument(
        default=Path("."),
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Target directory"
    ),
):
    """Short description of the command."""
    my_new_command(target)
```

### Running the CLI in Development

```bash
# Install in editable mode
make install

# Run the CLI
uv run rhiza --help
uv run rhiza init
uv run rhiza materialize --branch main
```

## Troubleshooting

### Common Issues

**Import errors after adding dependencies:**
- Run `make install` to sync dependencies
- Ensure `pyproject.toml` is updated with new dependencies

**Linting failures:**
- Run `make fmt` to auto-fix most issues
- Check `ruff.toml` for configured rules
- Ensure docstrings follow Google convention

**Test failures:**
- Run `make test` to see detailed output
- Check test coverage report in `_tests/html-coverage/`
- Ensure new code has corresponding tests

**Pre-commit hook failures:**
- Run `make fmt` to fix formatting issues
- Check `.pre-commit-config.yaml` for hook configuration
- Install hooks with `uv run pre-commit install`

## When Making Changes

1. Run `make fmt` to ensure code follows style guidelines
2. Run `make test` to verify tests pass
3. Update docstrings if changing public APIs
4. Add tests for new functionality
5. Keep changes focused and minimal
6. Follow existing code patterns and conventions
