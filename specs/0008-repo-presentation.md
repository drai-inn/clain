---
id: 0008
title: GitHub repository presentation + discoverability for AI-dev workspace storage audience
status: shipped
goal: Goal 8 (Version-controlled, reviewable evolution) — extended to the public-facing surface; supports project visibility to the AI-dev audience that hits the workspace-storage problem this project addresses
---

## Problem

The repo is public at https://github.com/drai-inn/clain, but its GitHub presentation gives no signal about who it's for or what it does. Specifically:

- Repo description, topics, and homepage URL are empty.
- Wiki is enabled but redundant (we have `docs/`).
- Discussions are disabled.
- Delete-branch-on-merge is off (clutter accumulates).
- No `.github/` directory — issues open into a blank textarea, PR template lives in CONTRIBUTING.md but isn't auto-loaded.
- No `SECURITY.md` — security-conscious users have no place to report concerns or read the project's threat model.
- No `CHANGELOG.md` — the spec audit trail is the source of truth but isn't easy to scan for "what's new".
- README's "above-the-fold" content is a tagline plus a tabular three-paths section; the "this is for *you*, the AI dev with workspaces sprawling across Google Drive" framing isn't present.

The audience this project exists to help is *specifically* the developer doing AI-assisted coding who has dozens of workspaces piling up. The README should make them recognise themselves in the first three sentences, not at the end of the second section.

## Intent

Make the GitHub repository self-explanatory at first glance for the AI-dev audience that hits the workspace-storage problem. Add the missing community-health files (`.github/` templates, `SECURITY.md`, `CHANGELOG.md`), tighten the README's framing for the target user, and configure the GitHub-side repo settings (description, topics, features). Keep scope to presentation and onboarding ergonomics — no behaviour changes, no new code.

## Spec

### 1. README front-matter rewrite

- A two-line tagline at the very top: what `clain` is + who it's for. Mentions "AI-assisted coding" and "workspaces piling up in Google Drive" by name so the target reader recognises the situation.
- A "Why this exists" callout (3-5 sentences) immediately under the tagline. Plain prose, no headers. Names the specific failure mode (`node_modules`/`site-packages` re-syncing forever, ambiguous toolchains breaking when venvs move, dozens of half-abandoned AI-spawned workspaces).
- A "What you get" block: a short sample of `clain classify` output (rendered as a Markdown table inline) so the reader sees concrete shape before being asked to install anything.
- The existing three-paths section ("CLI user / agent user / contributor") stays, but moves below the framing.

### 2. `.github/` directory

- `.github/ISSUE_TEMPLATE/bug-report.yml` — structured form: clain version, OS, what happened, expected, reproduction. YAML form so GitHub renders it nicely.
- `.github/ISSUE_TEMPLATE/feature-request.yml` — name the goal in INTENT it serves, the proposed approach, alternatives considered, and a note that non-trivial features become specs via the contributor workflow.
- `.github/ISSUE_TEMPLATE/config.yml` — disables blank issues; points users at Discussions for open-ended questions.
- `.github/PULL_REQUEST_TEMPLATE.md` — lifted from the template in CONTRIBUTING.md so PRs auto-populate. The template links back to CONTRIBUTING.md for the full workflow.

### 3. `SECURITY.md` at the repo root

Short and honest. Sections:

- Supported versions — pre-1.0, latest `main` only.
- What `clain` does and does not do that affects security:
  - It is read-only against the scanned root by design.
  - It does not network, spawn processes (while the phase gate is closed), or write outside `$XDG_STATE_HOME/clain/`.
  - Plans contain shell commands (`rm -rf`, `rsync`) intended for the developer to run; the developer is responsible for what they execute.
- How to report a security issue — GitHub's private vulnerability reporting feature, with a fallback contact.
- What is *not* a security issue, to set expectations: the phase gate raising errors by design, plans containing destructive-looking commands by design, dependencies declared in `pyproject.toml`.

**Phase-gate framing rule (load-bearing).** SECURITY.md must describe the phase gate as a *design property* of the project's pre-execution development phase, **not** as a hardening control or a security boundary. Phrasings like "the phase gate is a design property of this development phase" are required; phrasings like "the phase gate provides defence in depth" or "the gate hardens against accidental execution" are forbidden. This is to prevent a future edit from quietly reframing `EXECUTE_ENABLED` as a security knob that could be loosened — the gate is lifted only by spec 00NN, not by relaxing a security control.

