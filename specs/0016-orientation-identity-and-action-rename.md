---
id: 0016
title: Orientation identity (brand meter + command emoji + intent prose) + `type → action` field rename
status: draft
goal: Goal 1 (Categorical visibility — first contact with a render should anchor the eye and state intent in plain English, not restate the command); Goal 8 (Reviewable evolution — the plan JSON field name should match the concept it represents)
---

## Problem

Two distinct concerns that share a PR because they both touch the orientation/header code paths in `src/clain/ui/tables.py` and both warrant a single docs/captures regen pass.

### A — Orientation crowding

The first lines of every `clain` render currently look like this when invoked via `pixi run`:

```
✨ Pixi task (clain in default): python -m clain classify --here
clain classify --here  →  one-workspace classification

  Workspace:       clain
```

Pixi prints the literal command. Clain's orientation header restates the command in slightly different syntax. Two near-duplicate lines compete for attention, and neither tells you *what the command is for*. When the user scrolls back through a long output, there's no distinctive visual anchor that says "start of clain render here".

Spec 0014 added breathing room *within* the body. The orientation header above the body is still doing two contradictory jobs (restate the command + identify the render type) and not doing either well.

### B — `type` is the wrong word for the action field

Plan JSON uses `type` for the action category (delete / recreate / move / smoke-test):

```json
{ "type": "delete", "class": "cache-managed", "target": "...", ... }
```

`type` is overloaded across Python, JSON Schema, and most programming domains. The actual concept is *action*: the thing this entry tells the executor to do. `"action": "delete"` reads naturally; `"type": "delete"` makes the reader ask "type of what?". Same data, clearer label. Schema break, so the rename pairs with a plan-schema-version bump.

## Intent

Two coordinated changes, one PR:

**A — Orientation identity.** Drop the command-restate header. Replace with a fixed visual anchor (brand meter + command emoji + command name) and a plain-English intent line that says what the command is *for*. The brand meter is also the section-start marker the eye scans back to on a long output. On a user's first-ever `classify` invocation, prepend a full ASCII/emoji "clain" banner with the repo URL and tagline — shown once, persisted via a state-dir marker file.

**B — `type → action` rename.** Rename the field across the plan JSON, the executor, the renderers, the explain command, the snapshot fixture, and every test. Bump plan schema version. Apply the same schema-versioned cache filename pattern from spec 0014 (`<UTC>-v<schema>.json`) so old saved plans don't get loaded by the new binary.

No behaviour change in plan / executor / phase gate. No new CLI flags. The orientation rework affects rendered output; the rename affects on-disk JSON.

## Spec

### Part A — Orientation identity

#### The brand meter (5-point)

A fixed 5-position meter at the top of every primary render. Each position is one of two glyphs:

- **Solid** — `▰` (U+25B0) — filled in the command's accent colour
- **Outline** — `▱` (U+25B1) — dim/empty

The meter has a meaning: **how far along the workflow this command sits**. The five workflow positions:

| Position | Meaning |
|---|---|
| 1 | install / setup (no command renders here; conceptual) |
| 2 | classify — what's there |
| 3 | plan — what would happen |
| 4 | review — explain a single action |
| 5 | execute (currently gated; will light up when the execute spec lands) |

Per-command mapping for the meter level:

| Command | Meter | Reading |
|---|---|---|
| `classify` (any mode) | `▰▰▱▱▱` | 2/5 |
| `plan recreate --dry` / `plan move --dry` | `▰▰▰▱▱` | 3/5 |
| `plan explain` | `▰▰▰▰▱` | 4/5 |
| `plan recreate` / `plan move` (execute path; currently gate-blocked) | `▰▰▰▰▰` | 5/5 |

The colour gradient across the five blocks (Tokyo Night palette, spec 0017 token names — until 0017 lands, the meter renders in single-colour `brand` cyan):

- Block 1: `brand.step1` (cyan, e.g. `#7dcfff` dark)
- Block 2: `brand.step2` (blue, `#7aa2f7`)
- Block 3: `brand.step3` (magenta, `#bb9af7`)
- Block 4: `brand.step4` (orange, `#ff9e64`)
- Block 5: `brand.step5` (red-warning, `#f7768e`) — execute is the highest-stakes step

