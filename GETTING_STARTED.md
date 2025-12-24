# Getting Started with Rhiza

**Rhiza helps you keep multiple Python projects consistently configured** by using templates stored in central repositories. Instead of manually copying configuration files between projects, Rhiza automates synchronization and ensures your projects stay aligned.

**More than just a template or starter project**, Rhiza is a **continuous synchronization system** that adapts as standards evolve.

Think of it as **an autopilot for syncing hundreds of repos with one or more anchor repositories**. You decide which template repositories act as your anchor repositories — the default `jebel-quant/rhiza`, your organization’s custom templates, your personal hub, or a combination of sources.

When your anchor templates evolve — new workflows, updated linting rules, or security improvements — Rhiza ensures all your projects stay in sync with **a single command** or automatically via scheduled materializations.

---

## Quick Start

Get your project connected and synchronized in just a few steps.

### Explore Rhiza commands

```bash
uvx rhiza --help
```

This lists all available commands and options.

### Connect a project to an anchor repository

```bash
uvx rhiza init --anchor <ANCHOR_REPO_URL>
```

Replace <ANCHOR_REPO_URL> with the URL of your anchor repository, for example:

```
uvx rhiza init --anchor https://github.com/jebel-quant/rhiza
```

This sets up your project to track and synchronize with the anchor repository.

### Materialize templates

```bash
uvx rhiza materialize
```

This will:

   - Pull the latest templates from your anchor repository

   - Apply workflows, CI rules, and tooling updates

   - Keep your project aligned without overwriting local changes unexpectedly

### Schedule automatic updates (optional)

Rhiza supports scheduled materializations, so projects stay in sync automatically. Example GitHub Actions snippet:

```yaml
on:
  schedule:
    - cron: '0 3 * * *' # daily at 3 AM UTC
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: uvx rhiza materialize

