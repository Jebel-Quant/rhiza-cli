# Rhiza Usage Guide

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

# Initialize Rhiza
rhiza init
```

You should see output like:
```
[INFO] Initializing Rhiza configuration in: /path/to/my-awesome-project
[INFO] Creating default .rhiza/template.yml
✓ Created .rhiza/template.yml
```

### Understanding the Configuration

View the created configuration:

```bash
cat .rhiza/template.yml
```

You'll see:
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

### Materializing Templates

Apply the templates to your project:

```bash
rhiza materialize
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

After materialization, Rhiza creates a `.rhiza.history` file that tracks all files under template control:

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
- Understand what will be updated when you re-run `rhiza materialize`
- Identify which files to be careful with when making local modifications
- **Detect orphaned files** - when you re-run `rhiza materialize`, any files listed in `.rhiza.history` but no longer in the current template configuration will be automatically deleted

**Important:** The `.rhiza.history` file is regenerated each time you run `rhiza materialize`, so you should commit it along with your other template files. When re-running materialize, Rhiza will compare the old history with the new configuration and remove any files that are no longer being managed.

## Basic Workflows

### Workflow 1: Starting a New Project

Complete workflow for a new Python project:

```bash
# 1. Create project structure
mkdir new-python-lib
cd new-python-lib
git init

# 2. Initialize Rhiza
rhiza init

# 3. Materialize templates
rhiza materialize

# 4. Review and commit
git status
git diff
git add .
git commit -m "feat: initial project setup with rhiza"

# 5. Validate everything is correct
rhiza validate
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

# 4. Initialize Rhiza
rhiza init

# 5. Review generated template.yml and customize if needed
vim .rhiza/template.yml

# 6. Materialize templates (use --force carefully!)
rhiza materialize

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

# 2. Validate current configuration
rhiza validate

# 3. Update templates (overwrite existing)
rhiza materialize --force

# 4. Review changes
git diff

# 5. If changes look good, commit
git add .
git commit -m "chore: update rhiza templates to latest"

# 6. If not, revert
git checkout .
```

## Advanced Usage

### Specifying Template Repository at Init

By default, `rhiza init` creates a configuration that uses the `jebel-quant/rhiza` repository. You can specify your own template repository during initialization using the `--template-repository` option:

```bash
# Initialize with a custom template repository
rhiza init --template-repository myorg/python-standards

# Use a custom repository and branch
rhiza init --template-repository myorg/python-standards --template-branch v2.0

# Combine with other options
rhiza init --git-host gitlab --template-repository myorg/gitlab-templates --template-branch production
```

This automatically creates a `.rhiza/template.yml` file configured to use your custom template, eliminating the need to manually edit the file afterwards.

**Example workflow:**
```bash
mkdir my-project
cd my-project
git init

# Initialize with your organization's template
rhiza init --template-repository mycompany/python-templates --template-branch stable

# Materialize templates
rhiza materialize
```

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

**Materialize:**

```bash
rhiza materialize --force
```

### Using Different Branches

Test templates from a development branch:

```bash
# Temporarily override template branch
rhiza materialize --branch develop

# Or update template.yml
vim .rhiza/template.yml  # Change template-branch to 'develop'
rhiza materialize
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

**Materialize:**

```bash
rhiza materialize --force
```

**Notes:**
- The `template-host` field supports `github` (default) and `gitlab`
- Repository format is the same: `owner/repo` for GitHub or `group/project` for GitLab
- All other Rhiza features work identically with GitLab repositories

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
  rhiza materialize --force
done
```

## Integration Examples

### GitHub Actions Validation

Validate Rhiza configuration in CI:

**`.github/workflows/validate-rhiza.yml`:**

```yaml
name: Validate Rhiza Configuration

on:
  push:
    paths:
      - '.rhiza/template.yml'
  pull_request:
    paths:
      - '.rhiza/template.yml'

jobs:
  validate:
    name: Validate Template Configuration
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
      
      - name: Validate configuration
        run: rhiza validate
```

### Pre-commit Hook

Validate before every commit:

**`.git/hooks/pre-commit`:**

```bash
#!/bin/sh
# Validate Rhiza configuration before commit

if [ -f .rhiza/template.yml ]; then
    echo "Validating Rhiza configuration..."
    rhiza validate || {
        echo "ERROR: Rhiza validation failed"
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
.PHONY: template-init template-update template-validate

template-init: ## Initialize Rhiza templates
	rhiza init

template-update: ## Update templates from repository
	rhiza materialize --force
	@echo "Review changes with: git diff"

template-validate: ## Validate template configuration
	rhiza validate

sync-templates: template-validate template-update ## Validate and update templates
```

Usage:

```bash
make template-init
make template-update
make template-validate
make sync-templates
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

# Initialize templates if needed
RUN if [ ! -f .rhiza/template.yml ]; then rhiza init; fi

# Validate configuration
RUN rhiza validate

CMD ["/bin/bash"]
```

### Pre-commit Framework

Use with the pre-commit framework:

**`.pre-commit-config.yaml`:**

```yaml
repos:
  - repo: local
    hooks:
      - id: rhiza-validate
        name: Validate Rhiza Configuration
        entry: rhiza validate
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
0 0 1 * * cd /path/to/project && rhiza materialize --force
```

### 4. Review Before Committing

Always review changes before committing:

```bash
rhiza materialize --force
git diff                    # Review all changes
git add -p                  # Stage changes selectively
git commit -m "chore: update templates"
```

### 5. Test in Branches

Test template changes in feature branches:

```bash
git checkout -b test-template-update
rhiza materialize --force
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

### 7. Validate in CI

Always validate in your CI pipeline:

```yaml
# In your CI workflow
- name: Validate Rhiza
  run: rhiza validate
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
rhiza materialize --force

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

# Test materialize
rhiza materialize

# Review what would be added
ls -la
cat important-file.yml

# If satisfied, apply to real project
cd /path/to/project
rhiza materialize --force
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
