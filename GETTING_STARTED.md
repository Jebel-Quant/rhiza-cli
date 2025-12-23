# Getting Started with Rhiza

Welcome! This guide will help you get started with Rhiza, a CLI tool for managing reusable configuration templates for Python projects.

## What is Rhiza?

Rhiza helps you maintain consistent configuration across multiple Python projects by using templates stored in a central repository. Instead of manually copying configuration files between projects, Rhiza automates the process and keeps your projects synchronized.

**Works for both new and existing projects!** Whether you're starting fresh or want to add template management to an existing codebase, Rhiza has you covered.

## Prerequisites

Before you begin, make sure you have:

- **Python 3.11 or higher** installed
- **Git** installed and configured
- A **terminal** or command prompt
- **An existing git repository** (or you'll create one in this guide)

You can verify your Python version:

```bash
python --version
# or
python3 --version
```

## Installation

### Option 1: Using uvx (Recommended - No installation required!)

The easiest way to use Rhiza is with `uvx`, which runs CLI tools without installing them. First, install `uv`:

**On macOS and Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**On Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Now you can run Rhiza directly:

```bash
uvx rhiza --help
```

With `uvx`, you always get the latest version automatically - no need to update!

### Option 2: Using pip (For regular use)

If you prefer to install Rhiza globally:

```bash
pip install rhiza
```

Verify the installation:

```bash
rhiza --help
```

### Option 3: From source (For development)

Clone and install from the repository:

```bash
git clone https://github.com/jebel-quant/rhiza-cli.git
cd rhiza-cli
make install
```

## Your First Rhiza Project

Let's create a new Python project with Rhiza templates in 6 simple steps:

### Step 1: Create a Project Directory

```bash
mkdir my-python-project
cd my-python-project
```

### Step 2: Initialize Git

Rhiza requires a git repository to work:

```bash
git init
```

### Step 3: Create a pyproject.toml File

**Important:** For Python projects, you should have a `pyproject.toml` file that defines your project metadata and dependencies. This is the modern standard for Python projects (PEP 518, PEP 621).

Create a minimal `pyproject.toml`:

```bash
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "my-python-project"
version = "0.1.0"
description = "My awesome Python project"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [
  { name = "Your Name", email = "your.email@example.com" }
]

dependencies = []

[project.optional-dependencies]
dev = []
EOF
```

**Why is pyproject.toml important?**

- It's the standard way to define Python projects (replaces setup.py)
- Contains project metadata (name, version, description, authors)
- Manages dependencies and their versions
- Configures build tools and other tooling
- Required by modern package managers like `pip`, `uv`, and `poetry`

**Note:** If you're adding Rhiza to an existing project, you likely already have a `pyproject.toml` file, so you can skip this step!

### Step 4: Initialize Rhiza

Create the Rhiza configuration:

```bash
uvx rhiza init
```

**💡 What does `uvx rhiza init` do?**

When you run `uvx rhiza init`, several things happen automatically:

1. **uvx downloads and caches Rhiza** - The first time you run this, `uvx` downloads the latest version of Rhiza from PyPI and caches it. Subsequent runs are instant!

2. **Rhiza creates the configuration directory** - A `.github/rhiza/` directory is created in your project to store Rhiza configuration.

3. **A default template file is generated** - The file `.github/rhiza/template.yml` is created with sensible defaults that fetch common Python project files from the `jebel-quant/rhiza` template repository.

You should see:
```
[INFO] Initializing Rhiza configuration in: /path/to/my-python-project
[INFO] Creating default .github/rhiza/template.yml
✓ Created .github/rhiza/template.yml

Next steps:
  1. Review and customize .github/rhiza/template.yml to match your project needs
  2. Run 'uvx rhiza materialize' to inject templates into your repository
```

**Note:** If you installed Rhiza with pip, you can use `rhiza init` instead of `uvx rhiza init`.

### Step 5: Review the Configuration

Take a look at what was created:

```bash
cat .github/rhiza/template.yml
```

You'll see something like:

```yaml
template-repository: jebel-quant/rhiza
template-branch: main
include:
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - Makefile
  - pytest.ini
```

This configuration will fetch common Python project files from the template repository.

### Step 6: Materialize Templates

Apply the templates to your project:

```bash
uvx rhiza materialize
```

**💡 What does `uvx rhiza materialize` do?**

When you run this command, Rhiza performs several actions:

1. **Reads your configuration** - Rhiza reads `.github/rhiza/template.yml` to understand what templates you want

2. **Performs a sparse clone** - Instead of downloading the entire template repository, Rhiza uses git's sparse checkout to fetch only the files you specified in the `include` list. This is fast and efficient!

3. **Copies files to your project** - The specified files are copied from the template repository to your project, maintaining their directory structure

4. **Creates `.rhiza.history`** - A tracking file is created that lists all files under Rhiza's control, along with metadata about the template repository and branch used

5. **Respects existing files** - By default, Rhiza won't overwrite existing files (including your `pyproject.toml`) unless you use the `--force` flag

You'll see output like:
```
[INFO] Target repository: /path/to/my-python-project
[INFO] Rhiza branch: main
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
```

**Important:** Your `pyproject.toml` file is preserved! Rhiza doesn't overwrite it unless you explicitly include it in your template configuration and use the `--force` flag.

Review what was added:

```bash
git status
```

Commit the changes:

```bash
git add .
git commit -m "chore: initialize project with rhiza templates"
```

**Congratulations!** 🎉 You've successfully set up your first Rhiza project!

## Understanding What Just Happened

Let's break down what Rhiza did:

1. **Created `.github/rhiza/template.yml`**: This configuration file defines:
   - Which template repository to use
   - Which branch to use
   - Which files/directories to include

2. **Materialized templates**: Rhiza copied files from the template repository to your project:
   - `.github/` - GitHub workflows and configurations
   - `.editorconfig` - Editor configuration
   - `.gitignore` - Git ignore rules
   - `.pre-commit-config.yaml` - Pre-commit hooks
   - `Makefile` - Build and development commands
   - `pytest.ini` - Test configuration

3. **Created `.rhiza.history`**: This file tracks all files under Rhiza's control, making it easy to see what's managed by templates.

4. **Preserved your `pyproject.toml`**: Your project-specific configuration file remains untouched! Rhiza doesn't manage `pyproject.toml` by default since it contains your project's unique metadata and dependencies.

## Common Use Cases

### Use Case 1: Add Rhiza to an Existing Project

Already have a project? No problem! Rhiza works perfectly with existing projects:

```bash
cd existing-project

# Verify you have a pyproject.toml (required for Python projects)
ls pyproject.toml

# Initialize Rhiza
uvx rhiza init

# Review and edit .github/rhiza/template.yml if needed
# TIP: Make sure NOT to include pyproject.toml in the template
# unless you want to overwrite your existing one!
cat .github/rhiza/template.yml

# Materialize templates (won't overwrite existing files by default)
uvx rhiza materialize

# Review what was added
git status
git diff

# Commit if satisfied
git add .
git commit -m "chore: add rhiza template management"
```

**Important for existing projects:**
- Rhiza will NOT overwrite your existing files (including `pyproject.toml`) by default
- Your project-specific configuration remains intact
- Only new files from the template are added
- Use `--force` only if you want to overwrite existing files

### Use Case 2: Update Templates Periodically

Keep your templates up to date:

```bash
uvx rhiza materialize --force
git diff  # Review what changed
git add .
git commit -m "chore: update rhiza templates"
```

The `--force` flag overwrites existing files with the latest versions from the template repository.

### Use Case 3: Validate Configuration

Check if your configuration is valid:

```bash
uvx rhiza validate
```

This is useful before committing changes or in CI/CD pipelines.

## Customizing Your Templates

### Using a Different Template Repository

Edit `.github/rhiza/template.yml` to use your organization's templates:

```yaml
template-repository: myorg/python-templates
template-branch: main
include:
  - .github/workflows
  - pyproject.toml
  - Makefile
```

Then materialize:

```bash
uvx rhiza materialize --force
```

### Using GitLab Repositories

Rhiza supports GitLab too! Just add `template-host: gitlab`:

```yaml
template-repository: mygroup/python-templates
template-host: gitlab
template-branch: main
include:
  - .gitlab-ci.yml
  - .editorconfig
  - Makefile
```

### Excluding Specific Files

Include a directory but exclude certain files:

```yaml
template-repository: jebel-quant/rhiza
include:
  - .github
exclude:
  - .github/CODEOWNERS
  - .github/workflows/deploy.yml
```

## Next Steps

Now that you have the basics, here's what to explore next:

### 📚 Dive Deeper into Rhiza

- **[CLI Quick Reference](CLI.md)** - Command syntax and options
- **[Usage Guide](USAGE.md)** - Advanced workflows and best practices  
- **[README](README.md)** - Complete documentation

### 🔧 Customize Your Setup

- Edit `.github/rhiza/template.yml` to include only the files you need
- Create your own template repository for your organization
- Set up automated template updates in CI/CD

### 🤝 Get Involved

- **[Contributing Guidelines](CONTRIBUTING.md)** - Learn how to contribute
- **[GitHub Issues](https://github.com/jebel-quant/rhiza-cli/issues)** - Report bugs or request features
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines

## Quick Command Reference

Here are the essential commands you'll use regularly:

| Command | Description |
|---------|-------------|
| `uvx rhiza init` | Create or validate `.github/rhiza/template.yml` |
| `uvx rhiza materialize` | Copy template files to your project |
| `uvx rhiza materialize --force` | Update templates, overwriting existing files |
| `uvx rhiza validate` | Check if configuration is valid |
| `uvx rhiza --help` | Show all available commands and options |

**Note:** If you installed Rhiza with `pip install rhiza`, you can use `rhiza` instead of `uvx rhiza`.

## Troubleshooting

### "Command not found: rhiza"

The easiest solution is to use `uvx` which doesn't require installation:

```bash
uvx rhiza --help
```

Or install Rhiza with pip and ensure it's in your PATH:

```bash
pip install --user rhiza
export PATH="$HOME/.local/bin:$PATH"
```

### "Target directory is not a git repository"

Initialize git first:

```bash
git init
uvx rhiza init
```

### Need More Help?

1. Run `uvx rhiza --help` or `uvx rhiza <command> --help` for command-specific help
2. Check the [Usage Guide](USAGE.md) for detailed examples
3. Search [existing issues](https://github.com/jebel-quant/rhiza-cli/issues)
4. Open a new issue with details about your problem

## Summary

You've learned how to:

- ✅ Install `uv`/`uvx` for running Rhiza without installation
- ✅ Create a `pyproject.toml` file for Python projects (or work with an existing one)
- ✅ Initialize a project with `uvx rhiza init`
- ✅ Understand what `uvx rhiza init` and `uvx rhiza materialize` do under the hood
- ✅ Materialize templates with `uvx rhiza materialize`
- ✅ Validate configuration with `uvx rhiza validate`
- ✅ Customize template configurations
- ✅ Work with both new and existing projects

**Key Takeaway:** Rhiza helps you maintain consistent tooling and configuration files (like `.github/`, Makefile, linting configs) across projects, while respecting your project-specific files like `pyproject.toml`.

Rhiza makes it easy to maintain consistent configurations across all your Python projects. Start using it in your projects today!

**Happy coding!** 🚀
