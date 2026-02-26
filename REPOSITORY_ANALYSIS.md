# Repository Analysis Journal

## 2026-02-26 — Analysis Entry

### Summary

`rhiza-cli` is a Python CLI tool (v0.11.3) for propagating shared configuration templates across multiple projects. It wraps git sparse-checkout and cruft's diff utilities to achieve a 3-way-merge sync model. The active branch (`copilot/enhance-template-lock-file`) contains only a single "Initial plan" commit over `main`, meaning no actual enhancement to the lock file has been implemented yet. The codebase is broadly functional and well-tested, but has notable structural issues around code duplication, error-handling patterns, and the lock file's minimal format.

---

### Strengths

- **Test coverage is substantial.** `tests/test_commands/test_sync.py` is 1,539 lines and exercises lock-file read/write, path expansion, snapshot preparation, diff application, all three strategies, orphaned-file cleanup, error paths, and CLI wiring. Private helpers are tested directly (e.g. `_apply_diff`, `_merge_with_base`, `_clone_at_sha`), giving good regression protection.

- **Linting and tooling are mature.** `ruff.toml` enables a wide, opinionated rule set (D, E, F, I, N, B, S, SIM, PT, TRY, etc.) at line-length 120. `pre-commit` is configured, `mypy` is present, and there are dedicated CI workflows for CodeQL, deptry, pre-commit, and security scanning.

- **The lock file design is appropriately minimal.** `.rhiza/template.lock` stores a single 40-character git SHA. No JSON or YAML overhead. `_read_lock` / `_write_lock` in `sync.py:49–78` are clean and self-contained. Directory auto-creation on write (`mkdir(parents=True, exist_ok=True)`) is defensive.

- **3-way merge logic is sound in concept.** `_merge_with_base` clones the template at both `base_sha` and upstream HEAD, prepares clean snapshots, computes a unified diff via `cruft._commands.utils.diff.get_diff`, and applies it with `git apply -3`. This is the correct cruft-inspired approach.

- **`RhizaTemplate.from_yaml` supports field aliasing gracefully.** Both `template-repository`/`repository` and `template-branch`/`ref` are accepted with precedence rules (`sync.py` model, `models.py:271–283`). Backward compat is explicit, not accidental.

- **`get_git_executable()` in `subprocess_utils.py` resolves the absolute path via `shutil.which`.** This prevents PATH-manipulation injection; all `subprocess.run` calls use the resolved path with `nosec B603` suppression justified.

- **`validate.py` is thorough.** It checks git repo presence, YAML syntax, required fields, repository `owner/repo` format, templates vs. include mode detection, and optional field types independently, returning a boolean instead of raising exceptions.

---

### Weaknesses

