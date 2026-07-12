# ADR-0006: Make `rhiza-cli` the home of the Claude Code plugin

**Status:** Proposed

## Context

Rhiza currently ships across two repositories:

- **`rhiza-cli`** (this repo) — the engine. A Typer application (`rhiza`) with real
  domain models (`models/lock.py`, `models/template.py`, the `_git/` merge engine)
  and eight commands: `init`, `sync`, `status`, `tree`, `validate`, `list`,
  `uninstall`, `summarise`. It is pip/uv-installable (`project.scripts.rhiza`) and
  is what `make sync` invokes inside managed repos.
- **`rhiza-config`** — the Claude Code plugin. A `.claude-plugin/plugin.json` plus
  `commands/*.md` exposing four slash commands: `/boost`, `/quality`, `/revisit`,
  `/stats`.

These two serve different execution contexts (a CLI for humans and CI; slash
commands driven interactively by an agent), but they overlap in substance. The
`/stats` command was recently reworked into a bundled Python script
(`rhiza-config/scripts/stats.py`) so it could run without an agent. That script
re-derives, with ad-hoc regular expressions, information that `rhiza-cli` already
computes properly — its "Rhiza template status" section duplicates what
`rhiza status` and `rhiza tree` produce from `models/lock.py` and
`models/template.py`.

That duplication is the crux. With the plugin in a separate repo, every command
that needs engine logic faces a bad choice: **reimplement it** (drift, as
`stats.py` began to) or **coordinate across two repos** (a version-matching
burden). The plugin has no way to call the engine it conceptually depends on,
because a plugin install and a CLI install are unrelated artifacts.

## Decision

Relocate the Claude Code plugin into `rhiza-cli`, so a single repo has two faces:
the CLI (unchanged) and a Claude Code plugin whose slash commands are thin
wrappers over the co-located engine.

**1. Plugin lives beside the engine.** Add `.claude-plugin/plugin.json` (+ a
marketplace entry, plugin `name: "rhiza"`) and a `commands/` directory to
`rhiza-cli`. The four slash commands move here from `rhiza-config`.

**2. Slash commands invoke the bundled CLI.** A plugin install copies the repo
into `~/.claude/plugins/cache/…` but does **not** put `rhiza` on `PATH`. Because
the plugin root then contains `pyproject.toml` + `src/`, commands run the engine
from its own bundled source:

```bash
uvx --from "${CLAUDE_PLUGIN_ROOT}" rhiza status
```

This needs no separate `pip install` and **guarantees the slash commands and the
CLI are the same version**. (Requiring `uv tool install rhiza` on `PATH` was
considered and rejected as the default — see Alternatives.)

**3. Deterministic commands become CLI subcommands; judgement commands stay
Markdown.** The governing rule:

| Slash command | Disposition |
|---|---|
| `/stats` | Fold into a new `rhiza stats` subcommand that reuses `models/lock.py`/`template.py` (not regex) and deduplicates against `status`/`tree`/`summarise`; the `.md` becomes a thin `uvx --from … rhiza stats` wrapper. |
| `/boost` | Stays an agent-orchestrated `.md` (conflict resolution, quality scorecard, issue-dedup are genuine LLM work) but calls `rhiza sync`/`rhiza status` for its mechanical steps. |
| `/quality` | Stays `.md` (code-quality judgement). |
| `/revisit` | Stays `.md`; may lean on `rhiza summarise`. |

That is: deterministic/report work belongs in the engine wrapped by a thin `.md`;
judgement work stays in `.md` but delegates its mechanical sub-steps to the engine.

**4. One version, one release.** The plugin `version` tracks the `rhiza` package
version, enforced by a parity check (mirroring `rhiza-config`'s
`check_version_parity.py`). `rhiza-cli`'s existing release machinery (`cliff`,
`rhiza_release.yml`, bump scripts) becomes the single release path.

**5. `rhiza-config` is retired.** It becomes either a marketplace pointer at the
`rhiza-cli` plugin or a deprecated repo with a redirect. Because the plugin
`name` is `"rhiza"` in both, existing installs need a documented transition.

### Phased rollout (each phase non-breaking on its own)

1. **Skeleton (additive):** add `.claude-plugin/` + `commands/` to `rhiza-cli`,
   copying the four `.md` files; add manifest-validation + version-parity to CI.
2. **Wire to the engine:** rewrite command bodies to `uvx --from
   "${CLAUDE_PLUGIN_ROOT}" rhiza …`; add `rhiza stats`; retire the duplicated
   `stats.py` logic.
3. **Cut over:** point `rhiza-config`'s marketplace at this plugin (or deprecate
   it); announce the transition.
4. **Cleanup:** single version/release story; delete the `rhiza-config` scripts.

## Consequences

- ✅ **Single source of truth.** Engine logic lives once; slash commands wrap it
  instead of reimplementing it. The `stats.py` drift risk is removed, not grown.
- ✅ **`rhiza stats` gets *better*, not just relocated** — it uses the real lock
  and template models rather than the regex parsing the standalone script used.
- ✅ **No version skew.** `uvx --from "${CLAUDE_PLUGIN_ROOT}"` runs the plugin's
  own copy of the CLI; slash commands and CLI cannot disagree.
- ✅ **One release process** for both faces.
- ⚠️ **Marketplace continuity.** The plugin `name` is shared across both repos;
  users who installed from `rhiza-config` need a migration path.
- ⚠️ **`uvx --from` cold start.** The first invocation builds an ephemeral
  environment (seconds). Acceptable for interactive use; `uv tool install rhiza`
  can be documented as a faster opt-in.
- ⚠️ **Dual audience.** `rhiza-cli`'s README/issues now serve both CLI users and
  plugin users; docs must address both.
- ⚠️ **Two unrelated "plugin" systems coexist.** `rhiza-cli`'s `rhiza.plugins`
  entry-point mechanism (CLI subcommand plugins, e.g. `rhiza-tools`) is unrelated
  to the Claude Code plugin (just files under `.claude-plugin/` + `commands/`);
  documentation must keep the two from being conflated.

## Alternatives considered

- **Keep the repos separate and reimplement engine logic in `rhiza-config`
  scripts.** Rejected — this is the drift `stats.py` already started; it scales
  badly as more commands need engine data.
- **Port the CLI commands *into* `rhiza-config`.** Rejected — it inverts
  ownership: the substantive Python (models, merge engine) already lives in
  `rhiza-cli`, and moving it toward the presentation layer is backwards.
- **Require `uv tool install rhiza` on `PATH` instead of `uvx --from`.** Rejected
  as the default — it adds a setup step and reintroduces version skew between an
  installed CLI and the plugin. Fine as a documented fast-path opt-in.
