---
id: 0007
title: Agent-agnostic project handoff — Agent Skills adoption + audience-separated docs
status: shipped
goal: Goal 1 (Categorical visibility) and Goal 8 (Version-controlled, reviewable evolution) — extended by making the project pickup-able by any agent and any audience
---

## Problem

Today `clain` ships an Agent Skills-compatible skill (`plugin/skills/clain-version/SKILL.md`), but the file lives under `plugin/`, which by name and location reads as Claude-Code-specific. The other docs (CLAUDE.md especially) reinforce a Claude-Code-shaped frame even though the underlying CLI and skills are cross-agent.

Worse, the documentation currently conflates three distinct audiences:

1. **The standard CLI user** — runs `clain classify` / `clain plan recreate --dry` from a terminal, no agent involved.
2. **The agent user** — uses an AI agent (Claude Code, OpenCode, Cursor, Aider, Cline, Continue, Codex, whatever) that picks up skills/SKILL.md files and drives the CLI on their behalf.
3. **The developer / contributor** — extends the rule base, adds skills, writes specs, opens PRs.

INTENT goal 8 names "version-controlled, reviewable evolution" as a project goal. Without onboarding that distinguishes these audiences clearly, an agent or human landing in the repo has to derive the right path from context — exactly the kind of friction this spec exists to remove.

## Intent

