# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Rhiza CLI project.

ADRs document significant architectural decisions made during development, capturing
the context, the decision itself, and its consequences for future maintainers.

## Format

Each ADR follows this structure:

- **Status**: Proposed / Accepted / Rejected / Deprecated / Superseded
- **Context**: What situation or problem prompted this decision?
- **Decision**: What did we decide to do?
- **Consequences**: What are the positive and negative results of this decision?

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](0001-inline-get-diff-instead-of-cruft.md) | Inline `get_diff` instead of depending on `cruft` | Accepted |
| [ADR-0002](0002-repository-ref-as-canonical-keys.md) | Make `repository`/`ref` canonical keys in `template.yml` | Accepted |
| [ADR-0003](0003-lock-file-concurrency.md) | Concurrency-safe lock file I/O with fcntl and atomic rename | Accepted |
| [ADR-0004](0004-keep-git-utils-as-single-module.md) | Keep `models/_git_utils.py` as a single module | Superseded by ADR-0005 |
| [ADR-0005](0005-split-git-engine-into-subpackage.md) | Split the git engine into a `models/_git/` subpackage | Accepted |
| [ADR-0006](0006-rhiza-cli-as-claude-plugin.md) | Make `rhiza-cli` the home of the Claude Code plugin | Rejected (reversed in practice) |

## Creating a New ADR

Run `make adr` to trigger the AI-assisted ADR creation workflow, or copy an existing
ADR file and increment the number manually.
