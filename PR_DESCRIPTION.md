# feat: Add exclude-only template mode and deprecated repository migration

## Summary

This PR introduces exclude-only template mode and improves the migration experience for users of deprecated template repositories.

## Problem

1. **Limited template flexibility**: Users could only specify files to `include`, requiring them to list every file they wanted. For repositories where you want "everything except a few files", this was cumbersome.

2. **Deprecated repository**: The original `.tschm/.config-templates` repository is deprecated in favor of `Jebel-Quant/rhiza`, but users had no guidance on migrating.

3. **Validation too strict**: In exclude-only mode, validation failed if `pyproject.toml` didn't exist locally, even though the template would provide it.

4. **Efficiency**: Full clones were used when exclusions were needed, wasting bandwidth and disk space.

## Solution

### 1. Exclude-only mode

Users can now use templates like:

```yaml
template-repository: Jebel-Quant/rhiza
template-branch: main
exclude:
  - LICENSE
  - README.md
  - .github/CODEOWNERS
```

This includes all files from the template repository **except** those listed.

### 2. Combined include/exclude

Users can also combine both for fine-grained control:

```yaml
template-repository: Jebel-Quant/rhiza
template-branch: main
include:
  - .github
exclude:
  - .github/workflows/update-readme.yml
```

### 3. Deprecated repository migration

- During `rhiza migrate`: Interactive prompt asks if user wants to switch from `.tschm/.config-templates` to `Jebel-Quant/rhiza`
- During `rhiza materialize`: Deprecation warning informs users the old repo will be removed in v1.0.0

### 4. `.rhiza` folder validation

- Warns if `.rhiza` is in the exclude list (would break rhiza functionality)
- Prompts to add `.rhiza` to include list if missing (when using include mode)

### 5. Lenient validation for exclude-only mode

When in exclude-only mode, validation is lenient about missing `pyproject.toml` **if** the template will provide it (i.e., `pyproject.toml` is not in the exclude list). This allows users to run `rhiza materialize` on a fresh repo.

| Scenario | pyproject.toml excluded? | pyproject.toml exists? | Validation |
|----------|--------------------------|------------------------|------------|
| Exclude-only | No | No | Lenient (pass) |
| Exclude-only | Yes | No | Strict (fail) |
| Exclude-only | No | Yes | Pass |
| Exclude-only | Yes | Yes | Pass |
| Include mode | n/a | No | Strict (fail) |
| Include mode | n/a | Yes | Pass |

### 6. Efficient sparse checkout

Uses Git sparse-checkout with negation patterns instead of full clone:

```
/*
!LICENSE
!README.md
```

This reduces bandwidth and disk usage for exclude-only mode.

## Changes

| File | Changes |
|------|---------|
| `pyproject.toml` | Added `questionary>=2.0.0` dependency |
| `src/rhiza/models.py` | Added helper methods: `is_exclude_only_mode()`, `is_deprecated_repository()`, `has_rhiza_folder_in_include()`, `has_rhiza_folder_in_exclude()` |
| `src/rhiza/commands/materialize.py` | Added exclude-only sparse checkout, deprecation warnings, `.rhiza` exclusion warning, lenient validation |
| `src/rhiza/commands/migrate.py` | Added deprecated repo prompt, `.rhiza` include prompt, template normalization |
| `src/rhiza/commands/validate.py` | Added `lenient` parameter to allow missing `pyproject.toml` in exclude-only mode |
| `tests/test_models.py` | Added tests for new helper methods |
| `tests/test_commands/test_materialize.py` | Added tests for exclude-only mode, deprecation warning, lenient validation edge cases |
| `tests/test_commands/test_migrate.py` | Added tests for deprecated repo and `.rhiza` prompts |
| `tests/test_commands/test_validate.py` | Added tests for exclude-only validation and lenient mode |

## Testing

```bash
make test
```

**259 tests pass** with 97% coverage.

### Edge Cases Covered

| Test | Scenario | Expected |
|------|----------|----------|
| `test_materialize_exclude_only_without_pyproject_toml` | Exclude-only, no pyproject, NOT excluded | Lenient pass |
| `test_materialize_exclude_only_with_pyproject_excluded_fails` | Exclude-only, no pyproject, IS excluded | Strict fail |
| `test_materialize_exclude_only_with_pyproject_in_repo` | Exclude-only, pyproject exists | Pass |
| `test_materialize_exclude_only_with_pyproject_excluded_but_exists_in_repo` | Exclude-only, pyproject excluded but exists | Pass |
| `test_materialize_empty_include_with_exclude_without_pyproject` | `include: []` with exclude | Lenient pass |
| `test_materialize_empty_include_with_pyproject_excluded_fails` | `include: []`, pyproject excluded | Strict fail |
| `test_materialize_include_mode_without_pyproject_fails` | Include mode, no pyproject | Strict fail |
| `test_materialize_include_with_exclude_without_pyproject_fails` | Include + exclude, no pyproject | Strict fail |

## Examples

### Before (include-only)

```yaml
template-repository: Jebel-Quant/rhiza
template-branch: main
include:
  - .github
  - Makefile
  - .pre-commit-config.yaml
  - pyproject.toml
  # ... list every file you want
```

### After (exclude-only)

```yaml
template-repository: Jebel-Quant/rhiza
template-branch: main
exclude:
  - LICENSE
  - README.md
```

### Migration prompt

```
⚠ The repository '.tschm/.config-templates' is deprecated.
? Would you like to migrate to 'Jebel-Quant/rhiza'? [Y/n]
```

## Checklist

- [x] Tests added/updated (259 passing)
- [x] All tests passing
- [x] Backwards compatible
- [x] No breaking changes
- [x] Edge cases covered for lenient validation
