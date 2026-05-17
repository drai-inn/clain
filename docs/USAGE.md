# Using clain

A walkthrough for the standard CLI user. For the agent perspective, see [../AGENTS.md](../AGENTS.md). For the contributor perspective, see [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Prerequisites

- macOS or Linux (the synced-tree concern is macOS-specific but the tool is portable).
- [Pixi](https://pixi.sh/) — install with `brew install pixi` or per the Pixi docs.
- Python 3.12+ (Pixi will install this for you).

## First-time setup

```sh
git clone https://github.com/drai-inn/clain.git
cd clain
pixi install
```

Decide which root you want to operate on, then export it:

```sh
export CLAIN_DEV_ROOT="$HOME/some/dev/tree"
```

There is no baked-in default — this is deliberate, so the public repo doesn't carry anyone's personal paths.

## The first run: classify

```sh
pixi run clain classify
```

You'll see a Rich table with one row per workspace under `CLAIN_DEV_ROOT`:

| Workspace | In sync tree | Class tags | Manifests | Errors |
|---|---|---|---|---|
| alpha-node | ✓ | cache-managedx2 | package.json, pnpm-lock.yaml | |
| beta-pixi | ✓ | cache-managedx2 | pixi.toml | |

Reading the columns:

- **Workspace** — depth-1 child directory of the root.
- **In sync tree** — whether the workspace itself sits inside `CLAIN_SYNCED_ROOT` (defaults to `CLAIN_DEV_ROOT`). Workspaces under a synced root are candidates for `clain plan move`.
- **Class tags** — counts of subtrees per class (`cache-managedx2` means two cache-managed dirs, e.g. `node_modules` plus `.venv`). The scan stops at each class boundary — it never recurses into `node_modules`, `.venv`, etc.
- **Manifests** — files present at the workspace root that drive `clain plan recreate`'s command derivation (`pixi.toml`, `pnpm-lock.yaml`, etc.).
- **Errors** — count of read errors during the scan (usually permission issues; the row is still produced).

If you want machine-readable output:

```sh
pixi run clain classify --json > classify.json
```

The result is cached under `~/.local/state/clain/classify/<root-hash>.json` for 24 hours. Pass `--refresh` to force a fresh scan, or `--no-cache` to bypass cache for one run.

## The recreate plan

Once you have a classify cache, produce a delete-and-recreate plan:

```sh
pixi run clain plan recreate --dry
```

Always pass `--dry` for now — execution is gated behind a development-phase guard documented in [../CONTRIBUTING.md](../CONTRIBUTING.md#the-phase-gate-load-bearing).

The output has three parts:

1. **Unsafe actions table** (if any) — red-titled, lists each action that can't be safely executed and why. Common reasons:
   - `ambiguous Python toolchain — workspace has pyproject.toml but no pixi.toml / uv.lock / poetry.lock` — the workspace declares Python intent but doesn't disambiguate which tool drives installs. You decide (pick a toolchain and add its lockfile), then re-run.
   - `package.json without a lockfile — recreate would resolve fresh versions` — Node project without a lockfile, so recreate could pull non-reproducible versions.
   - `no recognised manifest — investigate manually` — the workspace has cache-managed subtrees but no manifest the rule base understands.

2. **Plan table** — one row per action. Each row has `workspace`, `type` (`delete` or `recreate`), `class`, `target` path, the actual shell `commands`, and a safe/unsafe marker.

3. **Footer** — workspace count, total action count, unsafe count, and the path to the persisted JSON plan under `~/.local/state/clain/plans/recreate-<UTC>.json`. The plan file is your audit record; nothing about your workspaces has changed.

## The move plan

For workspaces that sit inside a synced tree and should be relocated to a local home:

```sh
pixi run clain plan move --dest ~/dev/ --dry
```

For each in-sync workspace, the plan emits a smoke-test step (read-only checks of `pyvenv.cfg`, `.envrc`, `docker-compose.*`) and a move step (`rsync -a --delete` excluding cache-managed/ephemeral/bytecode directories). The smoke-test result populates `preconditions` on the move action — for instance, "venv directories embed absolute paths in pyvenv.cfg and console scripts — delete-and-recreate via `clain plan recreate`, do not move."

The expected sequence in a real migration:

1. `clain plan move --dry` — see what would move.
2. Run the move commands by hand for the workspaces you've reviewed.
3. `clain classify` against the new local root.
4. `clain plan recreate --dry` against the new root — review the recreate commands.
5. Run the recreate commands by hand.

The tool itself never performs steps 2, 5. Until spec 00NN lifts the gate, that boundary is absolute.

## Explaining a single action

Every action has a 12-character `id`. To see the full record:

```sh
pixi run clain plan explain <ACTION_ID>
```

By default this reads the most recent plan under `~/.local/state/clain/plans/`. To target a specific plan: `--plan ~/.local/state/clain/plans/recreate-2026-05-18T....json`.

## Customising the rule base

Class membership, manifest→recreate command mappings, and ecosystem placement advice live in [`src/clain/rules.toml`](../src/clain/rules.toml). It's a hand-editable (or genAI-editable) TOML file with a schema-version field.

You can fork the repo and adjust this file to suit your environment — adding a class for Rust's `target/` directories, for example, or a recreate rule for an internal package manager. The loader validates structure on load; duplicate directory names across classes will refuse to load.

For the PR-side workflow of contributing such a change back, see [../CONTRIBUTING.md § Extending the rule base](../CONTRIBUTING.md#extending-the-rule-base-srcclainrulestoml).

## Common scenarios

### "I have 30 Node workspaces under GDrive — what's the right sequence?"

1. `clain classify` — see which are in the sync tree.
2. `clain plan move --dest ~/dev/ --dry` — preview moves out of the sync tree.
3. For each workspace you want to migrate: run the rsync command from the plan by hand.
4. `clain classify ~/dev/` — re-classify against the new root.
5. `clain plan recreate ~/dev/ --dry` — preview the dependency rehydration.
6. For each workspace: run the `pnpm install --frozen-lockfile` (or equivalent) by hand.

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
