# Rhiza CLI Quick Reference

This document provides a quick reference for the Rhiza command-line interface.

## Command Overview

| Command | Description |
|---------|-------------|
| `rhiza init` | Initialize or validate `.rhiza/template.yml` |
| `rhiza sync` | Sync templates (first-time copy **or** 3-way merge on updates) |
| `rhiza materialize` | *(Deprecated)* Use `rhiza sync` instead |
| `rhiza migrate` | Migrate to the new `.rhiza` folder structure |
| `rhiza validate` | Validate template configuration |

## Common Usage Patterns

### First-time setup
```bash
cd your-project
rhiza init
rhiza sync
```

### Update templates (preserving local changes)
```bash
rhiza sync
```

### Sync template files
```bash
rhiza sync
```

### Validate before committing
```bash
rhiza validate && git add . && git commit
```

## Command Details

### rhiza init

**Purpose:** Create or validate `.rhiza/template.yml`

**Syntax:**
```bash
rhiza init [OPTIONS] [TARGET]
```

**Parameters:**
- `TARGET` - Directory to initialize (default: current directory)

**Options:**
- `--project-name <name>` - Custom project name (default: directory name)
- `--package-name <name>` - Custom package name (default: normalized project name)
- `--with-dev-dependencies` - Include development dependencies in pyproject.toml
- `--git-host <host>` - Target Git hosting platform (github or gitlab)
- `--template-repository <owner/repo>` - Custom template repository (default: jebel-quant/rhiza)
- `--template-branch <branch>` - Custom template branch (default: main)

**Examples:**
```bash
rhiza init                                          # Initialize current directory
rhiza init /path/to/project                         # Initialize specific directory
rhiza init --git-host gitlab                        # Use GitLab CI configuration
rhiza init --template-repository myorg/my-templates # Use custom template repository
rhiza init --template-repository myorg/my-templates --template-branch develop  # Custom repo and branch
rhiza init ..                                       # Initialize parent directory
```

---

### rhiza sync

**Purpose:** Sync template files into your project — first-time copy *or* 3-way merge on subsequent updates

**Syntax:**
```bash
rhiza sync [OPTIONS] [TARGET]
```

**Parameters:**
- `TARGET` - Target repository directory (default: current directory)

**Options:**
- `--branch, -b <branch>` - Template branch to use (default: main)
- `--strategy, -s <strategy>` - Sync strategy: `merge` (default) or `diff`
- `--target-branch <branch>` - Create / checkout a branch in the target repo for changes

**Strategies:**
| Strategy | What it does |
|----------|-------------|
| `merge` (default) | 3-way merge — upstream changes applied, local edits preserved |
| `diff` | Dry-run — show what *would* change, no files modified |

**Examples:**
```bash
rhiza sync                                  # First sync or 3-way merge update
rhiza sync --strategy diff                  # Preview changes
rhiza sync --branch develop                 # Use develop branch
rhiza sync --target-branch update-templates # Work in a dedicated branch
```