### 4. `CHANGELOG.md` at the repo root

[Keep a Changelog](https://keepachangelog.com/) format, derived from the spec status transitions.

- **Unreleased** section at the top.
- One section per release tag once we cut tags (out of scope for this spec; the section is documented but empty until then).
- An initial "Pre-history (pre-public)" section listing specs 0001–0007 as the captured baseline. **Entries cite spec ID and title only** — no dates, no author names, no email addresses. Dates live in git history; author attribution lives in `pyproject.toml`. The CHANGELOG is presentation, not provenance.
- Update rule: each shipped spec adds a one-line entry; each amendment adds another. The PR for that spec includes the CHANGELOG bump.

### 5. GitHub-side settings (applied via `gh`)

Outside the source tree but inside this spec's scope:

- Repo description: a single sentence drawn from the INTENT mission.
- Topics: `ai-dev-tools`, `workspace-management`, `python`, `cli`, `agent-skills`, `pixi`, `claude-code`, `pnpm`, `uv`, `monorepo`, `dependency-management`.
- Homepage URL: leave empty for now (no project site yet).
- Disable wiki (we have `docs/`).
- Enable discussions (with Q&A and Ideas categories enabled by default; GitHub's defaults are fine for the rest).
- Enable delete-branch-on-merge.

These are durable repo-level settings, so the `gh` commands run once during this PR's review-and-merge cycle and the spec's acceptance bullets verify the result.

### 6. Out of scope

- GitHub Actions / CI. Separate spec when it bites.
- Dependabot / supply-chain automation. Separate spec.
- Social preview image. Worth doing eventually but not now.
- Funding / sponsorship configuration. Pre-1.0, not appropriate yet.
- Code of conduct. Skipped for early stage; can be added when the project has external contributors.
- Releases / tags. Pre-1.0; first release tag is its own future spec.
- Screenshots beyond a Markdown table. Asciinema or animated GIFs are nice but add maintenance cost.

## Acceptance

- [ ] README opens with a tagline that names the AI-dev audience and the GDrive failure mode; the "Why this exists" callout sits above the three-paths section.
- [ ] README contains a sample `clain classify` output rendered as a Markdown table (anonymised — same discipline as `examples/`).
- [ ] The anonymisation test is extended to cover README.md, SECURITY.md, and CHANGELOG.md. The existing `test_examples_anonymised` is generalised (or a sibling `test_public_docs_anonymised` added) so the same needle list (`GoogleDrive`, `CloudStorage`, `njon001`, `clain-me`, `nick@`, `/Users/`) catches leaks in the new files.
- [ ] SECURITY.md uses the design-property framing for the phase gate, not a hardening-control framing. A grep-test or review check confirms phrases like "hardening", "defence in depth", or "security control" do not appear in association with the phase gate.
- [ ] `.github/ISSUE_TEMPLATE/bug-report.yml` and `feature-request.yml` exist and validate (YAML form schema).
- [ ] `.github/ISSUE_TEMPLATE/config.yml` disables blank issues and points at Discussions.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` exists with the same sections as CONTRIBUTING.md's PR template; opening a fresh PR auto-fills it.
- [ ] `SECURITY.md` exists at the repo root with the four sections named above. No personal information.
- [ ] `CHANGELOG.md` exists at the repo root with the keep-a-changelog header, the Pre-history section listing specs 0001–0007, and an empty Unreleased section.
- [ ] CONTRIBUTING.md is updated with a one-line "PRs auto-populate via .github/PULL_REQUEST_TEMPLATE.md" note so contributors don't think they have to copy the template by hand.
- [ ] GitHub-side: description set, topics applied (the list above), wiki disabled, discussions enabled, delete-branch-on-merge enabled. Verified by `gh repo view` after the PR merges.
- [ ] All existing tests, lint, and typecheck continue to pass. (No code changes here; this is a docs/config-only spec.)
- [ ] PR follows the spec 0006 template (spec ref, advisor verdict, acceptance bullets, gate results).

## Notes for future specs

- Once we cut a 0.1 release, the CHANGELOG section under "Unreleased" rolls forward and the spec for that release captures the cut.
- A future *Repository automation* spec covers CI, Dependabot, and any required-status-checks branch protection.
