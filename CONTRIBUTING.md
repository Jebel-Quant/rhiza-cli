# Contributing to Rhiza CLI

Thank you for your interest in contributing to **Rhiza CLI**! We welcome contributions from everyone and appreciate your effort to make this project better.

## Code of Conduct

Please note that this project is governed by our [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- **Python 3.11 or higher** (required)
- **uv** - Modern Python package manager (install from https://docs.astral.sh/uv/)
- **Git** - For version control

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jebel-quant/rhiza-cli.git
   cd rhiza-cli
   ```

2. **Install dependencies using uv:**
   ```bash
   uv sync
   ```

3. **Set up pre-commit hooks:**
   ```bash
   pre-commit install
   ```

   This ensures code quality checks run automatically before each commit.

4. **Verify your setup:**
   ```bash
   make test
   ```

## Documentation

Before contributing, please familiarize yourself with the project documentation:

- [GETTING_STARTED.md](./GETTING_STARTED.md) - Quick start guide and basic usage
- [USAGE.md](./USAGE.md) - Detailed usage documentation and examples
- [CLI.md](./CLI.md) - Complete command-line interface reference
- [README.md](./README.md) - Project overview and features

## Development Workflow

### Running Tests

Execute the full test suite:

```bash
make test
```

Tests should pass before submitting a pull request.

### Code Formatting and Linting

Format your code and check for linting issues:

```bash
make fmt
```

This command will:
- Format code automatically using `ruff`
- Check for linting violations
- Fix issues where possible

### Code Style Guidelines

This project follows strict code style standards:

- **Language**: Python 3.11+
- **Formatter**: `ruff` (PEP 8 compliant)
- **Linter**: `ruff`
- **Type Hints**: Required for all public functions and methods
- **Docstrings**: Follow Google style guide format
- **Line Length**: Maximum 100 characters
- **Imports**: Organize using standard library, third-party, then local imports

Before submitting a pull request, ensure:

1. All tests pass: `make test`
2. Code is properly formatted: `make fmt`
3. No linting violations exist
4. Type hints are present for all public APIs
5. Docstrings are complete and follow the Google style

### Pre-Commit Hooks

This project uses pre-commit hooks configured in `.pre-commit-config.yaml`. These hooks automatically:

- Format code according to project standards
- Check for linting issues
- Verify type hints
- Prevent commits that violate style guidelines

When hooks fail:
1. They automatically fix what they can
2. You must stage the changes: `git add .`
3. Try the commit again

Pre-commit hooks run automatically, but you can also run them manually:

```bash
pre-commit run --all-files
```

## Package Management with uv

This project uses **uv** for dependency management. Common commands:

- **Install/update dependencies**: `uv sync`
- **Add a new dependency**: `uv add package-name`
- **Add development dependency**: `uv add --dev package-name`
- **Remove a dependency**: `uv remove package-name`
- **Update lock file**: `uv lock`

See the [uv documentation](https://docs.astral.sh/uv/) for comprehensive details.

## Contributing Changes

### Creating a Feature Branch

Create a descriptive feature branch from `main`:

```bash
git checkout -b feature/short-description
```

Use conventional branch naming:
- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation updates
- `test/` for test additions
- `refactor/` for code refactoring

### Making Commits

Write clear, concise commit messages:

```bash
git commit -m "Brief description of change"
```

Guidelines for commit messages:
- Use the imperative mood ("Add feature" not "Added feature")
- Keep the first line under 50 characters
- Reference issue numbers when applicable: "Fix #123"
- Be specific about what changed and why

### Running Checks Before Pushing

Before pushing your branch, ensure everything passes:

```bash
# Run all tests
make test

# Format and lint code
make fmt

# Run pre-commit hooks
pre-commit run --all-files
```

### Submitting a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a pull request** on GitHub at https://github.com/jebel-quant/rhiza-cli

3. **Write a clear PR description** that includes:
   - What problem does this solve or what feature does it add?
   - Reference any related issues using `#issue_number`
   - Explain any design decisions
   - Include before/after examples if applicable
   - Note any breaking changes

4. **Ensure CI passes**: GitHub Actions workflows must pass before review

5. **Respond to feedback**: Address review comments professionally and promptly

6. **Keep your branch updated**: Rebase on main if needed during review

## Reporting Issues

Found a bug or have a feature request?

1. **Check existing issues** first to avoid duplicates
2. **Provide a clear description** of the problem or request
3. **Include reproduction steps** for bugs (minimal code example if possible)
4. **Share your environment**: Python version, OS, rhiza-cli version
5. **Add relevant labels** if you have repository access

## Project Structure

Understanding the project layout:

```
rhiza-cli/
├── src/                    # Source code
│   └── rhiza/             # Main package
├── tests/                 # Test suite
├── docs/                  # Documentation files
├── Makefile               # Common commands
├── pyproject.toml         # Project metadata and dependencies
├── ruff.toml              # Ruff configuration
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── pytest.ini             # Pytest configuration
└── README.md              # Project README
```

## Questions or Need Help?

- Open an issue on GitHub: https://github.com/jebel-quant/rhiza-cli/issues
- Check existing documentation in GETTING_STARTED.md, USAGE.md, and CLI.md
- Review the project's GitHub discussions (if enabled)

## Licensing

By contributing to Rhiza CLI, you agree that your contributions will be licensed under the project's existing license.

---

Thank you for contributing to Rhiza CLI! Your efforts help make this project better for everyone. 🚀
