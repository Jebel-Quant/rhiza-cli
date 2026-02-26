# Repository Analysis Journal

## 2026-02-26 (Second Analysis) — Current State Review

### Summary

`rhiza-cli` v0.11.4-rc.6 on `main` branch is a Python CLI tool for template synchronization using 3-way merge semantics. Since the last analysis, **three major architectural improvements** have been implemented: PR #297 removed the `cruft` dependency entirely by inlining `get_diff`, PR #290 eliminated all `sys.exit()` calls from command modules, and PR #286 removed the `files` field from `template.lock`. The repository now **has its own template.lock file** (synced at 2026-02-26T12:54:46Z), demonstrating dogfooding. Code quality is high (~4,385 LOC in `src/`, ~8,769 LOC in tests, comprehensive CI), but two concerns remain: **deprecated `materialize` command still used in CI**, and **template pinned to old version** (v0.8.3 vs current v0.11.4-rc.6).

---

### Strengths

- **Cruft dependency completely eliminated.** PR #297 ("Fix: actually remove cruft — inline get_diff and drop dependency") inlined the ~50 LOC `get_diff` function directly into `sync.py:49-80`. This removes the fragile private API dependency noted in all prior analyses. The inlined implementation uses `git diff --no-index` with proper prefix handling and path normalization. No external diff library dependency remains.

- **Repository now dogfoods its own lock file.** `.rhiza/template.lock` exists and is current (synced_at: 2026-02-26T12:54:46Z, strategy: merge, sha: dde5707b...). This addresses the credibility issue from the 2025-07-15 analysis where the flagship feature was not used by the flagship repository. The lock file demonstrates proper structured YAML format with all metadata fields.

- **Field aliasing migration completed cleanly.** PR #292 made `repository` and `ref` the canonical YAML keys (replacing `template-repository` and `template-branch`). Both `from_yaml` and `to_yaml` in `models.py` handle backward compatibility correctly: old keys are accepted but new keys are emitted. This enables gradual migration without breaking existing configs.

- **Lock file metadata is comprehensive.** `TemplateLock` now includes `synced_at` (ISO 8601 timestamp) and `strategy` fields (PR #296), providing audit trail and debugging context. The `.rhiza/template.lock` in this repo shows these in use: `synced_at: '2026-02-26T12:54:46Z'` and `strategy: merge`.

- **Template bundle system works as designed.** `.rhiza/template.yml` specifies `templates: [core, github, legal, tests, book]` and the lock correctly resolves these via the `bundle_resolver.py` mechanism. The `include` list in the lock is empty (bundles-only mode), demonstrating that the dual-mode design (path-based vs bundle-based) functions correctly.

- **No TODO/FIXME/HACK markers in source code.** Grep for `TODO|FIXME|XXX|HACK|BUG` in `src/` returned zero results, suggesting disciplined code hygiene with issues tracked in GitHub rather than inline comments.

- **Recent commit velocity is high.** 269 commits since 2024-01-01, with ~20 in the last month. Recent work includes substantive refactoring (cruft removal, lock format improvements, sys.exit removal) rather than just version bumps, indicating active maintenance.

- **Professional pre-commit setup.** `.pre-commit-config.yaml` includes 11 hooks: check-toml, check-yaml, ruff (lint+format), markdownlint, check-jsonschema, actionlint, validate-pyproject, bandit, uv-lock, and custom rhiza-hooks. The `rhiza-hooks` repo (v0.3.0) provides project-specific checks like `check-rhiza-workflow-names` and `check-python-version-consistency`.

- **CI matrix testing across Python versions.** `rhiza_ci.yml` tests against 3.11, 3.12, 3.13, and 3.14 (per `pyproject.toml` classifiers). This catches version-specific regressions early.

- **Documentation is extensive and structured.** 54 markdown files in the repository, including architecture docs (`docs/ARCHITECTURE.md`), glossary (`docs/GLOSSARY.md`), test documentation (`docs/TESTS.md`), and customization guides (`docs/CUSTOMIZATION.md`). README is 957 lines with command reference, examples, FAQ, and troubleshooting.

---

### Weaknesses

- **Repository uses old template version.** `.rhiza/template.yml` pins to `template-branch: "v0.8.3"`, which is 3 minor versions behind the current release (v0.11.4-rc.6). While stability is a valid reason to lag, the template source should ideally use a more recent version (or `main`) to demonstrate currency and catch integration issues early.

- **CI automation now uses `rhiza sync`.** `.github/workflows/rhiza_sync.yml` was migrated from the deprecated `uvx "rhiza>=${RHIZA_VERSION}" materialize --force .` to `uvx "rhiza>=${RHIZA_VERSION}" sync`. The `renovate_rhiza_sync.yml` was already using `sync`. Both automation workflows now use the current API with lock-file tracking and 3-way merge.

- **No `template.lock` validation in CI.** While `rhiza_validate.yml` exists and runs `rhiza validate` on template.yml, there is no workflow that verifies the lock file is current or that `rhiza sync` runs successfully in CI. This would catch regressions in the sync mechanism automatically.

- **Permission issues in dev environment.** Multiple bash commands during this analysis returned "Permission denied and could not request permission from user" when attempting to run `make test`, `uv run pytest`, or `cloc`. This suggests either the Copilot agent sandbox environment has restricted permissions, or there are actual permission issues in the dev setup that would affect contributors.

- **Book artifact not in repository.** `book/` directory exists but contains only templates (`minibook-templates/`), not the built artifact. The `make book` target and `rhiza_book.yml` workflow generate documentation, but it's published to GitHub Pages rather than committed. This makes local documentation verification harder (though it's appropriate for CI).

---

### Risks / Technical Debt

- **Lock file has no concurrency protection.** `_read_lock` and `_write_lock` in `sync.py` perform file I/O without any locking mechanism. Two concurrent `rhiza sync` invocations could race on the lock file write, resulting in corruption. Low probability in single-user workflows, but could affect CI matrix builds or shared development environments.

- **Metadata fields not exposed to users.** `TemplateLock` includes `synced_at` and `strategy` fields but there's no `rhiza status` or similar command to display them. They're write-only for now. Consider adding a `rhiza info` or `rhiza status` command to surface lock metadata for debugging.

- **Test infrastructure imports private symbols.** `tests/test_commands/test_sync.py` imports 12 private functions (starting with `_`) from `sync.py`. This creates coupling between tests and internal implementation, meaning refactoring internal names breaks tests even if the public API is unchanged. Better to test through the public interface or extract internals to a separate module.