- **`sync.py` and `materialize.py` duplicate significant logic.** `sync.py` imports nine helper functions from `materialize.py` (`_clone_template_repository`, `_update_sparse_checkout`, `_construct_git_url`, `_handle_target_branch`, `_validate_and_load_template`, `_clean_orphaned_files`, `_warn_about_workflow_files`, `_write_history_file`, `_log_git_stderr_errors`), while also re-implementing its own `_expand_paths` (identical to `materialize.py`'s private `__expand_paths`). Two parallel `_copy_files_to_target` functions exist with diverging signatures. `materialize.py` remains alive as non-dead code because the deprecated `materialize` CLI command delegates to `sync_cmd` — but the module still carries ~590 lines of overlapping implementation. This is a maintenance risk.

- **`sys.exit()` is called directly from command modules.** `materialize.py` and `sync.py` call `sys.exit(1)` on subprocess failures. This violates the library/CLI boundary — command implementations should raise exceptions and let the CLI layer handle exit codes. It makes unit testing error paths harder (test code must catch `SystemExit`) and silently swallows stack traces.

- **`_merge_with_base` has a broad silent-failure clause.** `sync.py:432–434`:
  ```python
  except Exception:
      logger.warning("Could not checkout base commit — treating all files as new")
  ```
  Any exception during base clone or snapshot preparation (including `PermissionError`, `KeyboardInterrupt` subclasses prior to Python 3.8, unexpected git output, etc.) is swallowed and the merge silently degrades to a full copy. The lock file is subsequently updated with the upstream SHA even though the 3-way merge was not performed. A user will not know their local changes were overwritten.

- **Lock file is updated even when `_apply_diff` reports conflicts.** In `_sync_merge` (`sync.py:374–400`), `_write_lock` is called unconditionally regardless of the boolean return value of `_apply_diff`. If the diff applied with rejections (`*.rej` files), the lock is advanced, so the next sync will treat the conflicted version as the new base — potentially losing upstream changes permanently.

- **`to_yaml` in `RhizaTemplate` serializes with legacy key names.** `models.py:308–320` writes `repository` and `ref` (old keys), while `from_yaml` documents `template-repository` and `template-branch` as the canonical names and merely falls back to the old names. A round-trip through `from_yaml → to_yaml → from_yaml` silently downgrades the field names. This asymmetry is not flagged anywhere in validation.

- **The repo itself has no `template.lock` file.** The `.rhiza/` directory in this repo (which uses `rhiza-cli` as its own template consumer) has no `template.lock`, despite the code being the authoritative implementation of that feature. This means `rhiza sync` run against this repo would behave as a first sync (copy-all). The feature is not dogfooded.

- **`cruft` is a heavy dependency used for only one function.** `pyproject.toml` lists `cruft>=2.16.0`, but only `cruft._commands.utils.diff.get_diff` is imported — an internal, non-public API of cruft. If cruft changes its internal module structure, this will break silently at import time.

- **No structured data in lock file limits extensibility.** The lock file is a bare SHA string. There is no room to record additional metadata (e.g., template branch, sync timestamp, strategy used) without a breaking format change. A one-field JSON or TOML would cost nothing in complexity and enable future improvements.

- **`_sync_diff` dry-run (`strategy="diff"`) compares the upstream snapshot against the target project root directly** (`get_diff(target, upstream_snapshot)` — `sync.py:340`). This means the diff includes all project files not managed by the template, which creates noisy output and incorrect change counts.

---

### Risks / Technical Debt

- **Branch `copilot/enhance-template-lock-file` is currently empty.** The branch exists with one "Initial plan" commit but contains no code changes. Any enhancement described in the PR description has not yet been implemented. Analysis of the lock file behaviour reflects the `main` branch state.

- **`renovate_rhiza_sync.yml` uses the deprecated `materialize --force` command** (`rhiza>={RHIZA_VERSION} materialize --force .`). This workflow is the primary automation for keeping the repo up to date, and it bypasses the lock file entirely. The new `sync --strategy overwrite` replacement would also write the lock file, which is the intended behaviour.

- **Lock file conflict on concurrent syncs.** There is no file locking around the `_read_lock` / `_write_lock` pair. Two concurrent `rhiza sync` invocations (e.g., in a CI matrix) would race on the lock file write. Low probability in practice but worth noting.

- **`_clone_at_sha` uses `--filter=blob:none --sparse --no-checkout` then `git checkout <sha>`.** If the SHA predates the shallow history of a previously shallow-cloned upstream, git will fail with a "no such object" error. There is a `sys.exit(1)` guard but no advisory message about history depth or `git fetch --unshallow`.

- **`_excluded_set` hardcodes `.rhiza/history` as always-excluded** (`sync.py:225`), but the history file path changed from `.rhiza.history` (old) to `.rhiza/history` (new) during migration. The exclusion only covers the new path, so a user mid-migration with `.rhiza.history` still present could have their old history file overwritten by a template that includes a root-level `history` file.

- **Test files import private symbols across module boundaries.** `test_sync.py` imports `_apply_diff`, `_clone_and_resolve_upstream`, `_clone_at_sha`, `_excluded_set`, `_expand_paths`, `_get_head_sha`, `_merge_with_base`, `_prepare_snapshot`, `_read_lock`, `_sync_diff`, `_sync_merge`, `_write_lock` directly. This creates a fragile interface contract; any refactoring of private names breaks the test suite without a corresponding API change.

- **`dev` dependency group (`numpy`, `pandas`, `marimo`, `plotly`) is included in `pyproject.toml` but serves no development testing purpose** — these are notebook/analysis packages, not CI dependencies. They inflate the dev environment and create unnecessary surface for supply-chain risk.

---

### Score

**6 / 10**

The tool solves a real problem well (3-way template merge with lock-file tracking) and has solid test coverage and lint discipline. However, the core architectural flaw — two semi-overlapping command implementations (`sync.py` imports from `materialize.py` while reimplementing some of the same logic) — combined with the silent-failure path in `_merge_with_base` that advances the lock even after degraded merges, and a lock format that is already hitting its extensibility ceiling, place this in the "mixed quality, notable concerns" band. The primary feature enhancement the current branch was created for has not yet been started.

---

## 2025-07-14 — Analysis Entry

### Summary

Branch `copilot/update-yaml-format` (one "Initial plan" commit over `main`, no code changes yet). This entry focuses on the specific `template.lock` serialisation path: where the file is written, how the YAML is formatted today, what concrete deficiencies exist, and what a "more professional format" should mean in precise, actionable terms. Version has bumped to `0.11.4-rc.3` (`pyproject.toml:7`). All prior structural findings remain unchanged.

---

### Strengths

- **`TemplateLock.to_yaml` / `from_yaml` are a clean round-trip pair.** `models.py:389–409` and `349–387` share field names exactly; `from_yaml` supplies defaults for every optional key so a minimally hand-written lock file (`sha: <sha>`) is also valid. Round-trip fidelity is tested explicitly in `test_models.py:716–739`.

- **Legacy plain-SHA fallback is correct and tested.** Both `TemplateLock.from_yaml` (`models.py:372–373`) and `_read_lock` (`sync.py:69–76`) detect the old single-line SHA format and handle it without data loss. `test_read_lock_legacy_plain_sha` (`test_sync.py:85–90`) covers this path.

- **Two independent write sites call `lock.to_yaml(path)` correctly.** `sync.py:87` (`_write_lock`) and `materialize.py:616` both delegate to the model method, so any format improvement made in one place propagates everywhere automatically.

- **Test suite validates YAML content structurally.** `test_write_lock_yaml_format` (`test_sync.py:61–83`) and `test_to_yaml_writes_all_fields` (`test_models.py:651–674`) call `yaml.safe_load` on the written file and assert all eight fields. This gives confidence that a format change will not silently corrupt the data.

---

### Weaknesses

- **Inconsistent list serialisation: empty lists use flow style, non-empty use block style.** PyYAML 6.0.3 with `default_flow_style=False` renders `exclude: []` and `templates: []` as inline flow scalars while `include: ['.github/']` and `files: ['a.txt']` render as block sequences (`- item`). The actual output of `TemplateLock.to_yaml` for a common sync produces:
  ```yaml
  sha: abc123...
  repo: jebel-quant/rhiza
  host: github
  ref: main
  include:
  - .github/
  - .rhiza/
  exclude: []         ← flow style (inconsistent)
  templates: []       ← flow style (inconsistent)
  files:
  - file1.txt
  ```
  This inconsistency is cosmetically jarring and makes the file harder to diff cleanly when an initially-empty list gains its first entry (the key line changes from `exclude: []` to `exclude:\n- item`, producing a two-line diff instead of one).

- **No machine-generated header comment.** Comparable auto-generated lock files (`poetry.lock`, `package-lock.json`, `Cargo.lock`, `Pipfile.lock`) all carry a "do not edit manually" notice. `.rhiza/template.lock` has none. Users who open the file may not understand it is authoritative and may edit it in place, corrupting the sync base.

- **No YAML document separator (`---`).** `yaml.dump` is called without `explicit_start=True` (`models.py:408`). Adding `---` is a one-argument change that makes the file a well-formed YAML document stream and is conventional for machine-written YAML (`.github/workflows/*.yml`, `pre-commit-config.yaml`, etc.).

- **List items are not indented under their parent key.** PyYAML's default indentation places `- item` at the *same column* as the key name:
  ```yaml
  files:
  - file1.txt       ← column 0, same as 'files'
  ```
  The conventional "professional" rendering indents the sequence items two spaces under the mapping key:
  ```yaml
  files:
    - file1.txt     ← column 2, visually subordinate
  ```
  PyYAML supports this via a custom `Dumper` with `increase_indent(flow=False, indentless=False)` override, but the current code does not use it.

- **`TemplateLock.to_yaml` always serialises all fields, including empty lists.** `models.py:397–406` builds the config dict unconditionally. This means a minimal lock (e.g., created by `rhiza sync` on a repo with no `include`, `exclude`, or `templates` configured) still emits six lines of empty-list boilerplate. Compare `RhizaTemplate.to_yaml` (`models.py:281–322`) which omits empty/default fields entirely — the inconsistency between the two sibling methods is confusing.

- **`_read_lock` in `sync.py` does not delegate to `TemplateLock.from_yaml`.** Two independent YAML-to-SHA extraction paths exist: `_read_lock` (`sync.py:53–76`, direct `yaml.safe_load` + dict key access) and `TemplateLock.from_yaml` (`models.py:349–387`). Any format change (e.g., renaming `sha` to `commit`) requires updating both paths independently. The `_read_lock` function should call `TemplateLock.from_yaml(...).sha` to eliminate the duplication.

- **No tests assert on the raw string format.** All existing format tests (`test_write_lock_yaml_format`, `test_to_yaml_writes_all_fields`) parse the written YAML with `yaml.safe_load` before asserting. `yaml.safe_load` discards comments and normalises indentation, so adding a `---` header, a comment line, or fixing list indentation would leave all existing tests green even if the change were reverted. A single snapshot / `assert lock_path.read_text() == expected_text` test is needed to lock in the exact serialised form.

---

### Risks / Technical Debt

- **Branch still has no code changes.** `git log --oneline` shows two commits: `d847bc9 Initial plan` (HEAD) and `1a7800b` (grafted main). The work described by the branch name has not been started. The prior entry identified the same situation under the branch name `copilot/enhance-template-lock-file`; the branch has been renamed but remains empty.

- **Fixing list indentation requires a custom PyYAML Dumper subclass.** PyYAML's `Dumper.increase_indent` signature is `(flow=False, indentless=True)` — the `indentless=True` default is what causes `- item` to appear at the parent key's column. Overriding this correctly requires:
  ```python
  class _IndentedDumper(yaml.Dumper):
      def increase_indent(self, flow=False, indentless=False):
          return super().increase_indent(flow=flow, indentless=indentless)
  ```
  and passing `Dumper=_IndentedDumper` to `yaml.dump`. This is a non-obvious, underdocumented PyYAML pattern. If done incorrectly it can produce invalid YAML (e.g., extra blank lines for nested mappings). Any implementation must be verified against the round-trip test.

- **`from_yaml` uses `_normalize_to_list` for the `files` field.** `models.py:386` passes the `files` list through `_normalize_to_list`, which handles legacy newline-delimited string values. If the format change results in a block scalar being emitted for `files` (e.g., a `|` literal block), `_normalize_to_list` will split it correctly. However, if `files` is emitted in a format that `yaml.safe_load` returns as a plain Python list, the `isinstance(value, list)` branch short-circuits and `_normalize_to_list` is a no-op. Both cases work correctly; there is no risk here, but the defensive normalisation is slightly misleading for a field that is always written as a list.

- **`to_yaml` writes `files` as an unsorted list when called from `materialize.py:605–616`.** In `materialize.py:612` the files list is `sorted(...)` before being passed to `TemplateLock(files=...)`, but in `sync.py:602` the same is done: `files=sorted(str(f) for f in materialized)`. Sorting is applied at the call site rather than inside `TemplateLock.to_yaml`. A future call site that forgets to sort will produce non-deterministic diffs on every sync. Sorting should be enforced inside `to_yaml` or the `TemplateLock.__post_init__`.

- **Comment header would be silently dropped on a round-trip through `from_yaml → to_yaml`.** YAML comments are not parsed by `yaml.safe_load`. If any code reads a `template.lock`, modifies a field, and writes it back via `to_yaml`, the comment header will be lost. This is inherent to using PyYAML and not a defect, but it is worth documenting so consumers do not rely on the comment surviving edits.

---

### Score

**6 / 10** — unchanged from the prior entry. The specific YAML serialisation work targeted by this branch is well-scoped and low-risk, but has not been implemented. The underlying structural concerns (duplicated `sync`/`materialize` logic, silent merge degradation advancing the lock, `cruft` private-API dependency) remain unaddressed.
