---
id: 0014
title: Vertical rhythm + 0013 follow-through fixes
status: shipped
goal: Goal 1 (Categorical visibility — the output should *teach*, which requires the typography between sections to be intentional, not accidental); Goal 7 (Honest sync hygiene — leftover `CLAIN_SYNCED_ROOT` hint text in the renderer contradicts the 0013 removal)
---

## Problem

Continued dogfooding after spec 0013 surfaced two distinct concerns. They share a PR because they're both "0013 didn't quite land" — but they're not the same kind of thing, and this spec keeps them labelled separately.

### Part A — Two correctness fixes from 0013 fallout

These are bugs, not polish. They got missed because the 0013 sweep was about the *new* shape of the renders, not the leftovers from the old shape.

1. **Classify cache survives a schema change.** A user upgrading from pre-0013 to 0013 (by pulling `main` on an existing checkout) sees the *old* sync-placement string `? unknown` even though `detect_synced_storage` correctly returns `("local", None, None)` on their macOS path. The cause: the classify cache at `~/.local/state/clain/classify/<root-hash>.json` was written before the schema added the `sync_placement` block, the renderer falls through `_sync_placement_line(sp=None)` to the unknown branch, and `(cached — pass --refresh to rescan)` masks the staleness. The cache key must include enough version information that a schema change forces a re-scan.

2. **Stale `CLAIN_SYNCED_ROOT` references in `src/clain/ui/tables.py`.** The 0013 startup gate hard-errors if the env var is set, but four render strings still mention it:
   - line 55 — tree-mode header hint
   - line 93 — sync-placement fallback string
   - line 386 — `_sync_placement_line` unknown branch tells you to set the env var
   - line 518 — footer text
   Telling the user to set an env var that the gate refuses to honour is a contradiction shipped under the same release. Sweep them.

### Part B — Vertical rhythm

Spec 0013 added orientation headers, breathing room *inside* panels, and structured meta blocks. What it didn't tune is the rhythm between the **non-panel/non-table elements** — the lines and section breaks that surround the structured content. Concretely, on the current default render of `clain classify --here` and `clain plan recreate --here --dry`:

- Trailing meta lines `(cached — pass --refresh to rescan)` and `(dry mode — execution skipped)` print flush against the preceding content, at column 0, with no blank line above. They read as accidental shell echo rather than deliberate run-status notes.
- Horizontal rules (`Rule()`) abut their neighbours: on classify, `scan {duration}s` sits on the very next line; on plan, the `Summary / Saved / Mode` trio starts immediately below the rule. The rule is supposed to *separate*; if it doesn't, it isn't doing its job.
- The Key block on plan ends without breathing room before the closing rule, so the rule reads as "next paragraph starts here" rather than "end of document".
- Class-header lines on classify-here jam the count and the prose description together: `cache-managed (1)   Lives in a per-ecosystem store…`. Three spaces between count and description floats the prose with no anchor on a wide terminal.
- Key treatment is inconsistent across views: classify-here uses an inline one-liner (dense, dot-separated), plan uses a multi-line block. Two flavours of the same idea in two adjacent commands.
- Horizontal rules span the full terminal width. On a 190-col terminal they read as a long horizontal scar rather than punctuation between sections.
- The render terminates with no trailing blank line; the next shell prompt abuts the last printed line.

None of these affect *correctness*. They affect whether the eye can parse the output in one pass — which is exactly what 0013 was trying to deliver.

## Intent

Two coordinated changes in one spec:

**Part A — correctness fixes.** Cache invalidation on schema bump, and a textual sweep of `CLAIN_SYNCED_ROOT` references in the renderer. Both are tightening the bolts on what 0013 already decided.

**Part B — vertical rhythm pass.** A consistent set of typography rules applied across every primary render so the rhythm between sections is deliberate. No new flags, no new commands, no JSON change.

The deliverable is "the existing renders, tightened" — not "new renders". A reader who liked the 0013 shape should still recognise everything; they should just read it faster.

## Spec

### Part A.1 — Classify cache schema-aware invalidation

The classify cache file at `~/.local/state/clain/classify/<root-hash>.json` currently uses `<root-hash>` as the sole identity. We add **a schema-version component** so cache files written under an older schema are not consulted by a newer binary.

Two options considered:

