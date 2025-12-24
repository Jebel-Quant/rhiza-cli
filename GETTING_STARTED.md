# Getting Started with Rhiza

Welcome! This guide will help you get started with Rhiza, a CLI tool for managing reusable configuration templates for Python projects.

## What is Rhiza?

**Rhiza is more than just a template or a starting point** — it's a continuous synchronization system that keeps your projects aligned with a moving target.

Think of it as **an autopilot for syncing hundreds of repos with one or multiple "motherships"**. You have full control over which template repositories serve as your motherships — whether it's the default `jebel-quant/rhiza`, your organization's custom templates, your personal configuration hub, or a combination of multiple sources. Rhiza actively maintains consistency across all your Python projects by pulling from your chosen central repository templates.

When your central templates evolve (new workflows, updated linting rules, security improvements), Rhiza ensures all your projects can stay in sync with a single command — or even automatically through scheduled materializations.

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

**Security Note:** The commands above download and execute installation scripts from [astral.sh](https://astral.sh/uv/). You can review the installation scripts before running them, or visit the [official uv documentation](https://docs.astral.sh/uv/) for alternative installation methods.

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

Let's create a new Python project with Rhiza templates in just 4 simple steps:

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

### Step 3: Initialize Rhiza

Create your complete Python project structure with one command:

```bash
uvx rhiza init
```

**💡 What does `uvx rhiza init` do?**

When you run `uvx rhiza init`, it sets up your entire Python project automatically:

1. **uvx downloads and caches Rhiza** - The first time you run this, `uvx` downloads the latest version of Rhiza from PyPI and caches it. Subsequent runs are instant!

2. **Creates the Rhiza configuration** - A `.github/rhiza/` directory is created with a `template.yml` file that defines which template files to fetch from the `jebel-quant/rhiza` template repository.

3. **Creates your Python package structure** - Automatically creates a `src/<project-name>/` directory with:
   - `__init__.py` - Makes it a Python package
   - `main.py` - A starter Python file with a simple "Hello, World!" example

4. **Creates `pyproject.toml`** - Generates a modern Python project configuration file with:
   - Project name (based on your directory name)
   - Version set to "0.1.0"
   - Python version requirement (>=3.11)
   - Empty dependencies list (ready for you to add)

5. **Creates `README.md`** - An empty README file for your project documentation

You should see:
```
[INFO] Initializing Rhiza configuration in: /path/to/my-python-project
[INFO] Creating default .github/rhiza/template.yml
✓ Created .github/rhiza/template.yml

Next steps:
  1. Review and customize .github/rhiza/template.yml to match your project needs
  2. Run 'rhiza materialize' to inject templates into your repository
```

**What gets created:**
```
my-python-project/
├── .github/
│   └── rhiza/
│       └── template.yml
├── src/
│   └── my-python-project/
│       ├── __init__.py
│       └── main.py
├── pyproject.toml
└── README.md
```

**Note:** If you installed Rhiza with pip, you can use `rhiza init` instead of `uvx rhiza init`.

### Step 4: Review the Configuration

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

You can also check the generated Python files:

```bash
# View the project metadata
cat pyproject.toml

# Check the starter Python code
cat src/my-python-project/main.py
```

### Step 5: Materialize Templates

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

5. **Respects existing files** - By default, Rhiza won't overwrite existing files (including your `pyproject.toml` and source code) unless you use the `--force` flag

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

**Important:** Your project files (`pyproject.toml`, source code in `src/`) are preserved! Rhiza doesn't overwrite them unless you explicitly include them in your template configuration and use the `--force` flag.

Review what was added:

```bash
git status
```

Commit the changes:

```bash
git add .
git commit -m "chore: initialize project with rhiza templates"
```

**Congratulations!** 🎉 You've successfully set up your first Rhiza project with a complete Python package structure!

## Understanding What Just Happened

Let's break down what Rhiza did across the two commands:

### From `uvx rhiza init`:

1. **Created your Python package structure**:
   - `src/<project-name>/` - Following the modern "src layout" pattern
   - `__init__.py` - Makes your directory a Python package
   - `main.py` - A starter file with a simple example function

2. **Created `pyproject.toml`**: Your project's metadata and configuration file with:
   - Project name (based on directory)
   - Version (0.1.0)
   - Python requirement (>=3.11)
   - Empty dependencies list

3. **Created `README.md`**: An empty file ready for your documentation

4. **Created `.github/rhiza/template.yml`**: Configuration defining which template files to fetch

### From `uvx rhiza materialize`:

1. **Materialized templates**: Rhiza copied configuration and tooling files from the template repository:
   - `.github/` - GitHub workflows and configurations
   - `.editorconfig` - Editor configuration
   - `.gitignore` - Git ignore rules
   - `.pre-commit-config.yaml` - Pre-commit hooks
   - `Makefile` - Build and development commands
   - `pytest.ini` - Test configuration

2. **Created `.rhiza.history`**: Tracks all files under Rhiza's control

3. **Preserved your code**: Your `pyproject.toml` and `src/` directory remain untouched since they're not in the template's `include` list

## Common Use Cases

### Use Case 1: Add Rhiza to an Existing Project

Already have a project? No problem! Rhiza works perfectly with existing projects:

```bash
cd existing-project

# Initialize Rhiza (creates missing files only, won't overwrite existing)
uvx rhiza init

# If you didn't have a pyproject.toml, Rhiza created one!
# If you didn't have a src/ directory, Rhiza created it!
# Check what was created:
ls -la

# Review and edit .github/rhiza/template.yml if needed
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
- `uvx rhiza init` is **safe** - it only creates files that don't exist
- If you already have `pyproject.toml`, `src/`, or `README.md`, they're left untouched
- If you're missing these files, Rhiza helpfully creates them with sensible defaults
- `uvx rhiza materialize` won't overwrite existing files unless you use `--force`

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

**Note:** The `export` command above is temporary and only affects your current shell session. To make it permanent, add it to your shell profile:

```bash
# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# For zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

Then restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc`).

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
- ✅ Initialize a complete Python project with `uvx rhiza init` (creates `pyproject.toml`, `src/` structure, `README.md`)
- ✅ Understand what `uvx rhiza init` and `uvx rhiza materialize` do under the hood
- ✅ Materialize templates with `uvx rhiza materialize`
- ✅ Validate configuration with `uvx rhiza validate`
- ✅ Customize template configurations
- ✅ Work with both new and existing projects safely

**Key Takeaway:** Rhiza's powerful `init` command sets up
your entire Python project structure (package layout, pyproject.toml, README)
while also configuring template management. It then helps you maintain
consistent tooling and configuration files (like `.github/`, Makefile, linting configs) across all your projects.

Rhiza’s killer feature? **Scheduled materializations**.
Set it, forget it, and your repo automatically updates itself from .github/rhiza/template.yml.
When your template is always changing, this keeps everything perfectly
in sync—like a self-updating repo on autopilot. We discuss details in [USAGE](USAGE.md)

Rhiza makes it easy to bootstrap and maintain consistent Python projects. Start using it today!

**Happy coding!** 🚀
