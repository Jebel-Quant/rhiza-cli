# ADR-0002: Make `repository`/`ref` canonical keys in `template.yml`

**Status**: Accepted

## Context

The `.rhiza/template.yml` configuration file originally used verbose, prefixed key
names inherited from `cruft`:

- `template-repository` — the upstream template repository slug
- `template-branch` — the branch or tag to track

As Rhiza evolved into a standalone tool these names became awkward:

1. The `template-` prefix is redundant inside a file that is already called
   `template.yml` and lives inside `.rhiza/`.
2. The word *branch* is too narrow: the field accepts any git ref (branch, tag, SHA),
   so the name was misleading.
3. New projects created with `rhiza init` write `repository` and `ref` to
   `template.yml`, producing files that mixed the two naming schemes when old
   `template.yml` files were retained unchanged.
4. CLI options and internal model attributes already used `repository` / `ref` as
   their canonical names, creating a confusing mismatch with the YAML keys.

## Decision

Adopt `repository` and `ref` as the canonical YAML keys in `template.yml`.

`RhizaTemplate.from_yaml` reads both the old and new names, with the new names taking
precedence:

```python
# Support both 'repository' and 'template-repository' (repository takes precedence)
template_repository = config.get("repository") or config.get("template-repository")

# Support both 'ref' and 'template-branch' (ref takes precedence)
template_branch = config.get("ref") or config.get("template-branch")
```

`RhizaTemplate.to_yaml` writes only the canonical keys (`repository`, `ref`) when
serialising configuration, so any new file or round-tripped file uses the new scheme.

The old key names are kept as read-only aliases indefinitely to preserve backward
compatibility with existing `.rhiza/template.yml` files in downstream projects.

## Consequences

**Positive**

- New projects get concise, self-explanatory configuration.
- Internal model attributes, CLI flags, and YAML keys share the same vocabulary,
  reducing cognitive load.
- `ref` correctly signals that tags and SHAs are valid values, not just branch names.
- Existing projects continue to work without any migration step.

**Negative**

- The repository's own `.rhiza/template.yml` still uses the old keys because the
  self-managed template has not been updated to write the new keys during sync. Until
  that sync happens, the file is technically in legacy format even though it is read
  correctly.
- Two accepted key names for the same field can cause confusion when reading raw YAML
  files; contributors may not know which form is preferred without consulting this ADR
  or the model docstring.
