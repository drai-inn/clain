---
id: 0010
title: Single-workspace mode — `clain` on the workspace you're currently in
status: shipped
goal: Goal 1 (Categorical visibility) and Goal 3 (Two action categories) — extended to the everyday "one workspace" case, not just the "tree of workspaces" case
---

## Problem

`clain` currently assumes ROOT *contains* workspaces as depth-1 children. That fits the "I have 30 AI-spawned workspaces piling up under GDrive" framing but misses the much more common everyday case: a developer sitting inside *one* workspace, wanting to know "what's regenerable here, and how would I clean and rebuild this project?"

Demonstrated by running `clain classify` against `clain-me` itself:

```
┃ Workspace ┃ In sync tree ┃ Class tags ┃ Manifests ┃
│ docs      │      ?       │ —          │ —         │
│ examples  │      ?       │ —          │ —         │
│ plugin    │      ?       │ —          │ —         │
│ skills    │      ?       │ —          │ —         │
│ specs     │      ?       │ —          │ —         │
│ src       │      ?       │ bytecodex2 │ —         │
│ tests     │      ?       │ bytecodex1 │ —         │
```

`clain-me` is one workspace, not seven. Treating `docs/`, `specs/`, `src/`, etc. as siblings of `node_modules/`-bearing workspaces is wrong.

The single-workspace case is more common than the multi-workspace one. Most developers have *one* active project at a time. Onboarding into `clain` is much easier when the entry-point experience is `cd into-a-project && clain classify --here` and you immediately get a useful answer.

## Intent

Add an explicit `--here` flag to `classify`, `plan recreate`, and `plan move` that switches the tool into **single-workspace mode**: ROOT (or cwd if not given) *is* the workspace, not a parent of workspaces. The rule base, the recreate-rule derivation, and the action ban list are all reused unchanged. Only the entry point and the rendering differ.

The default behaviour is unchanged. Passing `--here` is required to opt into single-workspace mode — there is no auto-detection. The user's call (recorded in question round): "explicit flag required" beats auto-detection for predictability and lower magic.

## Spec

### Flag surface

Add `--here` to three subcommands:

- `clain classify --here [PATH]`
- `clain plan recreate --here [PATH]`
- `clain plan move --here [PATH] --dest <DEST>`

Semantics:

