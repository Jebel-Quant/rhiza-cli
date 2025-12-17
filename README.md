# Rhiza CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Rhiza** is a command-line tool for managing reusable configuration templates across modern Python projects. It helps you maintain consistency by materializing shared configurations, workflows, and tooling setups from a template repository into your projects.

## Features

- 🚀 **Template Materialization**: Clone and inject configuration files from a template repository
- ✅ **Validation**: Validate template configurations before applying them
- 🔧 **Selective Syncing**: Choose which files and directories to include or exclude
- 🌿 **Branch Support**: Work with different template branches
- 📝 **YAML Configuration**: Simple, declarative configuration via `.github/template.yml`

## Installation

### Using pip

```bash
pip install rhiza
```

### From source

```bash
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli
make install
```

## Quick Start

### 1. Initialize Your Project

Create a `.github/template.yml` file in your project:

```bash
rhiza init
```

This creates a default configuration file that you can customize.

### 2. Configure Your Template

Edit `.github/template.yml` to specify your template source:

```yaml
template-repository: "jebel-quant/rhiza"
template-branch: "main"
include:
  - .github
  - tests
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - CODE_OF_CONDUCT.md
  - CONTRIBUTING.md
  - Makefile
  - ruff.toml
  - pytest.ini
exclude:
  - .github/workflows/docker.yml
  - .github/workflows/devcontainer.yml
```

### 3. Materialize Templates

Apply the templates to your project:

```bash
rhiza materialize
```

Or force overwrite existing files:

```bash
rhiza materialize --force
```

## Usage

### Commands

#### `rhiza init`

Initialize or validate `.github/template.yml` in your project.

```bash
rhiza init [TARGET]
```

**Arguments:**
- `TARGET`: Target directory (defaults to current directory)

**Example:**
```bash
rhiza init .
rhiza init /path/to/project
```

#### `rhiza materialize`

Inject Rhiza configuration templates into a target repository.

```bash
rhiza materialize [OPTIONS] [TARGET]
```

**Arguments:**
- `TARGET`: Target git repository (defaults to current directory)

**Options:**
- `-b, --branch TEXT`: Rhiza branch to use (default: "main")
- `-y, --force`: Overwrite existing files without prompting

**Examples:**
```bash
# Materialize templates from default branch
rhiza materialize

# Use a specific branch
rhiza materialize --branch develop

# Force overwrite existing files
rhiza materialize --force

# Materialize to a specific directory
rhiza materialize /path/to/project
```

#### `rhiza validate`

Validate the Rhiza template configuration.

```bash
rhiza validate [TARGET]
```

**Arguments:**
- `TARGET`: Target git repository (defaults to current directory)

**Example:**
```bash
rhiza validate
rhiza validate /path/to/project
```

## Configuration

### Template Configuration File

The `.github/template.yml` file defines how Rhiza should materialize templates:

```yaml
# Required: GitHub repository containing templates
template-repository: "owner/repo"

# Optional: Branch to use (defaults to "main")
template-branch: "main"

# Required: Files/directories to include
include:
  - .github
  - Makefile
  - pyproject.toml

# Optional: Files/directories to exclude
exclude:
  - .github/workflows/custom.yml
```

### Configuration Fields

- **template-repository**: GitHub repository in `owner/repo` format
- **template-branch**: Git branch to use from the template repository
- **include**: List of paths to copy from the template repository
- **exclude**: List of paths to skip (subset of included paths)

## Development

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (installed automatically via `make install`)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli

# Install dependencies
make install

# Run tests
make test

# Run linters
make fmt

# Generate documentation
make docs
```

### Running Tests

```bash
make test
```

This will run pytest with coverage reporting.

### Code Style

The project uses:
- **Ruff** for linting and formatting
- **pytest** for testing
- **Google-style docstrings**

Before submitting changes:

```bash
make fmt  # Run all pre-commit hooks
```

## Available Make Targets

Run `make help` to see all available commands:

- `make install` - Install dependencies
- `make test` - Run tests with coverage
- `make fmt` - Run linters and formatters
- `make docs` - Generate documentation
- `make clean` - Clean build artifacts
- `make book` - Compile companion book
- `make all` - Run fmt, deptry, and book

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Before submitting a pull request:

1. Run `make fmt` to ensure code style compliance
2. Run `make test` to verify all tests pass
3. Add tests for new functionality
4. Update documentation as needed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Jebel Quant Research

## Resources

- **Repository**: [https://github.com/jebel-quant/rhiza-cli](https://github.com/jebel-quant/rhiza-cli)
- **Issues**: [https://github.com/jebel-quant/rhiza-cli/issues](https://github.com/jebel-quant/rhiza-cli/issues)
- **Template Repository**: [https://github.com/jebel-quant/rhiza](https://github.com/jebel-quant/rhiza)

## Support

For questions, issues, or feature requests, please [open an issue](https://github.com/jebel-quant/rhiza-cli/issues) on GitHub.