**Behavior:**
- **First run (no lock):** copies all template files, writes `.rhiza/template.lock`
- **Subsequent runs:** computes diff (base → upstream) and applies it via `git apply -3`
- Automatically removes orphaned files (files no longer in the template's `include` list)
- Updates `.rhiza/history` with the current set of managed files

---

### rhiza materialize *(Deprecated)*

> **Deprecated.** Use `rhiza sync` instead.
>
> | Old command | Equivalent new command |
> |-------------|----------------------|
> | `rhiza materialize` | `rhiza sync` |
> | `rhiza materialize --force` | `rhiza sync` |

---

### rhiza migrate

**Purpose:** Migrate project to the new `.rhiza` folder structure

**Syntax:**
```bash
rhiza migrate [TARGET]
```

**Parameters:**
- `TARGET` - Target repository directory (default: current directory)

**Examples:**
```bash
rhiza migrate                    # Migrate current directory
rhiza migrate /path/to/project   # Migrate specific directory
```

**What It Does:**
- Creates the `.rhiza/` directory in the project root
- Moves `template.yml` from `.github/rhiza/` or `.github/` to `.rhiza/template.yml`
- Moves `.rhiza.history` to `.rhiza/history`
- Provides instructions for next steps
- Skips files that already exist in `.rhiza/` (leaves old files in place for manual cleanup)

**When to Use:**
- Transitioning to the new `.rhiza/` folder structure
- Organizing Rhiza configuration separately from `.github/`
- Cleaning up project structure

---

### rhiza validate

**Purpose:** Validate `.rhiza/template.yml` configuration

**Syntax:**
```bash
rhiza validate [TARGET] [OPTIONS]
```

**Parameters:**
- `TARGET` - Repository directory to validate (default: current directory)

**Options:**
- `--path-to-template DIRECTORY` - Directory containing `template.yml` (default: `<TARGET>/.rhiza`). Use `.` to keep the file in the project root.

**Exit Codes:**
- `0` - Validation passed
- `1` - Validation failed

**Examples:**
```bash
rhiza validate                                      # Validate current directory
rhiza validate /path/to/project                     # Validate specific directory
rhiza validate ..                                   # Validate parent directory
rhiza validate --path-to-template /custom/rhiza     # Custom template directory
rhiza validate --path-to-template .                 # Template in project root
```

**Validation Checks:**
- ✓ File exists
- ✓ Valid YAML syntax
- ✓ Required fields present
- ✓ Field types correct
- ✓ Repository format (owner/repo)
- ✓ Include list not empty

---

## Generated Files

### .rhiza/template.lock

After running `rhiza sync`, a `.rhiza/template.lock` file is created (or updated) in the `.rhiza/` directory.
It records the full state of the last successful sync as a YAML file, enabling incremental 3-way merges on subsequent runs.

**Fields:**

| Field | Description |
|-------|-------------|
| `sha` | Commit SHA of the last-synced template snapshot |
| `repo` | Template repository (e.g., `jebel-quant/rhiza`) |
| `host` | Git hosting platform (`github` or `gitlab`) |
| `ref` | Branch or ref that was synced (e.g., `main`) |
| `include` | Paths included from the template repository |
| `exclude` | Paths excluded from the template repository |
| `templates` | Bundle names used (empty when using path-based mode) |
| `files` | Sorted list of every file materialized in this sync |

**Example:**
```yaml
sha: abc123def456789abcdef0123456789abcdef0123
repo: jebel-quant/rhiza
host: github
ref: main
include:
- .github/
- .rhiza/
exclude: []
templates: []
files:
- .github/workflows/ci.yml
- .rhiza/template.yml
- Makefile
```

**Usage:**
```bash
# View the current lock state
cat .rhiza/template.lock

# Check which SHA was last synced
grep "^sha:" .rhiza/template.lock
```

> **Note:** Commit this file to version control alongside `.rhiza/history`.
> It is the anchor used by the 3-way merge — without it the next `rhiza sync` treats the project as a first-time sync and copies all template files.

---

### .rhiza/history

After running `rhiza sync`, a `.rhiza/history` file is created in the `.rhiza/` directory. This file:

- Lists all files managed by the template
- Includes metadata about the template repository and branch
- Is regenerated each time `rhiza sync` runs
- Should be committed to version control
- Is used to detect and remove orphaned files (files that were previously managed but are no longer in the current template configuration)

**Example:**
```
# Rhiza Template History
# This file lists all files managed by the Rhiza template.
# Template repository: jebel-quant/rhiza
# Template branch: main
#
# Files under template control:
.editorconfig
.gitignore
Makefile
```

**Usage:**
```bash
# View tracked files
cat .rhiza/history

# Check if a file is managed by template
grep "myfile.txt" .rhiza/history
```

---

## Configuration File Reference

### Location
`.rhiza/template.yml`

### Format
```yaml
# Required: Template repository (owner/repo format)
template-repository: jebel-quant/rhiza

# Optional: Hosting platform (default: github)
template-host: github

# Optional: Branch to use (default: main)
template-branch: main

# Required: Files/directories to include
include:
  - .github
  - .editorconfig
  - .gitignore
  - Makefile

# Optional: Files/directories to exclude
exclude:
  - .github/workflows/deploy.yml
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template-repository` | string | Yes | GitHub or GitLab repo in `owner/repo` format |
| `template-host` | string | No | Hosting platform: `github` (default) or `gitlab` |
| `template-branch` | string | No | Branch name (default: `main`) |
| `include` | list | Yes | Paths to copy from template |
| `exclude` | list | No | Paths to skip when copying |

---

## Tips and Best Practices

### Shell Completion

Enable shell completion for tab completion of commands:

```bash
# Install completion
rhiza --install-completion

# Show completion script
rhiza --show-completion
```

### Using with Git

Add to your git workflow:

```bash
# Before making changes
rhiza validate || exit 1

# Update templates periodically
git checkout -b update-templates
rhiza sync
git diff  # Review changes
git commit -am "chore: update rhiza templates"
```

### CI/CD Integration

Add validation to your CI pipeline:

```yaml
# .github/workflows/validate.yml
- name: Validate Rhiza config
  run: |
    pip install rhiza
    rhiza validate
```

### Multiple Template Repositories

While Rhiza doesn't directly support multiple template repositories, you can:

1. Create separate template.yml files
2. Rename and use them sequentially:

```bash
# Use different templates
cp .rhiza/template-base.yml .rhiza/template.yml
rhiza sync

cp .rhiza/template-testing.yml .rhiza/template.yml  
rhiza sync
```

### Debugging

Enable verbose output with Python logging:

```bash
# Set log level to DEBUG
export LOGURU_LEVEL=DEBUG
rhiza sync
```

View what git operations are happening:

```bash
# Watch git commands
GIT_TRACE=1 rhiza sync
```

---

## Common Issues

### "Command not found: rhiza"

**Solution:** Ensure rhiza is installed and in your PATH:
```bash
pip install --user rhiza
export PATH="$HOME/.local/bin:$PATH"
```

### "Target directory is not a git repository"

**Solution:** Initialize git first:
```bash
git init
rhiza init
```

### "Template file not found"

**Solution:** Run init first:
```bash
rhiza init
```

### Files not being copied

**Checklist:**
- [ ] Paths in `include` are correct
- [ ] Paths exist in template repository
- [ ] Not filtered by `exclude` patterns
- [ ] Using `--force` if files already exist

### Clone fails during sync

**Possible causes:**
- Repository doesn't exist or is private
- Branch doesn't exist
- No network connectivity
- Git credentials not configured for private repos

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOGURU_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |

---

## Getting Help

```bash
# Main help
rhiza --help

# Command-specific help
rhiza init --help
rhiza sync --help
rhiza validate --help
```

---

## Version Information

```bash
# Check installed version (pip)
pip show rhiza

# Check version with uvx
uvx rhiza --version

# Upgrade to latest (pip)
pip install --upgrade rhiza

# With uvx - no upgrade needed!
# uvx always uses the latest version automatically
uvx rhiza --help
```

---

For detailed documentation, see [README.md](README.md)
