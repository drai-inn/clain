---
id: 0005
title: Executable plan model — delete+recreate and move+triage actions, execute by default, gated; `--dry` opts into preview
status: shipped
goal: Goal 2 (Deliberate execution) and Goal 3 (Two action categories, fully covered); supports Goal 4 (Deliberate consolidation)
supersedes: previously-shipped 0005 (Duplication detection) — dropped wholesale; previously-shipped 0006 (Recommendations) — superseded by this executable model
amended: 2026-05-18 — flag semantics inverted. Execution is the **default**; `--dry` opts into preview. `--execute` removed. `--destination` → `--dest`. Phase gate unchanged.
---

## Flag semantics (amendment, 2026-05-18)

The original spec said "Plans default to dry-run; `--execute` opts in." That is reversed:

- **Default** — render the plan, persist it, then attempt execution. While `EXECUTE_ENABLED = False`, this attempt raises `ExecuteGateClosed`; the CLI catches it and renders a Rich error pointing the user at `--dry`. The user always sees their plan before the gate error fires.
- **`--dry`** — render the plan, persist it, **stop**. No execution attempt, no gate error. The safe-preview mode.
- **`--execute` removed.** Execution is implicit in the default behaviour. No flag is required to opt into the primary capability once the gate is lifted.

The phase-gate invariant is unchanged: while `EXECUTE_ENABLED = False`, no real execution can occur regardless of flag posture. The future spec 00NN — *Lift the dry-run gate* — remains the only way to enable real execution. The flag change is a CLI-surface change only.

Related: `--destination` shortened to `--dest`. Multi-word flags remain only where no good single-word form exists (e.g. `--no-cache`, `--workspace`).

Additional acceptance bullets:

- [x] `clain plan recreate` with no flags renders the plan, then fails with the gate error pointing at `--dry`.
- [x] `clain plan recreate --dry` renders the plan and exits 0.
- [x] `clain plan move --dest <path>` is the spelling; `--destination` is not accepted.
- [x] `--execute` is not a recognised flag.
- [x] Tests updated: `test_cli_plan_recreate_default_attempts_execute_and_is_gated` and `test_cli_plan_recreate_dry_exits_zero` replace the old `test_cli_plan_recreate_execute_blocked`.

## Problem

After classification (0004), the developer knows what each subtree is. They still need a *plan* — a concrete, reviewable, auditable record of actions per workspace — and the ability to run that plan once they trust it. The previous 0006 emitted descriptive prose with no execution path, which was the right development-stage stance but wrong as a permanent model: it leaves the developer to translate "you should re-install with pnpm" into actual commands, repeatedly, by hand. The eventual product is a tool that can *execute* the plan it produces, with `--dry-run` as the safe default and `--execute` required to act. Right now, execution itself stays disabled — but the plan format must already be executable so that lifting the gate is a single named spec rather than a rewrite.

## Intent

Two `clain plan` subcommands that consume the classification cache and emit a structured, executable plan:

- **`clain plan recreate`** — for `cache-managed`, `ephemeral`, and `bytecode` subtrees: a *delete + recreate* plan. Recreate commands are derived from the workspace's manifests.
- **`clain plan move`** — for workspace source code being relocated (synced tree → `~/dev/`, or to an archive): a *move + triage* plan including integrity smoke tests.

Both produce the same artefact shape: a JSON plan + a Rich-rendered review surface. Both honour a single execution semantics: `--dry-run` (default) renders and validates the plan; `--execute` is recognised but currently rejected by an explicit **phase gate**. A future named spec — *Lift the dry-run gate* (referred to here as 00NN) — is the only thing that can flip the gate.

## Spec

### Plan record format (schema v1)

A plan is a JSON document with this shape:

```json
{
  "schema": 1,
  "kind": "recreate" | "move",
  "generated_at": "<UTC ISO>",
  "root": "<resolved root>",
  "classify_cache_id": "<root hash + ended_at of the classify scan it was built from>",
  "actions": [<Action>, ...],
  "summary": { "workspace_count": N, "action_count": M, "unsafe_count": K }
}
```

