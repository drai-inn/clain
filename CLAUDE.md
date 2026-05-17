# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first, every session

1. [INTENT.md](INTENT.md) — what this project is for. Source of truth.
2. [specs/README.md](specs/README.md) — how work gets proposed and tracked (and the once-invoked renumber exception).
3. The list of active specs under `specs/` (any with status `draft` or `accepted`).

A `SessionStart` hook prints INTENT and active spec headers into context automatically.

## Architecture (authoritative: [specs/0001-architecture.md](specs/0001-architecture.md))

`clain` is a Python CLI (Pixi-managed) + a thin Claude Code plugin wrapper. The CLI is the contract — all behaviour is reachable there. The plugin orchestrates, prompts, and renders; it never holds business logic.

State and outputs live under `$XDG_STATE_HOME/clain/` (caches, plans, logs). Never inside the project working tree, never inside the Google-Drive-synced tree.

## Rule base (data-driven)

Class membership, manifest→recreate command mappings, and ecosystem placement advice live in [src/clain/rules.toml](src/clain/rules.toml) and are loaded by [src/clain/rules_loader.py](src/clain/rules_loader.py). The file is schema-versioned, hand- and genAI-editable, and packaged with the wheel. Adding a class or recreate rule is a normal source change subject to PR review per spec 0006. The loader refuses to load if the same directory name appears in more than one class.

## Current model (categorical, not quantitative)

Per [spec 0004](specs/0004-classification-scan.md), `clain` operates on directory **classes** rather than file sizes:

| Class | Examples | Action category |
|---|---|---|
| `cache-managed` | `node_modules`, `.venv`, `venv`, `site-packages` | delete + recreate |
| `ephemeral` | `dist`, `build`, `.next`, `.cache` | delete (regenerable by normal use) |
| `bytecode` | `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache` | delete (regenerable) |
| `workspace-source` | everything else | keep; move + triage if in synced tree |

The scan stops at the first class boundary — no recursion into `node_modules` etc. Runtime is seconds, not minutes.

## Plans are executable; execution is phase-gated

Per [spec 0005](specs/0005-executable-plan-model.md), `clain plan {recreate,move}` produces a JSON plan of actions (with `commands`, `safe_to_execute`, `unsafe_reason` per action). **Execution is the default**; `--dry` opts into preview-only.

While `EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py), every default-mode invocation renders the plan, then raises `ExecuteGateClosed`. The CLI catches it and points the user at `--dry`. Lifting the gate requires a named future spec — *00NN — Lift the dry-run gate* — which must specify rollback, audit, and additional safety mechanisms. Editing `EXECUTE_ENABLED` outside that workflow is a process violation.

Tests that enforce the gate:
- `test_cli_plan_recreate_default_attempts_execute_and_is_gated` — runtime check.
- `test_cli_plan_recreate_dry_exits_zero` — `--dry` bypasses the gate cleanly.
- `test_executor_module_imports_no_banned_modules` — static check on imports (no `subprocess`, network, clipboard, `shutil`).

## Spec-driven workflow

No non-trivial code without an accepted spec.

1. New work → `specs/NNNN-slug.md` per [specs/README.md](specs/README.md).
2. Before accepting → invoke the **goal-advisor** subagent (`.claude/agents/goal-advisor.md`). Verdicts: `aligned | drift | out-of-scope | spec-missing`.
3. Conflicts with INTENT → update INTENT deliberately rather than letting the spec broaden the mission.
4. Implementation commits reference the spec id.

Trivial changes (typos, formatting, doc fixes) do not require a spec.

## Git + GitHub workflow (per [spec 0006](specs/0006-git-workflow.md))

- The repo lives on GitHub as a public repo named `clain` (local directory remains `clain-me`).
- Every non-trivial change lands on a feature branch: `spec/NNNN-foo`, `fix/...`, `docs/...`.
- PR descriptions reference the spec id, include the goal-advisor verdict, and confirm tests/lint/typecheck pass.
- `main` is reserved for trivia direct-pushes; everything else goes through a PR.
- Spec status transitions happen in the same PR that lands the implementation.
- `gh` CLI is the standard interface for GitHub operations.

## The two `dev/` directories

- `~/dev/` — local, **not** synced. Future home for new workspaces.
- `~/Library/CloudStorage/GoogleDrive-…/Documents/dev/` — the legacy synced tree, the cleanup target.

Anything `clain` generates lives under `$XDG_STATE_HOME/clain/`. The repo itself (`~/dev/clain-me/`) must keep its `.gitignore` honest so that nothing transient ends up tracked.

## Guardrails wired in

- `SessionStart` hook (`.claude/settings.json`) surfaces INTENT and active spec status.
- `PreToolUse` hook flags `rm -rf` Bash commands for explicit approval.
- Phase gate in `src/clain/executor.py` prevents any execute path until spec 00NN lifts it.

## Tasks

```sh
pixi install                          # install env from pixi.toml
pixi run clain --version              # 0.0.1
pixi run clain classify ~/some/root   # categorical scan
pixi run clain plan recreate ~/... --dry             # preview only (safe default during phase gate)
pixi run clain plan move ~/... --dest ~/dev/ --dry   # preview move plan
pixi run -e dev test                  # pytest
pixi run -e dev lint                  # ruff check + format check
pixi run -e dev typecheck             # mypy --strict
```
