# clain

**Tidy up workspace sprawl from AI-assisted coding.** A tool for developers who use AI coding agents (Claude Code, Cursor, OpenCode, Aider, Cline, …) and end up with workspaces piling up — on synced storage (Google Drive, OneDrive, Dropbox, iCloud Drive, …) where every dependency tree re-uploads forever, or just on a constrained local disk where each project's `node_modules` / `.venv` / `.pixi` quietly chews through your headroom.

`clain` does two things. It **classifies** each workspace by the kind of subtree it carries (cache-managed dependency trees, ephemeral build outputs, bytecode, workspace source). And it emits **reviewable plans** for tidying it up — *delete-and-recreate* via the right package manager (pnpm / Pixi / uv / poetry / npm / yarn), or *move-and-triage* the source code out of synced storage to a local home. Every plan is preview-only today; execution is gated until a future named spec authorises it.

The everyday entry point is one workspace at a time. Two-command demo:

```sh
pixi install                                   # one-off
cd ~/some/project                              # any project with pyproject.toml / package.json / etc.
pixi run clain classify --here                 # categorical view of THIS workspace
pixi run clain plan recreate --here --dry      # what a clean rebuild would look like
```

Here's what the single-workspace classify looks like against a project with both a Pixi env and the usual Python tool caches:

```text
example-workspace  (~/dev/example-workspace)
├── Manifests: pixi.toml, pyproject.toml
├── Sync placement: ? unknown (CLAIN_SYNCED_ROOT not set)
├── bytecode
│   ├── .mypy_cache
│   ├── .pytest_cache
│   ├── .ruff_cache
│   ├── src/example/__pycache__
│   └── tests/__pycache__
└── cache-managed
    └── .pixi

Next: clain plan recreate --here --dry  →  pixi install
```

`clain` recognised the manifests at the project root, identified the regenerable subtrees, and pointed you at the recreate command derived from `pixi.toml`. The scan stops at `.pixi/` — it doesn't recurse through every nested `__pycache__` in the bundled CPython.

See [INTENT.md](INTENT.md) for the project's mission. See [docs/USAGE.md](docs/USAGE.md) for the full walkthrough.

---

## Three ways in

### I want to tidy one project

```sh
pixi install
cd ~/some/project
pixi run clain classify --here
pixi run clain plan recreate --here --dry
```

This is the lowest-friction entry point. Walkthrough in [docs/USAGE.md](docs/USAGE.md).

### I have a tree of workspaces to triage

If your historical `dev/` directory has accumulated dozens of AI-spawned workspaces — say under a synced cloud drive — point `clain` at the tree:

```sh
export CLAIN_DEV_ROOT=~/some/dev/tree              # no personal-info default baked in
export CLAIN_SYNCED_ROOT=~/path/to/your/synced/storage     # optional; enables in-sync detection
pixi run clain classify
pixi run clain plan recreate --dry
pixi run clain plan move --dest ~/dev/ --dry
```

In tree mode `clain` enumerates each workspace under `CLAIN_DEV_ROOT` and classifies them side by side:

```text
                           Workspace classification                           
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Workspace       ┃ In sync tree ┃ Class tags     ┃ Manifests       ┃ Errors ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ example-ambigu… │      ?       │ cache-managed… │ pyproject.toml  │        │
│ example-fronte… │      ?       │ cache-managed… │ package.json,   │        │
│                 │              │ ephemeralx1    │ pnpm-lock.yaml  │        │
│ example-pipeli… │      ?       │ cache-managed… │ pixi.toml,      │        │
│                 │              │                │ pyproject.toml  │        │
│ example-uv-pro… │      ?       │ cache-managed… │ pyproject.toml, │        │
│                 │              │                │ uv.lock         │        │
└─────────────────┴──────────────┴────────────────┴─────────────────┴────────┘
```

The `?` in the *In sync tree* column means `CLAIN_SYNCED_ROOT` isn't set — set it to your synced-storage path (GDrive / OneDrive / Dropbox / iCloud Drive) to enable in-sync detection.

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