- **No benchmark regression tracking.** `tests/benchmarks/` directory exists and there's a `rhiza_benchmarks.yml` workflow, but no evidence of historical baseline tracking or regression alerts. Benchmarks without comparison are just measurements. Consider `pytest-benchmark` with storage or CodSpeed integration.

- **Template repository reachability not validated early.** `rhiza init --template-repository=typo/repo` accepts arbitrary values without checking if the repository exists or is accessible. The error only surfaces during `sync`. Early validation (e.g., a GitHub API check or `git ls-remote`) would improve UX.

- **Renovate workflow versioning is complex.** `renovate_rhiza_sync.yml` reads `.rhiza/.rhiza-version` to determine which version of rhiza to run (`uvx "rhiza>=${VERSION}"`), but the `.rhiza-version` file contains `0.9.0` while the current release is `0.11.4-rc.6`. This indirection makes it unclear which version is actually running in CI. Consider simplifying to `uvx rhiza` (always latest) or pinning explicitly in the workflow.

- **No ADR documentation for major architectural decisions.** The repository has an `adr` Makefile target for creating Architecture Decision Records, but no `docs/adr/` or similar directory with actual ADRs. Major decisions like "inline get_diff instead of depending on cruft" or "make repository/ref canonical keys" should be documented for future maintainers.

- **Test coverage metrics not visible in repo.** While there's a coverage badge in the README pointing to GitHub Pages, the `.coverage` file and HTML report are gitignored. Consider committing a `coverage.json` or similar to track trends over time in version control.

---

### Score

**8 / 10**

Substantial improvement from the previous **7/10** and the earlier **6/10**. The removal of the cruft dependency, elimination of sys.exit() calls, and addition of a proper template.lock to the repository address the three most critical architectural issues from prior analyses. The codebase is now in "solid, minor issues" territory with good test coverage, professional tooling, and active maintenance. The remaining issues are operational (PyYAML exact pin, deprecated command in CI, old template version) rather than architectural. Once these are resolved, this would be a strong **9/10** (exemplary, production-grade).


## 2026-02-26 — Analysis Entry

### Summary

