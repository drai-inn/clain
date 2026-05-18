---
id: 0011
title: Documentation generalisation — synced storage broadly, single-workspace-first quickstart, captured Rich output
status: accepted
goal: Goal 1 (Categorical visibility) and Goal 8 (Version-controlled, reviewable evolution) — extended to making the project's framing accurate to the real audience and the real CLI shape after specs 0009 and 0010
---

## Problem

The project's docs were written when the only audience model was "the developer drowning in 30 AI-spawned workspaces under Google Drive". That framing is now too narrow on two axes:

1. **Storage substrate.** GDrive is *one* synced-storage tax. The same tool helps developers using **OneDrive, Dropbox, iCloud Drive, Box**, or just **a constrained local disk** with no cloud sync at all. Hammering "Google Drive" in the README, INTENT.md, AGENTS.md, etc. signals "this is a Google-Drive tool" to anyone arriving via search — which is wrong, and narrows the project's reach.
2. **Audience entry point.** Spec 0010 shipped single-workspace mode (`clain classify --here`). The everyday entry point is now `cd into-a-project && clain classify --here`, not "configure CLAIN_DEV_ROOT, point at a tree of 30 workspaces". The quickstart still leads with the multi-workspace flow, which is the lower-frequency case.

The other piece, named in earlier review:

3. **Output presented as Markdown table rather than captured Rich output.** The README's "What classification looks like" sample is a hand-crafted Markdown table approximation. A real captured Rich render — including the new single-workspace Tree from 0010 — is more lifelike and reflects the actual user experience.

## Intent

Sweep the user-facing docs (INTENT.md, README.md, AGENTS.md, CONTRIBUTING.md, docs/USAGE.md, SECURITY.md, CHANGELOG.md, the active SKILL.md files) to:

- Replace "Google Drive" as the centrepiece with **"synced storage (Google Drive, OneDrive, Dropbox, iCloud Drive, …)"** as the class, with Google Drive cited as the *motivating example on this machine*. The CLAIN_SYNCED_ROOT env var is the general handle.
- Lead README and docs/USAGE.md quickstarts with the **single-workspace flow** (`clain classify --here`). Multi-workspace tree mode appears below as the second use case.
- Embed **captured Rich output** as ANSI text snippets in README and docs/USAGE.md, replacing the hand-crafted Markdown approximations. Use the anonymised fixture paths from `examples/` (the discipline carried forward from specs 0007 + 0008).
- Update CHANGELOG.md's Unreleased section with entries for 0009, 0010, and 0011.

No code changes. No CLI surface changes. Pure documentation.

## Spec

### 1. Storage substrate generalisation

Every occurrence of "Google Drive" / "GDrive" in user-facing docs (i.e. not the spec audit trail) is reviewed against this rule:

- If the wording is **historical context** (e.g. "the dev root on this machine sits inside Google Drive"), it stays — the spec history is the audit trail of *this* developer's experience, and that experience is real and useful.
- If the wording is **forward-looking onboarding** ("for developers whose workspaces pile up in Google Drive"), it generalises to "synced storage (Google Drive, OneDrive, Dropbox, iCloud Drive)" with GDrive cited as the example that motivated the project.

