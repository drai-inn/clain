---
id: 0012
title: Plan presentation — workspace-grouped panels with relative paths, plus `--table` for copy-paste
status: shipped
goal: Goal 1 (Categorical visibility) — extended to plan output, which today is wide and repetitive; Goal 8 (Version-controlled, reviewable evolution) — readable output makes review meaningful
---

## Problem

The current `clain plan recreate --dry` / `clain plan move --dry` output presents every action as a row in a single wide Rich `Table` with absolute paths. On the real `clain-me` workspace today (8 actions, all under one workspace) that produces ~32 rows of wrapping text:

```
┃ Workspace ┃ Type     ┃ Class         ┃ Target                  ┃ Command(s)              ┃ Safe? ┃
│ clain-me  │ delete   │ cache-managed │ /Users/njon001/dev/clai │ rm -rf                  │   ✓   │
│           │          │               │ n-me/.pixi              │ '/Users/njon001/dev/cla │       │
│           │          │               │                         │ in-me/.pixi'            │       │
│ clain-me  │ recreate │ cache-managed │ /Users/njon001/dev/clai │ pixi install            │   ✓   │
│           │          │               │ n-me                    │                         │       │
│ clain-me  │ delete   │ bytecode      │ /Users/njon001/dev/clai │ rm -rf                  │   ✓   │
│           │          │               │ n-me/.pytest_cache      │ '/Users/njon001/dev/cla │       │
…
```

Three concrete failures:

1. **Workspace column repeats** — every row says `clain-me`. Pure noise.
2. **Absolute path repeats twice per row** — once in *Target*, once embedded in `rm -rf '<path>'` in *Command(s)*. Both wrap across multiple lines.
3. **No visual separation between workspaces** in tree-mode plans — actions for `workspace-A` and `workspace-B` blend together unless you carefully read the first column.

For multi-workspace plans (typical of tree-mode use against a synced-root cleanup), the issue compounds.

## Intent

Restructure plan rendering to group by workspace, surface the workspace's location as a Panel header, and render *Target* / *Commands* **relative** to that location. The JSON shape stays absolute (unambiguous for execution); only the human-facing rendering changes. Preserve the existing single-table layout as `--table` mode for users who want to copy-paste into a spreadsheet.

A mock pass (run during spec authoring against the real `clain-me` plan) compared four layouts. The chosen direction is **per-workspace Panel containing a Rich Table** (mock candidate A) because it uses Rich's column model honestly, multi-workspace stacking is unambiguous, and the workspace+location pair sits where it reads naturally — the Panel title.

## Spec

### Default rendering (no flag)

For each workspace in the plan:

- A Rich `Panel` whose title is `[bold cyan]{workspace_name}[/]  [dim]{location}[/dim]`.
- The Panel body is a Rich `Table` with columns: `Type`, `Class`, `Target`, `Command(s)`, `Safe?`.
- The `Target` column shows paths **relative to the location**:
  - If the action target equals the location, render `.`
  - If the target begins with `location + "/"`, strip that prefix
  - Otherwise (shouldn't normally happen for in-workspace actions), render the absolute target as a fallback
- The `Command(s)` column rewrites embedded path quotes:
  - `'<location>/X'` → `'X'`
  - `'<location>'` → `'.'`
  - Other commands (e.g. `pixi install`) pass through unchanged
- `Safe?` column unchanged: `✓` for `safe_to_execute: true`, `[red]✗[/red]` otherwise
- Long values **wrap** (no truncation). Full information stays visible across multiple lines.

Multi-workspace plans stack panels vertically, in workspace order from the plan.

### Location derivation

For each workspace's set of actions, the **location** is computed as `os.path.commonpath` of the action `target` fields. For typical plans this is the workspace root (the recreate action's `target` is the workspace root; delete actions' targets are subpaths).

**Disjoint-tree fallback (load-bearing):** if `os.path.commonpath` over a workspace's action targets returns `/`, or returns a path that is not a strict prefix of any individual action's target, OR if `commonpath` raises (e.g. inputs on different mount points), the location MUST fall back to the workspace's classify-cache `path` field — i.e. the workspace root as recorded by classify. The renderer then renders **absolute** targets (the "otherwise" fallback branch of the Target rules) without erroring. This case is rare in practice (it would imply a hand-edited or programmatically-generated plan with disjoint targets) but the spec must not crash on it. A test exercises a fixture plan with two actions whose targets share no common prefix below `/`.

### `--table` mode

Pass `--table` to `clain plan recreate` or `clain plan move` to render the **existing single-table layout** instead. This preserves backwards compatibility for users who want to copy-paste into a spreadsheet, and it remains the simplest form for batch / piped contexts. With `--table`:

- Single Rich `Table` with columns: `Workspace`, `Type`, `Class`, `Target`, `Command(s)`, `Safe?`
- Absolute paths in `Target` and `Command(s)` — same as today
- No Panel wrapping; one continuous table

`--table` and `--json` are mutually exclusive. **Reason:** both write the plan to stdout in a single format; only one stdout format may be selected per invocation. Allowing them together would require a `--json-out PATH` sink (or equivalent) for the second format, which is out of scope for 0012. The CLI error message names this so a future reviewer doesn't re-litigate the choice.

### `--json` mode

Unchanged from spec 0005. Same JSON shape, same absolute paths in `target` and `commands` fields. The presentation changes are render-only; the persisted plan JSON does not change.

### Unsafe-actions banner

The existing red-banner `unsafe_actions_table` (from spec 0005) is preserved in the default Panel-per-workspace render: if any action is `safe_to_execute: false`, the unsafe table renders **above** the per-workspace panels, surfacing the dangerous-or-blocked actions before the user scans the safe ones. `--table` mode keeps the same precedence.

### Footer

The existing `plan_footer` (workspace count, action count, unsafe count, saved-to path) renders below all per-workspace panels in the default mode. Identical in `--table` mode.

### Implementation surface

- `src/clain/ui/tables.py`:
  - Rename current `plan_table()` to `plan_table_flat()` (keep its signature). This becomes the `--table` renderer.
  - New `plan_panels(plan)` returns an iterable of Rich renderables (one Panel per workspace).
  - New helpers: `_location_for_workspace(actions)` and `_relativise(target, location)` / `_relativise_command(cmd, location)`.
- `src/clain/cli.py`:
  - Add `--table` flag to `plan recreate` and `plan move`.
  - Mutex check: `--table` and `--json` together is a CLI error.
  - Default render path: call `plan_panels()` and print each.
- Skills bodies (`skills/clain-plan-recreate/SKILL.md`): mention `--table` as the copy-paste-friendly output and note that the default render is workspace-grouped panels with relative paths.

### Tests

- `test_plan_table_flat_snapshot_unchanged` — `plan_table_flat()` produces byte-identical output to the pre-0012 `plan_table()` against a fixed-width Console on a fixture plan. The snapshot lives at `tests/snapshots/plan_table_flat.txt`. This is the machine-checkable form of the backwards-compat claim.
- `test_persisted_plan_json_identical_across_modes` — the JSON file written under `$XDG_STATE_HOME/clain/plans/` is byte-identical regardless of whether the run was default, `--table`, or `--json`. The render mode does not bleed into the persisted artefact.
- `test_plan_panels_disjoint_tree_falls_back_to_workspace_path` — a fixture plan whose actions have targets with no common prefix below `/` renders without error, falls back to the workspace's classify-cache `path`, and emits absolute targets in the Target column.
- `test_plan_panels_renders_one_per_workspace` — multi-workspace plan produces N Panel renderables.
- `test_plan_panels_workspace_in_title` — workspace name and location appear in the Panel title.
- `test_plan_panels_target_is_relative` — for a delete action with target `<loc>/.pixi`, the rendered Target column contains `.pixi`, not the absolute path.
- `test_plan_panels_command_is_relative` — for a delete command `rm -rf '<loc>/.pixi'`, the rendered Command(s) contains `rm -rf '.pixi'`.
- `test_plan_panels_recreate_target_is_dot` — for a recreate action whose target equals the workspace root, the rendered Target column is `.`.
- `test_plan_panels_long_value_wraps` — a long target wraps rather than truncates.
- `test_plan_table_flat_unchanged` — the renamed `plan_table_flat` produces output equivalent to the current `plan_table` (absolute paths, single table).
- `test_cli_table_flag_renders_flat_layout` — `clain plan recreate --here --dry --table` produces the flat layout.
- `test_cli_table_and_json_are_mutex` — passing both flags errors.
- `test_json_output_unchanged` — JSON shape is identical to before this spec.

### Documentation updates

- `docs/USAGE.md`: replace the current plan capture with the new Panel-per-workspace capture; add a one-paragraph note about `--table` for spreadsheet copy-paste.
- README.md: no plan capture is shown there today, but the "what classify produces" caption can mention that `clain plan recreate --here --dry` produces the matching workspace-grouped action list.
- CHANGELOG.md: Unreleased gets a 0012 entry.
- Captures regenerated via `examples/capture.py` (already exists per spec 0011).

## Acceptance

- [ ] Default `clain plan recreate --here --dry` output is one Rich Panel per workspace, with workspace name + location in the title and a Rich Table of actions below.
- [ ] Target column shows paths relative to the location; recreate-workspace-root actions show `.`.
- [ ] Command(s) column rewrites embedded location-prefixed paths to relative form.
- [ ] Long values wrap (don't truncate).
- [ ] `--table` renders the existing single-table layout with absolute paths — verified by `test_plan_table_flat_snapshot_unchanged` (snapshot equality against a captured pre-0012 output).
- [ ] Persisted plan JSON on disk is byte-identical across all three modes (default, `--table`, `--json`) — verified by `test_persisted_plan_json_identical_across_modes`. Rendering is render-only; the JSON-shape invariant from spec 0005 is preserved.
- [ ] Disjoint-tree fallback works without crashing (`test_plan_panels_disjoint_tree_falls_back_to_workspace_path`).
- [ ] `--table` and `--json` together exit non-zero with a Rich error.
- [ ] JSON shape is unchanged from before this spec (full absolute paths preserved).
- [ ] Unsafe-actions banner still renders above the workspace panels when any action is unsafe.
- [ ] Footer renders below the workspace panels in default mode; below the flat table in `--table` mode.
- [ ] Skills' bodies mention `--table` and note the default layout change.
- [ ] CHANGELOG.md Unreleased has a 0012 entry.
- [ ] All existing tests pass; new tests above all pass.
- [ ] PR follows the workflow template.

## Out of scope

- TSV / CSV pure-text output (no Rich rendering at all). A future spec can add `--csv` if `--table` proves insufficient for spreadsheet workflows.
- Pager / `less`-style interactive scroll for very large plans. Rich supports `Console.pager()`; defer until a real plan size makes this necessary.
- Collapsible / interactive Panel — Rich is render-and-print; full interactive collapse needs a TUI (Textual), which is a much larger surface change. Future spec if developers want it.
- Sorting / filtering controls (`--sort by-class`, `--filter unsafe-only`, etc.). Defer until a real use case appears.
- Width auto-tuning beyond Rich's defaults. The Console figures it out; the spec doesn't add complexity here.

## Notes

- The mock-up pass during spec authoring rendered four candidate layouts (A: panel+table, B: Tree, C: section-header rows in one table, D: manual alignment). The mock script lives at `/tmp/0012-mock.py` for re-running during implementation review; it is not persisted in the repo because its purpose is review-time exploration, not regression-test infrastructure (the actual capture script `examples/capture.py` from spec 0011 is the persistent artefact).
- A future spec — *clain plan summary* — could add a one-line-per-workspace summary mode (`--summary`) for very wide trees. Not in 0012.
