# clain

Manage local AI-dev workspaces — categorical visibility, deliberate execution.

See [INTENT.md](INTENT.md) for the project's mission and goals, and [specs/](specs/) for the active design specs. Architecture is fixed by [spec 0001](specs/0001-architecture.md): a portable Python CLI named `clain` (Pixi-managed) plus a thin Claude Code plugin wrapper.

## What it does

`clain` reads your AI-dev workspace tree and produces *executable plans* for tidying it up — without executing them yet.

1. **Classify** — recognise the kind of each subtree (cache-managed, ephemeral, bytecode, or workspace-source). Stops at class boundaries; no expensive file walks.
2. **Plan recreate** — for cache-managed / ephemeral / bytecode subtrees: a delete + recreate plan, with the recreate command derived from the workspace's manifest (`pixi.toml` → `pixi install`, `pnpm-lock.yaml` → `pnpm install --frozen-lockfile`, etc.).
3. **Plan move** — for workspaces sitting in a synced tree (e.g. Google Drive): a move plan to relocate them to a local home, with integrity smoke tests (venvs embed absolute paths, lockfiles, `.envrc`, docker-compose) flagged as preconditions.

Plans are JSON artefacts saved to `$XDG_STATE_HOME/clain/plans/`. Each action has `commands`, `safe_to_execute`, and `unsafe_reason` fields, so you can read what would happen, why, and where it's risky — before anyone touches anything.

## Phase-gated execution

`--execute` exists as a flag but is currently rejected by a development-phase gate (`EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py)). Lifting it requires a future spec named *00NN — Lift the dry-run gate*, which must specify rollback, audit, and additional safety mechanisms. The dry-run output stays useful regardless — copy/paste commands as needed.

## Quickstart

Requires [Pixi](https://pixi.sh/) and Python 3.12+.

```sh
pixi install
export CLAIN_DEV_ROOT=~/some/dev/tree   # required — no personal-info default baked in
pixi run clain classify
pixi run clain plan recreate
pixi run clain plan move --destination ~/dev/
```

## Subcommands

```
clain classify [ROOT] [--json] [--workspace NAME] [--refresh] [--no-cache]
clain plan recreate [ROOT] [--json] [--execute]
clain plan move [ROOT] [--destination DIR] [--json] [--execute]
clain plan explain ACTION_ID [--plan FILE]
```

All accept `ROOT` positionally, fall back to `$CLAIN_DEV_ROOT`, and error if neither is set. Use `$CLAIN_SYNCED_ROOT` to mark a separate path as "the synced tree" for the `in_sync_tree` test (defaults to `CLAIN_DEV_ROOT`).

## State location

Everything `clain` writes lives under `$XDG_STATE_HOME/clain/` (default `~/.local/state/clain/`):

- `classify/<root-hash>.json` — classification cache (24h TTL).
- `plans/<kind>-<UTC>.json` — every generated plan, timestamped.
- `logs/{classify,plan}.log` — audit lines.

Nothing is written under the scanned root. The full mutation-vector ban list is enforced by tests.

## Development

```sh
pixi run -e dev test          # pytest
pixi run -e dev lint          # ruff check + format check
pixi run -e dev fmt           # ruff format
pixi run -e dev typecheck     # mypy --strict
```

## Status

Specs 0001–0005 shipped; spec 0006 (git/GitHub workflow) is the workflow this repo now follows.
