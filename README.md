# clain

Manage local AI-dev workspaces — categorical visibility, deliberate execution.

`clain` reads a tree of developer workspaces, classifies each subtree by kind (cache-managed, ephemeral, bytecode, workspace-source), and emits *executable plans* for tidying it up. Plans are reviewable artefacts; execution is gated until a future spec authorises it.

See [INTENT.md](INTENT.md) for the mission and goals.

---

## Three ways in

### I just want to run the CLI

```sh
pixi install
export CLAIN_DEV_ROOT=~/some/dev/tree   # no personal-info default baked in
pixi run clain classify
pixi run clain plan recreate --dry
pixi run clain plan move --dest ~/dev/ --dry
```

The full walkthrough — first run, reading the output, common scenarios, customising the rule base — is in [docs/USAGE.md](docs/USAGE.md).

### I want my AI agent to drive this

`clain` ships skills in the cross-agent [Agent Skills](https://agentskills.io) format under [`skills/`](skills/). Any Agent Skills-compatible agent (Claude Code, Cursor, Aider, Cline, Continue, OpenCode, …) picks them up automatically. See [AGENTS.md](AGENTS.md) for the agent-onboarding brief.

### I want to extend or contribute

The project is spec-driven. Every non-trivial change starts as a numbered spec under [`specs/`](specs/), reaches an *aligned* goal-advisor verdict, and lands via a feature-branch + PR. The full developer workflow — PR template, quality gates, rule-base extension rules, skill-authoring constraints — is in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## State location

Caches, plans, and logs land under `$XDG_STATE_HOME/clain/` (default `~/.local/state/clain/`):

- `classify/<root-hash>.json` — classification cache (24h TTL).
- `plans/<kind>-<UTC>.json` — every generated plan, timestamped.
- `logs/{classify,plan}.log` — audit lines.

Nothing is written under the scanned root. The mutation-vector ban list is enforced by tests.

## Phase-gated execution

Execution is the **default** behaviour of `clain plan`. While the development-phase gate is closed (`EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py)), default-mode invocations render the plan and then error with a pointer to `--dry`. Lifting the gate requires a future spec named *00NN — Lift the dry-run gate*, which must specify rollback, audit, and additional safety mechanisms. Use `--dry` to preview cleanly today.

## License

[MIT](LICENSE).
