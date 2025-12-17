# Rhiza CLI Quick Reference

This document provides a quick reference for the Rhiza command-line interface.

## Command Overview

| Command | Description |
|---------|-------------|
| `rhiza init` | Initialize or validate `.github/template.yml` |
| `rhiza materialize` | Inject templates into a target repository |
| `rhiza validate` | Validate template configuration |

## Common Usage Patterns

### First-time setup
```bash
cd your-project
rhiza init
rhiza materialize
```

### Update templates
```bash
rhiza materialize --force
```

### Validate before committing
```bash
rhiza validate && git add . && git commit
```

## Command Details

### rhiza init

**Purpose:** Create or validate `.github/template.yml`

**Syntax:**
```bash
rhiza init [TARGET]
```

**Parameters:**
- `TARGET` - Directory to initialize (default: current directory)

**Examples:**
```bash
rhiza init                    # Initialize current directory
rhiza init /path/to/project   # Initialize specific directory
rhiza init ..                 # Initialize parent directory
```

---

### rhiza materialize

**Purpose:** Copy template files into your project

**Syntax:**
```bash
rhiza materialize [OPTIONS] [TARGET]
```

**Parameters:**
- `TARGET` - Target repository directory (default: current directory)

**Options:**
- `--branch, -b <branch>` - Template branch to use (default: main)
- `--force, -y` - Overwrite existing files without prompting

**Examples:**
```bash
rhiza materialize                           # Basic usage
rhiza materialize --branch develop          # Use develop branch
rhiza materialize --force                   # Overwrite existing files
rhiza materialize /path/to/project -b v2.0  # Specific directory and branch
rhiza materialize -b main -y                # Short form
```

**Behavior:**
- Creates `.github/template.yml` if it doesn't exist
- Performs sparse clone of template repository
- Copies only specified files/directories
- Respects exclude patterns
- Skips existing files unless `--force` is used

---

### rhiza validate

**Purpose:** Validate `.github/template.yml` configuration

**Syntax:**
```bash
rhiza validate [TARGET]
```

**Parameters:**
- `TARGET` - Repository directory to validate (default: current directory)

**Exit Codes:**
- `0` - Validation passed
- `1` - Validation failed

**Examples:**
```bash
rhiza validate                    # Validate current directory
rhiza validate /path/to/project   # Validate specific directory
rhiza validate ..                 # Validate parent directory
```

**Validation Checks:**
- ✓ File exists
- ✓ Valid YAML syntax
- ✓ Required fields present
- ✓ Field types correct
- ✓ Repository format (owner/repo)
- ✓ Include list not empty

---

## Configuration File Reference

### Location
`.github/template.yml`

### Format
```yaml
# Required: Template repository (owner/repo format)
template-repository: jebel-quant/rhiza

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
| `template-repository` | string | Yes | GitHub repo in `owner/repo` format |
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
rhiza materialize --force
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
cp .github/template-base.yml .github/template.yml
rhiza materialize --force

cp .github/template-testing.yml .github/template.yml  
rhiza materialize --force
```

### Debugging

Enable verbose output with Python logging:

```bash
# Set log level to DEBUG
export LOGURU_LEVEL=DEBUG
rhiza materialize
```

View what git operations are happening:

```bash
# Watch git commands
GIT_TRACE=1 rhiza materialize
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

### Clone fails during materialize

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
rhiza materialize --help
rhiza validate --help
```

---

## Version Information

```bash
# Check installed version
pip show rhiza

# Upgrade to latest
pip install --upgrade rhiza
```

---

For detailed documentation, see [README.md](README.md)
