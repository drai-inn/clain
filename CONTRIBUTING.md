# Contributing to clain

This guide is for **developers extending or contributing to `clain`**. If you're a CLI user looking to *run* the tool, see [docs/USAGE.md](docs/USAGE.md). If you're driving `clain` from an AI agent, see [AGENTS.md](AGENTS.md).

## Source of truth

- [INTENT.md](INTENT.md) — what the project is for. Every change must trace to a goal here.
- [specs/](specs/) — the design audit trail. Numbered, dated, with status transitions captured in git history.
- Every shipped spec is authoritative for its slice of the system. When two sources disagree, the spec wins.

## The spec-driven workflow

**No non-trivial change without an accepted spec.** Trivial = typos, formatting, doc clarifications, dependency bumps.

1. **Propose** — create `specs/NNNN-short-slug.md` using the template in [specs/README.md](specs/README.md). Status: `draft`.
2. **Goal-advisor verdict** — invoke the goal-advisor pattern (see below) and record the verdict. If the verdict is `drift` or `out-of-scope`, tighten the spec or update INTENT before proceeding.
3. **Accept** — flip status to `accepted`. Implementation begins.
4. **PR** — feature branch (`spec/NNNN-…`, `fix/…`, `docs/…`), PR title referencing the spec, body following the template below. Direct pushes to `main` are reserved for trivia.
5. **Ship** — when the PR merges, the same commit flips the spec status to `shipped`.

If a spec is abandoned mid-flight, flip its status to `dropped` with a one-sentence reason in the frontmatter.

## The goal-advisor pattern

Any AI agent (or human reviewer) can play this role. It is **not Claude-Code-specific** — the `.claude/agents/goal-advisor.md` file is one instantiation, but the pattern is portable. The advisor reads INTENT and the proposed spec, and returns a verdict in this exact structure:

```
Spec NNNN
Verdict: <aligned | drift | out-of-scope | spec-missing>
Goal(s) it serves: <list>
Reasoning: <2-5 sentences quoting INTENT / the spec where wording matters>
Recommended next step: <proceed | tighten spec NNNN | write new spec | update INTENT | stop and discuss>
```

Verdict definitions:
- **aligned** — change clearly serves a stated goal and respects accepted constraints.
- **drift** — touches the right area but exceeds what was agreed.
- **out-of-scope** — doesn't serve any goal in INTENT.
- **spec-missing** — refers to behaviour not yet specified.

The advisor's verdict is pasted into the PR description as evidence.

## PR template

PRs auto-populate from [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md), so you don't have to copy the template below by hand — it's the source of truth that GitHub renders into the PR body.

The template body, for reference:

```markdown
## Spec reference

Lands [specs/NNNN-slug.md](specs/NNNN-slug.md) as `shipped` (or amends it; or addresses fix XYZ).

## Goal-advisor verdict

> Spec NNNN
> Verdict: aligned
> Goal(s) it serves: …
> Reasoning: …
> Recommended next step: proceed

## Acceptance bullets

- [x] (each acceptance bullet from the spec, with evidence or a link)

## Checks

- `pixi run -e dev test` → N passed
- `pixi run -e dev lint` → clean
- `pixi run -e dev typecheck` → clean
```

## Quality gates (must pass before merge)

```sh
pixi run -e dev test          # pytest — all tests must pass
pixi run -e dev lint          # ruff check + format check
pixi run -e dev typecheck     # mypy --strict
```

CI integration is a future spec; for now the gates run locally and the PR body asserts they passed.

## The phase gate (load-bearing)

