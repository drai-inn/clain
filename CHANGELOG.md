# Changelog

All notable changes to `clain` are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is pre-1.0; semantic versioning will start applying once we cut a 0.1.0 release.

Entries cite the spec ID and title. Dates live in git history; author attribution lives in `pyproject.toml`.

## [Unreleased]

- spec 0008 — *GitHub repository presentation + discoverability*
- spec 0009 — *Rule base completeness*: `.pixi` cache-managed, bare `venv` dropped, `.git`-family pruned, nullable `in_sync_tree`. Schema-1 additive: `in_sync_tree` may now be `null` when `CLAIN_SYNCED_ROOT` is unset.
- spec 0010 — *Single-workspace mode*: `--here` flag on `classify` / `plan recreate` / `plan move`. Rich `Tree` renderer for single-workspace classify. `scan.mode = "tree" | "single"` (additive; absent = `"tree"` for backwards compat).
- spec 0011 — *Documentation generalisation*: synced-storage framing (GDrive / OneDrive / Dropbox / iCloud Drive as the class, not just GDrive), single-workspace-first quickstart, captured Rich output, reproducible via `examples/capture.py`.
- spec 0012 — *Plan presentation*: workspace-grouped Rich Panels with relative `Target` / `Command(s)` (default render), and `--table` to keep the pre-0012 single-table layout for copy-paste / spreadsheet use. `--table` and `--json` are mutually exclusive. Persisted plan JSON is unchanged (absolute paths preserved); relativisation is render-only.
- spec 0014 — *Vertical rhythm + 0013 follow-through fixes*. **Part A (correctness fixes from 0013 fallout):** classify cache filenames gain a `-v<schema>` suffix and the classify schema bumps to **2** so stale caches from before spec 0013 invalidate cleanly — old `<root-hash>.json` / `<root-hash>-v1.json` files are removed on access. Four remaining `CLAIN_SYNCED_ROOT` references in `src/clain/ui/tables.py` user-visible strings are swept (the startup gate already rejected the env var, but render hints still mentioned it). The legacy `classify_footer` / `single_workspace_tree` / `single_workspace_footer` renderers (unused since 0013) are removed. **Part B (vertical rhythm):** meta lines `(cached …)` / `(dry mode …)` render with one blank line above and indent to `BODY_INDENT` instead of column 0; horizontal rules become fixed-measure (`RULE_WIDTH=72`) with one blank line above and below; class headers on `classify --here` use a hanging-indent form (count on its own line, description and members aligned below); the classify Key block converges to the multi-line form already used by plan view; every render ends with a trailing blank line. New `src/clain/ui/rhythm.py` exposes the four typography constants (`SECTION_GAP` / `META_GAP` / `BODY_INDENT` / `RULE_WIDTH`). No JSON schema break, no new CLI flags, no behaviour change in plan / executor / phase gate. Cache files regenerate on next scan; no user action needed.
- spec 0013 — *Output legibility + sync-placement autodetect*: orientation headers, inline legends with `--legend` / `--no-legend` / `CLAIN_LEGEND` (default *on* for `--here`, *off* for tree mode), more breathing room around panels and classify renders, macOS sync-placement autodetection against six known synced-storage path patterns. **Removed `CLAIN_SYNCED_ROOT`** — it conflated workspace-parent and sync-claim into one env var, and autodetect covers the real cases. If still set in the environment, the CLI hard-errors with a pointer to unset it. The classify JSON gains a `sync_placement` block (`state` / `provider` / `source` / `synced_root`); the legacy `in_sync_tree` boolean stays and aligns with `sync_placement.state`.

## Pre-history (pre-public, captured as initial baseline)

These specs landed during the project's pre-git phase and were captured as a single baseline commit on first push. They are listed in order shipped.

- spec 0001 — *Architecture — hybrid CLI core + Claude Code plugin wrapper, named `clain`*
- spec 0002 — *Pixi environment, Python package skeleton, and Rich-powered CLI entry point*
- spec 0003 — *Claude Code plugin skeleton under `plugin/`, driving the CLI*
- spec 0004 — *Categorical workspace classification scan* (replaced an earlier quantitative inventory spec that was retracted in the same commit)
- spec 0005 — *Executable plan model — delete+recreate and move+triage actions, execute by default, gated; `--dry` opts into preview*
- spec 0006 — *Git + GitHub workflow for the clain repo itself*
- spec 0007 — *Agent-agnostic project handoff — Agent Skills adoption + audience-separated docs*

[Unreleased]: https://github.com/drai-inn/clain/commits/main
