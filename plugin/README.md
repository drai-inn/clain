# clain (Claude Code plugin)

Claude-Code-specific packaging of `clain`. The actual skills live in [`../skills/`](../skills/) and conform to the [Agent Skills](https://agentskills.io) specification — they work with any Agent Skills-compatible agent, not just Claude Code.

The `plugin/skills/` directory under this folder contains **symlinks** back to `../../skills/<name>/` as a compatibility shim for the current Claude Code plugin loader. There is no separate copy of any skill body here, and there must not be.

For the universal project brief, see [../AGENTS.md](../AGENTS.md). For the boundary rule that skills must never contain business logic, see [../specs/0001-architecture.md](../specs/0001-architecture.md).