Empty/outline blocks render in `dim` regardless of their step colour, so the filled prefix is what carries the message.

#### Anchor row

After the meter, the brand name and the command identity:

```
▰▰▱▱▱  clain  🏷  classify --here
```

Format (left to right):

1. **Meter** (5 chars + 2 trailing spaces)
2. **`clain`** in `brand` bold colour
3. **Command emoji** (2 chars including the variation selector, then 2 trailing spaces)
4. **Command name + flags** in regular weight, dim style

First-pass emoji mapping:

| Command | Emoji | Why |
|---|---|---|
| `classify` | `🏷` (U+1F3F7 LABEL) | Tagging subtrees. The whole concept. |
| `plan recreate` | `♻️` (U+267B RECYCLE) | Delete + rebuild. Cycle. |
| `plan move` | `📦` (U+1F4E6 PACKAGE) | Relocate workspace. |
| `plan explain` | `💬` (U+1F4AC SPEECH BALLOON) | Explanation. |

The emoji is **content-bearing**, not decoration. If terminal can't render emoji (very rare on modern terminals; falls back to a tofu box), the layout still parses because each field is space-separated.

#### Intent line

A single plain-English sentence below the anchor row, describing what the command *does*, not what was typed:

| Command | Intent line |
|---|---|
| `classify --here` | `Categorical scan of this workspace — what's regenerable, what isn't, and the recreate command derived from your manifest.` |
| `classify` (tree) | `Categorical scan across every workspace under the root — class tags, manifests, sync placement.` |
| `plan recreate --dry` | `Preview the delete-and-recreate plan. Nothing executes; this is the review step before the real thing.` |
| `plan move --dry` | `Preview the move-and-triage plan for workspaces in synced storage. Nothing moves; this is the review step.` |
| `plan explain <id>` | `Full record for one action — preconditions, command, safety reasoning.` |

The intent line text lives in a `clain.ui.intent` module as a mapping, so future commands add a one-line entry. No hard-coded strings in render functions.

#### Spacing rules (extends spec 0014 rhythm)

