# Repository Analysis Journal

This document provides ongoing technical analysis of the rhiza-cli repository.

---

## 2026-02-20 — Initial Analysis Entry

### Summary
Rhiza-cli is a well-structured Python CLI tool for managing reusable configuration templates across Python projects. The codebase is mature, with 627 lines in the `sync` command alone, comprehensive test coverage, and modern Python tooling (Python 3.11+, Typer, loguru). The project uses a modular architecture with clear separation between CLI layer, command implementations, and data models. The recent addition of a `sync` command using cruft-based 3-way merging represents a significant evolution beyond simple file materialization.

### Strengths

- **Clean Architecture**: Strong separation of concerns with:
  - Thin CLI layer in `cli.py` (437 lines) using Typer for argument parsing
  - Command implementations isolated in `commands/` directory (9 separate modules)
  - Shared models in `models.py` using dataclasses for type safety
  - Utility modules (`subprocess_utils.py`, `bundle_resolver.py`) for cross-cutting concerns

- **Comprehensive Sync Command Implementation** (`src/rhiza/commands/sync.py`, 627 lines):
  - Three distinct strategies: `merge` (3-way merge preserving local changes), `overwrite` (replaces files), and `diff` (dry-run preview)
  - Uses cruft's `get_diff` utility for computing template diffs
  - Implements lock file mechanism (`.rhiza/template.lock`) to track last-synced commit SHA
  - Smart handling: first sync falls back to simple copy, subsequent syncs use 3-way merge
  - Git-based conflict resolution using `git apply -3` with fallback to `--reject` for non-git repos
  - Supports bundle resolution for template-based configuration

- **Robust Testing Structure**:
  - Test files mirror source structure in `tests/test_commands/`
  - `test_sync.py` has 381 lines covering: lock file operations, path expansion, exclusion sets, snapshot preparation, diff application, integration tests for all three strategies, and CLI wiring
  - Uses pytest fixtures, mocking for isolation, and CliRunner for end-to-end CLI tests
  - Benchmarking support in `tests/benchmarks/`

- **Bundle System** (advanced feature):
  - `models.py` defines `BundleDefinition` and `RhizaBundles` dataclasses
  - `bundle_resolver.py` loads `template-bundles.yml` from template repos
  - Supports dependency resolution with topological sort and circular dependency detection
  - Allows hybrid mode: both `templates` (bundle names) and `include` (explicit paths) can coexist
  - Example usage in `.rhiza/template.yml`: uses bundles `core`, `github`, `legal`, `tests`, `book`

- **Security Consciousness**:
  - Uses `subprocess_utils.get_git_executable()` to get absolute git path (prevents PATH manipulation)
  - All subprocess calls use full executable paths with explicit `nosec B603` annotations
  - Sets `GIT_TERMINAL_PROMPT=0` to prevent interactive prompts in automation

- **Modern Python Practices**:
  - Type hints throughout (using `pathlib.Path`, not string paths)
  - Dataclasses for configuration models
  - loguru for structured logging with success/info/warning/error levels
  - Uses `field(default_factory=list)` for mutable defaults in dataclasses
  - Proper `__all__` exports in modules

- **Multi-Language Support**:
  - `language` field in template configuration (defaults to "python")
  - Language validators in `language_validators.py` 
  - Template repository varies by language (e.g., `jebel-quant/rhiza` for Python, `jebel-quant/rhiza-go` for Go)

- **Plugin System**:
  - `__main__.py` loads plugins via entry points (`rhiza.plugins` group)
  - Allows extending CLI with additional commands (e.g., `rhiza-tools` package adds `tools` subcommands)

### Weaknesses

- **Sync Command Complexity**:
  - 627 lines in a single module is substantial; could benefit from further decomposition
  - Multiple nested functions (`_merge_with_base`, `_sync_merge`, `_sync_overwrite`, `_sync_diff`) suggest opportunities for class-based organization
  - Error handling relies heavily on `sys.exit(1)` rather than raising specific exceptions
  - Heavy use of temporary directories (3 different temp dirs in merge strategy) could be hard to debug

