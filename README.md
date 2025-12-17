# rhiza-cli

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Command-line interface for managing reusable configuration templates for modern Python projects.

## Overview

Rhiza is a CLI tool that helps you maintain consistent configuration across multiple Python projects by using templates stored in a central repository. It allows you to:

- Initialize projects with standard configuration templates
- Materialize (inject) templates into target repositories
- Validate template configurations
- Keep project configurations synchronized with template repositories

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [init](#rhiza-init)
  - [materialize](#rhiza-materialize)
  - [validate](#rhiza-validate)
- [Configuration](#configuration)
- [Examples](#examples)
- [Development](#development)
- [Additional Documentation](#additional-documentation)

## Additional Documentation

For more detailed information, see:

- **[CLI Quick Reference](CLI.md)** - Command syntax and quick examples
- **[Usage Guide](USAGE.md)** - Practical tutorials and workflows
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines

## Installation

### Using pip

```bash
pip install rhiza
```

### From source

```bash
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli
pip install -e .
```

### Using uv (recommended for development)

```bash
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli
make install
```

### Verify installation

```bash
rhiza --help
```

## Quick Start

1. **Initialize a project with Rhiza templates:**

   ```bash
   cd your-project
   rhiza init
   ```

   This creates a `.github/template.yml` file with default configuration.

2. **Customize the template configuration:**

   Edit `.github/template.yml` to specify which files/directories to include from your template repository.

3. **Materialize templates into your project:**

   ```bash
   rhiza materialize
   ```

   This fetches and copies template files into your project.

4. **Validate your configuration:**

   ```bash
   rhiza validate
   ```

   This checks that your `.github/template.yml` is correctly formatted and valid.

## Commands

### `rhiza init`

Initialize or validate `.github/template.yml` in a target directory.

**Usage:**

```bash
rhiza init [TARGET]
```

**Arguments:**

- `TARGET` - Target directory (defaults to current directory)

**Description:**

Creates a default `.github/template.yml` file if it doesn't exist, or validates an existing one. The default configuration includes common Python project files like `.github`, `.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `Makefile`, and `pytest.ini`.

**Examples:**

```bash
# Initialize in current directory
rhiza init

# Initialize in a specific directory
rhiza init /path/to/project

# Initialize in parent directory
rhiza init ..
```

**Output:**

When creating a new template file:
```
[INFO] Initializing Rhiza configuration in: /path/to/project
[INFO] Creating default .github/template.yml
✓ Created .github/template.yml

Next steps:
  1. Review and customize .github/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
```

When validating an existing file:
```
[INFO] Validating template configuration in: /path/to/project
✓ Found template file: /path/to/project/.github/template.yml
✓ YAML syntax is valid
✓ Field 'template-repository' is present and valid
✓ Field 'include' is present and valid
✓ template-repository format is valid: jebel-quant/rhiza
✓ include list has 6 path(s)
✓ Validation passed: template.yml is valid
```

---

### `rhiza materialize`

Inject Rhiza configuration templates into a target repository.

**Usage:**

```bash
rhiza materialize [OPTIONS] [TARGET]
```

**Arguments:**

- `TARGET` - Target git repository directory (defaults to current directory)

**Options:**

- `--branch, -b TEXT` - Rhiza branch to use [default: main]
- `--force, -y` - Overwrite existing files without prompting
- `--help` - Show help message and exit

**Description:**

Materializes template files from the configured template repository into your target project. This command:

1. Reads the `.github/template.yml` configuration
2. Performs a sparse clone of the template repository
3. Copies specified files/directories to your project
4. Respects exclusion patterns defined in the configuration

**Examples:**

```bash
# Materialize templates in current directory
rhiza materialize

# Materialize templates from a specific branch
rhiza materialize --branch develop

# Materialize and overwrite existing files
rhiza materialize --force

# Materialize in a specific directory with custom branch
rhiza materialize /path/to/project --branch v2.0 --force

# Short form with all options
rhiza materialize -b main -y
```

**Output:**

```
[INFO] Target repository: /path/to/project
[INFO] Rhiza branch: main
[INFO] Initializing Rhiza configuration in: /path/to/project
[INFO] Include paths:
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - Makefile
  - pytest.ini
[INFO] Cloning jebel-quant/rhiza@main into temporary directory
[ADD] .github/workflows/ci.yml
[ADD] .editorconfig
[ADD] .gitignore
[ADD] Makefile
✓ Rhiza templates materialized successfully

Next steps:
  1. Review changes:
       git status
       git diff

  2. Commit:
       git add .
       git commit -m "chore: import rhiza templates"

This is a one-shot snapshot.
Re-run this script to update templates explicitly.
```

**Notes:**

- Files that already exist will not be overwritten unless `--force` is used
- The command performs a sparse clone for efficiency
- Template files are copied with their original permissions
- Excluded paths (if defined) are filtered out

---

### `rhiza validate`

Validate Rhiza template configuration.

**Usage:**

```bash
rhiza validate [TARGET]
```

**Arguments:**

- `TARGET` - Target git repository directory (defaults to current directory)

**Description:**

Validates the `.github/template.yml` file to ensure it is syntactically correct and semantically valid. This performs authoritative validation including:

- Checking if the file exists
- Validating YAML syntax
- Verifying required fields are present
- Checking field types and formats
- Validating repository name format
- Ensuring include paths are not empty

**Examples:**

```bash
# Validate configuration in current directory
rhiza validate

# Validate configuration in a specific directory
rhiza validate /path/to/project

# Validate parent directory
rhiza validate ..
```

**Exit codes:**

- `0` - Validation passed
- `1` - Validation failed

**Output (success):**

```
[INFO] Validating template configuration in: /path/to/project
✓ Found template file: /path/to/project/.github/template.yml
✓ YAML syntax is valid
✓ Field 'template-repository' is present and valid
✓ Field 'include' is present and valid
✓ template-repository format is valid: jebel-quant/rhiza
✓ include list has 6 path(s)
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - Makefile
  - pytest.ini
✓ Validation passed: template.yml is valid
```

**Output (failure):**

```
[ERROR] Target directory is not a git repository: /path/to/project
```

or

```
[ERROR] Template file not found: /path/to/project/.github/template.yml
[INFO] Run 'rhiza materialize' or 'rhiza init' to create a default template.yml
```

---

## Configuration

Rhiza uses a `.github/template.yml` file to define template sources and what to include in your project.

### Configuration File Format

The `template.yml` file uses YAML format with the following structure:

```yaml
# Required: GitHub repository containing templates (format: owner/repo)
template-repository: jebel-quant/rhiza

# Optional: Branch to use from template repository (default: main)
template-branch: main

# Required: List of paths to include from template repository
include:
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - Makefile
  - pytest.ini
  - ruff.toml

# Optional: List of paths to exclude (filters out from included paths)
exclude:
  - .github/workflows/specific-workflow.yml
  - .github/CODEOWNERS
```

### Configuration Fields

#### `template-repository` (required)

- **Type:** String
- **Format:** `owner/repository`
- **Description:** GitHub repository containing your configuration templates
- **Example:** `jebel-quant/rhiza`, `myorg/python-templates`

#### `template-branch` (optional)

- **Type:** String
- **Default:** `main`
- **Description:** Git branch to use when fetching templates
- **Example:** `main`, `develop`, `v2.0`

#### `include` (required)

- **Type:** List of strings
- **Description:** Paths (files or directories) to copy from the template repository
- **Notes:**
  - Paths are relative to the repository root
  - Can include both files and directories
  - Directories are recursively copied
  - Must contain at least one path

**Example:**
```yaml
include:
  - .github          # Entire directory
  - .editorconfig    # Single file
  - src/config       # Subdirectory
```

#### `exclude` (optional)

- **Type:** List of strings
- **Description:** Paths to exclude from the included set
- **Notes:**
  - Useful for excluding specific files from broader directory includes
  - Paths are relative to the repository root

**Example:**
```yaml
exclude:
  - .github/workflows/deploy.yml  # Exclude specific workflow
  - .github/CODEOWNERS            # Exclude specific file
```

### Complete Configuration Example

```yaml
template-repository: jebel-quant/rhiza
template-branch: main
include:
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - CODE_OF_CONDUCT.md
  - CONTRIBUTING.md
  - Makefile
  - pytest.ini
  - ruff.toml
exclude:
  - .github/workflows/release.yml
  - .github/CODEOWNERS
```

## Examples

### Example 1: Setting up a new Python project

```bash
# Create a new project directory
mkdir my-python-project
cd my-python-project

# Initialize git
git init

# Initialize Rhiza
rhiza init

# Review the generated template.yml
cat .github/template.yml

# Materialize templates
rhiza materialize

# Review the imported files
git status

# Commit the changes
git add .
git commit -m "chore: initialize project with rhiza templates"
```

### Example 2: Updating existing project templates

```bash
# Navigate to your project
cd existing-project

# Validate current configuration
rhiza validate

# Update templates (overwrite existing)
rhiza materialize --force

# Review changes
git diff

# Commit if satisfied
git add .
git commit -m "chore: update rhiza templates"
```

### Example 3: Using a custom template repository

Edit `.github/template.yml`:

```yaml
template-repository: myorg/my-templates
template-branch: production
include:
  - .github/workflows
  - pyproject.toml
  - Makefile
  - docker-compose.yml
exclude:
  - .github/workflows/experimental.yml
```

Then materialize:

```bash
rhiza materialize --force
```

### Example 4: Validating before CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/validate-rhiza.yml
name: Validate Rhiza Configuration

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install rhiza
        run: pip install rhiza
      - name: Validate configuration
        run: rhiza validate
```

## Development

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`
- Git

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli

# Install dependencies
make install

# Run tests
make test

# Run linters and formatters
make fmt

# Generate documentation
make docs
```

### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific test file
pytest tests/test_cli.py

# Run with verbose output
pytest -v
```

### Code Quality

The project uses:

- **Ruff** for linting and formatting
- **pytest** for testing
- **pre-commit** hooks for automated checks

```bash
# Run all quality checks
make fmt

# Run dependency checks
make deptry
```

### Building Documentation

```bash
# Generate API documentation
make docs

# Build complete documentation book
make book
```

## Makefile Targets

The project includes a comprehensive Makefile for common development tasks:

```
Bootstrap
  install-uv       ensure uv/uvx is installed
  install-extras   run custom build script (if exists)
  install          install
  clean            clean

Development and Testing
  test             run all tests
  marimo           fire up Marimo server
  marimushka       export Marimo notebooks to HTML
  deptry           run deptry if pyproject.toml exists

Documentation
  docs             create documentation with pdoc
  book             compile the companion book
  fmt              check the pre-commit hooks and the linting
  all              Run everything

Releasing and Versioning
  bump             bump version
  release          create tag and push to remote with prompts
  post-release     perform post-release tasks

Meta
  sync             sync with template repository as defined in .github/template.yml
  help             Display this help message
  customisations   list available customisation scripts
  update-readme    update README.md with current Makefile help output
```

Run `make help` to see this list in your terminal.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Reporting Issues

If you find a bug or have a feature request, please open an issue on [GitHub](https://github.com/jebel-quant/rhiza-cli/issues).

### Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- **Repository:** https://github.com/jebel-quant/rhiza-cli
- **Issues:** https://github.com/jebel-quant/rhiza-cli/issues
- **Documentation:** Generated with `make docs`

## Architecture

Rhiza follows a modular architecture:

```
src/rhiza/
├── __init__.py         # Package initialization
├── __main__.py         # Entry point for python -m rhiza
├── cli.py              # Typer app and CLI command definitions
├── models.py           # Data models (RhizaTemplate)
└── commands/           # Command implementations
    ├── __init__.py
    ├── init.py         # Initialize template.yml
    ├── materialize.py  # Materialize templates
    └── validate.py     # Validate configuration
```

### Design Principles

1. **Thin CLI Layer:** Commands in `cli.py` are thin wrappers that delegate to implementations in `commands/`
2. **Separation of Concerns:** Each command has its own module with focused functionality
3. **Type Safety:** Uses `pathlib.Path` for file operations and Typer for type-checked CLI arguments
4. **Clear Logging:** Uses `loguru` for structured, colored logging output
5. **Validation First:** Always validates configuration before performing operations

## Troubleshooting

### Command not found: rhiza

Ensure the package is installed and your Python scripts directory is in your PATH:

```bash
pip install --user rhiza
# Add ~/.local/bin to PATH if needed
export PATH="$HOME/.local/bin:$PATH"
```

### Template validation fails

Check that:
1. Your `.github/template.yml` file exists
2. The YAML syntax is valid
3. Required fields (`template-repository` and `include`) are present
4. The repository format is `owner/repo`

Run `rhiza validate` for detailed error messages.

### Git clone fails during materialize

Ensure:
1. The template repository exists and is accessible
2. The specified branch exists
3. You have network connectivity to GitHub
4. The repository is public (or you have appropriate credentials configured)

### Files not being copied

Check:
1. The paths in `include` are correct relative to the template repository root
2. The paths exist in the specified branch
3. Any `exclude` patterns are not filtering out wanted files
4. You're using `--force` if files already exist and need to be overwritten

## FAQ

**Q: Can I use Rhiza with private template repositories?**

A: Yes, as long as you have Git credentials configured that allow access to the repository.

**Q: Does Rhiza support template repositories hosted outside GitHub?**

A: Currently, Rhiza is designed for GitHub repositories. Support for other Git hosting services could be added in the future.

**Q: Can I materialize templates from multiple repositories?**

A: Not directly. However, you can run `rhiza materialize` multiple times with different configurations, or combine templates manually.

**Q: What's the difference between `rhiza init` and `rhiza materialize`?**

A: `init` creates or validates the `.github/template.yml` configuration file. `materialize` reads that configuration and actually copies the template files into your project.

**Q: How do I update my project's templates?**

A: Simply run `rhiza materialize --force` to fetch and overwrite with the latest versions from your template repository.

**Q: Can I customize which files are included?**

A: Yes, edit the `include` and `exclude` lists in `.github/template.yml` to control exactly which files are copied.

## Acknowledgments

Rhiza is developed and maintained by the Jebel Quant team as part of their effort to standardize Python project configurations across their portfolio.
