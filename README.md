# clain

**Tidy up the workspace sprawl from AI-assisted coding.** For developers whose `dev/` directory has 30+ workspaces — each carrying its own `node_modules` and `.venv` — quietly re-syncing to Google Drive forever.

If your AI coding tools (Claude Code, Cursor, OpenCode, Aider, Cline, …) have left you with dozens of half-explored workspaces piling up under your synced cloud folder, and you can feel the storage tax every time you `ls`, `clain` is for you. It classifies each subtree by kind (cache-managed dependency trees, ephemeral build outputs, bytecode, workspace source), emits *reviewable plans* for tidying them up (delete-and-recreate via pnpm/Pixi/uv; move workspace source out of the synced tree), and refuses to act on those plans until you've read them. The phase gate is closed by design while the project is pre-1.0 — every plan is a preview today, and lifting that gate requires its own named spec.

## What classification looks like

```text
                            Workspace classification
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Workspace           ┃ In sync tree ┃ Class tags                     ┃ Manifests                  ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ example-frontend    │      ✓       │ cache-managedx1, ephemeralx1   │ package.json, pnpm-lock... │
│ example-pipeline    │      ✓       │ cache-managedx1, bytecodex1    │ pixi.toml, pyproject.toml  │
│ example-uv-project  │      ✓       │ cache-managedx1                │ pyproject.toml, uv.lock    │
│ example-ambiguous   │      ✓       │ cache-managedx1                │ pyproject.toml             │
└─────────────────────┴──────────────┴────────────────────────────────┴────────────────────────────┘
Workspaces: 4  In synced tree: 4  Class tags: 6  scan 0.011s
```

Each workspace gets a categorical view in seconds. The scan stops at every class boundary — it never recurses into `node_modules` or `.venv`. Then `clain plan recreate --dry` produces a delete-and-recreate plan with the right command for each workspace's manifest (`pixi install`, `pnpm install --frozen-lockfile`, `uv sync`, …) and flags the ambiguous ones (`pyproject.toml` with no toolchain lockfile → `safe_to_execute: false`).

See [docs/USAGE.md](docs/USAGE.md) for the full walkthrough. See [INTENT.md](INTENT.md) for the mission.

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

Full walkthrough — reading the output, customising the rule base, common scenarios — in [docs/USAGE.md](docs/USAGE.md).

### I want my AI agent to drive this

`clain` ships skills in the cross-agent [Agent Skills](https://agentskills.io) format under [`skills/`](skills/). Any Agent Skills-compatible agent (Claude Code, Cursor, Aider, Cline, Continue, OpenCode, …) picks them up automatically. See [AGENTS.md](AGENTS.md) for the agent-onboarding brief.

### I want to extend or contribute

The project is spec-driven. Every non-trivial change starts as a numbered spec under [`specs/`](specs/), reaches an *aligned* goal-advisor verdict, and lands via a feature-branch + PR. The full developer workflow is in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## State location

Caches, plans, and logs live under `$XDG_STATE_HOME/clain/` (default `~/.local/state/clain/`):

- `classify/<root-hash>.json` — classification cache (24h TTL).
- `plans/<kind>-<UTC>.json` — every generated plan, timestamped.
- `logs/{classify,plan}.log` — audit lines.

Nothing is written under the scanned root. The mutation-vector ban list is enforced by tests.

## Phase-gated execution

Execution is the **default** behaviour of `clain plan`. While the development-phase gate is closed (`EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py)), default-mode invocations render the plan and then error with a pointer to `--dry`. Lifting the gate requires a future spec named *00NN — Lift the dry-run gate*, which must specify rollback, audit, and additional safety mechanisms. Use `--dry` to preview cleanly today.

## License

[MIT](LICENSE).