Adopt the [Agent Skills](https://agentskills.io) format as the canonical, cross-agent skill surface. Promote skills to a top-level `skills/` directory so any agent that implements the spec discovers them. Restructure the docs around the three audiences. Ship two new skills (`clain-classify`, `clain-plan-recreate`) and keep the existing `clain-version` skill — all conforming to the format. Add an `AGENTS.md` at the repo root per the emerging convention so non-Claude agents have a natural entry point.

After this spec ships, a developer should be able to point any Agent Skills-compatible agent at this repo and have it usefully drive `clain` without any further onboarding.

## Spec

### 1. Top-level `skills/` directory (canonical home)

- Move `plugin/skills/clain-version/SKILL.md` → `skills/clain-version/SKILL.md`.
- Add two new skills (both call out to `clain` per the spec 0001 boundary rule — no business logic in the skill body):
  - `skills/clain-classify/SKILL.md` — invokes `clain classify` for a developer-supplied root, surfaces the rendered table.
  - `skills/clain-plan-recreate/SKILL.md` — invokes `clain plan recreate --dry` for a developer-supplied root and surfaces the rendered plan plus the path of the persisted JSON.
- Each skill conforms to the Agent Skills format: YAML frontmatter (`name`, `description`, optional `license` / `compatibility` / `metadata`) followed by Markdown body. Names match parent directory names (kebab-case).
- Skill `description` strings name the specific user phrasings that should trigger the skill (e.g. "use when the user asks for an inventory / classification of a dev workspace tree", "use when the user wants a deletion plan").

### 2. Claude Code plugin disposition

- Keep `plugin/.claude-plugin/plugin.json` as a Claude-Code-specific manifest. **Prefer manifest-level indirection** to the top-level `skills/` directory if the current Claude Code plugin loader supports it.
- If manifest indirection is not supported, fall back to a `plugin/skills/` directory **containing only symlinks** to `../../skills/<name>/`. The directory is then a compatibility shim, not a second source of truth.
- The old `plugin/skills/clain-version/SKILL.md` (real file, not symlink) must be removed in either case. `plugin/README.md` is rewritten to one paragraph stating: "This directory contains the Claude Code-specific manifest; the actual skills are in `../skills/` and conform to the Agent Skills spec at https://agentskills.io."

### 3. `AGENTS.md` (new, repo root)

The agent-agnostic entry point. Format: short prose, no Claude Code-isms. Sections:

- **What this project is** — one paragraph, lifted from INTENT.md mission.
- **For agents using this repo** — pointer to `skills/` and the Agent Skills spec. Tells the agent: `pixi install`, set `CLAIN_DEV_ROOT`, then invoke skills or shell out to `clain` directly.
- **For agents extending this repo** — pointer to INTENT.md, specs/, CONTRIBUTING.md. Names the goal-advisor pattern (any agent can play that role, not just Claude Code).
- **Guardrails** — short summary (one or two sentences each) of the phase gate, the no-personal-info-in-defaults rule, and the read-only-against-ROOT discipline. **Authoritative content lives in CONTRIBUTING.md** — AGENTS.md links there and does not restate the rules in detail. This avoids two sources of truth drifting.

### 4. `CONTRIBUTING.md` (new, repo root)

The developer/contributor audience. Lifts the relevant content from CLAUDE.md and spec 0006:

- The spec-driven workflow (draft → accepted → shipped → optional drop; goal-advisor verdict required for non-trivial changes).
- The feature-branch + PR practice (spec 0006), including the PR body template (spec ref, advisor verdict, acceptance bullets, gate results).
- How to run tests / lint / typecheck.
- How to extend `rules.toml` safely (add a class without colliding directory names; add a recreate rule with the right priority slot).
- The phase-gate rule: do not edit `EXECUTE_ENABLED` outside of the future spec 00NN — *Lift the dry-run gate*.

### 5. `README.md` (rewrite, repo root)

Short pitch + three paths in:

- *I just want to use the CLI* → quickstart + link to docs/USAGE.md.
- *I want my AI agent to drive this* → link to AGENTS.md and skills/.
- *I want to extend or contribute* → link to CONTRIBUTING.md.

No more conflation. No more burying the install commands behind project philosophy.

### 6. `CLAUDE.md` (prune — order matters)

**Author CONTRIBUTING.md and AGENTS.md first; prune CLAUDE.md last.** That way the universal content has moved before it is removed from CLAUDE.md, and the diff is reviewable (lines deleted from CLAUDE.md must appear in CONTRIBUTING.md or AGENTS.md).

After the prune, CLAUDE.md retains only Claude-Code-specific content: the `.claude/` developer config (hooks, the local goal-advisor agent definition), the `SessionStart` hook behaviour, the `PreToolUse` rm-rf flag. The file ends with "for the universal project brief, see AGENTS.md; for the contribution workflow, see CONTRIBUTING.md".

### 7. `docs/USAGE.md` (new)

CLI-user audience. Walkthrough format:

- Prereqs (Pixi, Python 3.12, `CLAIN_DEV_ROOT`).
- First-run sequence: `clain classify`, then `clain plan recreate --dry`, then `clain plan move --dest ~/dev/ --dry`.
- Reading the output: what `safe_to_execute: false` means, what `unsafe_reason` strings look like, where plans land on disk.
- Customising the rule base: where `rules.toml` lives, what each section does, how to add a class (link to CONTRIBUTING.md for the PR side of it).
- Common scenarios: "I have 30 Node workspaces under GDrive — what's the right sequence?"; "My venv just got recreated and broke — what happened and what to do."

### 8. `examples/` (new)

- `examples/classify-output.json` — a representative classify cache, anonymised path names.
- `examples/plan-recreate-output.json` — a representative recreate plan with a safe action and an unsafe action.
- `examples/plan-move-output.json` — a representative move plan with smoke-test preconditions.
- `examples/rules-extension.toml` — a snippet showing how to add a hypothetical class (e.g. `target/` for Rust) without breaking validation, with comments explaining what to put in a corresponding PR description.

All anonymised: use `~/dev/example-workspace` and `example.com` style placeholders, no personal info, no actual GDrive paths. **Grep-testable**: a unit test asserts that no file under `examples/` contains any of `GoogleDrive`, `CloudStorage`, `njon001`, `clain-me`, `nick@`, or any path beginning with `/Users/`. (Note: `~/Library/pnpm/store` and similar are canonical macOS placement advice — not personal info — so the ban list does *not* include `~/Library/` outright. Mirrors the way spec 0003 made the boundary rule grep-testable, but tuned to distinguish identifying paths from generic recommended paths.)

### 9. Verification

- `skills-ref validate ./skills/<each>` (or its current entrypoint) passes for every skill. If `skills-ref` is non-trivial to bootstrap inside Pixi, add a lightweight in-repo check that validates the frontmatter shape against the spec's field rules (name kebab-case length, description length, etc.). Don't block the spec on tooling that may not be in conda-forge yet.
- A new test `test_skills_frontmatter_valid` walks `skills/` and validates each `SKILL.md` against the field constraints.
- All gates (tests, ruff, mypy) continue to pass.

## Acceptance

- [ ] `skills/` at the repo root, with `clain-version`, `clain-classify`, `clain-plan-recreate` skill directories. Each contains a `SKILL.md` with valid Agent Skills frontmatter.
- [ ] `plugin/skills/` no longer exists. `plugin/.claude-plugin/plugin.json` references the top-level skills (via manifest config or symlink, whichever Claude Code supports).
- [ ] `AGENTS.md` at the repo root, written without Claude-Code-specific language.
- [ ] `CONTRIBUTING.md` at the repo root, covering spec workflow + PR template + gate requirements + rule-base extension how-to.
- [ ] `README.md` restructured around the three audiences. No section mixes more than one audience.
- [ ] `CLAUDE.md` pruned to Claude-Code-specific content; the universal pieces have moved to AGENTS.md / CONTRIBUTING.md.
- [ ] **Order assertion**: no universal content (workflow rules, phase gate, no-personal-info rule, rule-base extension how-to) remains *only* in CLAUDE.md. Spot-check by listing CLAUDE.md's contents and confirming each section is either Claude-Code-specific (hooks, `.claude/`) or already present in CONTRIBUTING.md/AGENTS.md.
- [ ] `plugin/skills/` either does not exist, or contains only symlinks back to `../../skills/<name>/` (compatibility shim only).
- [ ] `test_examples_anonymised` asserts no file under `examples/` contains any of the personal-info needles listed in section 8.
- [ ] `docs/USAGE.md` present and covers the first-run walkthrough + customisation paths.
- [ ] `examples/` present with the four files listed above. No personal information in any example.
- [ ] `test_skills_frontmatter_valid` exercises every skill and asserts the field constraints.
- [ ] PR description follows the spec 0006 template (spec ref, advisor verdict, acceptance bullets, gate results).

## Out of scope

- Implementing the Agent Skills `scripts/` / `references/` / `assets/` subdirectories per skill. Defer until a skill genuinely needs them.
- Publishing skills as a separate distributable (the skills-ref repo's `--package` mode). The skills live in this repo for now.
- Hooks shipped with the plugin (e.g. blocking risky deletions in user repos). Independent future spec.
- A `clain doctor` subcommand or its skill. Future spec.
- Translating any docs to non-English.
- Internationalising the rule base.

## Notes for future specs

- Spec 00NN — *Lift the dry-run gate* — is still the only spec that can flip `EXECUTE_ENABLED`. Nothing in 0007 changes that.
- A future *clain doctor* spec would add a skill `clain-doctor` once the subcommand exists.
- If we add many more skills, a `skills/README.md` with an index becomes worthwhile.
