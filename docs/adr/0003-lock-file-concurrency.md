# ADR-0003: Concurrency-safe lock file I/O with fcntl and atomic rename

**Status:** Accepted

## Context

Two concurrent `rhiza sync` invocations (CI matrix builds, shared dev containers) can race
on `.rhiza/template.lock`, corrupting the file or losing metadata.

## Decision

- Use `fcntl.flock(LOCK_EX)` around lock file reads and writes on Unix.
- Use `os.replace()` (atomic rename) for writes: write to `.tmp`, then rename.
- Guard `import fcntl` with `try/except ImportError` — Windows falls back gracefully.

## Consequences

- ✅ Lock file is corruption-safe under concurrent access on Unix/macOS.
- ✅ Zero new dependencies (stdlib only).
- ⚠️ Advisory locking only — processes must cooperate. Does not prevent OS-level file deletion.
- ⚠️ Windows has no advisory locking (falls back to unprotected I/O with a debug log).
