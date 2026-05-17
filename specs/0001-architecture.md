---
id: 0001
title: Architecture — hybrid CLI core + Claude Code plugin wrapper, named `clain`
status: shipped
goal: Goal 4 (Portability); supports Goal 5 (Honest sync hygiene) and the multi-agent constraint
---

## Problem

The project must serve a developer who uses several AI coding tools simultaneously (Claude Code, OpenCode, others) and a raw terminal. A Claude-only implementation (plugin or skills alone) would lock the tool to one agent and violate the INTENT constraint that nothing here assume a single agent or shell. A pure CLI would work everywhere but forgo the polished agent UX that makes the tool actually get used inside Claude Code. We need a single architectural decision that resolves this before any code lands.

## Intent

Lock in a hybrid architecture so that:

- The cleanup/inspection/orchestration logic is reachable identically from every agent or from a bare shell.
- Claude Code users still get a first-class skill/agent surface, but only as a *thin* wrapper — never as the home of logic.
- A second contributor (or the user, six months from now) can tell at a glance which side of the boundary any new code belongs on.

Traces to INTENT goal 4 (Portability) directly, and reinforces goal 5 because both surfaces store state in the same controlled location outside the synced tree.

## Spec

**Name.** The project, the CLI binary, and the Claude Code plugin all use the name `clain`.

**Two surfaces, one engine.**

1. **CLI core — `clain`.**
   - Language: Python.
   - Toolchain: [Pixi](https://pixi.sh/) for environment and dependency management. No `venv`/`pip install -e` workflows; Pixi is the single source of truth for the dev env.
   - Distribution-shaped: must be runnable as `clain <subcommand>` once installed. (Exact distribution mechanism — `pixi global install`, `uv tool`, `pipx`, standalone binary — is a later spec.)
   - All behaviour the project offers is reachable here. The CLI is the contract.

2. **Claude Code plugin — `clain` (the plugin).**
   - Lives under this repo (path/layout in a later spec) and is installable as a Claude Code plugin.
   - Contains: skills, subagents, commands, and hooks that drive the CLI. May add agent-UX-only conveniences (prompts, summaries, confirmation flows).
   - **Must not contain behaviour that is not also reachable from the CLI.** If a skill wants to do X, X is a CLI subcommand first; the skill calls it.

**Boundary rule (the load-bearing one).** Plugin code may *orchestrate*, *prompt*, *summarise*, and *render*. It may not *decide what to delete*, *compute what is duplicated*, *touch the filesystem*, or hold any business logic. All of that lives behind `clain` CLI subcommands.

**State and artefacts.** Anything `clain` writes (caches, logs, inventories, audit trails) lives under `$XDG_STATE_HOME/clain` (default `~/.local/state/clain`) or `$XDG_CACHE_HOME/clain`. **Never** inside `~/dev/clain-me/` (except transient build artefacts) and **never** inside the Google Drive synced tree.

**Repo layout (target shape, not a directive to scaffold yet).**

```
clain-me/
├── INTENT.md
├── CLAUDE.md
├── specs/
├── .claude/                  # repo-local Claude Code config (hooks, agents) — not the plugin
├── pixi.toml                 # Pixi env definition (added by a later spec)
├── src/clain/                # Python package; CLI entry point
└── plugin/                   # Claude Code plugin source (skills/, agents/, commands/, hooks/)
```

The `.claude/` directory at the repo root is for *developing* this project (the goal-advisor, dev hooks). The `plugin/` directory is the distributable plugin product. They are different things and must not be conflated.

## Acceptance

- [ ] `specs/0001-architecture.md` exists and is `accepted`.
- [ ] CLAUDE.md references this spec as the architectural authority and restates the boundary rule.
- [ ] INTENT.md is unchanged (this spec serves existing goals; it does not amend them).
- [ ] A short ADR-style note in this spec explains why option 4 (hybrid) was chosen over options 1–3 — covered above under Problem/Intent.
- [ ] Any future spec that proposes plugin-only logic, or CLI logic that depends on a Claude Code construct, is rejected on first read with a pointer to this spec's boundary rule.

## Out of scope

- The Pixi `pixi.toml`, project layout scaffolding, and Python package skeleton. Each is its own follow-up spec.
- Plugin manifest format, install path, and marketplace publication.
- The first actual feature (inventory of the synced tree). That is spec 0002 territory.
- Choice of CLI framework (Typer, Click, argparse). Decided when 0002 needs it.
- Distribution mechanism (`pixi global`, `uv tool`, `pipx`, PyInstaller).
- Any non-Python rewrite. If Python turns out to be the wrong call, that requires a new spec superseding this one — not a quiet swap.