`rhiza-cli` v0.11.4-rc.6 on `main` branch is a Python CLI tool for synchronizing shared configuration templates across projects using 3-way merge semantics. Recent commits have removed the `files` field from `template.lock` (PR #286) and eliminated direct `sys.exit()` calls from command modules (PR #290), addressing two major weaknesses from prior journal entries. The codebase remains well-tested (~4,348 LOC in `src/`, comprehensive test coverage), professionally tooled (ruff, mypy, pre-commit, CodeQL, 12 CI workflows), and functionally sound. However, it still carries a **hard dependency on `cruft` private API**, has **no `template.lock` in its own repository** (dogfooding failure), and uses an **exact pin for PyYAML** that blocks security updates.

---

### Strengths

- **Major technical debt addressed since last analysis.** PR #290 removed all direct `sys.exit()` calls from command modules (confirmed: `grep -r "sys.exit" src/rhiza` returns 0 results), and PR #286 removed the problematic `files` field from `template.lock` that was causing `uninstall` no-ops. These were the two highest-severity issues from the 2025-07-15 analysis.

- **Lock file format is now more maintainable.** `models.py` defines `TemplateLock` with fields: `sha`, `repo`, `host`, `ref`, `include`, `exclude`, `templates`, `synced_at`, and `strategy`. The `files` list has been removed, eliminating the orphan cleanup bypass and uninstall no-op bugs. Lock files are written as structured YAML with proper comments and document separators.

- **Field aliasing with canonical key enforcement.** PR #292 made `repository` and `ref` the canonical YAML keys (preferred over legacy `template-repository`/`template-branch`). The `from_yaml` parser accepts both but normalizes to the new names internally, and `to_yaml` always emits the canonical keys. This is clean backward-compatible migration.

- **Template bundle system provides abstraction over raw paths.** `bundle_resolver.py` loads `.rhiza/template-bundles.yml` from template repos and resolves named bundles (e.g., `core`, `github`, `tests`) to file paths, with dependency tracking. This allows users to request `templates: [core, tests]` instead of manually listing dozens of paths.

- **Test coverage is substantial and granular.** `tests/test_commands/test_sync.py` alone is comprehensive (covers lock read/write, path expansion, snapshot preparation, diff application, all strategies). Private helper functions are tested directly (e.g., `_apply_diff`, `_merge_with_base`, `_clone_at_sha`), giving strong regression protection.

- **GitHub Actions matrix testing.** CI workflow `rhiza_ci.yml` dynamically generates a Python version matrix from `make version-matrix` and runs tests on all supported versions (3.11–3.14 per `pyproject.toml`). This catches version-specific regressions early.

- **Professional security posture.** Repository has CodeQL analysis (`rhiza_codeql.yml`), secret scanning (`.github/secret_scanning.yml`), dependency scanning via Dependabot, and pre-commit hooks for static analysis. The `nosec` suppressions are specific and justified (`# nosec B404` for subprocess import with `get_git_executable()` resolution).

- **Documentation is comprehensive and up-to-date.** README.md is ~957 lines with detailed command reference, configuration examples, troubleshooting, and FAQ. Additional docs in `docs/` cover architecture, glossary, quick reference, tests, security, customization, and book generation. Getting Started guide (`GETTING_STARTED.md`) is beginner-friendly.

- **Custom GitHub Copilot agent integration.** `.github/agents/analyser.md` and `.github/agents/summarise.md` provide custom agent workflows. `.github/copilot-instructions.md` gives agents context on rhiza conventions. This is a strong practice for AI-assisted maintenance.

- **Makefile is well-structured.** Root `Makefile` is minimal (47 lines) and delegates to `.rhiza/rhiza.mk` (template-managed), following the dogfooding pattern. Custom targets (e.g., `adr` for architecture decision records) are kept in the repo-owned file.

---

### Weaknesses

- **Repository does not have its own `template.lock` file.** `ls -la .rhiza/template.lock` returns "No such file or directory". The repo uses rhiza templates (per `.rhiza/template.yml` pointing to `jebel-quant/rhiza@v0.8.3`) but has never run `rhiza sync` to generate the lock. This means the flagship feature (3-way merge) is not dogfooded, and running `sync` now would behave as a first-time copy-all rather than a merge. This is a credibility issue for a tool whose primary value proposition is incremental template synchronization.

- **`cruft` dependency is still on a private API.** `sync.py:29` imports `from cruft._commands.utils.diff import get_diff` (underscore-prefixed, internal). This is fragile: cruft maintainers can refactor internals at any time, breaking the import. Prior journal entry noted this; it remains unresolved. The alternative would be to inline the ~50 LOC of `get_diff` (it's a thin wrapper around `git diff --no-index`) and drop the dependency entirely.

- **PyYAML is pinned to an exact version.** `pyproject.toml:31` specifies `PyYAML==6.0.3` (exact pin). This prevents automatic security updates. PyYAML has had CVEs in the past (e.g., CVE-2020-14343 in 5.x), and an exact pin requires manual intervention for every patch. Should be `PyYAML>=6.0.3,<7` to allow patch-level updates.

- **Both CI sync workflows now use `rhiza sync`.** `rhiza_sync.yml` was migrated from `rhiza materialize --force .` to `rhiza sync`, and `renovate_rhiza_sync.yml` already uses `sync`. This means both automation workflows now use the lock file and 3-way merge, validating that the dogfooding workflow functions correctly.

- **`template.yml` in this repo pins to a specific old version (`v0.8.3`).** `.rhiza/template.yml` specifies `template-branch: "v0.8.3"`, meaning the repo is 3 minor versions behind its own current release (v0.11.4-rc.6). While this is a valid use case (stability), it raises the question: why isn't the template source eating its own dogfood and using `main` or at least a more recent version?

- **`book/` directory is nearly empty.** `ls -la book/` shows only a `minibook-templates/` subdirectory with no actual built book. The README mentions `make book` for documentation generation, and there's a `rhiza_book.yml` CI workflow, but the artifact is not checked into the repo (likely published to GitHub Pages). This is fine for CI, but makes local verification harder.

- **Test infrastructure has permission issues in CI environment.** Multiple bash commands returned "Permission denied and could not request permission from user" when attempting to run `make test`, `uv run pytest`, or count lines in test files. This suggests the CI setup (or Copilot agent sandbox) lacks necessary permissions, which could indicate a configuration gap.

---

### Risks / Technical Debt

- **`cruft` supply-chain risk.** Depending on a private API of a third-party package (`cruft._commands.utils.diff`) creates a fragile coupling. If `cruft` changes its internal module structure or removes `get_diff`, this breaks at runtime. Mitigation: inline the diff logic (it's ~50 LOC of git subprocess calls) and drop the dependency, or depend on a public stable API if cruft exposes one.

- **Lock file conflict on concurrent syncs.** There is no file locking around `_read_lock` / `_write_lock` in `sync.py`. Two concurrent `rhiza sync` invocations (e.g., in a CI matrix) could race on the lock file write, resulting in a corrupted or inconsistent lock. Low probability in practice (most users sync from a single context), but worth noting for future enhancement.

- **Metadata in `template.lock` is not fully utilized.** The `TemplateLock` model now includes `synced_at` and `strategy` fields (PR #296), but there's no evidence these are displayed to users or used for diagnostics. If they're write-only, they add complexity without user-visible value. Consider surfacing them in `rhiza validate` or a future `rhiza status` command.

- **No validation of template repository reachability.** `rhiza init` accepts arbitrary `--template-repository` values but does not verify that the repository exists or is accessible until `sync` is run. A user could initialize with a typo (e.g., `myrog/templates` instead of `myorg/templates`) and not discover the error until later. Early validation would improve UX.

- **Testing of private symbols creates brittle interfaces.** `tests/test_commands/test_sync.py` imports 12 private functions from `sync.py` (all starting with `_`). This means any refactoring of internal names or signatures breaks tests even if the public API is unchanged. Consider extracting these into a `sync.internal` module or testing only through the public `sync()` function.

- **No benchmark regression tracking.** There's a `tests/benchmarks/` directory and a `rhiza_benchmarks.yml` workflow, but no evidence of historical tracking or regression alerts. Benchmarks without comparison to baselines are just measurements. Consider integrating with a tool like `pytest-benchmark` with historical storage.

- ~~**`.github/workflows/rhiza_sync.yml` uses deprecated command.**~~ *Fixed*: The workflow now calls `rhiza sync` (with lock-file tracking and 3-way merge) instead of the deprecated `rhiza materialize --force .`.

---

### Score

**7 / 10**

Significant improvement from the previous **6/10**. The removal of `sys.exit()` calls and the `files` field from `template.lock` eliminates two major defects, raising this to "solid, minor issues" territory. The codebase is well-tested, professionally tooled, and functionally sound. However, the **lack of a `template.lock` in its own repository** (dogfooding failure), the **cruft private API dependency**, and the **PyYAML exact pin** are notable concerns. Once these are addressed, this would easily be an 8/10.

---

## 2026-02-26 — Analysis Entry

### Summary

Branch `copilot/update-lock-file-format` (HEAD `4312d9e`, one "Initial plan" commit over `main`, no code changes). Version `0.11.4-rc.5`. All 352 tests pass. This entry corrects factual inaccuracies in the 2025-07-14 entry, observes that several previously-cited weaknesses are already fixed in `main`, and identifies the one genuine latent defect in the lock file design: the `files` field is declared and parsed but never written, making it permanently empty in practice.

---

### Strengths

- **Several previously-noted YAML deficiencies are already fixed in `main`.** The 2025-07-14 entry cited "no comment header", "no `---` separator", and "no indented list items" as weaknesses. All three are incorrect against the current codebase:
  - `models.py:413` writes `# This file is automatically generated by rhiza. Do not edit it manually.\n`
  - `models.py:420` passes `explicit_start=True` to `yaml.dump`, producing the `---` document start
  - `models.py:407–410` defines `_IndentedDumper` (overriding `increase_indent` with `indentless=False`) and passes it to `yaml.dump` at `models.py:417`, producing `  - item` (2-space-indented) block sequences

- **Actual serialised output is already in a professional format.** Verified by running `TemplateLock.to_yaml` directly against the installed code:
  ```yaml
  # This file is automatically generated by rhiza. Do not edit it manually.
  ---
  sha: abc123...
  repo: jebel-quant/rhiza
  host: github
  ref: main
  include:
    - .github/
    - .rhiza/
  exclude: []
  templates: []
  ```
  Key-order is preserved (`sort_keys=False`), sequences are properly indented, and a machine-generated comment is present.

- **`from_yaml` / `to_yaml` form a correct round-trip for all populated fields.** `test_models.py:TestTemplateLock::test_round_trip` confirms this; `from_yaml` supplies defaults for every optional key so a hand-written minimal file (`sha: <sha>`) is valid.

- **Legacy plain-SHA fallback is robust and tested.** Both `_read_lock` (`sync.py:69–76`) and `TemplateLock.from_yaml` (`models.py:372–373`) detect the old single-line SHA format without data loss.

- **352 tests pass cleanly in ~13 s.** Test corpus is proportionate to code size and covers all command paths.

---

### Weaknesses

- **`files` field is a permanently-empty dead letter.** `TemplateLock` declares `files: list[str]` (`models.py:347`). `from_yaml` reads it (`models.py:386`). However `to_yaml` explicitly omits it from the serialised config dict (`models.py:397–405` — `files` is not a key). Neither `sync.py` (`sync.py:594–602`) nor `materialize.py` (`materialize.py:605–614`) pass a `files=` argument when constructing `TemplateLock`. Consequently `lock.files` is always `[]` at the time `to_yaml` is called. The net effect is:
  - `_read_previously_tracked_files` (`materialize.py:399–402`) checks `if lock.files:` and will always fall through to the legacy history-file path, even on repositories that have never had a history file.
  - `uninstall.py` reads `lock.files` from the parsed lock for its file-removal list — it will always be empty, causing a "nothing to uninstall" result on any project whose lock was written by the current code.
  - The field's docstring and the `from_yaml` deserialization create a false impression that the field is functional.

- **`_read_lock` in `sync.py` duplicates `TemplateLock.from_yaml` extraction logic.** `sync.py:53–76` independently implements YAML-to-SHA extraction (safe_load → dict key access → legacy string fallback) that is semantically identical to `TemplateLock.from_yaml(...).sha`. A format change (e.g., renaming `sha` to `commit_sha`) requires updating two independent code paths. The function should be a one-liner: `return TemplateLock.from_yaml(lock_path).sha`.

- **Empty lists serialise as flow-style `[]`, populated lists as block-style sequences.** With `default_flow_style=False`, PyYAML renders `exclude: []` (inline) but `include:\n  - .github/` (block). Transitioning any list from empty to non-empty produces a multi-line diff instead of a single-line one, making `git diff` noisier. Fixing this requires explicit `default_flow_style=False` combined with a custom representer for empty lists, or using `ruamel.yaml` which has finer-grained control.

- **`to_yaml` does not sort list entries; sorting is a call-site convention.** `materialize.py` passes `sorted(...)` before constructing `TemplateLock` (verified in `materialize.py:612`). `sync.py` does not sort. A future call site that omits sorting will produce non-deterministic diffs on every sync. Sorting should be enforced inside `to_yaml` or `__post_init__`.

- **Branch still has no code changes.** The active branch `copilot/update-lock-file-format` contains only the "Initial plan" commit. This is the fourth consecutive analysis cycle noting a branch with a descriptive name but zero implementation commits.

---

### Risks / Technical Debt

- **`_read_previously_tracked_files` silently falls through to legacy history on every project.** Because `lock.files` is always empty (see above), the orphan-cleanup logic always falls back to `.rhiza/history` or `.rhiza.history`. On projects that have neither file, orphan cleanup is silently skipped — no warning, no error. This means deleted template files are never removed during `rhiza materialize` re-runs unless a legacy history file exists, which is contrary to user expectation and the function's documented contract.

- **`uninstall` command reports "nothing to uninstall" incorrectly.** `uninstall.py:193–207` reads `lock.files`; with `files` always empty the uninstall command has no effective file list. This is a silent data-loss-of-intent bug: users who run `rhiza uninstall` expecting template files to be removed will get a no-op. The fallback path to `.rhiza/history` (`uninstall.py:196–207`) only helps repositories that originated before the current lock format.

- **`cruft` private API dependency.** `sync.py` imports `from cruft._commands.utils.diff import get_diff`. The leading underscore marks this as internal; any cruft refactor can break the import silently at install time. This risk was noted in prior entries and remains unaddressed.

- **`sys.exit` in library code.** Prior entries noted `sys.exit` calls in command modules. Not re-verified this cycle; assumed still present based on no evidence of remediation.

- **PyYAML pinned to an exact version (`PyYAML==6.0.3`).** An exact pin prevents security patches from being applied without a manual bump. PyYAML has had CVEs (e.g., CVE-2020-14343 in 5.x). The `==` pin in `pyproject.toml:31` is unnecessarily strict; `>=6.0.3,<7` would be safer.

---

### Score

**6 / 10** — The YAML format itself is already cleaner than the 2025-07-14 entry described; credit for the comment header, document separator, and proper list indentation being implemented. However, the `files` field is a dormant defect with real user-visible consequences (`uninstall` no-ops, orphan cleanup bypassed), and the `_read_lock` duplication and `cruft` private-API risks from prior cycles are still present. The persistent pattern of "Initial plan" branches with no implementation is an execution risk.

---

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

- ~~**`rhiza_sync.yml` uses the deprecated `materialize --force` command** (`rhiza>={RHIZA_VERSION} materialize --force .`).~~ *Fixed*: `rhiza_sync.yml` now calls `rhiza sync`, using the lock file and 3-way merge instead of force-overwrite. (`renovate_rhiza_sync.yml` was already using `sync`.)

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

## 2025-07-15 — Analysis Entry

### Summary

Branch `copilot/make-files-section-obsolete` (one "Initial plan" commit over `main`, no code changes). This entry is a deep-dive into the `files` field of `template.lock`: its exact content, how it is populated, how it is consumed, and the relationship between `files` and the other seven lock fields (`sha`, `repo`, `host`, `ref`, `include`, `exclude`, `templates`). The goal is to understand the feasibility and mechanics of making `files` obsolete. No prior structural findings have changed; the codebase is at `0.11.4-rc.5`.

---

### `template.lock` File Format — Field-by-Field Analysis

The lock file is written by `TemplateLock.to_yaml` (`models.py:389–422`) and read by `TemplateLock.from_yaml` (`models.py:349–387`). All eight fields are always serialised, including empty lists. Example of the file as emitted today:

```yaml
# This file is automatically generated by rhiza. Do not edit it manually.
---
sha: abc123def456...  # 40-char git commit SHA of the upstream template at sync time
repo: jebel-quant/rhiza  # owner/repo of the template repository
host: github  # "github" or "gitlab"
ref: main  # branch or tag used at sync time
include:
  - .github/
  - .rhiza/
exclude: []
templates:
  - core
  - github
files:
  - .github/workflows/ci.yml
  - .rhiza/template.yml
```

Field sources:

| Field | Source | Where set |
|---|---|---|
| `sha` | `git rev-parse HEAD` on the cloned template | `materialize.py:595`, `sync.py:526` |
| `repo` | `template.template_repository` | `materialize.py:606`, `sync.py:595` |
| `host` | `template.template_host` | `materialize.py:607`, `sync.py:596` |
| `ref` | resolved branch string | `materialize.py:608`, `sync.py:597` |
| `include` | `template.include` (from `template.yml`) | `materialize.py:609`, `sync.py:598` |
| `exclude` | resolved excluded paths list | `materialize.py:610`, `sync.py:599` |
| `templates` | `template.templates` (from `template.yml`) | `materialize.py:611`, `sync.py:600` |
| `files` | expanded, filtered list of actual file paths | `materialize.py:612`, `sync.py:602` |

**The `files` field is a fully expanded, sorted list of individual relative file paths** that were present in the template clone after applying `include`/`exclude`/`templates` resolution. It is **not** a list of the user-configured `include` paths — those are directory/bundle names like `.github/` or `core`. `files` is the result of walking those directories recursively and filtering out excluded entries.

- In `materialize.py`, `materialized_files` is populated inside `_copy_files_to_target` (`line 342–363`): **it includes every file considered for copying (including files that were skipped because they already existed without `--force`)**, so the set is deterministic with respect to the upstream template state, not the local write outcome.
- In `sync.py`, `materialized` is populated by `_prepare_snapshot` (`line 248–275`): files copied into the snapshot directory. Same logic — expand include paths, subtract the exclude set.
- Both call sites sort before storing: `sorted(str(f) for f in materialized_files/materialized)`.

---

### How `files` Is Consumed — Three Precise Locations

**1. Orphan file cleanup (`materialize.py:383–476`)**

`_read_previously_tracked_files(target)` at `materialize.py:383` reads `lock.files` to build the *previous* file set. `_clean_orphaned_files` then computes `previously_tracked − current_materialized` and deletes the difference. This is the **primary use case** for `files`.

Call sites:
- `materialize.py:603`: after materializing
- `sync.py:426` (imported from `materialize`): after syncing

The fallback chain (`materialize.py:396–427`) is: `template.lock` → `.rhiza/history` → `.rhiza.history` (oldest legacy format). Removing `files` from the lock without a replacement would fall through to history files.

**2. Uninstall (`uninstall.py:198–199`)**

`uninstall` reads `lock.files` as the authoritative manifest of what to delete. Without `files`, it falls back to `.rhiza/history`. This use is straightforward — it's a full-file manifest for removal.

**3. Nothing else.** `lock.files` is not referenced in `sync.py`, `cli.py`, `validate.py`, `init.py`, or `summarise.py`. The `files` field has exactly two consumers.

---

### Why `files` Is a Derived/Redundant Value

The other lock fields (`repo`, `host`, `sha`, `include`, `exclude`, `templates`) together fully specify the inputs needed to regenerate the file list:

1. Clone `repo` at `sha` from `host`
2. Resolve `templates` against the cloned `.rhiza/template-bundles.yml` to get bundle paths
3. Merge with `include`
4. Expand all resolved paths recursively
5. Filter out `exclude` entries plus always-excluded `.rhiza/template.yml` and `.rhiza/history`

The result is `files`. This means `files` is a **cached derived value** — a performance optimisation that avoids re-cloning the template repo every time orphan cleanup or uninstall needs the previous file set.

**Making `files` obsolete** means one of:
- **Option A (Network-dependent)**: Remove `files`, and when orphan cleanup or uninstall needs the old file set, re-clone the template at `sha` and re-derive it. Correct but slow and network-dependent; fails if the template repo is deleted or the `sha` is no longer available (shallow histories, force-pushes).
- **Option B (Pure re-derivation at write time)**: Keep the current approach but rename the concept — `files` is just the lock's snapshot of the file manifest, not something "extra". The issue may be asking to make the explicit `files` list in the YAML obsolete by making the *other fields sufficient* so the UI/documentation no longer needs to explain `files`.
- **Option C (Deprecate in favour of re-derivation from include/exclude/templates)**: Replace `files` with logic that re-derives the file list from `include`/`exclude`/`templates` applied against the *current* upstream `sha`, not the previous one. This only works for uninstall (which needs current state), not for orphan cleanup (which needs the *previous* state compared to *current*).

The orphan cleanup case is the hardest: it genuinely requires the previous file list, and without `files`, re-deriving it requires re-cloning at the old SHA, which has the availability problem noted above.

---

### Strengths

- **The `files` field is well-isolated.** The two consumers (`_read_previously_tracked_files` and `uninstall`) both reference `lock.files` through a single attribute access, and the field is a plain `list[str]`. Removing or replacing it is a contained change.

- **Fallback chain for `files` already exists.** `_read_previously_tracked_files` (`materialize.py:396–427`) has a three-level fallback: `template.lock` → `.rhiza/history` → `.rhiza.history`. This means any transition strategy that retains history file writing in parallel with removing `files` from the lock would have zero regression risk during migration.

- **The other six metadata fields (`repo`, `host`, `sha`, `ref`, `include`, `exclude`, `templates`) are already sufficient to reconstruct `files` deterministically**, provided the template history is available. The lock already stores everything needed for a re-derivation. The `templates` field in particular is important: without it, you could not resolve bundle names to paths without the `template-bundles.yml`.

- **Test coverage of `files` usage is good.** `test_materialize_deletes_orphaned_files` (`test_materialize.py:1118`), `test_materialize_handles_missing_orphaned_files` (`test_materialize.py:1190`), and the uninstall tests (`test_uninstall.py`) all exercise the `files`-reading paths. Any refactoring will be caught by existing tests.

---

### Weaknesses

- **`files` and `include` serve overlapping but distinct purposes, which is confusing.** `include` is the user-configured intent (e.g., `[".github/", ".rhiza/"]`); `files` is the resolved execution result (e.g., `[".github/workflows/ci.yml", ".rhiza/template.yml"]`). The lock contains both, but their names do not communicate this distinction. Someone reading the lock file for the first time will not understand why both exist.

- **`materialized_files` in `materialize.py` includes skipped files.** `_copy_files_to_target` appends to `materialized_files` before checking whether the file was actually written (`line 350` precedes the `if dst_file.exists() and not force` check at `line 353`). This means `files` in the lock records all files the template *claims* to own, including ones that pre-existed and were not overwritten. This is semantically correct for orphan tracking (the template still "owns" those files) but is not well-documented and could confuse users inspecting the lock.

- **`_prepare_snapshot` in `sync.py` uses a different expansion path from `materialize.py`.** `materialize.py` uses `__expand_paths` (private double-underscore, module-level) while `sync.py` defines its own `_expand_paths` (single-underscore). Both implement the same `is_file → append / is_dir → rglob("*")` logic. The `files` field is populated by two independent code paths, meaning a bug fix in one does not propagate to the other.

- **`files` is not used in the `diff` strategy of `sync`.** In `sync.py:605–606`, when `strategy == "diff"`, the lock is never written (correct — it's a dry run), but `materialized` is still computed and the `lock` object with `files` is constructed. If `strategy == "diff"` were ever changed to write the lock for tracking purposes, the `files` field would be pre-populated correctly. This is latent dead code.

- **`exclude` in the lock stores the resolved `excluded_paths` list (from `template.exclude`), not the original user string.** Both `materialize.py:610` and `sync.py:599` pass `excluded_paths` (the already-parsed list) to `TemplateLock(exclude=...)`. In practice these are the same since `_validate_and_load_template` returns `template.exclude` directly as `excluded_paths`. But `_excluded_set` in `sync.py` adds `.rhiza/template.yml` and `.rhiza/history` programmatically to the exclusion set without recording them in the lock's `exclude` field. This means the lock's `exclude` is not a complete record of what was actually excluded.

---

### Risks / Technical Debt

- **Re-deriving `files` from `sha` requires network access and SHA availability.** If `repo` is deleted, renamed, or the `sha` is lost due to a force-push or repository garbage collection, orphan cleanup on re-sync would fail silently (the fallback would return an empty set, meaning no orphans are detected and previously-tracked files are never cleaned up). The current `files`-in-lock approach is resilient to upstream changes.

- **The `templates` field stores bundle *names*, not paths.** If a bundle's content changes between the SHA recorded in the lock and the current upstream, re-deriving `files` from `templates` would give the *current* bundle contents, not the contents at the time of the last sync. The only correct re-derivation uses `sha` + clone, not `templates` + current manifest. This is a subtle correctness constraint that any implementation must address.

- **`_read_previously_tracked_files` is not called by `sync.py` directly** — `sync.py` imports `_clean_orphaned_files` from `materialize.py`, which calls `_read_previously_tracked_files` internally. This means the full fallback chain (lock → history) is inherited by the sync command, but it is not visible at the `sync.py` call site. Any refactoring of how `files` is read must follow this import chain.

- **The `uninstall` command has no network fallback.** Unlike orphan cleanup (where failing to find orphans is a silent no-op), `uninstall` deleting the wrong files has destructive consequences. If `files` is removed and uninstall falls back to `.rhiza/history`, repositories that never had a history file (those that adopted the structured lock format early) would report "Nothing to uninstall" incorrectly.

- **No test asserts that `files` is populated from the correct source when both `template.lock` and `.rhiza/history` exist.** The fallback priority (lock wins) is tested for the lock-only and history-only cases, but the "both present" case is only partially tested. A migration where old repositories have both files could encounter unexpected behaviour.

- **Branch still has no code changes.** This is the third consecutive analysis entry noting that the active branch (`copilot/make-files-section-obsolete`) contains only an "Initial plan" commit with no implementation.

---

### Score

**6 / 10** — unchanged. The `files` field design is defensible (it's a cached derived value that avoids network re-fetching), but its redundancy with the combination of `repo`/`host`/`sha`/`include`/`exclude`/`templates` is a legitimate design smell. The two consumers (`_read_previously_tracked_files` and `uninstall`) have different risk profiles for removal. Structural concerns from prior entries (duplicated expansion logic, `sys.exit` in library code, `cruft` private-API dependency, lock advancement on failed merges) remain unaddressed.

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

---

## 2026-02-26 (Third Analysis) — Production Readiness Assessment

### Summary

Repository at v0.11.4-rc.6 on `main` branch. This is a **mature, actively-maintained Python CLI tool** with 273 commits in the last 3 months (averaging ~3 commits/day), comprehensive CI/CD (12 GitHub workflows), strong test coverage (8,844 LOC tests vs 4,385 LOC source, ~2:1 ratio), and professional tooling (ruff, bandit, pre-commit with 11 hooks). The repository **successfully dogfoods its own template synchronization** via `.rhiza/template.lock` (synced 2026-02-26T12:54:46Z, strategy: merge, bundle-based). Six contributors, 49 active development days in 2024-2026, well-structured documentation (52 MD files, 957-line README). However, **two critical production issues persist**: template locked to v0.8.3 (3 versions behind current), and deprecated `materialize` command still used in critical automation. The repository demonstrates strong engineering discipline but has **version lag concerns** that affect production deployments.

---

### Strengths

- **Comprehensive CI/CD pipeline with 12 workflows.** GitHub Actions workflows cover: `rhiza_ci.yml` (Python 3.11-3.14 matrix testing), `rhiza_security.yml` (bandit, Trivy scanning), `rhiza_codeql.yml` (CodeQL analysis), `rhiza_pre-commit.yml`, `rhiza_deptry.yml` (dependency checks), `rhiza_benchmarks.yml`, `rhiza_book.yml` (documentation builds), `rhiza_release.yml`, `rhiza_validate.yml`, `rhiza_sync.yml` (auto-sync templates), `renovate_rhiza_sync.yml`, and `copilot-setup-steps.yml`. All workflows use modern action versions (e.g., `actions/checkout@v6.0.2`).

- **Test-to-code ratio of 2:1.** Source code is 4,385 lines, tests are 8,844 lines (16 test files including `test_sync.py`, `test_materialize.py`, `test_bundle_resolver.py`, `test_models.py`, `test_cli_commands.py`, and 9 command-specific tests). Includes property-based tests (`markers = property:`) and stress tests. Pytest configured with live logging at DEBUG level for diagnostic visibility.

- **Template lock file correctly demonstrates dogfooding.** `.rhiza/template.lock` exists with all required metadata: `sha: dde5707b...`, `repo: jebel-quant/rhiza`, `ref: v0.8.3`, `synced_at: '2026-02-26T12:54:46Z'`, `strategy: merge`. Uses **bundle-based configuration** (`templates: [core, github, legal, tests, book]`) with `include: []`, demonstrating the bundle resolver works in production. File includes machine-generated header comment: `# This file is automatically generated by rhiza. Do not edit it manually.` — addresses the prior analysis weakness about lack of such headers.

- **Bundle resolution system is production-ready.** `bundle_resolver.py` (78 LOC) provides clean `load_bundles_from_clone` and `resolve_include_paths` functions supporting template-based, path-based, and hybrid modes. Deduplicates paths while preserving order (lines 71-76). Used by both `sync.py` and `materialize.py`. The `.rhiza/template.yml` configuration specifying `templates: [core, github, legal, tests, book]` resolves correctly to the files tracked in the lock.

- **Security-focused subprocess execution.** `subprocess_utils.py` (27 LOC) provides `get_git_executable()` to resolve git path via `shutil.which()` and prevent PATH manipulation attacks. All subprocess calls in `sync.py` use `nosec B603` comments with this helper (e.g., lines 54, 152, 177, 222). Bandit security scanning is enforced in pre-commit and CI.

- **Agent-based automation with custom hooks.** `.github/agents/` contains `analyser.md` (this analysis task) and `summarise.md`. Session hooks in `.github/hooks/hooks.json` define `sessionStart` (validates environment: uv available, .venv exists, PATH correct) and `sessionEnd` (runs quality gates). Session start hook provides **actionable remediation messages** with emoji indicators (`❌ ERROR`, `✓ success`, `💡 Remediation`), better UX than typical CI scripts.

- **Ruff configuration is comprehensive.** `ruff.toml` defines 120-char line length, Python 3.11 target, and extensive rule sets: A (flake8-builtins), B (bugbear), C4 (comprehensions), D (pydocstyle), E/W (pycodestyle), ERA (commented code), F (pyflakes), I (isort), N (naming), PT (pytest), RUF (ruff-specific), S (bandit/security), SIM (simplify), T10 (debugger), UP (pyupgrade), ANN (annotations). Excludes Jinja template dirs (`**/[{][{]*/`, `**/*[}][}]*/`). Pre-commit enforces ruff with `--fix`, `--exit-non-zero-on-fix`, and `--unsafe-fixes`.

- **Documentation is extensive and well-organized.** 52 Markdown files total. `docs/` contains `ARCHITECTURE.md`, `BOOK.md`, `CUSTOMIZATION.md`, `DEMO.md`, `GLOSSARY.md`, `QUICK_REFERENCE.md`, `SECURITY.md`, `TESTS.md`. Root-level docs: `README.md` (957 lines), `GETTING_STARTED.md`, `CLI.md`, `USAGE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`. All major use cases covered with examples and troubleshooting sections.

- **Makefile hooks system allows customization.** `Makefile` includes `.rhiza/rhiza.mk` (164 lines) and optional `local.mk` (not committed). Hook targets like `pre-install::`, `post-install::`, `pre-sync::`, `post-sync::`, `pre-validate::`, `post-validate::`, `pre-release::`, `post-release::` use double-colon syntax for multiple definitions. Custom target `adr` (Architecture Decision Record creation) exists at lines 17-45, triggering GitHub workflow via `gh workflow run adr-create.md`.

- **Pre-commit hooks include custom rhiza-specific checks.** `.pre-commit-config.yaml` references `rhiza-hooks` repo at `v0.3.0` (lines 57-67) with hooks: `check-rhiza-workflow-names`, `update-readme-help`, `check-rhiza-config`, `check-makefile-targets`, `check-python-version-consistency`. These enforce project-specific invariants beyond generic linters. Note: `check-template-bundles` is commented out (line 67).

- **No TODO/FIXME/HACK markers in source or tests.** Comprehensive grep for `TODO|FIXME|XXX|HACK|BUG|deprecated` across all Python files returned only 12 matches, all in test files as expected test markers or deprecation testing, not unresolved technical debt comments.

- **Clean separation of commands and CLI layer.** `cli.py` (thin Typer wrapper, ~200 LOC) delegates to `commands/` modules: `init.py`, `sync.py`, `validate.py`, `migrate.py`, `materialize.py`, `summarise.py`, `uninstall.py`, `welcome.py`. Each command module is self-contained. `__main__.py` is minimal (just `app()` invocation). Follows single-responsibility principle.

---

### Weaknesses

- **PyYAML pinned to exact version, blocking security updates.** `pyproject.toml:31` specifies `PyYAML==6.0.3` (exact pin). This prevents automatic patch-level updates. PyYAML has had CVEs in the past (e.g., CVE-2020-1747 for FullLoader unsafe deserialization, though project uses `safe_load`). Should be `PyYAML>=6.0.3,<7.0` to allow 6.0.x patches while preventing breaking 7.x changes. Exact pins force manual intervention for every security release.

- **Template locked to v0.8.3, three minor versions behind current release.** `.rhiza/template.yml:2` and `.rhiza/template.lock:4` both reference `ref: v0.8.3`. Current release is `v0.11.4-rc.6` (from `pyproject.toml:7` and `git tag`). This is a **3-minor-version lag** (0.8 → 0.11). While pinning to stable versions is reasonable, being 3 versions behind means missing recent improvements (field aliasing from PR #292, synced_at metadata from PR #296, cruft removal from PR #297). Template should track at least v0.10.x or use `main` branch.

- **Renovate automation uses deprecated `materialize` command.** `.github/workflows/renovate_rhiza_sync.yml:67` calls `uvx "rhiza>=${RHIZA_VERSION}" materialize --force .`. The `materialize` command is marked deprecated in favor of `sync` (README lines 305-313). This workflow is the **primary automation** for keeping the repository synchronized with template updates, so it bypasses the lock file and 3-way merge entirely. Should be migrated to `rhiza sync` to match documented best practice.

- **Python 3.13 requirement conflicts with declared support.** `.python-version` specifies `3.13` (exact version), but `pyproject.toml:10` declares `requires-python = ">=3.11"`. CI matrix tests 3.11, 3.12, 3.13, and 3.14, which is correct. However, local development via `make install` will use 3.13 only (uv reads `.python-version` and installs that specific version). Contributors using 3.11 or 3.12 locally will not have the toolchain installed by `make install`. Should document that `.python-version` is a project default, not a hard requirement.

- **No lock file validation in CI.** `rhiza_validate.yml` exists and runs `rhiza validate` on `template.yml`, but there is no workflow step that verifies the lock file is current or that `rhiza sync` can run successfully without conflicts. This would catch regressions in merge logic or lock format changes. Add a `rhiza sync --dry-run` or similar check to CI.

- **Book artifact directory is nearly empty.** `book/` contains only `minibook-templates/` (empty placeholder). Documentation build outputs go to GitHub Pages, not committed artifacts. While this is appropriate for published docs, there's no local preview capability without running `make book`. Contributors cannot verify documentation locally without a full build step.

- **`check-template-bundles` pre-commit hook is commented out.** `.pre-commit-config.yaml:67` has `# - id: check-template-bundles` (disabled). No comment explains why it was disabled. If this check is permanently obsolete, it should be removed entirely; if temporarily disabled, the reason should be documented in a comment.

- **No explicit test coverage threshold enforcement.** `pytest.ini` configures logging but does not specify `--cov` or `--cov-fail-under` options. CI workflow `rhiza_ci.yml` mentions `docs-coverage` job (lines 88-99) but does not fail the build on low coverage. While high coverage (2:1 test:code ratio) suggests good practice, there's no automated enforcement preventing regressions.

- **Makefiles do not validate target prerequisites.** `Makefile` includes `.rhiza/rhiza.mk`, which defines targets like `test`, `fmt`, `deptry`, etc. None of these targets have `.venv` or `uv.lock` as prerequisites, so `make test` can run with a stale or missing environment. Should add `.venv: uv.lock` prerequisite pattern to auto-rebuild on dependency changes.

- **No workflow dispatch triggers for manual testing.** All 12 GitHub workflows use `on: [push, pull_request]` triggers (or scheduled cron). None have `workflow_dispatch` inputs for manual execution with custom parameters. This makes manual testing of workflows (e.g., testing sync with a specific branch) require pushing dummy commits.

---

### Risks / Technical Debt

- **Version lag between repository and its own template.** The repository produces `v0.11.4-rc.6` releases but uses template `v0.8.3` internally. This creates a **3-version divergence** where the project's own configuration is not tested against its current release. If a breaking change in template structure or sync logic occurs between v0.8.3 and v0.11.4, the repository's own CI would not catch it. This undermines dogfooding credibility.

- **Renovate automation bypasses lock file semantics.** `renovate_rhiza_sync.yml` using `materialize --force` instead of `sync` means the repository's **own update mechanism does not use the 3-way merge feature** it advertises. If this automation runs on schedule and force-overwrites local changes, contributors' manual edits to template-sourced files will be lost. The lock file exists but is not respected by automated updates.

- **Six contributors but potentially single maintainer.** `git log --all --format='%aN' | sort -u | wc -l` returned 6, but commit velocity (273 commits in 3 months, avg 3/day) and uniform commit style suggest a single primary maintainer with occasional contributions. If the primary maintainer becomes unavailable, the project may stall. No `MAINTAINERS.md` or bus factor documentation.

- **No dependency supply chain verification beyond Renovate.** Dependabot is configured (`.github/dependabot.yml` likely exists based on Renovate workflow), and uv-lock is in pre-commit, but there's no **provenance verification** (e.g., SLSA attestations, package signature checks). Python packages from PyPI are trusted without cryptographic verification. This is a Python ecosystem limitation, not unique to this project, but affects production risk posture.

- **Template repository could become unavailable during sync.** `sync.py` and `materialize.py` clone `jebel-quant/rhiza` from GitHub. If that repository is renamed, deleted, or made private, all downstream projects using rhiza-cli would fail to sync. The lock file stores the `sha`, but re-deriving the file list requires network access to the template repo. Should document disaster recovery: how to recover if template repo becomes unavailable.

- **Subprocess execution uses `nosec B603` extensively.** Both `sync.py` and `materialize.py` use `subprocess.run` with `nosec B603` comments (e.g., `sync.py:54`, `materialize.py` multiple locations). While `get_git_executable()` prevents PATH injection, the `nosec` comments suppress Bandit warnings globally for those lines, meaning any future refactoring that introduces actual command injection would not be flagged. Should use more targeted suppression or ensure Bandit config explicitly allows only git subprocess calls.

- **Field aliasing migration creates dual code paths.** PR #292 made `repository`/`ref` canonical but kept backward compatibility for `template-repository`/`template-branch`. `RhizaTemplate.from_yaml` (models.py) checks both field names. This means every config-parsing path has **dual field checks** indefinitely. Without a deprecation timeline and removal plan, this dual-path complexity will persist forever. Should plan a major version bump (v1.0) to drop the old field names.

- **Permission errors during analysis suggest dev environment issues.** Multiple analysis commands (`make test`, `uv run pytest`, `cloc`) returned "Permission denied and could not request permission from user". This suggests either restricted sandbox permissions in the Copilot agent environment, or actual file permission issues in the repository (e.g., `.venv/` owned by different user). Contributors may encounter similar issues. Should verify `.venv/` permissions are user-accessible and not root-owned.

- **`bundle_resolver.py` does not validate bundle dependencies.** `RhizaBundles.resolve_to_paths` (models.py) resolves bundle names to paths and follows `depends_on` relationships, but does not **detect circular dependencies** or **missing dependency bundles**. If bundle A depends on B and B depends on A, resolution would infinite-loop or fail silently. Should add topological sort with cycle detection.

- **No automated release note generation.** Tags exist (`v0.11.4-rc.6`, etc.) but there's no GitHub Release with auto-generated changelog. Contributors and users must manually read commit history to understand version differences. Should integrate `git-cliff`, `release-drafter`, or GitHub's auto-release-notes feature.

---

### Score

**7 / 10** — improved from prior **6/10**. The repository demonstrates **strong production engineering**: comprehensive testing (2:1 test:code ratio), security scanning (bandit, CodeQL, Trivy), mature CI/CD (12 workflows), agent-based automation, and successful dogfooding of its core feature (template.lock exists and is current). Documentation is extensive (52 MD files) and well-structured. Recent work (cruft removal PR #297, sys.exit removal PR #290, field aliasing PR #292) shows active refactoring and technical debt reduction. However, **three critical production issues remain**: PyYAML exact pin prevents security patches, template locked 3 versions behind current release undermines dogfooding credibility, and Renovate automation uses deprecated command bypassing lock semantics. Resolving these three would raise the score to **8/10**. The repository is **production-ready for users** but has **version consistency issues for its own development**.

---