- If `PATH` is given, it is treated as the single workspace.
- If `PATH` is omitted, `cwd` (`Path.cwd()`) is used. **`cwd` is runtime context, not a baked-in default**, so this does not violate the no-personal-info-in-defaults rule from spec 0004.
- `CLAIN_DEV_ROOT` is not consulted in single-workspace mode (it's a tree-mode concept). Neither is `CLAIN_SYNCED_ROOT` for path *defaulting*. However, `CLAIN_SYNCED_ROOT` **is** still consulted for evaluating `in_sync_tree` on the chosen workspace — single-workspace mode inherits spec 0009's nullable semantics (`null` when unset, `bool` when set). This keeps "where am I sitting in storage" answerable regardless of mode.
- The classify cache key under single-workspace mode keys off the workspace's absolute path, exactly as in tree mode (the `root_hash` function is unchanged).
- `--here` and `--tree` (implied default) are mutually exclusive: if a future spec ever adds an explicit `--tree`, it must mirror `--here`'s shape. This spec does not add `--tree`; the current default IS tree mode.
- **`--here` vs `--workspace NAME` are distinct, not interchangeable.** `--workspace NAME` (existing, tree-mode only) drills into one named depth-1 child of ROOT; `--here` declares that ROOT *is* the workspace. Passing both flags together is a CLI error with a clear Rich message naming the conflict.

### Behaviour: classify

`clain classify --here [PATH]` runs the existing `classify_workspace()` on the chosen path **once** (skipping the `_iter_workspaces` step entirely). The result is a `WorkspaceClass` for that one workspace. The JSON payload shape stays the same as multi-workspace classify (`workspaces` is a list with exactly one entry), so downstream consumers (`build_recreate_plan`, `build_move_plan`) work without changes.

A new field on the `scan` block, `mode`, distinguishes the two modes: `"tree"` (default) or `"single"`. Plan commands read this field — see below.

**Schema backwards-compat:** older cached classify JSON written before this spec has no `mode` field. Code reading it MUST treat absent `mode` as `"tree"` (the prior, implicit behaviour). This is the additive-nullable pattern from spec 0009 applied to mode. Schema version stays at 1.

### Behaviour: plan recreate

`clain plan recreate --here [PATH]` reads the classify cache for that path (single-workspace mode). The recreate logic is unchanged — it iterates `classify_payload["workspaces"]`, which in single mode has length 1. The plan output is therefore naturally smaller.

The plan persists under `$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json` exactly as in tree mode.

### Behaviour: plan move

`clain plan move --here [PATH] --dest <DEST>` is unchanged in logic. In single-workspace mode the plan will have at most one move action (plus its smoke-test). If the workspace has `in_sync_tree: false` or `in_sync_tree: null`, the plan is empty — same as tree mode. The user's recourse is to set `CLAIN_SYNCED_ROOT` so the workspace's sync placement can be evaluated.

### Rendering

Single-workspace classify output uses a dedicated renderer rather than the multi-row table. The result is a **Rich `Tree`** rooted at the workspace name, with classes as branches and class-tag relative paths as leaves. Sketch:

```
clain-me  (~/dev/clain-me)
├─ Manifests: pyproject.toml, pixi.toml
├─ In sync tree: · (not under CLAIN_SYNCED_ROOT)
├─ cache-managed
│  └─ .pixi
├─ bytecode
│  ├─ .mypy_cache
│  ├─ .pytest_cache
│  ├─ .ruff_cache
│  ├─ src/clain/__pycache__
│  └─ tests/__pycache__
```

A narrative line under the tree summarises what the recreate plan would do: `[dim]Next: clain plan recreate --here --dry → pixi install[/dim]` (when the workspace's manifest unambiguously maps to a recreate command). When ambiguous, the line names the ambiguity briefly.

Plan tables in single-workspace mode use the existing renderer; the smaller row count is the only difference. Spec 0011 will further compress plan-table presentation (tree-grouped workspaces, `Location` column, relative `Target`/`Commands`) — those changes are mode-agnostic and benefit single-workspace runs too.

### Edge cases

- `--here` with a path that doesn't exist → exit non-zero with a clear Rich error (same shape as tree mode's missing-root error).
- `--here` with a path that has *no* recognised manifest → classify still produces output (the workspace has class tags or doesn't); `plan recreate` produces a single action with `safe_to_execute: false` and `unsafe_reason: "no recognised manifest — investigate manually"` (existing behaviour from spec 0005, unchanged).
- `--here` with a path that contains *nested* projects (e.g. a monorepo). Out of scope for this spec — single-workspace mode treats the path as one workspace; nested-project discovery is a future spec if it bites.

### Tests

- `test_classify_single_workspace_basic` — `clain classify --here <fixture-workspace>` returns one workspace with the expected class tags.
- `test_classify_single_workspace_cwd_default` — when no path is given, cwd is used.
- `test_classify_single_workspace_records_mode` — JSON payload has `scan.mode == "single"`.
- `test_classify_single_workspace_tree_render` — rendered output uses a Tree, not the multi-row table.
- `test_classify_tree_mode_unchanged` — without `--here`, behaviour matches the existing test set.
- `test_plan_recreate_here_uses_cached_single_workspace` — plan side reads the single-workspace cache correctly.
- `test_plan_move_here_excludes_when_not_in_sync_tree` — move plan empty when the single workspace isn't in the synced tree.
- `test_clain_classify_on_itself` — a real-world dogfood test: `clain classify --here /Users/.../clain-me`-style fixture (anonymised to `<TMP>/clain-me`) produces the expected one-row tree with `.pixi` cache-managed and the three tool caches as bytecode.

### What stays the same

- The rule base (`rules.toml`) is unchanged.
- The phase gate is unchanged. `--execute` (default mode for plan) still raises `ExecuteGateClosed` regardless of `--here`.
- The mutation-vector ban list against ROOT is unchanged.
- The Agent Skills frontmatter and skill bodies are unchanged. A *future* spec could add `clain-classify-here` skills, but the existing `clain-classify` and `clain-plan-recreate` skills can simply mention the `--here` flag in their body without business-logic implications. (This is a one-line edit per skill; landed in this spec.)

## Acceptance

- [ ] `clain classify --here` works against a fixture workspace with manifests, producing exactly one workspace entry with correct class tags.
- [ ] `clain classify --here` defaults to cwd when no path is given.
- [ ] `clain classify --here` against a test fixture that mirrors `clain-me`'s structure (a `pixi.toml` + `pyproject.toml` at the root, a `.pixi/` subtree, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, plus non-class subdirs like `docs/`, `tests/`) produces a tree-shaped render with `.pixi` cache-managed and the three tool caches as bytecode; no false positives like `docs/` or `tests/` being rendered as separate workspaces. The acceptance test uses the synthetic fixture; manual dogfooding against the developer's own checkout is a sanity check, not a CI dependency.
- [ ] `clain plan recreate --here --dry` against the same path produces a one-workspace recreate plan with the correct command derived from `pixi.toml` (or whichever manifest applies).
- [ ] `clain plan move --here --dest <DEST> --dry` produces a one-workspace move plan when `in_sync_tree` is true; empty plan otherwise.
- [ ] `scan.mode == "single"` in the JSON cache for single-workspace runs; `scan.mode == "tree"` for the existing default.
- [ ] Existing tree-mode tests pass unchanged.
- [ ] The two relevant skills mention the `--here` flag in their bodies; the skill-body grep tests still pass (no Python source, no version literals).
- [ ] PR follows the workflow template (auto-populated from `.github/PULL_REQUEST_TEMPLATE.md`).

## Out of scope

- Auto-detection of single-workspace mode (user explicitly preferred explicit flag).
- Recursive / nested-workspace detection in monorepos.
- A new top-level subcommand like `clain inspect`. The flag-based approach reuses the existing surface.
- Plan-table tree-view with `Location` column and relative paths. Spec 0011.
- Doc generalisation away from GDrive-specific framing. Spec 0011 (or a later spec; sequencing TBD after 0010 lands).
- Watch-mode (`clain classify --here --watch` that re-runs on file changes). Future spec if developers want it.

## Notes

- Once 0010 ships, the README quickstart should lead with the single-workspace flow because it's the lower-friction entry point: *"`cd into-a-project && clain classify --here`"* is a 2-second value demo. That rewrite belongs in spec 0011's doc generalisation.
- This spec's value is that every developer now has a use for `clain`, not just developers drowning in AI-spawned workspace sprawl. That broadens the audience considerably and is one of the strongest arguments for the project's reach.