- One blank line **above** the meter (separates from pixi's `✨` line or the previous shell prompt).
- One blank line **between** the anchor row and the intent line.
- One blank line **between** the intent line and the body content.

Combined with the spec-0014 trailing-blank-line rule, every render has the same top-and-bottom breathing.

#### First-run banner

On the user's first-ever `classify` invocation (single or tree), prepend a full-width banner:

```
   ██████╗██╗      █████╗ ██╗███╗   ██╗
  ██╔════╝██║     ██╔══██╗██║████╗  ██║
  ██║     ██║     ███████║██║██╔██╗ ██║
  ██║     ██║     ██╔══██║██║██║╚██╗██║
  ╚██████╗███████╗██║  ██║██║██║ ╚████║
   ╚═════╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝

  Categorical visibility, deliberate execution.
  https://github.com/drai-inn/clain

```

Rendered in the brand-gradient colours across the five visual rows (so each row of the ASCII art picks up one of the meter-block colours, top to bottom).

**Detection: how do we know it's the first run?** A marker file at `$XDG_STATE_HOME/clain/banner-shown` (created the first time the banner renders). If absent, render and create; if present, skip. Cheap, durable, survives across pixi rebuilds.

A `--no-banner` flag and `CLAIN_BANNER=off` env var force-suppress the banner (for users who upgrade and don't want the splash on next run); same precedence as `--legend`. A `--banner` flag and `CLAIN_BANNER=on` force-show (for screenshots / docs regen).

**The banner does not block.** It's printed to stdout, then the normal render continues. Pipelines (`clain classify --json | jq …`) skip the banner entirely because `--json` mode never prints Rich to stdout (existing behaviour).

#### TTY/no-TTY

Per spec 0017 (theme detection) and the existing `NO_COLOR` convention:

- Stdout is a TTY: full colour brand meter + emoji + colour intent + colour banner.
- Stdout is piped or `NO_COLOR` is set: drop colour throughout; meter renders as plain text `▰▰▱▱▱`; emoji renders as-is (it's just a unicode codepoint; downstream tooling can strip if needed); banner is suppressed entirely (pipes don't want splash).

This matches the existing Rich `force_terminal=False` behaviour — we're codifying it for the new elements, not changing anything else.

### Part B — `type → action` rename

#### Scope of the rename

| Layer | Today | After |
|---|---|---|
| Plan JSON action record | `"type": "delete"` | `"action": "delete"` |
| Plan JSON schema field | `SCHEMA_VERSION = 1` | `SCHEMA_VERSION = 2` |
| Persisted plan filename | `<kind>-<UTC>.json` | `<kind>-<UTC>-v<schema>.json` (matches the spec-0014 classify-cache pattern) |
| Plan-builder `Action` dataclass | `type: str` | `action: str` |
| Renderer column header | `Type` | `Action` |
| Renderer column variable | `a.get("type")` | `a.get("action")` |
| `plan_view` / `_plan_legend_block` | "Type: delete · recreate · move · smoke-test" | "Action: delete · recreate · move · smoke-test" |
| Tests + fixtures | `"type": ...` | `"action": ...` |
| `tests/snapshots/plan_table_flat.fixture.json` | `"type": ...` | `"action": ...` |
| `tests/snapshots/plan_table_flat.txt` | "Type" column header | "Action" column header |

The snapshot fixture and the snapshot output text both change in lockstep. The spec-0012 byte-equal invariant *is* preserved — it's just that "byte-equal" now means equal to the **new** snapshot. A test confirms the snapshot file got updated (i.e. the bytes the test reads include "Action" not "Type").

#### Schema version + stale-plan cleanup

Reuse the spec-0014 pattern:

- New plan files written as `<kind>-<UTC>-v<schema>.json`.
- `plan_explain` (which reads the most-recent plan file by default) ignores plan files whose embedded `schema` doesn't match the current `SCHEMA_VERSION`. A new helper `prune_stale_plan_files()` in `state.py` is called on plan save and removes any plan files older than 7 days whose schema doesn't match — bounded retention so the disk doesn't accumulate dead plans.
- Plans saved with the *old* schema (`"type": ..., "schema": 1`) are not loaded; `plan_explain` says "this plan was saved by an older clain (schema 1); run `clain plan recreate` again to regenerate".

The classify schema stays at 2 (spec 0014). Plan schema bumps to 2 (independent).

#### Why bump rather than read-both

We could write the new field and also read the old one ("compatible read, modern write"). Rejected because:

- Plans are throwaway artefacts (re-derivable from a fresh classify); not worth preserving across schema changes.
- The hard-error/regenerate path is honest and matches the spec-0013 stance on `CLAIN_SYNCED_ROOT`: when we change something, surface the change.
- Read-both branching is a maintenance tax that compounds across future renames.

### Tests

Part A (orientation):

- `test_classify_render_starts_with_meter_anchor` — first non-blank line is the meter + brand + emoji + command name.
- `test_meter_glyph_count_is_5` — exactly five meter glyphs, exactly the number-of-filled = the command's mapped position.
- `test_classify_meter_level_is_2` / `test_plan_recreate_dry_meter_level_is_3` / `test_plan_explain_meter_level_is_4` — pin the per-command level.
- `test_intent_line_present_below_anchor` — the intent string for each command appears below the anchor row.
- `test_no_command_restate_header` — the legacy `clain classify --here  →  one-workspace classification` style line does not appear.
- `test_first_run_banner_shown_when_marker_absent` — delete the marker, run classify, assert the ASCII art block appears in the output, assert the marker now exists.
- `test_first_run_banner_skipped_when_marker_present` — touch the marker, run classify, assert no ASCII art.
- `test_first_run_banner_skipped_in_json_mode` — `classify --json` never emits the banner regardless of marker.
- `test_no_banner_flag_force_suppresses` / `test_banner_flag_force_shows` / `test_clain_banner_env_precedence` — flag > env > marker-state.
- `test_meter_renders_without_color_in_no_color` — `NO_COLOR=1` strips colour, meter still readable.

Part B (rename):

- `test_plan_json_uses_action_not_type` — built plan has `"action"` keys, not `"type"`.
- `test_plan_schema_version_is_2` — `payload["schema"] == 2`.
- `test_plan_file_name_includes_schema_version` — saved plan filename matches `<kind>-<UTC>-v2.json`.
- `test_plan_explain_rejects_stale_schema` — pre-write a plan file with `schema: 1`; run `plan explain` against it; assert clear error.
- `test_prune_stale_plan_files_removes_old_schema_after_grace` — plant a 10-day-old schema-1 plan; save a new plan; assert the old one is gone.
- `test_plan_table_flat_snapshot_action_column` — snapshot file contains "Action" as the column header, not "Type". (The snapshot itself is updated as part of this spec.)
- `test_renderer_uses_action_field` — `plan_view` / `plan_table_flat` read from `a.get("action")`.

### Documentation updates

- **README.md** — replace the lead capture; document the brand meter convention briefly ("the meter shows where in the workflow this command sits"); note the `--no-banner` flag.
- **docs/USAGE.md** — orientation rework explained; intent-line convention; first-run banner; `--no-banner` / `CLAIN_BANNER`; rename of `type → action` in plan JSON.
- **AGENTS.md** — agents reading plan JSON look at `action` not `type`; the meter and banner are stdout chrome and don't appear in `--json` output.
- **CHANGELOG.md** — Unreleased entry for spec 0016, calling out the plan-schema bump and the rename.
- **examples/capture.py** — re-run to regenerate captures with the new orientation + the field rename. Banner is force-shown for one capture (`capture-first-run-banner.txt`) and suppressed for the rest via `--no-banner`.

## Acceptance

- [ ] Every primary render starts with the brand meter (5 glyphs) + `clain` + command emoji + command name, followed by an intent line.
- [ ] Meter levels match the per-command table (classify=2, plan-dry=3, plan-explain=4).
- [ ] The legacy `clain classify --here  →  one-workspace classification` header is gone.
- [ ] First-run banner appears on the first `classify` invocation per machine (marker absent); subsequent runs suppress it.
- [ ] `--no-banner` / `--banner` / `CLAIN_BANNER` resolve per the documented precedence; both flags together is a CLI error.
- [ ] Plan JSON uses `"action"` not `"type"`; `payload["schema"] == 2`.
- [ ] Saved plan files use `<kind>-<UTC>-v<schema>.json`.
- [ ] `plan explain` on a stale-schema file emits a clear error pointing at `plan recreate`.
- [ ] `tests/snapshots/plan_table_flat.fixture.json` and `tests/snapshots/plan_table_flat.txt` updated; the spec-0012 byte-equal invariant holds against the new snapshot.
- [ ] All Part A and Part B tests above pass; lint, typecheck, full test suite clean.
- [ ] Docs swept; captures regenerated.
- [ ] CHANGELOG entry added.
- [ ] PR follows the workflow template.

## Out of scope

- Configurable meter glyphs / colours. The five Tokyo Night colours are the chosen palette; if someone wants different glyphs they can fork. A future spec adds theme support if there's demand.
- Animated / progressive meter (e.g. each block lights up as the command runs). Defer; current command durations are sub-second.
- Renaming other plan fields. `type → action` is the worst-named one; the others (`class`, `target`, `commands`, `safe_to_execute`) are accurate.
- Banner localisation. English-only.
- Persisted banner-shown marker across machines / sync (it's per-machine state, which is the right scope).

## Notes

- The meter is the durable anchor; the emoji is the disambiguator; the intent line is the teacher. Three different jobs, three different visual treatments, all anchored on the same starting column.
- Choice of `▰` / `▱` (geometric medium small black/white square) is deliberate — they render at the same width in all major terminal fonts I tested (iTerm2, kitty, alacritty, gnome-terminal, Windows Terminal). U+2588 FULL BLOCK and U+2591 LIGHT SHADE are alternatives but the medium-small pair has better weight balance with the brand name.
- The first-run banner is a one-shot. It's not a tutorial mode; it's a "welcome / here's where to read more" hand-off. A future spec could add a `clain tour` interactive intro if that proves useful.
- The `type → action` rename is the kind of change that's easy to defer indefinitely because it's "just a name". Worth doing now because (a) every additional renderer / consumer added later makes it more painful, (b) the schema-version bump infrastructure from spec 0014 makes it cheap, (c) it removes the friction of explaining "type of what?" every time we onboard someone.