1. Include the schema version in the cache filename (`<root-hash>-schema-<N>.json`). Pro: old files become inert immediately; new files don't collide. Con: leaves abandoned old files on disk forever unless we sweep.
2. Read the cached payload, check its `schema` field, and treat a mismatch as a cache miss. Pro: same path, no rename. Con: we still load + parse the old file before discarding it.

**Chosen: option 1** — append `-v<schema>` to the cache filename. The schema component reads from the same `schema: 1` field that already lives in the classify payload (currently `1`; bumps when the payload shape changes). When the loader looks up a cache for `<root-hash>`, it asks for the file matching the *current* schema; any other matching `<root-hash>-v*.json` files are stale and get unlinked on access (cheap, bounded). This way the disk doesn't accumulate dead cache files across upgrades.

The schema version is **also bumped to `2`** as part of this spec, because the addition of the `sync_placement` block in spec 0013 was technically additive but introduced a render-affecting field. Bumping forces all existing caches to invalidate cleanly, even on machines that already upgraded silently.

Tests:

- `test_classify_cache_filename_includes_schema_version` — write a cache via the normal classify path, assert the on-disk filename contains the current schema version.
- `test_classify_cache_old_schema_is_ignored` — pre-write a file matching the legacy name (`<root-hash>.json`) or an older `<root-hash>-v1.json`, run classify, assert it does a fresh scan rather than reading the stale file.
- `test_classify_cache_old_schema_file_is_cleaned_up` — after a fresh scan, the legacy/old-schema file no longer exists on disk.

### Part A.2 — `CLAIN_SYNCED_ROOT` hint-text sweep

Edit `src/clain/ui/tables.py` to remove every reference to `CLAIN_SYNCED_ROOT` in user-visible render strings. Specifically:

- **Line 55 / line 93** — these compose the tree-mode header hint string ("`Sync placement: unknown (CLAIN_SYNCED_ROOT not set)`"). Replace with the platform-aware string: on non-macOS, `unknown (sync placement not autodetected on this platform)`; on macOS the case shouldn't arise (everything is detected), so this branch is dead code under the 0013 model and gets removed.
- **Line 386** — `_sync_placement_line` "unknown" branch currently reads `"? unknown  (set CLAIN_SYNCED_ROOT to enable in-sync detection)"`. Replace with `"? unknown  (sync placement not autodetected on this platform)"` — matching the language in `docs/USAGE.md`.
- **Line 518** — footer text in tree-mode meta. Replace `"Sync placement unknown for {n}/{m} (autodetect / CLAIN_SYNCED_ROOT)"` with `"Sync placement unknown for {n}/{m} (autodetect off on this platform)"`.

A test pins this: `test_no_env_var_strings_in_rendered_output` greps every render produced by classify (single + tree) and plan (default + table) for the literal string `CLAIN_SYNCED_ROOT` and asserts zero occurrences. This is the same defensive style as `test_public_docs_contain_no_personal_info` — a cheap textual guard against regressions when someone reintroduces the env var hint by force of habit.

### Part B — Vertical rhythm rules

We codify a small set of typography rules as a module-level constant in a new `src/clain/ui/rhythm.py`, used by every renderer:

```python
# src/clain/ui/rhythm.py
SECTION_GAP = 1           # blank lines between named sections in a render
META_GAP = 1              # blank lines before status/meta lines (cached/dry-mode)
BODY_INDENT = "  "        # 2 spaces — the leading indent for body content
META_INDENT = "  "        # status lines indent matches body, not col 0
RULE_WIDTH = 72           # fixed measure for Rule()s — punctuation, not architecture
```

The constants are exported via a single `from clain.ui.rhythm import …` import; no other modules hard-code `Padding((1, 2))` or `Rule()` defaults. The values themselves are a deliberate choice, not magic — `72` is the standard "comfortable line measure" Rich and most CLI tools settle on; `BODY_INDENT="  "` matches the existing renderer's spacing.

The rules below name where each constant gets applied.

#### Rule 1 — Meta lines (cached / dry-mode) are deliberate asides

The lines `(cached — pass --refresh to rescan)` and `(dry mode — execution skipped)` are not body content; they're aside notes about the run. We treat them consistently:

- One blank line above (`META_GAP`).
- Indented to match `BODY_INDENT` (`  `).
- Dim styled (Rich `[dim]…[/dim]`) so the typography signals "supplementary".

