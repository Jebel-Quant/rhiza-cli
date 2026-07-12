# Getting Started with Rhiza

> **📚 Documentation map** — **Getting Started** (you are here, start here) · [README](README.md) (overview & full command reference) · [Usage Guide](USAGE.md) (workflows & examples) · [CLI Reference](CLI.md) (command cheatsheet)

**Rhiza helps you keep multiple Python projects consistently configured** by using templates stored in central repositories. Instead of manually copying configuration files between projects, Rhiza automates synchronization and ensures your projects stay aligned.

**More than just a template or starter project**, Rhiza is a **continuous synchronization system** that adapts as standards evolve.

Think of it as **an autopilot for syncing hundreds of repos with one or more anchor repositories**. You decide which template repositories act as your anchor repositories — the default `jebel-quant/rhiza`, your organization’s custom templates, your personal hub, or a combination of sources.

When your anchor templates evolve — new workflows, updated linting rules, or security improvements — Rhiza ensures all your projects stay in sync with **a single command** or automatically via scheduled syncs.

---

## Quick Start

Get your project connected and synchronized in just a few steps.

### Explore Rhiza commands

```bash
uvx rhiza --help
```

This lists all available commands and options.

### Connect a project to an anchor repository

Create a `.rhiza/template.yml` file in your project by hand. It points at your
anchor repository and lists what to pull from it. At a minimum it needs a
`template-repository` and one of `include`, `templates`, or `profiles`:

```yaml
# .rhiza/template.yml
template-repository: jebel-quant/rhiza
include:
  - .github
  - .editorconfig
  - .gitignore
  - .pre-commit-config.yaml
  - Makefile
```

Replace `jebel-quant/rhiza` with your own anchor repository (in `owner/repo`
form) if you maintain your own templates. This sets up your project to track and
synchronize with the anchor repository.

### Sync templates

Before applying anything, you can validate your configuration and preview the
changes with a dry-run:

```bash
uvx rhiza sync --strategy diff
```

When you are happy, apply the changes:

```bash
uvx rhiza sync
```

This will:

   - Pull the latest templates from your anchor repository

   - Apply workflows, CI rules, and tooling updates

   - Keep your project aligned without overwriting local changes unexpectedly

### Schedule automatic updates (optional)

Rhiza supports scheduled syncs, so projects stay in sync automatically. Example GitHub Actions snippet:

```yaml
on:
  schedule:
    - cron: '0 3 * * *' # daily at 3 AM UTC
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: uvx rhiza sync
```