Each `Action` is:

```json
{
  "id": "<stable hash>",
  "workspace": "<name>",
  "type": "delete" | "recreate" | "move" | "smoke-test",
  "target": "<absolute path>",
  "class": "cache-managed" | "ephemeral" | "bytecode" | "workspace-source",
  "rationale": "<short sentence citing the class and the principle>",
  "commands": ["<executable shell-quoted command>", ...],
  "preconditions": [<Precondition>, ...],
  "safe_to_execute": true | false,
  "unsafe_reason": null | "<short string>"
}
```

The `commands` array is **the executable logic** — a small, ordered list of fully-formed shell commands. Where a command cannot be determined deterministically (e.g. a Python project with neither `pyproject.toml`/`pixi.toml`/`uv.lock`/`requirements.txt`), the action carries `safe_to_execute: false` and `unsafe_reason` names what is missing. The executor refuses to act on unsafe actions even when `--execute` is allowed.

### Recreate plan (`clain plan recreate`)

For each workspace, for each `cache-managed`/`ephemeral`/`bytecode` subtree found by classify:

1. Emit a **delete** action: `rm -rf <target>`. Marked `safe_to_execute: true` only when (a) the subtree is fully contained inside a workspace under a known manifest, and (b) the recreate action is also safe.
2. Emit a **recreate** action, only for `cache-managed` (ephemeral and bytecode are regenerated by normal use, not by an explicit command). The recreate command is derived from manifests present in the workspace root:
   - `pixi.toml` → `pixi install`
   - `uv.lock` → `uv sync`
   - `pyproject.toml` (without `pixi.toml` or `uv.lock`) → `pip install -e .` (marked `safe_to_execute: false` with a `unsafe_reason: "ambiguous Python toolchain — pick pixi/uv/poetry explicitly"`)
   - `requirements.txt` → `pip install -r requirements.txt` (same caveat — unsafe until toolchain is named)
   - `pnpm-lock.yaml` → `pnpm install --frozen-lockfile`
   - `package-lock.json` → `npm ci`
   - `yarn.lock` → `yarn install --frozen-lockfile`
   - `package.json` without a lockfile → `safe_to_execute: false`, `unsafe_reason: "no lockfile — recreate would resolve fresh versions"`