INTENT.md keeps its specific Problem paragraph (it's historical context — this *is* the machine that started the project) but the Mission becomes substrate-agnostic.

### 2. Single-workspace-first quickstart

README.md and docs/USAGE.md lead with this flow:

```sh
pixi install
cd ~/some/project           # any workspace with a pyproject.toml / package.json / pixi.toml / etc.
pixi run clain classify --here
pixi run clain plan recreate --here --dry
```

The multi-workspace tree-mode flow appears below as a secondary case ("If you have a whole tree of workspaces to triage..."). The reasoning is named in one sentence so a reader understands why both modes exist.

### 3. Captured Rich output

Two captures live in README and one in docs/USAGE.md:

- **Single-workspace classify** — Rich Tree against an anonymised fixture mirroring `clain-me`'s structure (path stylised as `~/dev/example-workspace`, no real usernames).
- **Multi-workspace classify** — Rich table against an anonymised fixture (three workspaces with realistic names like `example-frontend`, `example-pipeline`).
- **plan recreate --dry single-workspace** — the action table for the single-workspace case (in docs/USAGE.md; README stays minimal).

**How captures are produced (so they're reproducible, not screenshots):**

```python
from rich.console import Console
buf = Console(record=True, width=78, force_terminal=False)
buf.print(rendered_tree_or_table)
text = buf.export_text(clear=False)
```

That gives plain box-drawing characters with no ANSI escapes — embedded directly in fenced ```text``` blocks, renders cleanly on github.com, copy-pastes safely. The capture command lives as a small helper script under `examples/` (or as a one-liner in the spec) so anyone can regenerate the captures after a CLI change without manual screenshotting.

(SVG export via `rich.console.export_svg()` is technically possible but adds an asset-management burden and is out of scope for this spec.)

### 4. Narrative paragraphs

Each capture is preceded by one short paragraph (2–3 sentences) saying:
- What `clain` was asked to do.
- What the developer should look for in the output.
- The natural next command.

This avoids the failure mode of "table dropped into the README with no orientation."

### 5. CHANGELOG.md

Add entries to the Unreleased section:

```
- spec 0009 — *Rule base completeness*: `.pixi` cache-managed, bare `venv` removed, `.git` pruned, nullable `in_sync_tree`.
- spec 0010 — *Single-workspace mode*: `--here` flag on classify/plan; Rich Tree renderer; the everyday entry point.
- spec 0011 — *Documentation generalisation*: synced-storage framing, single-workspace-first quickstart, captured Rich output.
- spec 0008 — *GitHub repository presentation*: community-health files + GitHub-side settings (this PR).
```

### 6. SKILL.md updates

The two skills already updated by spec 0010 (`clain-classify`, `clain-plan-recreate`) get a one-line phrasing pass to remove any remaining GDrive specificity in their `description:` fields, keeping the broader "synced storage" framing.

### 7. AGENTS.md, CONTRIBUTING.md, SECURITY.md

Search-and-replace pass for "Google Drive" → "synced storage (GDrive / OneDrive / Dropbox / iCloud Drive)" where the wording is onboarding-flavoured. Where it's historical or example-flavoured, keep but soften.

## Acceptance

- [ ] No user-facing onboarding doc (README.md, INTENT.md **mission only — not Problem**, AGENTS.md, CONTRIBUTING.md, docs/USAGE.md, SECURITY.md, SKILL.md frontmatter) leads with "Google Drive" as the centrepiece. Where GDrive is mentioned, it's cited as an example among others. INTENT.md's Problem section is **exempt** because it's historical provenance, not onboarding — see Out of scope.
- [ ] The substrate generalisation does not introduce new personal-info leaks. The existing `test_public_docs_contain_no_personal_info` needle list catches only `GoogleDrive`, `CloudStorage`, `njon001`, `clain-me`, `nick@`, `/Users/`. Adding mentions of OneDrive, Dropbox, iCloud Drive must stay generic (the *service name only*, no tenant URLs, no email-bearing paths). A focused review check during implementation confirms this.
- [ ] README.md and docs/USAGE.md lead with the `--here` single-workspace flow; multi-workspace tree-mode appears as a secondary case with a one-sentence framing of why both exist.
- [ ] README.md contains at least one captured Rich output (single-workspace Tree), preceded by a 2-3 sentence narrative.
- [ ] docs/USAGE.md contains captures for both single-workspace classify and a plan recreate, each with a narrative paragraph.
- [ ] CHANGELOG.md's Unreleased section includes entries for 0008, 0009, 0010, and 0011 — spec IDs and titles only, no dates or author names (carries forward spec 0008's discipline).
- [ ] All existing tests continue to pass; the public-docs anonymisation test (`test_public_docs_contain_no_personal_info`) still passes against the updated docs.
- [ ] The phase-gate framing rule (no "hardening control" language in SECURITY.md re: the gate) is preserved.
- [ ] PR follows the workflow template, references both spec 0008 and spec 0011.

## Out of scope

- Plan-table tree-grouped rendering, `Location` column, relative `Target`/`Commands`. Spec 0012 (was the originally-numbered 0011 plan-presentation work; renumbered here because doc generalisation made more sense to land first).
- A spec for releases / tags / semver. Pre-1.0, post-poned.
- A dedicated *changelog automation* spec (e.g. towncrier). The keep-a-changelog manual-entry pattern is fine until contributor volume warrants automation.
- SVG / asciinema captures. Plain ANSI text in fenced blocks is the practical capture form for now.
- Restructuring INTENT.md's Problem section to remove its developer-specific narrative. INTENT is the historical record of *this* project's motivation; rewriting it for a generic audience would erase honest context. Mission and Goals generalise; Problem stays as-is.

## Notes

- After 0011 ships, the README's headline pitch is "Tidy up workspace sprawl from AI-assisted coding — across synced storage and local drives" rather than the GDrive-centric framing.
- This spec is bundled with spec 0008 in PR #3 (the rebased/amended branch). The PR title becomes `spec(0008+0011): ...`. The reason for bundling: spec 0008's README rewrite landed before 0010 existed and before the doc generalisation question was asked; landing 0008 alone with stale framing would mean immediately reopening it. Bundling avoids that churn.