- **Documentation Gaps**:
  - README.md doesn't mention the `sync` command at all (only shows `init`, `materialize`, `migrate`, `validate`)
  - No examples of using the bundle/template system in main documentation
  - USAGE.md briefly mentions `sync-templates` in Makefile context but lacks dedicated `rhiza sync` section
  - Missing documentation on when to use `sync` vs `materialize --force`

- **Inconsistent Terminology**:
  - Uses both "materialize" and "inject" to describe the same operation
  - "Rhiza branch" vs "template branch" (used interchangeably)
  - "Target" means both "target directory" and "target repository"

- **Bundle Resolution Complexity**:
  - Bundle system requires `.rhiza/template-bundles.yml` in template repository
  - No clear error messages if bundles.yml exists but is malformed
  - Resolution happens at two different points: initial sparse checkout uses `[".rhiza"]`, then updates after bundle resolution
  - `_clone_and_resolve_upstream` function performs double-checkout (initial + update after bundle resolution)

- **Limited Conflict Resolution Guidance**:
  - When 3-way merge creates conflicts, only logs "Check for *.rej files and resolve manually"
  - No helper commands to list conflicts or assist resolution
  - No documentation on best practices for resolving template conflicts

- **Test Coverage Gaps**:
  - `test_sync.py` heavily mocks dependencies (clone, mkdtemp, sha retrieval)
  - Few integration tests with actual git operations
  - No tests for bundle resolution path in sync command
  - Missing tests for error conditions (network failures, invalid commits, corrupted lock files)

### Risks / Technical Debt

- **Git Dependency**:
  - Entire sync mechanism depends on git being available (`get_git_executable()` raises if missing)
  - Uses git sparse checkout (requires git 2.25+) without version check
  - `git apply -3` requires git repository; fallback to `--reject` may leave project in inconsistent state

- **Cruft Dependency**:
  - Imports `cruft._commands.utils.diff.get_diff` (private API indicated by underscore)
  - Cruft API changes could break sync functionality
  - No version pinning visible for cruft in dependencies (pyproject.toml shows `cruft>=2.16.0`)

- **Lock File Management**:
  - `.rhiza/template.lock` contains only commit SHA (no metadata about template repo, branch, or timestamp)
  - No validation that lock SHA is reachable from current template repository
  - Changing template repository invalidates lock but no detection/warning
  - Lock file location not mentioned in README or main docs

- **Tempfile Cleanup**:
  - Multiple `tempfile.mkdtemp()` calls with try/finally cleanup
  - If process killed mid-sync, temp directories accumulate
  - No documented cleanup procedure

- **Sparse Checkout Limitations**:
  - Uses `--filter=blob:none` and `--sparse` for efficiency
  - Some git hosts (older GitLab) may not support partial clones
  - Error messages for sparse checkout failures could be more helpful (currently just logs stderr)

- **Backward Compatibility**:
  - Supports legacy field names (`repository` → `template-repository`, `ref` → `template-branch`)
  - No migration path or warnings for deprecated fields
  - `.rhiza/history` file format not versioned (plain text, one path per line)

- **Missing Dry-Run Validation**:
  - `--strategy diff` shows diff but doesn't validate that changes would apply cleanly
  - Could give false confidence before actually running sync

### Score

**8/10**

**Rationale:**
- **Strong fundamentals**: Clean architecture, good testing, modern Python practices, security-conscious
- **Advanced features**: Bundle system, plugin support, multi-language, 3-way merge sync
- **Production-ready**: Comprehensive error handling, validation, logging
- **Deductions**:
  - -1 for documentation gaps (sync command not in README, limited bundle docs)
  - -1 for complexity concerns (sync.py at 627 lines, heavy mocking in tests, cruft private API dependency)

This is a well-maintained, feature-rich tool that would benefit from:
1. Documenting the sync command in README.md and USAGE.md
2. Breaking down sync.py into smaller, more testable units
3. Adding integration tests with real git operations
4. Providing better conflict resolution guidance and tooling