Before:
```
…  Key:  cache-managed regenerable from a manifest  · …
(cached — pass --refresh to rescan)
```

After:
```
…  Key:  cache-managed regenerable from a manifest  · …

  (cached — pass --refresh to rescan)
```

#### Rule 2 — Rules separate

Every `Rule()` gets one blank line above and one blank line below. The current renderer emits the Rule then immediately the next line of content; this rule fixes both sides symmetrically. Applies to:

- The closing rule on `classify --here` (before `scan {duration}s`).
- The closing rule on `plan recreate` (before `Summary / Saved / Mode`).
- Any future rule added to a render.

#### Rule 3 — Rules are a fixed measure, not full-width

`Rule(width=72)` (or whatever `RULE_WIDTH` is set to). On wide terminals this stops the rule from reading as a horizontal scar; on narrow terminals (≤72 cols) Rich already wraps it sensibly. The rule is left-aligned to `BODY_INDENT` so it sits under the body content's leading column, not centred (centring rules on a left-aligned render makes the eye jump).

#### Rule 4 — Class headers use a hanging indent

On `classify --here`, replace the current single-line class header:

```
cache-managed (1)   Lives in a per-ecosystem store. Safe to delete if…
  .pixi
```

with a two-line hanging-indent form:

```
cache-managed (1)
    Lives in a per-ecosystem store. Safe to delete if you can re-install
    — your manifest tells clain how.
    .pixi
```