Spec 0005 introduced a development-phase gate: `EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py) blocks real execution of any plan. **Editing this constant is a process violation** unless you are landing the named future spec — *00NN — Lift the dry-run gate* — which must specify rollback, audit requirements, and additional safety mechanisms.

Tests enforce the gate:
- `test_cli_plan_recreate_default_attempts_execute_and_is_gated` — runtime check.
- `test_executor_module_imports_no_banned_modules` — static check on `clain.executor` imports.

If your PR removes either of these tests, that is also a process violation.

## Extending the rule base (`src/clain/rules.toml`)

The rule base is data, not code. Adding a class, a recreate rule, or a placement is a normal source change subject to PR review. The loader (`src/clain/rules_loader.py`) validates structure on load:

- **Adding a class**: append a `[[classes]]` block with `name`, `description`, `default_action` (`delete` or `delete-and-recreate`), and `directory_names`. The loader refuses to load if any directory name overlaps with an existing class.
- **Adding a recreate rule**: append a `[[recreate_rules]]` block with `manifest`, `command`, `ecosystem`, `priority` (lower = preferred match), and `safe: true|false`. If `safe: false`, include `unsafe_reason`. Pick the priority deliberately — lower than existing entries you want it to override, higher than entries that should still win.
- **Adding a placement**: append a `[[placements]]` block per the existing pattern. Cite the canonical doc URL.

When you change the rule base in a PR, the PR description should explain *why* the addition is needed (e.g. "Rust workspaces are common in the synced tree; `target/` directories regularly hit several GiB"). The goal-advisor verdict should confirm the addition serves an INTENT goal.

## Anonymisation rule (public repo discipline)

This is a public repository. **No personal information may appear in source defaults, `examples/`, or public docs.** That means: no email addresses, no tenant-bearing synced-storage paths (the format used by GDrive / OneDrive that embeds a user identifier after a hyphen), no absolute home paths, no machine-specific hostnames. Tests enforce this via `tests/test_examples_anonymised.py` against `examples/` and the public docs (README, AGENTS, CONTRIBUTING, SECURITY, CHANGELOG, docs/USAGE). The `CLAIN_DEV_ROOT` env var carries machine-specific configuration at runtime; do not encode it in source.

## Read-only-against-ROOT discipline

The classify, plan, and any future scanning subcommand must not write to any path under the scanned ROOT. The full mutation-vector ban list is documented in [specs/0004-classification-scan.md](specs/0004-classification-scan.md). Tests enforce this for `classify` (`test_classify_module_does_not_modify_root`).

## Adding a skill

Skills live in `skills/<skill-name>/SKILL.md` per the [Agent Skills](https://agentskills.io) format. The skill body **must not contain business logic** — it orchestrates and renders, but the real work is a CLI subcommand. Specifically:

- The skill body shells out to `clain <subcommand>` (or `pixi run clain <subcommand>` in a dev context).
- The skill does not parse Python source, import Python modules, or duplicate version strings or class names.
- If the skill needs a behaviour the CLI doesn't expose, add a CLI subcommand first (via a spec), then have the skill call it.

This rule comes from spec 0001 and is checked by reading the skill body.

## Repository layout

```
clain-me/
├── INTENT.md                      # Mission, goals, non-goals (source of truth)
├── README.md                      # Audience-routed overview
├── AGENTS.md                      # Agent-agnostic entry point
├── CONTRIBUTING.md                # This file
├── CLAUDE.md                      # Claude Code-specific developer notes
├── LICENSE                        # MIT
├── pixi.toml                      # Env definition
├── pyproject.toml                 # Package metadata + tooling config
├── specs/                         # The design audit trail
├── src/clain/                     # CLI source (the contract)
│   ├── rules.toml                 # Rule base — class membership, recreate rules, placements
│   └── rules_loader.py            # Validation + typed access to rules.toml
├── skills/                        # Cross-agent skills (Agent Skills format)
├── plugin/                        # Claude Code-specific manifest
├── docs/                          # User-facing walkthroughs
├── examples/                      # Sample inputs/outputs (anonymised)
└── tests/                         # pytest
```

## Getting started as a contributor

```sh
pixi install                       # default env
pixi install -e dev                # dev env
pixi run -e dev test               # confirm baseline is green
```

Read [INTENT.md](INTENT.md), skim [specs/](specs/) in order, then pick a spec to amend or propose a new one.
