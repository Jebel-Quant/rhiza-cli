# Rhiza Usage Guide

> **📚 Documentation map** — [Getting Started](GETTING_STARTED.md) (start here) · [README](README.md) (overview & full command reference) · **Usage Guide** (you are here) · [CLI Reference](CLI.md) (command cheatsheet)

This guide provides practical examples and tutorials for using Rhiza CLI.

## Table of Contents

- [Getting Started](#getting-started)
- [Basic Workflows](#basic-workflows)
- [Advanced Usage](#advanced-usage)
- [Integration Examples](#integration-examples)
- [Best Practices](#best-practices)

## Getting Started

### Installation

Install Rhiza using pip:

```bash
pip install rhiza
```

Or use uvx to run without installation:

```bash
uvx rhiza --help
```

With uvx, you don't need to install rhiza - it automatically uses the latest version each time you run it.

Verify installation:

```bash
rhiza --help
```

### Your First Project

Let's set up a new Python project with Rhiza templates:

```bash
# Create a new project directory
mkdir my-awesome-project
cd my-awesome-project

# Initialize git repository
git init

# Create the Rhiza configuration by hand
mkdir -p .rhiza
$EDITOR .rhiza/template.yml
```

### Understanding the Configuration

Rhiza is driven by `.rhiza/template.yml`, which you create by hand. A minimal
configuration must set `template-repository` and one of `include`, `templates`,
or `profiles`:

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

This tells Rhiza to fetch these files from the `jebel-quant/rhiza` repository.
`rhiza sync` validates this file every time it runs and reports a clear error if
it is missing, malformed, or missing a required field.

### Syncing Templates

Apply the templates to your project:

```bash
rhiza sync
```

Review what was added:

```bash
git status
ls -la
```

Commit the changes:

```bash
git add .
git commit -m "chore: initialize project with rhiza templates"
```

### Understanding the History File

After syncing, Rhiza creates a `.rhiza.history` file that tracks all files under template control:

```bash
cat .rhiza.history
```

You'll see:
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
.github/workflows/ci.yml
...
```

This file helps you:
- Track which files are managed by the template
- Understand what will be updated when you re-run `rhiza sync`
- Identify which files to be careful with when making local modifications
- **Detect orphaned files** - when you re-run `rhiza sync`, any files listed in `.rhiza.history` but no longer in the current template configuration will be automatically deleted

**Important:** The `.rhiza.history` file is regenerated each time you run `rhiza sync`, so you should commit it along with your other template files. When re-running sync, Rhiza will compare the old history with the new configuration and remove any files that are no longer being managed.

## Basic Workflows

### Workflow 1: Starting a New Project

Complete workflow for a new Python project:

```bash
# 1. Create project structure
mkdir new-python-lib
cd new-python-lib
git init

# 2. Create .rhiza/template.yml by hand (see "Understanding the Configuration")
mkdir -p .rhiza
$EDITOR .rhiza/template.yml

# 3. Sync templates
rhiza sync

# 4. Review and commit
git status
git diff
git add .
git commit -m "feat: initial project setup with rhiza"
```

### Workflow 2: Updating Existing Project

Add Rhiza to an existing project:

```bash
# 1. Navigate to existing project
cd existing-project

# 2. Ensure it's a git repository
git status

# 3. Create feature branch
git checkout -b add-rhiza-templates

# 4. Create .rhiza/template.yml by hand and customize it
mkdir -p .rhiza
vim .rhiza/template.yml

# 5. Preview what would change (validating dry-run)
rhiza sync --strategy diff

# 6. Sync templates
rhiza sync

# 7. Review changes carefully
git diff

# 8. Commit
git add .
git commit -m "chore: add rhiza template management"

# 9. Create PR
git push -u origin add-rhiza-templates
```

### Workflow 3: Updating Templates

Periodically update your project's templates:

```bash
# 1. Create update branch
git checkout -b update-templates

# 2. Update templates (validates the configuration before applying changes)
rhiza sync

# 3. Review changes
git diff

# 4. If changes look good, commit
git add .
git commit -m "chore: update rhiza templates to latest"

# 5. If not, revert
git checkout .
```

## Advanced Usage

### Custom Template Repository

Use your organization's template repository:

**Edit `.rhiza/template.yml`:**

```yaml
template-repository: myorg/python-templates
template-branch: production
include:
  - .github/workflows
  - .github/dependabot.yml
  - pyproject.toml
  - Makefile
  - docker-compose.yml
  - src/config
exclude:
  - .github/workflows/experimental.yml
```

**Sync:**

```bash
rhiza sync
```

### Using Different Branches

Test templates from a development branch:

```bash
# Temporarily override template branch
rhiza sync --branch develop

# Or update template.yml
vim .rhiza/template.yml  # Change template-branch to 'develop'
rhiza sync
```

### Using GitLab Repositories

Configure Rhiza to use a GitLab template repository:

**Edit `.rhiza/template.yml`:**

```yaml
template-repository: mygroup/python-templates
template-host: gitlab
template-branch: main
include:
  - .gitlab-ci.yml
  - .editorconfig
  - .gitignore
  - Makefile
  - pytest.ini
exclude:
  - .gitlab-ci.yml  # Example exclusion
```

**Sync:**

```bash
rhiza sync
```

**Notes:**
- The `template-host` field supports `github` (default) and `gitlab`
- Repository format is the same: `owner/repo` for GitHub or `group/project` for GitLab
- All other Rhiza features work identically with GitLab repositories

### Multi-Language Support

Rhiza supports templates for multiple programming languages, not just Python. By default, Rhiza assumes Python projects (requiring `pyproject.toml`), but you can specify a different language in your template configuration.

#### Supported Languages

- **Python** (default): Validates `pyproject.toml`, `src/`, and `tests/` directories
- **Go**: Validates `go.mod`, `cmd/`, `pkg/`, and `internal/` directories

#### Configuring a Go Project

For a Go project, specify the language in `.rhiza/template.yml`:

```yaml
template-repository: jebel-quant/rhiza-go
language: go
include:
  - .github
  - .editorconfig
  - .gitignore
  - Makefile
```

**Sync your Go project:**

```bash
rhiza sync
```

`rhiza sync` validates the configuration first, so you'll see
language-specific validation:

```
[INFO] Project language: go
[SUCCESS] go.mod exists: /path/to/project/go.mod
[WARNING] Standard 'cmd' folder not found
[WARNING] Consider creating a 'cmd' directory for main applications
```

#### Configuring a Python Project (Explicit)

While Python is the default, you can explicitly specify it:

```yaml
template-repository: jebel-quant/rhiza
language: python
include:
  - .github
  - pyproject.toml
  - Makefile
```

#### Backward Compatibility

If you omit the `language` field, Rhiza defaults to Python for backward compatibility:

```yaml
# This is treated as a Python project
template-repository: jebel-quant/rhiza
include:
  - .github
```

#### Language-Specific Validation

Each language has its own validation rules:

**Python projects must have:**
- `pyproject.toml` (required)
- `src/` directory (recommended, warning if missing)
- `tests/` directory (recommended, warning if missing)

**Go projects must have:**
- `go.mod` (required)
- `cmd/` directory (recommended, warning if missing)
- `pkg/` or `internal/` directory (recommended, warning if missing)

#### Example: Converting a Project to Go

If you have an existing Python project and want to convert it to Go:

```bash
# 1. Update template.yml
vim .rhiza/template.yml

# Add or change language field:
# language: go
# template-repository: jebel-quant/rhiza-go

# 2. Create Go project structure
go mod init example.com/myproject
mkdir -p cmd/myapp
mkdir -p pkg/mypackage

# 3. Sync Go templates (validates the configuration first)
rhiza sync
```

### Selective Inclusion

Include only specific files:

```yaml
template-repository: jebel-quant/rhiza
include:
  - .github/workflows/ci.yml         # Single file
  - .github/workflows/release.yml    # Another file
  - .editorconfig                    # Configuration file
  - Makefile                         # Build file
```

### Exclusion Patterns

Include a directory but exclude specific files:

```yaml
template-repository: jebel-quant/rhiza
include:
  - .github                    # Include entire directory
exclude:
  - .github/CODEOWNERS         # But exclude this file
  - .github/workflows/deploy.yml  # And this workflow
```

### Multiple Template Sources

While Rhiza doesn't directly support multiple repositories, you can manage them:

**Create multiple configuration files:**

```bash
# .rhiza/template-base.yml
# .rhiza/template-testing.yml
# .rhiza/template-docs.yml
```

**Use a script to apply them:**

```bash
#!/bin/bash
# apply-all-templates.sh

for template in .rhiza/template-*.yml; do
  cp "$template" .rhiza/template.yml
  rhiza sync
done
```

## Integration Examples

### GitHub Actions Check

Check Rhiza configuration in CI. `rhiza sync --strategy diff` validates the
configuration and reports what would change without modifying any files:

**`.github/workflows/check-rhiza.yml`:**

```yaml
name: Check Rhiza Configuration

on:
  push:
    paths:
      - '.rhiza/template.yml'
  pull_request:
    paths:
      - '.rhiza/template.yml'

jobs:
  check:
    name: Check Template Configuration
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Rhiza
        run: pip install rhiza
      
      - name: Check configuration
        run: rhiza sync --strategy diff
```

### Pre-commit Hook

Check before every commit:

**`.git/hooks/pre-commit`:**

```bash
#!/bin/sh
# Check Rhiza configuration before commit

if [ -f .rhiza/template.yml ]; then
    echo "Checking Rhiza configuration..."
    rhiza sync --strategy diff || {
        echo "ERROR: Rhiza check failed"
        exit 1
    }
fi
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

### Makefile Integration

Add Rhiza commands to your Makefile:

```makefile
.PHONY: template-update template-check

template-update: ## Update templates from repository
	rhiza sync
	@echo "Review changes with: git diff"

template-check: ## Check template configuration (dry-run)
	rhiza sync --strategy diff
```

Usage:

```bash
make template-update
make template-check
```

### Docker Integration

Include Rhiza in your Docker workflow:

**`Dockerfile.dev`:**

```dockerfile
FROM python:3.11

WORKDIR /app

# Install Rhiza
RUN pip install rhiza

# Copy project
COPY . .

# Check configuration (validating dry-run)
RUN rhiza sync --strategy diff

CMD ["/bin/bash"]
```

### Pre-commit Framework

Use with the pre-commit framework:

**`.pre-commit-config.yaml`:**

```yaml
repos:
  - repo: local
    hooks:
      - id: rhiza-check
        name: Check Rhiza Configuration
        entry: rhiza sync --strategy diff
        language: system
        pass_filenames: false
        files: ^\.rhiza/template\.yml$
```

Install and run:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Best Practices

### 1. Version Control Template Configuration

Always commit `.rhiza/template.yml`:

```bash
git add .rhiza/template.yml
git commit -m "feat: add rhiza template configuration"
```

### 2. Document Custom Configurations

Add comments to your template.yml:

```yaml
# Custom template configuration for our microservices
template-repository: myorg/microservice-templates
template-branch: v2.0  # Use stable v2.0 branch

# Core files needed for all microservices
include:
  - .github/workflows       # CI/CD pipelines
  - docker-compose.yml      # Local development
  - Dockerfile              # Container definition
  - pyproject.toml          # Python project config
  - src/config              # Shared configuration

# Exclude service-specific files
exclude:
  - .github/workflows/deploy-specific.yml
```

### 3. Regular Template Updates

Set up a schedule for template updates:

```bash
# Monthly template update
0 0 1 * * cd /path/to/project && rhiza sync
```

### 4. Review Before Committing

Always review changes before committing:

```bash
rhiza sync
git diff                    # Review all changes
git add -p                  # Stage changes selectively
git commit -m "chore: update templates"
```

### 5. Test in Branches

Test template changes in feature branches:

```bash
git checkout -b test-template-update
rhiza sync
# Test your project
# If OK: merge; If not: delete branch
```

### 6. Document Exclusions

If you exclude files, document why:

```yaml
exclude:
  # We maintain our own deployment workflow
  - .github/workflows/deploy.yml
  
  # Team-specific CODEOWNERS
  - .github/CODEOWNERS
```

### 7. Check in CI

Always check your template configuration in your CI pipeline. `rhiza sync
--strategy diff` validates the config and shows what would change without
modifying files:

```yaml
# In your CI workflow
- name: Check Rhiza
  run: rhiza sync --strategy diff
```

### 8. Keep Templates Minimal

Only include what you actually need:

```yaml
# Good: Specific files
include:
  - .github/workflows/ci.yml
  - .editorconfig
  - pyproject.toml

# Less good: Too broad
include:
  - .github
  - src
  - tests
```

### 9. Use Semantic Versioning for Template Branches

In your template repository:

```bash
# Create versioned branches
git checkout -b v1.0
git checkout -b v2.0
```

In projects:

```yaml
# Pin to specific version
template-branch: v1.0
```

### 10. Communicate Changes

When updating templates, explain why:

```bash
# Use proper multi-line commit message
git commit -m "chore: update rhiza templates" \
  -m "" \
  -m "Updated from template repo v1.0 to v2.0:" \
  -m "- New GitHub Actions workflows" \
  -m "- Updated linting rules in ruff.toml" \
  -m "- Added security scanning workflow" \
  -m "" \
  -m "Refs: https://github.com/org/templates/releases/v2.0"
```

## Troubleshooting Scenarios

### Scenario 1: Merge Conflicts After Update

**Problem:** Template update causes merge conflicts

**Solution:**

```bash
# Update templates
rhiza sync

# If conflicts, review each file
git diff path/to/conflicted/file

# Manually resolve or keep local version
git checkout --ours path/to/file  # Keep local
git checkout --theirs path/to/file  # Keep template

# Commit resolution
git add .
git commit -m "chore: update templates, resolve conflicts"
```

### Scenario 2: Template Override Local Changes

**Problem:** Need to keep local modifications to template files

**Solution:**

```yaml
# Exclude files you've customized
exclude:
  - .github/workflows/custom-ci.yml
  - Makefile  # We have custom targets
```

### Scenario 3: Testing New Templates

**Problem:** Want to test templates before applying

**Solution:**

```bash
# Create a test directory
mkdir /tmp/template-test
cd /tmp/template-test
git init

# Copy your template.yml
cp /path/to/project/.rhiza/template.yml .rhiza/

# Test sync
rhiza sync

# Review what would be added
ls -la
cat important-file.yml

# If satisfied, apply to real project
cd /path/to/project
rhiza sync
```

## Additional Resources

- [CLI Quick Reference](CLI.md)
- [Full Documentation](README.md)
- [Template Repository](https://github.com/jebel-quant/rhiza)
- [Issue Tracker](https://github.com/jebel-quant/rhiza-cli/issues)

## Getting Help

If you need help:

1. Check this usage guide
2. Review the [CLI Quick Reference](CLI.md)
3. Run `rhiza <command> --help`
4. Check existing [GitHub issues](https://github.com/jebel-quant/rhiza-cli/issues)
5. Open a new issue with details about your problem