The description and the member list align under the same indent (4 spaces from `BODY_INDENT`'s 2), making the eye read header → describing prose → instances vertically. Costs one extra line per class; on a workspace with 3 classes that's 3 lines, well worth it for the readability gain on wide terminals.

#### Rule 5 — Key block is consistent across views

The classify-here inline `Key:  cache-managed … · bytecode … · ephemeral …` becomes a multi-line block matching the plan view:

```
Key
  cache-managed   regenerable from a manifest
  bytecode        regenerated automatically on use
  ephemeral       build output, regenerable by the build step
```

…same shape as the plan-view Key (minus the columns plan needs that classify doesn't — Type, Target, Command, Safe?). The convergence means a user who learned to read the Key on one view reads it the same way on the other.

The Key block sits before the closing Rule on every render that has one.

#### Rule 6 — Closing margin

Every render ends with one trailing blank line so the next shell prompt has air. Tiny but matters; the alternative is "last line abuts prompt", which feels like the tool didn't finish printing.

### Render order, after all rules apply

**`clain classify --here`:**

```
clain classify --here  →  one-workspace classification

  Workspace:       <name>
  Location:        <path>
  Sync placement:  <state>
  Manifests:       <list>

  Regenerable subtrees (<n>):

    cache-managed (<k>)
        <description>
        <member>
        <member>

    bytecode (<k>)
        <description>
        <member>

  Next step:
    <command>
    → <effect>

  ────────────────────────────────  (RULE_WIDTH, left-aligned to BODY_INDENT)

  scan <duration>s

  Key
    cache-managed   regenerable from a manifest
    bytecode        regenerated automatically on use
    ephemeral       build output, regenerable by the build step

  (cached — pass --refresh to rescan)

<trailing blank>
```

**`clain plan recreate --here --dry`:**

```
clain plan recreate --here --dry  →  delete-and-recreate plan

  ╭─ <name>  <path> ─╮
  │  …Panel…         │
  ╰──────────────────╯

  Key
    Type     delete · recreate · move · smoke-test
    Class    cache-managed   regenerable from a manifest (your real win)
             bytecode        regenerated automatically on use
             ephemeral       build output, regenerable by the build step
    Target   path being acted on, relative to the workspace location
    Command  the actual shell command this action represents
    Safe?    ✓ — clain has all it needs to run this reproducibly
             ✗ — something blocks safe execution; run `clain plan explain
             <ACTION_ID>` for the reason

  ────────────────────────────────  (RULE_WIDTH)

  Summary  <n> workspace · <m> actions · <u> unsafe
  Saved    <path>
  Mode     dry-run (execution gate is closed — see executor.py)

  (dry mode — execution skipped)

<trailing blank>
```

### Tests

For each rule we add a focused test against captured render strings:

- `test_meta_line_has_blank_line_above` — `(cached …)` / `(dry mode …)` is preceded by exactly one empty line in the rendered output.
- `test_meta_line_is_indented_not_col_zero` — the meta line starts with `BODY_INDENT`.
- `test_rule_has_blank_line_both_sides` — the line above and below any `Rule()` is empty.
- `test_rule_width_is_capped` — captured rule character count is ≤ `RULE_WIDTH + len(BODY_INDENT)`.
- `test_class_header_uses_hanging_indent` — on classify-here, the class header line ends at the count (no inline description); the next non-empty line is the description, indented one level deeper than the header.
- `test_classify_key_block_form` — classify-here Key is a multi-line block, not a single dotted line. `"Key\n"` appears in the output (the block header), and the legacy `"Key:"` one-liner does not.
- `test_render_ends_with_trailing_blank` — every captured render ends with at least one trailing empty line.
- `test_no_env_var_strings_in_rendered_output` — see Part A.2.

These tests deliberately assert on **render shape** (blank lines, indent prefixes) rather than exact byte sequences, so a future colour tweak doesn't break them. The capture snapshots in `examples/` are regenerated as part of the spec; they're documentation artefacts, not the test oracle.

### Documentation updates

- `docs/USAGE.md` — refresh the captures inline; the "Reading the output" section gains a sentence about the typography conventions (rules separate sections; meta lines below rules; Key as a block).
- README.md — refresh the lead capture.
- CHANGELOG.md — Unreleased entry for spec 0014 noting the schema bump (cache files regenerate on next scan; no user action needed).
- `examples/capture.py` — re-run to regenerate `examples/capture-*.txt`.

## Acceptance

- [x] `~/.local/state/clain/classify/<root-hash>-v2.json` is the cache filename produced by the current binary; pre-existing `<root-hash>.json` / `<root-hash>-v1.json` files are ignored and removed on next access.
- [x] No render produced by `classify` or `plan recreate` (default, `--table`, or `--json` modes) contains the literal string `CLAIN_SYNCED_ROOT`. Verified by `test_no_env_var_strings_in_*_renders`.
- [x] `(cached …)` and `(dry mode …)` lines render with one blank line above and indented to `BODY_INDENT`.
- [x] Every horizontal rule has one blank line above and below; rules are ≤ `RULE_WIDTH` characters wide and left-aligned to `BODY_INDENT`.
- [x] Class headers on `classify --here` use the hanging-indent form: header line ends at the count, description on the next indented line, members below.
- [x] The Key block on `classify --here` is the multi-line block form, matching the shape used by `plan recreate`.
- [x] Every render ends with a trailing blank line.
- [x] `src/clain/ui/rhythm.py` exists and exports the four constants; no renderer hard-codes the values it owns.
- [x] Plan JSON is byte-identical (the spec 0012 invariant); the inner `plan_table_flat()` Rich `Table` snapshot from spec 0012 is byte-identical (existing `test_plan_table_flat_snapshot_unchanged` still passes).
- [x] Tests above pass; `pixi run -e dev test`, `lint`, `typecheck` all clean.
- [x] Captures regenerated; CHANGELOG entry added.
- [x] PR follows the workflow template.

## Out of scope

- Theme / colour customisation. Same defer-to-future as 0013.
- TUI / interactive collapse. Same defer-to-future.
- Cross-platform sync autodetection. Linux/Windows still report `unknown` per 0013.
- Pager support for long renders. The rhythm rules above assume the render is short enough to read in one screen; if a future spec adds a `--paged` mode, it can revisit.
- Per-section configurable spacing. The constants are deliberate, not configurable. If a user wants tighter output, `--no-legend` already drops the densest block.

## Notes

- `RULE_WIDTH = 72` is the standard comfortable line measure (the same one most prose linters default to). Picked because it matches what the existing captures *almost* render at when there's no terminal-width influence — codifying the apparent intent.
- The Part A items (cache invalidation, env-var sweep) are bugs from 0013 fallout and ship in the same PR because separating them would mean two PRs against the same five-file diff. The CHANGELOG entry calls out both parts.
- This spec is deliberately not a rework. If a future spec wants to replace the Rich renderer with Textual or a different layout engine, that's a different conversation; this one keeps the existing shape and tunes the rhythm.
