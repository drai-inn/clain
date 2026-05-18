# AGENTS.md

This file is the agent-agnostic entry point for `clain`. Any AI agent landing in this repository should read it first.

## What this project is

`clain` helps a developer doing AI-assisted coding manage the storage cost of running many parallel workspaces — wherever those workspaces live (synced cloud storage like Google Drive / OneDrive / Dropbox / iCloud Drive, or a local disk under pressure). It does two things: classify workspaces by directory class (cache-managed, ephemeral, bytecode, workspace-source), and emit executable plans (delete-and-recreate, move-and-triage) that the developer reviews before any action runs.

See [INTENT.md](INTENT.md) for the full mission, goals, and non-goals. INTENT is the source of truth; if anything here disagrees with it, INTENT wins.

## For agents *using* this repo (driving the CLI on a developer's behalf)

This project follows the [Agent Skills](https://agentskills.io) format. Skills live in [`skills/`](skills/) and conform to the standard `SKILL.md` schema (YAML frontmatter + Markdown body). Any agent that implements Agent Skills discovers them automatically.

What the developer expects you to do:

1. Install dependencies: `pixi install`. Requires [Pixi](https://pixi.sh/) and Python 3.12+.
2. **Pick the mode.** For the everyday "one project I'm currently in" case, use **single-workspace mode** by passing `--here`. For the historical "I have a tree of workspaces accumulated under a synced drive" case, use the default tree mode. Single-workspace mode is the recommended entry point.
3. **Single-workspace mode:** `clain classify --here [PATH]` (defaults to cwd). Then `clain plan recreate --here [PATH] --dry`.
4. **Tree mode:** the developer sets `CLAIN_DEV_ROOT` (or passes a path positionally). **There is no baked-in default** — you must not invent one. Optionally `CLAIN_SYNCED_ROOT` to enable in-sync detection.
5. **Always use `--dry`** on `plan` invocations unless the developer has explicitly authorised execution. Execution is gated regardless.
6. Render the plan output (or the JSON via `--json`) for the developer to review. Surface the `unsafe_count` and any `unsafe_reason` strings prominently.
Skills bundled in this repo (each shells out to the CLI — no business logic in the skill body):

- [`skills/clain-version/`](skills/clain-version/) — reports the installed CLI version.
- [`skills/clain-classify/`](skills/clain-classify/) — runs a classification scan.
- [`skills/clain-plan-recreate/`](skills/clain-plan-recreate/) — produces a delete-and-recreate plan in dry mode.

For CLI walkthroughs aimed at end users, see [docs/USAGE.md](docs/USAGE.md).

## For agents *extending* this repo (contributing back)

The project is spec-driven. Every non-trivial change starts as a numbered spec under [`specs/`](specs/), reaches an *aligned* verdict from a goal-advisor pass, and lands via a feature-branch + PR. **The goal-advisor pattern is portable** — it is not Claude-Code-specific. Any agent (or human) can play that role by reading INTENT plus the proposed spec and returning the verdict structure documented in [CONTRIBUTING.md](CONTRIBUTING.md#the-goal-advisor-pattern).

The contributor workflow, PR template, quality gates, rule-base extension rules, and skill-authoring constraints all live in [CONTRIBUTING.md](CONTRIBUTING.md). That file is the authoritative source — this one summarises and links.

## Guardrails (summary; authoritative content in CONTRIBUTING.md)

The following are load-bearing. Authoritative wording, tests, and rationale live in [CONTRIBUTING.md](CONTRIBUTING.md); this section is a short orientation.

- **Phase gate.** `EXECUTE_ENABLED = False` in `src/clain/executor.py` blocks all real execution. Default-mode `clain plan` invocations render the plan, then error with a pointer to `--dry`. Do not edit the constant. See [CONTRIBUTING.md § The phase gate](CONTRIBUTING.md#the-phase-gate-load-bearing).
- **No personal information in defaults or examples.** This is a public repo. The developer's machine-specific paths live in `CLAIN_DEV_ROOT` at runtime, never in source. See [CONTRIBUTING.md § Anonymisation rule](CONTRIBUTING.md#anonymisation-rule-public-repo-discipline).
- **Read-only against ROOT.** Classify and plan commands must not write to paths under the scanned root. See [CONTRIBUTING.md § Read-only-against-ROOT discipline](CONTRIBUTING.md#read-only-against-root-discipline).
- **Spec-driven workflow.** No non-trivial change without an accepted spec. See [CONTRIBUTING.md § The spec-driven workflow](CONTRIBUTING.md#the-spec-driven-workflow).

## What `clain` will *not* do for you (and why)

- It will not delete, move, or modify any file under the scanned root. Plans are reviewed-then-acted-upon by the developer.
- It will not infer a dev root from the user's home directory or `~/Library/CloudStorage/...`. The developer must point you at the right tree explicitly.
- It will not pick a Python toolchain for a workspace that has `pyproject.toml` but no `pixi.toml` / `uv.lock`. Those plans are marked `safe_to_execute: false` with `unsafe_reason: "ambiguous Python toolchain — …"`. Surface that ambiguity to the developer rather than guessing.
