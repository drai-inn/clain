# CLAUDE.md

Claude Code-specific developer notes. **For the universal project brief, see [AGENTS.md](AGENTS.md); for the contribution workflow, see [CONTRIBUTING.md](CONTRIBUTING.md).** This file documents the Claude Code-specific developer-side configuration only.

## Read first, every session

1. [INTENT.md](INTENT.md) — source of truth.
2. [AGENTS.md](AGENTS.md) — universal entry point.
3. [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, gates, rule-base extension.
4. The list of active specs under [`specs/`](specs/) (any with status `draft` or `accepted`).

A `SessionStart` hook (`.claude/settings.json`) prints INTENT and active spec headers into context automatically.

## Claude Code-specific developer config

- **`.claude/agents/goal-advisor.md`** — the goal-advisor pattern as a Claude Code subagent. The pattern itself is portable and documented in [CONTRIBUTING.md](CONTRIBUTING.md#the-goal-advisor-pattern); this file is one instantiation Claude Code can invoke directly.
- **`.claude/settings.json`** — wires two hooks:
  - `SessionStart` — prints INTENT and active specs at session start so the work always begins from the source of truth.
  - `PreToolUse` on Bash — flags `rm -rf` / `rm -fr` commands for explicit approval, citing INTENT goal 2 (deliberate execution). This is a Claude Code safety affordance; the equivalent guarantee on the `clain` side is the phase gate.

If a hook gets in the way of legitimate work, fix the hook in `.claude/settings.json` — do not bypass it ad hoc.

## Claude Code plugin

The repo ships a Claude Code plugin manifest at `plugin/.claude-plugin/plugin.json` that points at the top-level [`skills/`](skills/) directory. The skills themselves are agent-agnostic ([Agent Skills](https://agentskills.io) format) — Claude Code is one consumer. See [`plugin/README.md`](plugin/README.md) and [AGENTS.md](AGENTS.md) for the broader context.

## Working from inside Claude Code

The `pixi run` tasks are the standard entry points and work the same way they do for any developer:

```sh
pixi install
pixi install -e dev
pixi run clain --version
pixi run -e dev test
pixi run -e dev lint
pixi run -e dev typecheck
```

Spec, PR, and workflow conventions are not Claude-Code-specific — see [CONTRIBUTING.md](CONTRIBUTING.md).