The `placements.toml` data file in the repo provides per-ecosystem cache-store advice (where pnpm's store should live, etc.); the recreate plan attaches the relevant pointer in `rationale` so the developer sees the placement guidance alongside the recreate command.

### Move plan (`clain plan move`)

For each workspace marked `in_sync_tree: true` by classify, emit:

1. A **smoke-test** action that reads the workspace root's manifests + a small fixed set of integrity-relevant files (`pyvenv.cfg` if a `.venv` is present, `.envrc`, `docker-compose.yml`, `docker-compose.yaml`, top-level files matching `*.code-workspace`). Checks for:
   - Absolute paths embedded in `pyvenv.cfg` (always present — flags the workspace as "venv must be deleted-and-recreated post-move, not moved with the source").
   - Absolute paths referencing the workspace's *current* location inside `.envrc` or `docker-compose.*`.
   - Presence of a lockfile (so the recreate plan can rehydrate post-move).
   - Broken symlinks at workspace depth ≤ 2.
   The smoke-test action's `commands` array is empty (the executor performs the checks itself); its `safe_to_execute` is always `true` and the result populates downstream `preconditions`.

2. A **move** action: `rsync -a --delete <source>/ <destination>/` (rsync chosen for its handling of permissions, symlinks, and resumability). The action lists, in `preconditions`, the smoke-test findings — e.g. *"venv at .venv must be deleted before move; will be recreated by `clain plan recreate` after"*.

Move plans target `~/dev/<workspace-name>/` by default; configurable via `--destination`. They explicitly do not push to GitHub or any other remote.

### Execution semantics

- `--dry-run` (default): render the plan to stdout (Rich) or `--json`. Validate every action's `safe_to_execute` and surface unsafe ones in a separate red-titled table at the head of the output. Persist the plan to `$XDG_STATE_HOME/clain/plans/<kind>-<UTC>.json`.
- `--execute`: currently fails with a Rich error that names the **phase gate** and the doc string in `clain.executor`. The gate is implemented as a module-level constant `EXECUTE_ENABLED: bool = False` plus a runtime check; flipping it requires editing source code, which is itself a PR-reviewable act. The future spec 00NN — *Lift the dry-run gate* — is named in the error message and must include: who can flip it, what additional safety mechanisms come with it, what rollback path exists, and any environment requirement (e.g. signed git commit, clean working tree).
- `--explain ACTION_ID`: prints the full action record with its rationale, manifest evidence, and the source spec section it comes from.

### Logging and audit

Every plan generation appends one line to `$XDG_STATE_HOME/clain/logs/plan.log` and persists the full JSON plan to `$XDG_STATE_HOME/clain/plans/`. When `--execute` is eventually enabled by spec 00NN, every action attempt appends a corresponding line to `$XDG_STATE_HOME/clain/logs/execute.log` linked to the plan id. Together these are the audit trail INTENT goal 2 requires.

### Phase-gate invariant (current development phase)

While `EXECUTE_ENABLED = False`:

- No code path in `clain.executor` reachable from `clain plan` may invoke `subprocess.*`, `os.system`, `os.exec*`, `os.posix_spawn*`, network I/O, clipboard handoff, or any filesystem-mutating syscall against any path derived from `ROOT` or `--destination`. Writes are permitted only to `$XDG_STATE_HOME/clain/plans/` and `$XDG_STATE_HOME/clain/logs/`.
- A unit test (`test_phase_gate_blocks_execute`) asserts that invoking `clain plan recreate --execute` exits non-zero with the gate's named error.
- A static import-graph test asserts the executor module imports none of the banned modules.

These invariants are **additive** until spec 00NN authorises lifting them.

### Placements data file

`src/clain/placements.toml` (or `placements.py` module) is the curated table of per-ecosystem store locations and the env var / config command needed to set them. Updating it is a normal source change subject to the same PR review as code. Initial entries: pnpm, Pixi, uv/Rye, Poetry (legacy). Each entry cites the canonical doc URL.

## Acceptance

- [ ] `clain plan recreate` against a classified root emits a Rich table + a JSON plan persisted under `$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json`.
- [ ] `clain plan move` does the same for workspaces marked `in_sync_tree: true`, with a smoke-test pre-step per workspace.
- [ ] Every action carries `safe_to_execute` plus `unsafe_reason` when false; the renderer surfaces unsafe actions in a red-titled table.
- [ ] `clain plan recreate --execute` (and the `move` variant) exits non-zero with an error naming the phase gate, the future spec 00NN, and the source location to edit.
- [ ] Static import-graph test confirms the executor module imports no banned modules while `EXECUTE_ENABLED = False`.
- [ ] No personal information appears in any default; the `CLAIN_DEV_ROOT` discipline from 0004 carries through.
- [ ] Tests cover: each manifest → command derivation; the "no lockfile → unsafe" rule; the venv-must-be-recreated smoke test; the dry-run-by-default behaviour; the phase gate.
- [ ] `placements.toml` exists, covers pnpm/Pixi/uv/Poetry, and is referenced by the recreate plan's `rationale` strings.

## Out of scope

- Lifting the phase gate. That is spec 00NN's job. Even when this spec is `shipped`, no execution actually happens.
- Multi-host or multi-machine plans.
- Plan diffing / replay (rerunning a plan against a moved tree). Future spec if the practice emerges.
- Active detection of installed-tool versions or current cache-store locations. That is the *doctor* spec referenced previously (not yet numbered).
- Push-button restoration of a deleted dependency tree (the recreate plan emits the commands; the developer or 00NN runs them).
- Interactive prompts. Plans are reviewed by reading; there is no `clain plan --interactive` mode in v1.
