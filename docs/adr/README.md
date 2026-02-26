# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Rhiza CLI project.

ADRs document significant architectural decisions made during development, capturing
the context, the decision itself, and its consequences for future maintainers.

## Format

Each ADR follows this structure:

- **Status**: Proposed / Accepted / Deprecated / Superseded
- **Context**: What situation or problem prompted this decision?
- **Decision**: What did we decide to do?
- **Consequences**: What are the positive and negative results of this decision?

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](0001-inline-get-diff-instead-of-cruft.md) | Inline `get_diff` instead of depending on `cruft` | Accepted |
| [ADR-0002](0002-repository-ref-as-canonical-keys.md) | Make `repository`/`ref` canonical keys in `template.yml` | Accepted |

## Creating a New ADR

Run `make adr` to trigger the AI-assisted ADR creation workflow, or copy an existing
ADR file and increment the number manually.
