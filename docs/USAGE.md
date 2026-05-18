# Using clain

A walkthrough for the standard CLI user. For the agent perspective, see [../AGENTS.md](../AGENTS.md). For the contributor perspective, see [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Prerequisites

- macOS or Linux. The synced-storage concern is more acute on macOS (Google Drive / iCloud Drive / OneDrive / Dropbox all surface as `~/Library/CloudStorage/...` or similar) but the tool is portable.
- [Pixi](https://pixi.sh/) — install with `brew install pixi` or per the Pixi docs.
- Python 3.12+ (Pixi will install this for you).

## First-time setup

```sh
git clone https://github.com/drai-inn/clain.git
cd clain
pixi install
```

There are two ways to use `clain`, depending on what you're trying to do:

- **Single-workspace mode** (`--here`) — for "I want to tidy *this* project". This is the everyday entry point.
- **Tree mode** (default) — for "I have a whole `dev/` directory full of accumulated workspaces and want to triage them". Set `CLAIN_DEV_ROOT` to the tree.

Start with single-workspace mode unless you specifically need the tree view.

---

## Single-workspace mode

Run `clain` inside the project you want to inspect. No env vars needed — `--here` defaults to the current working directory.

```sh
cd ~/some/project
pixi run clain classify --here
```

`clain` looks at the project root, identifies which manifests are present (`pyproject.toml`, `pixi.toml`, `package.json`, `pnpm-lock.yaml`, `uv.lock`, …), walks the project tree stopping at every class boundary (`node_modules/`, `.venv/`, `.pixi/`, `dist/`, `__pycache__/`, etc.), and produces this:

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

A few things to notice:

- **Manifests** at the top tell you what package manager `clain` will use to derive the recreate command (here: `pixi install` from `pixi.toml`).
- **`Sync placement: ?`** means you haven't set `CLAIN_SYNCED_ROOT`. If your project lives inside Google Drive / OneDrive / Dropbox / iCloud Drive, set that env var to your synced-storage root path so `clain` can tell you whether the project is sitting inside it.
- The **class branches** name what's regenerable. `.pixi/` is one entry (the scan stops there); `__pycache__` directories appear individually because they're shallower and don't have a containing wrapper.
- The **Next:** line is the *categorical* hint at what `plan recreate --here --dry` will produce.

Then ask for the plan:

```sh
pixi run clain plan recreate --here --dry
```

```text
                          Plan: recreate (7 actions)                          
┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Workspace   ┃ Type     ┃ Class        ┃ Target      ┃ Command(s)   ┃ Safe? ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━┩
│ example-wo… │ delete   │ cache-manag… │ ~/dev/examp │ rm -rf       │   ✓   │
│             │          │              │ le-workspac │ '~/dev/examp │       │
│             │          │              │ e/.pixi     │ le-workspace │       │
│             │          │              │             │ /.pixi'      │       │
│ example-wo… │ recreate │ cache-manag… │ ~/dev/examp │ pixi install │   ✓   │
│             │          │              │ le-workspac │              │       │
│             │          │              │ e           │              │       │
│ example-wo… │ delete   │ bytecode     │ ~/dev/examp │ rm -rf       │   ✓   │
│             │          │              │ le-workspac │ '~/dev/examp │       │
│             │          │              │ e/.pytest_c │ le-workspace │       │
│             │          │              │ ache        │ /.pytest_cac │       │
│             │          │              │             │ he'          │       │
│ (… more bytecode rows for .ruff_cache, .mypy_cache, two __pycache__ dirs …)│
└─────────────┴──────────┴──────────────┴─────────────┴──────────────┴───────┘

Workspaces: 1  Actions: 7  Unsafe: 0  saved to 
$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json
```

Read this top-down. The plan is **7 actions, 0 unsafe**, with `pixi install` as the single recreate step. The path you see on every row is the action target (this exemplifies a current presentation issue tracked by spec 0012 — the absolute path repeats; a near-future change will tree-group by workspace and show paths relative to a workspace `Location`).

A full plan JSON also lands in `$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json` — that's your audit artefact.

Use `--json` to pipe machine-readable output:

```sh
pixi run clain plan recreate --here --dry --json > my-plan.json
```

## Tree mode

For "I have a whole `dev/` directory full of stuff":

```sh
export CLAIN_DEV_ROOT=~/some/dev/tree
export CLAIN_SYNCED_ROOT="$HOME/Library/CloudStorage/..."   # optional but recommended
pixi run clain classify
```

In tree mode `clain` enumerates each workspace at depth-1 under `CLAIN_DEV_ROOT`:

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

The `In sync tree` column reports `✓` / `·` / `?`:
- `✓` — workspace is under `CLAIN_SYNCED_ROOT` (likely candidate for `clain plan move`)
- `·` — workspace is *not* under the synced root
- `?` — `CLAIN_SYNCED_ROOT` is unset, so `clain` can't say

Drill into one workspace's full class-tag listing with `--workspace NAME`. Note that `--workspace` is tree-mode only — `--here` and `--workspace` are mutually exclusive.

The two plan commands in tree mode are:

- `clain plan recreate --dry` — per workspace, the delete-and-recreate actions across the tree.
- `clain plan move --dest ~/dev/ --dry` — for workspaces marked `in_sync_tree: true`, the rsync-out + smoke-test plan.

## Reading the output

What `safe_to_execute: false` means (look for it in `--json` output or the red "Unsafe" footer):

- `ambiguous Python toolchain — workspace has pyproject.toml but no pixi.toml / uv.lock / poetry.lock` — pick a toolchain and add its lockfile, then re-run.
- `package.json without a lockfile — recreate would resolve fresh versions` — non-reproducible. Commit a lockfile first.
- `no recognised manifest — investigate manually` — workspace has cache-managed subtrees but no manifest `clain` understands.

## Customising the rule base

Class membership, manifest→recreate command mappings, and ecosystem placement advice live in [`src/clain/rules.toml`](../src/clain/rules.toml). It's a hand-editable (or genAI-editable) TOML file with a schema-version field.

You can fork the repo and adjust this file to suit your environment — adding a class for Rust's `target/` directories, for example, or a recreate rule for an internal package manager. The loader validates structure on load; duplicate directory names across classes or between classes and `[prune]` will refuse to load.

For the PR-side workflow of contributing such a change back, see [../CONTRIBUTING.md § Extending the rule base](../CONTRIBUTING.md#extending-the-rule-base-srcclainrulestoml).

## Common scenarios

### "I'm in a project and just want to know what's regenerable"

```sh
cd ~/some/project && pixi run clain classify --here
```

Done. The output tells you what's a regenerable cache and what's source. The `Next:` line tells you the recreate command.

### "I have 30 Node workspaces under a synced drive — what's the right sequence?"

1. `export CLAIN_SYNCED_ROOT=...` (the synced storage root).
2. `clain classify --refresh` — see which workspaces are in the sync tree.
3. `clain plan move --dest ~/dev/ --dry` — preview moves out of the sync tree.
4. For each workspace you want to migrate: run the rsync command from the plan by hand.
5. `clain classify ~/dev/` — re-classify against the new local root.
6. `clain plan recreate ~/dev/ --dry` — preview the dependency rehydration.
7. For each workspace: run the recreate command by hand.

The `rationale` field on each recreate action includes placement advice (e.g. pnpm's store should live at `~/Library/pnpm/store`, not in-project). Apply that once, globally, before running any recreate commands.

### "My venv just got broken — what happened?"

If you moved a workspace containing `.venv` without first deleting and recreating: the venv's internal `pyvenv.cfg` and `bin/*` shebangs embed the old absolute path. The fix is `rm -rf .venv` followed by `pixi install` (or `uv sync` / `poetry install`, depending on the toolchain).

The move plan flags this in `preconditions` precisely so you don't move venvs by accident.

### "How do I know if a plan is safe to act on?"

Two signals:

- `summary.unsafe_count == 0` in the JSON, or no red Unsafe actions table at the head of the rendered output.
- Every action's `safe_to_execute: true`.

If anything is `false`, the `unsafe_reason` tells you what's missing. Fix it (pick a toolchain, add a lockfile, etc.) and re-run.

## Where things live

| What | Where |
|---|---|
| Classify caches | `~/.local/state/clain/classify/<root-hash>.json` |
| Plan artefacts | `~/.local/state/clain/plans/<kind>-<UTC>.json` |
| Run logs | `~/.local/state/clain/logs/{classify,plan}.log` |
| Rule base | `src/clain/rules.toml` (in the repo) |

Nothing is ever written under your scanned root. That is enforced by tests, not just convention.

## Captures and reproducibility

The terminal outputs shown above are real Rich captures generated by [`examples/capture.py`](../examples/capture.py) against anonymised fixture workspaces. Re-running that script after a CLI change regenerates the captures — they're not screenshots and they don't go stale silently.
