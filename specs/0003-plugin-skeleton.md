---
id: 0003
title: Claude Code plugin skeleton under `plugin/`, driving the CLI
status: shipped
goal: Goal 4 (Portability) — establishes the second surface from spec 0001 and proves the boundary rule with a real, minimal example
---

## Problem

Spec 0001 declared the Claude Code plugin as a thin wrapper that drives the CLI and contains no business logic. Until that wrapper exists in skeletal form, the boundary rule is hypothetical — every later plugin spec will be debating both the boundary *and* the format. We need one trivial, correct example that future plugin work can pattern-match against.

## Intent

A `plugin/` directory at the repo root, installable as a Claude Code plugin, containing exactly one skill that shells out to the `clain` CLI and renders its output. No agents, no commands, no hooks, no MCP. Just the smallest demonstration that the boundary holds and the plugin surface is real.

## Spec

**Location.** `plugin/` at the repo root. Distinct from `.claude/` (which is for developing *this* project, not the distributable product). Spec 0001's "do not conflate" rule is enforced here.

**Manifest.** Follow the Claude Code plugin format current at implementation time. The manifest declares the plugin name `clain`, a short description ("Manage local AI-dev workspaces — see clain CLI"), and points at `plugin/skills/`. Exact filename and schema are an implementation detail of this spec — record them in a short `plugin/README.md` so future specs can find them.

**One skill: `clain-version`.**

- Location: `plugin/skills/clain-version/SKILL.md` (or whatever the current format is).
- Description (skill frontmatter) is precise enough that the Skill tool only triggers it when the user asks about the `clain` CLI version specifically — not generic version questions.
- Body: instructions to invoke `clain --version` via Bash and report the result. No fallback, no inline logic, no business decisions. If the CLI isn't on PATH, the skill surfaces the error verbatim and stops.

**Invocation contract (boundary rule, made concrete).**

- The skill **must** call out to the `clain` binary. It must not parse a Python source file, import any Python, or duplicate version information.
- If `clain` is not installed, the skill must not attempt to install it, fall back to a known value, or guess. It instructs the user to install per the project README and exits.
- This pattern (skill → CLI subcommand, no fallback, no inline logic) is the reference implementation that 0004+ plugin work copies.

**`plugin/README.md`** explains: how to install the plugin locally during development, where the manifest lives, and the boundary rule restated in one paragraph with a link to spec 0001.

**No agents, commands, or hooks in this spec.** Adding any of those is a separate spec. This keeps the skeleton reviewable in one sitting.

## Acceptance

- [ ] `plugin/` exists at the repo root, with a valid Claude Code plugin manifest.
- [ ] `plugin/skills/clain-version/` contains one skill whose body shells out to `clain --version`.
- [ ] The skill contains zero business logic — verified by reading the file: it has prose + a Bash invocation, nothing else. Grep-testable: the skill body contains no `python`, no `import`, no `version` literal, no parsing of any file under `src/`.
- [ ] Installing the plugin into a Claude Code session and asking "what version of clain is installed?" triggers the skill, which invokes the CLI and reports the version.
- [ ] If the `clain` binary is not on PATH, the skill reports the failure clearly and does not attempt a workaround.
- [ ] `plugin/README.md` exists, restates the boundary rule, and links to spec 0001.

## Out of scope

- Any non-version skill (workspace inventory, cleanup, rehydration, etc.). Each is its own future spec.
- Subagents inside the plugin (e.g. a "cleanup advisor"). Future spec.
- Commands (e.g. `/clain-audit`). Future spec.
- Hooks shipped with the plugin (e.g. blocking risky deletions in user repos). Future spec.
- Plugin marketplace publication or signing.
- Auto-install of the `clain` CLI from inside the plugin. The plugin assumes the CLI is already on PATH; bootstrapping is a separate concern.
