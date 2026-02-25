# Repository Analysis Journal

<!-- Append new dated entries below. Do not edit previous entries. -->

## 2025-07-14 — Analysis Entry

### Summary

`rhiza-cli` is a Python 3.11+ CLI tool (published as `rhiza` on PyPI, v0.11.3) that manages "living templates" — reusable configuration files that downstream projects continuously sync from an upstream template repository. It is purpose-built to solve the problem that tools like cookiecutter and copier solve only once (one-shot generation), by keeping the template connection alive through repeatable `materialize` and `sync` commands. The current branch under review is `copilot/enhance-template-lock`, which introduces the new `sync` command with `template.lock`-based 3-way merge support (built on top of `cruft`'s diff utilities).

---

### 1. Overall Project Structure

```
rhiza-cli/
├── src/rhiza/               # Main package (src-layout via hatchling)
│   ├── cli.py               # Typer app: thin command wiring
│   ├── __main__.py          # Entry point
│   ├── models.py            # RhizaTemplate, RhizaBundles dataclasses
│   ├── bundle_resolver.py   # Bundle-to-path resolution
│   ├── subprocess_utils.py  # Git executable helper
│   ├── language_validators.py
│   └── commands/
│       ├── init.py          # rhiza init
│       ├── materialize.py   # rhiza materialize (sparse clone + copy)
│       ├── sync.py          # rhiza sync (cruft diff + 3-way merge)  ← NEW
│       ├── validate.py      # rhiza validate
│       ├── migrate.py       # rhiza migrate
│       ├── summarise.py     # rhiza summarise (PR description gen)
│       ├── uninstall.py     # rhiza uninstall
│       └── welcome.py
├── tests/                   # pytest suite (7421 lines across 15 files)
│   ├── test_commands/       # Per-command unit tests
│   ├── benchmarks/          # Performance tests
│   └── test_models.py, test_bundle_resolver.py, etc.
├── .rhiza/                  # The tool is its own downstream consumer
│   ├── template.yml         # Points to jebel-quant/rhiza@v0.8.3
│   ├── history              # Manifest of template-managed files
│   ├── make.d/              # Makefile modules auto-loaded by rhiza.mk
│   ├── requirements/        # Pinned requirement files
│   └── tests/               # Template-level tests (separate from src/tests/)
├── docs/                    # Architecture, glossary, usage, etc.
├── pyproject.toml           # hatchling build, deps: loguru, typer, PyYAML, jinja2, cruft
└── .github/workflows/       # CI, release, security, sync (template-managed)
```

The repo practices what it preaches: it is itself a consumer of its own template system (`.rhiza/template.yml` points at `jebel-quant/rhiza@v0.8.3`). This is a meaningful design signal — the tooling is dogfooded.

---

### 2. What `template.lock` Is and How It Is Currently Used

**File location:** `.rhiza/template.lock`

**Format:** A single-line plaintext file containing the full 40-character git SHA of the last successfully synced commit from the template repository. A trailing newline is written.

Example content:
```
abc123def456789...
```

**Purpose (analogous to `uv.lock` / `poetry.lock`):** Records *which exact upstream commit* the local template files were last synced against. This enables the `sync` command to compute a precise diff between `base` (last-synced state) and `upstream` (current HEAD of configured branch) — rather than blindly overwriting files.

**Lifecycle:**
| Event | Lock file behaviour |
|---|---|
| First `rhiza sync` (no lock exists) | Falls back to simple file copy; writes SHA after copy |
| Subsequent `rhiza sync` | Reads SHA → clones base at that SHA → diffs base↔upstream → applies via `git apply -3` → updates SHA |
| `rhiza sync --strategy overwrite` | Overwrites all files; updates lock |
| `rhiza sync --strategy diff` | Read-only (dry-run); does **NOT** write lock |
| `rhiza materialize` | Does **NOT** read or write lock (separate code path) |

**Code location:** `src/rhiza/commands/sync.py`, lines 48–76.

```python
LOCK_FILE = ".rhiza/template.lock"

def _read_lock(target: Path) -> str | None:
    lock_path = target / LOCK_FILE
    if not lock_path.exists():
        return None
    return lock_path.read_text(encoding="utf-8").strip()

def _write_lock(target: Path, sha: str) -> None:
    lock_path = target / LOCK_FILE
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(sha + "\n", encoding="utf-8")
```

**Early-exit optimisation:** If `_read_lock(target) == upstream_sha`, the command exits with "Already up to date" before performing any cloning. This avoids unnecessary network traffic.

**Critical gap:** `template.lock` is not mentioned in `.rhiza/history` — it is neither tracked nor excluded explicitly in the history manifest. There is no mechanism to prevent `materialize` from accidentally overwriting or deleting the lock file if a future template version includes a file at `.rhiza/template.lock`.

---

### 3. `.rhiza/history` Directory/File Usage

**File location:** `.rhiza/history` (plain text, not a directory despite the name)

**Format:**
```
# Rhiza Template History
# This file lists all files managed by the Rhiza template.
# Template repository: jebel-quant/rhiza
# Template branch: v0.8.3
#
# Files under template control:
.editorconfig
.github/actions/configure-git-auth/README.md
...
tests/benchmarks/test_benchmarks.py
```

Comment lines start with `#`. Every other non-empty line is a relative file path.

**Written by:** `materialize._write_history_file()` and `sync._write_history_file()` (re-exported from materialize).

**Read by:**
- `materialize._clean_orphaned_files()` — reads previous manifest to detect and delete files that used to be template-managed but are no longer in scope. Protected files (`.rhiza/template.yml`) are never auto-deleted.
- `uninstall` command — reads history to know what files to delete.
- `summarise` command — reads history to determine template metadata (repo, branch) for PR descriptions.

**Migration path:** The old location was `.rhiza.history` (a flat file in repo root). The `migrate` command moves it to `.rhiza/history`. `materialize._clean_orphaned_files()` checks both locations for backward compatibility, and auto-deletes the old file after migration.

**Exclusion:** Both `materialize` and `sync` explicitly exclude `.rhiza/history` from being overwritten by template content, even if the upstream template repo contains a `history` file.

---

### 4. Template Locking — Code, File Formats, Data Structures

#### Lock File (`.rhiza/template.lock`)

- **Format:** Plaintext, single SHA + newline. No YAML, no JSON, no metadata.
- **Read:** `_read_lock(target: Path) -> str | None`
- **Write:** `_write_lock(target: Path, sha: str) -> None`
- **Constant:** `LOCK_FILE = ".rhiza/template.lock"` (module-level string constant, not configurable)

#### Template Config (`.rhiza/template.yml`)

Parsed into `RhizaTemplate` dataclass (`models.py`):

```python
@dataclass
class RhizaTemplate:
    template_repository: str | None = None  # e.g. "jebel-quant/rhiza"
    template_branch: str | None = None      # e.g. "v0.8.3" or "main"
    template_host: str = "github"           # "github" | "gitlab"
    language: str = "python"
    include: list[str] = field(default_factory=list)   # path-based mode
    exclude: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list) # bundle-based mode
```

Serialisation: `from_yaml()` / `to_yaml()`. The `to_yaml()` method uses aliased keys on write (`repository` instead of `template-repository`, `ref` instead of `template-branch`) — a divergence from the read-side that accepts both. This is a subtle schema inconsistency.

#### Bundle Config (`.rhiza/template-bundles.yml` — in the *template* repo, not the consumer)

Parsed into `RhizaBundles` / `BundleDefinition` dataclasses:

```python
@dataclass
class BundleDefinition:
    name: str
    description: str
    files: list[str]
    workflows: list[str]
    depends_on: list[str]
```

Topological sort for dependency resolution is implemented in `RhizaBundles.resolve_dependencies()`.

#### Sync Strategy Dispatch (`sync.py`)

```
strategy="diff"      → _sync_diff()      — read-only, no lock update
strategy="overwrite" → _sync_overwrite() — copy all, update lock
strategy="merge"     → _sync_merge()     — 3-way merge via cruft, update lock
```

The merge path:
1. Clone upstream at `HEAD` of configured branch → get `upstream_sha`
2. If `base_sha` (from lock) ≠ `upstream_sha` → proceed
3. Clone base repo at `base_sha` (second clone, `--filter=blob:none --sparse --no-checkout`)
4. Build two snapshot directories: `base_snapshot`, `upstream_snapshot`
5. `get_diff(base_snapshot, upstream_snapshot)` → unified diff string (from `cruft._commands.utils.diff`)
6. `git apply -3` in target; fallback to `git apply --reject` on conflict
7. Write new SHA to lock

---

### 5. Test Structure and Organisation

**Framework:** pytest, configured in `pytest.ini` with `testpaths = tests`, `log_cli = true`, `log_cli_level = DEBUG`.

**Directory layout:**

```
tests/
├── benchmarks/
│   ├── conftest.py
│   └── test_benchmarks.py          # Performance tests (marked @pytest.mark.stress)
├── test_commands/
│   ├── test_init.py                # 454 lines
│   ├── test_init_language.py       # 109 lines
│   ├── test_materialize.py         # 2075 lines — largest test file
│   ├── test_materialize_bundles.py # 207 lines
│   ├── test_migrate.py             # 424 lines
│   ├── test_summarise.py           # 477 lines
│   ├── test_sync.py                # 380 lines — covers lock, snapshot, diff, strategies
│   ├── test_uninstall.py           # 607 lines
│   └── test_validate.py            # 1007 lines
├── test_bundle_resolver.py         # 365 lines
├── test_cli_commands.py            # 256 lines — integration-style CLI wiring tests
├── test_language_field.py          # 180 lines
├── test_language_validators.py     # 194 lines
├── test_models.py                  # 633 lines — dataclass round-trip, edge cases
└── test_package.py                 # 53 lines
```

**Total: ~7,421 lines of test code.**

**Test patterns observed:**
- Class-based grouping (`TestLockFile`, `TestExpandPaths`, `TestSyncCommand`, etc.) — consistent style.
- Heavy use of `unittest.mock.patch` at the `subprocess.run` level rather than introducing a testable abstraction. This means tests are coupled to the internal call signatures of `subprocess.run`.
- `typer.testing.CliRunner` used for CLI integration tests.
- `tmp_path` pytest fixture used correctly throughout.
- `pytest.mark.stress` marker registered for long-running tests.
- Notable: No `conftest.py` at the top-level `tests/` directory — shared fixtures are inlined or duplicated in test classes. The `_setup_project()` helper in `TestSyncCommand` is a local method rather than a fixture.
- The `.rhiza/tests/` directory (template-level tests) is a *separate* suite that tests the Makefile API, integration workflows, and structural invariants of the template repository itself. It is not part of the `src/rhiza` package test suite.

---

### 6. Key Source Files — Template Sync/Lock Functionality

| File | Role |
|---|---|
| `src/rhiza/commands/sync.py` | Core `sync` command; lock read/write; 3-way merge via cruft; 628 lines |
| `src/rhiza/commands/materialize.py` | `materialize` command; sparse clone + copy; writes `.rhiza/history`; 589 lines |
| `src/rhiza/commands/migrate.py` | Migrates `.rhiza.history` → `.rhiza/history` and old template.yml locations |
| `src/rhiza/models.py` | `RhizaTemplate` and `RhizaBundles` dataclasses; YAML load/save |
| `src/rhiza/bundle_resolver.py` | Resolves bundle names → file path lists |
| `src/rhiza/cli.py` | Typer wiring; documents 3-way merge semantics in docstring |
| `src/rhiza/commands/__init__.py` | Package docstring; re-exports `sync`, `materialize`, `validate`, `init` |
| `.rhiza/template.yml` | Consumer config (this repo syncing from `jebel-quant/rhiza@v0.8.3`) |
| `.rhiza/history` | Current manifest (97 files under template control) |
| `tests/test_commands/test_sync.py` | Unit + integration tests for sync command, 380 lines |
| `tests/test_models.py` | Model round-trip and edge-case tests, 633 lines |

---

### Strengths

- **Dogfooding:** The CLI project manages its own configuration via `.rhiza/template.yml`, providing a live integration test of the tooling and ensuring the authors feel the user experience directly.
- **Clean command separation:** `materialize` (one-shot copy) vs `sync` (incremental merge) are distinct commands with distinct semantics and separate code paths. No flag soup.
- **Lock file design is conceptually correct:** Storing the upstream SHA enables a true 3-way merge analogous to `cruft`'s approach. First-sync fallback to copy is sensible.
- **Sparse checkout throughout:** Both `materialize` and `sync` use `--filter=blob:none --sparse` to minimise bandwidth when cloning large template repositories.
- **Comprehensive test suite:** 7,421 lines covering most command paths; `test_models.py` has excellent edge-case coverage (multi-line YAML scalars, field aliasing, round-trips).
- **`_normalize_to_list`:** Thoughtful handling of YAML block scalar (`|`) vs list for `include`/`exclude` fields — a real user pain point caught proactively.
- **Topology-sorted bundle resolution:** `RhizaBundles.resolve_dependencies()` implements a proper DFS topological sort with cycle detection rather than a naive flat list.
- **Toolchain choices:** `uv` + `hatchling` + `ruff` + `loguru` + `typer` — modern, fast, coherent.
- **Strategy pattern for sync:** `diff` / `overwrite` / `merge` dispatch is clean and easily extensible.

### Weaknesses

- **`template.lock` is not self-described:** The file contains only a raw SHA with no metadata (no repo URL, no branch, no timestamp). If a project is reconfigured to point at a different template repository, the existing lock becomes silently invalid — there is no guard against this.
- **`to_yaml()` writes aliased keys:** `RhizaTemplate.to_yaml()` writes `repository` and `ref` instead of `template-repository` and `template-branch`. The read path accepts both. This creates a de facto two-schema situation that will cause confusion when users read the written YAML vs. the documented format.
- **`materialize` does not interact with `template.lock`:** Running `rhiza materialize --force` after `rhiza sync` will overwrite synced files without updating (or invalidating) the lock, leaving the lock SHA pointing at an earlier base that no longer reflects the file state. Subsequent `sync` operations will compute diffs against a stale base.
- **No lock file in `.gitignore` recommendation:** The lock file should typically be committed (like `uv.lock`), but this is not documented. Nothing prevents users from accidentally ignoring it.
- **`_apply_diff` fallback to `--reject` is silent:** When `git apply -3` fails, the fallback to `git apply --reject` is attempted without informing the user that the merge strategy degraded. The user only sees a post-hoc warning about `.rej` files.
- **`subprocess.run` is not abstracted for testing:** Tests mock at the `subprocess.run` level using `@patch("rhiza.commands.materialize.subprocess.run")`. This creates brittle tests coupled to internal invocation order and makes it impossible to substitute a fake git backend.
- **`_exclude_set` in `sync.py` duplicates logic from `materialize.py`:** The always-excluded set (`.rhiza/template.yml`, `.rhiza/history`) appears in both modules independently (`_copy_files_to_target` in materialize and `_excluded_set` in sync).
- **`test_materialize.py` is 2,075 lines:** Largest test file; no `conftest.py` shared fixtures. The `_setup_project()` pattern is duplicated across test classes rather than factored into a shared fixture.
- **`uninstall` command docstring references `.rhiza.history` (old path):** `cli.py` line 369 mentions `.rhiza.history` — the pre-migration name — in the public-facing command docstring. This is stale documentation.
- **No lock integrity check on `sync` entry:** `sync()` reads the lock SHA and uses it blindly. If the lock file contains a non-existent or garbage SHA (e.g., from a manual edit or a shallow clone that pruned the commit), `_clone_at_sha` will fail at runtime with an opaque git error rather than a clear validation error.

### Risks / Technical Debt

1. **`cruft` is a private API dependency.** `from cruft._commands.utils.diff import get_diff` imports from a private submodule. This is fragile — any cruft refactor can break it silently. There is no version pin beyond `>=2.16.0`, creating a wide compatibility window.

2. **Double-clone on every merge sync.** The merge strategy performs two separate full-network clone operations (upstream + base). For large template repositories or slow networks, this is expensive. There is no local cache of template clones between runs.

3. **`template.lock` and `materialize` divergence.** As noted: `materialize --force` intentionally does not write the lock. This means a project bootstrapped via `materialize` and then switched to `sync` will hit a first-sync copy on the next `rhiza sync` call regardless of how old the materialized files are. The initial copy overwrites any local customisations — the very thing `sync` is designed to preserve.

4. **`sys.exit(1)` called directly in command implementations** (`materialize.py`, `sync.py`). This bypasses Typer's exit mechanism and makes the commands difficult to unit-test without patching `sys.exit`. Tests in `test_materialize.py` use `pytest.raises(SystemExit)` as a workaround.

5. **`_warn_about_workflow_files` is defined in `materialize.py` and re-imported into `sync.py`.** This creates a coupling between the two modules where `sync.py` depends on `materialize.py`'s internals. If the materialize module is refactored, sync silently breaks. A shared `utils.py` would be cleaner.

6. **No atomic lock write.** `_write_lock` does `write_text(sha + "\n")` directly. If the process is interrupted mid-write (e.g., SIGKILL), the lock file could contain a partial SHA, causing silent failures on the next sync run.

7. **`validate` runs on every `materialize`/`sync` call** via `_validate_and_load_template()`. The validate command runs `subprocess` git checks and YAML parsing. For power users running sync frequently, this adds latency for no additional safety (since the template config rarely changes between syncs).

8. **Branch naming is a string with no enum/literal type.** The `strategy` parameter in `sync()` is `str` with manual validation (`if strategy not in ("merge", "overwrite", "diff")`). A `Literal["merge", "overwrite", "diff"]` type annotation or an `Enum` would provide static analysis coverage.

9. **The `copilot/enhance-template-lock` branch is only 1 commit ahead of `main`.** The branch name implies it was auto-generated. There is no PR description, no linked issue, and the single commit message is "Initial plan" — suggesting this is an AI-initiated work-in-progress branch, not a reviewed change.

---

### Score

**6 / 10**

The core design is sound — the lock-file/snapshot/3-way-merge approach is well-conceived and the codebase is clean and readable. The test coverage is substantial. However, the `materialize`/`sync` lock-state divergence is a correctness risk that will bite users in real workflows. The `cruft` private API import is a stability risk. The `to_yaml()` key aliasing is a schema inconsistency. These are not cosmetic issues — they affect the reliability of the primary user workflow. With those addressed, this would comfortably reach a 7–8.
