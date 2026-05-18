---
id: 0013
title: Output legibility + sync-placement autodetect (macOS); remove `CLAIN_SYNCED_ROOT`
status: shipped
goal: Goal 1 (Categorical visibility — the output should *teach* the categorical model, not assume it); Goal 7 (Honest sync hygiene — the sync-placement line should say what it knows, not punt)
---

## Problem

Dogfooding feedback from the core developer (the one who built it):

1. **The `Sync placement: ? unknown` line is unhelpful when the answer is obvious.** When a workspace clearly lives at `~/dev/clain-it-up/clain` — plainly not under any synced-storage tree — surfacing `?` is technically honest (per spec 0009) but reads as "the tool can't tell". The synced-storage paths on macOS are a finite, well-known list. We can detect them.

2. **The output is dense and hard to read.** The current classify and plan renders cram tables against headers with minimal whitespace. Even Rich's defaults are tight without explicit padding. Multiple captures look like a wall of text.

3. **There are no legends or explanatory text.** Even the core developer doesn't know what the **Safe?** column means without re-reading spec 0005. Columns like *Class* assume the reader has internalised the four classes from spec 0004. The output renders the data but doesn't *teach the model*.

All three are about making the same information more useful at first read, without changing what's underneath.

## Intent

Combine three related changes in one pass:

- **Orientation headers + breathing room + structured meta blocks** on every primary output (classify and plan, single-workspace and tree). Use Rich's `Group`, `Padding`, `Rule`, and `Console.print` separators honestly instead of relying on default densities.
- **Inline legends/keys** explaining each column and the conventional symbols (`✓`/`✗`/`⚠`). Toggleable via `--legend` / `--no-legend` / `CLAIN_LEGEND=on|off`. Default *on* for `--here` (single-workspace, friendly-onboarding case), default *off* for tree mode (power-user case where the legend would repeat).
- **Sync-placement autodetection on macOS.** Detect the standard synced-storage path patterns. `?` reserved for non-macOS (sync placement isn't autodetected on those platforms). **Removes `CLAIN_SYNCED_ROOT` entirely** — see the dedicated section below for the rationale.

No behaviour change to plan / executor / phase gate. No JSON schema break. Pure presentation + a small honest-detection helper.

## Spec

### Sync-placement autodetection (macOS only)

A new helper `clain.sync_detect.detect_synced_storage(workspace_path: Path) -> SyncPlacement` examines the absolute, resolved workspace path against a fixed pattern list:

| Pattern (prefix, with `~` expanded) | Provider |
|---|---|
| `~/Library/CloudStorage/GoogleDrive-` | Google Drive |
| `~/Library/CloudStorage/OneDrive-` | OneDrive |
| `~/Library/CloudStorage/Dropbox` | Dropbox |
| `~/Library/CloudStorage/Box-Box` | Box |
| `~/Library/Mobile Documents/com~apple~CloudDocs` | iCloud Drive |
| `~/Dropbox` | Dropbox (classic) |

Returns a three-tuple: `("synced", provider_name, matched_root)`, or `("local", None, None)`, or `("unknown", None, None)` (the last is for non-macOS). The `matched_root` is the prefix path that triggered detection — useful as evidence in the JSON output and for disambiguating which CloudStorage tenant matched when multiple are mounted.

Patterns are gated by `sys.platform == "darwin"`. Off macOS the helper always returns `("unknown", None, None)`; the developer can read the workspace path themselves (sync placement isn't autodetected; a future spec adds Linux/Windows patterns when a non-macOS developer needs them).

The patterns table lives in `src/clain/sync_detect.py` as a module-level constant — same data-not-code principle as the rule base, but small enough that a separate TOML feels like overkill. A test enumerates the patterns and asserts each detects its intended provider.

**On the provider-name strings (anonymisation discipline):** the provider names in the pattern table — `Google Drive`, `OneDrive`, `Dropbox`, `Box`, `iCloud Drive` — are generic service brand names, not personal information. Spec 0008's anonymisation discipline (no email-bearing paths, no `/Users/<name>/`, no tenant-specific identifiers) is not implicated by their presence. The `test_public_docs_contain_no_personal_info` needle list does not catch them and should not.

### Sync-placement resolution

1. **Autodetection on macOS** — match the workspace path against the patterns table. Match → `("synced", <provider>, <matched_root>)` rendered as `⚠ in synced storage (<provider>; autodetected)`. No match → `("local", None, None)` rendered as `✓ local (no synced-storage pattern detected)`.
2. **Off macOS** — `("unknown", None, None)` rendered as `? unknown (sync placement not autodetected on this platform)`.

There is **no environment-variable override**. See the `CLAIN_SYNCED_ROOT` removal section below for the rationale.

The render glyphs:

- `✓` (green) — workspace is *out of* synced storage (the desired state)
- `⚠` (yellow) — workspace *is in* synced storage; this is the actionable case
- `?` (dim) — genuinely unknown (non-macOS)

The JSON schema gains an additive `sync_placement` block in the workspace record:

```json
"sync_placement": {
  "state": "synced" | "local" | "unknown",
  "provider": "Google Drive" | null,
  "source": "autodetect" | "unset",
  "synced_root": "/Users/.../CloudStorage/GoogleDrive-..." | null
}
```

- `source` enum reduced to two values (`"env"` removed alongside `CLAIN_SYNCED_ROOT`).
- `synced_root` is populated whenever `state == "synced"` with the matched prefix path (evidence).
- `null` everywhere when `state == "unknown"` or `"local"`.

The existing `in_sync_tree` boolean stays for backwards compatibility — it equals `state == "synced"` (and `null` when `state == "unknown"`).

### Removal of `CLAIN_SYNCED_ROOT` (load-bearing)

`CLAIN_SYNCED_ROOT` was introduced in spec 0009 as the workspace-parent pointer for in-sync detection. After this spec lands, **it is removed entirely** for three reasons:

1. **It was always a workspace-parent pointer, not a sync claim.** Calling it `SYNCED_ROOT` implied "this path is what counts as synced storage", but in practice everyone set it to `CLAIN_DEV_ROOT` or its parent — the same path used for tree-mode scans. Two env vars for one concept.
2. **Autodetection covers the real case.** The macOS path patterns are unambiguous and there's no plausible workspace under a synced-storage tree that *doesn't* match one of them — that's how the providers mount.
3. **Honest off-platform behaviour.** Off macOS, sync placement just isn't autodetectable from the path; a half-supported env-var fallback is worse than saying "unknown" honestly. A future spec adds per-OS patterns.

**Hard-error on the deprecated env var.** If `CLAIN_SYNCED_ROOT` is set in the environment when `clain` runs (any subcommand), the CLI exits non-zero before doing anything with a Rich-formatted error pointing the user at this spec and instructing them to `unset CLAIN_SYNCED_ROOT`. Hard error rather than warning because the change is unambiguous: if you had the env var set, you had it set for a reason; that reason no longer applies; surfacing the change immediately prevents silent confusion.

The error fires in `cli.py`'s `@app.callback()` so it runs before any subcommand. `--version` and `--help` use eager callbacks and still work (they exit before the main callback runs).

### Legend toggle: precedence and defaults

A single `legend: bool` flag drives all renderers. Resolution:

1. Explicit `--legend` / `--no-legend` flag — highest precedence.
2. `CLAIN_LEGEND` env var.
3. Mode default: `--here` ⇒ on; tree mode ⇒ off.

**`CLAIN_LEGEND` accepted values** (case-insensitive): `on`, `1`, `true`, `yes` map to *on*; `off`, `0`, `false`, `no` map to *off*. Any unset/empty value falls through to the mode default. **Unknown values** (e.g. `CLAIN_LEGEND=maybe`) trigger a clear Rich error at CLI invocation time naming the accepted vocabulary — silently falling through would mask typos.

A small helper `clain.ui.legend.should_show_legend(here: bool, flag: bool | None, env: str | None) -> bool` centralises this so every command applies the rule identically. Tests cover each precedence case and the unknown-value error.

### Classify renderers

**Single-workspace (`--here`) default view** — replaces the current `single_workspace_tree`. Structure:

- Top line: `clain classify --here  →  one-workspace classification` (orientation header)
- Blank line
- **Header block** (label-aligned, indented): Workspace / Location / Sync placement / Manifests
- Blank line
- **Regenerable subtrees** section, with the total count in the heading. For each class found: bold class name + count + one-sentence description, then the indented relative-path list. Classes ordered by a fixed sort (cache-managed, ephemeral, bytecode, then alphabetical for any future classes).
- Blank line
- **Next step** section: the command to run and what it would do.
- A `Rule` separator
- Meta line: `scan {duration}s` + cache hint if applicable
- If `legend` is on: a Key section explaining the classes succinctly.

**Tree-mode default view** — keeps the existing multi-row `classify_table` (it's the right shape for many workspaces) but wraps it with:

- Orientation header line
- Brief sync-placement summary above the table (count of workspaces in synced storage)
- Footer with structured meta (Workspaces · In synced tree · Class tags · scan duration · cache state)
- If `legend` is on (forced via flag/env): a Key section below.

The default for tree mode is `legend: off` — the table itself is the focus; the legend would force vertical scroll past it.

**Wrapping invariant (symmetric with the plan-table guarantee):** the orientation header, sync summary, footer, and Key section sit **outside** the inner `classify_table()` Rich `Table`. The inner `Table` body is unchanged from spec 0009. If a future snapshot test wants to assert classify-table backwards-compatibility, the wrapping doesn't pollute the assertion target.

### Plan renderers

**Default `clain plan recreate --dry` view** — replaces the current call sequence `plan_header + plan_panels + plan_footer`. Structure:

- Top line: `clain plan recreate --here --dry  →  delete-and-recreate plan` (with `--here` suppressed in tree mode)
- Blank line
- The existing workspace-grouped Panels from spec 0012, but with the Panel's `padding` increased from `(0, 1)` to `(1, 2)` for breathing room inside the panel body.
- If `legend` is on: a **Key** section explaining the Type / Class / Target / Command / Safe? columns and the `✓`/`✗` semantics, including a pointer to `clain plan explain <ACTION_ID>` for unsafe actions.
- A `Rule` separator
- A structured **Summary / Saved / Mode** meta block (label-aligned, three rows instead of one wide line).

Unsafe-actions banner from spec 0005 still renders above the panels when applicable.

### `--table` mode

The single-table render (`plan_table_flat`) is preserved per spec 0012. Its legibility is also affected by these changes:

- Orientation header line (consistent with default mode)
- If `legend` is on: the same Key section appears after the table.
- Structured meta block at the foot.

The table content (columns, absolute paths) is unchanged. The snapshot test from spec 0012 still asserts byte-equality of just the inner `plan_table_flat()` Table — the orientation/legend wrapping is around it, not inside.

### CLI surface

Add to `classify`, `plan recreate`, `plan move`:

```
--legend / --no-legend     toggle the legend explicitly
```

The classify command keeps `--here`. Behaviour:

- No flag passed: mode default applies (here ⇒ on, tree ⇒ off), unless `CLAIN_LEGEND` is set.
- `--legend`: force on.
- `--no-legend`: force off.

Mutual flag handling: `--legend` and `--no-legend` together is a CLI error with a clear message.

### Tests

- `test_sync_detect_macos_patterns` — each pattern in the table detects its intended provider; non-matching local path returns `("local", None, None)`.
- `test_sync_detect_returns_matched_root_on_synced` — when a pattern matches, the third tuple element is the matched prefix path (evidence).
- `test_sync_detect_non_macos_returns_unknown` — patch `sys.platform` to `linux` and verify behaviour.
- `test_clain_synced_root_env_is_hard_error` — set `CLAIN_SYNCED_ROOT`, run any `clain` subcommand, assert exit code is non-zero and the error names the spec.
- `test_legend_resolution_precedence` — flag beats env beats mode default; explicit on/off cases enumerated; `CLAIN_LEGEND` accepts the documented vocabulary; unknown values raise.
- `test_legend_mutex_flags` — passing both `--legend` and `--no-legend` errors.
- `test_classify_here_view_has_orientation_and_header_block` — captured output contains the orientation line and the label/value pairs (Workspace/Location/Sync placement/Manifests).
- `test_classify_here_view_includes_legend_when_on` and `_excludes_legend_when_off`.
- `test_classify_tree_view_default_no_legend` — tree mode renders without a Key block by default.
- `test_plan_view_orientation_and_summary_meta` — meta block has Summary/Saved/Mode rows.
- `test_plan_view_panel_padding_increased` — visually verified via a capture snapshot diff (or render width assertions).
- `test_plan_table_flat_snapshot_still_unchanged` — spec 0012's backwards-compat invariant still holds; the inner flat table is byte-equal to the existing snapshot.
- `test_sync_placement_jsoned_in_payload` — the new `sync_placement` block appears in classify JSON.
- `test_in_sync_tree_aligns_with_sync_placement_state` — the legacy `in_sync_tree` boolean aligns with `sync_placement.state` across all three cases: `synced` ⇒ `True`, `local` ⇒ `False`, `unknown` ⇒ `null`. Machine-checked, not just documented.

### Documentation updates

- `docs/USAGE.md` — replace existing captures with new ones; add a "Reading the output" subsection naming the orientation/header/legend convention; document `--legend` / `--no-legend` / `CLAIN_LEGEND`.
- README.md — refresh the lead capture with the new classify-here render.
- CHANGELOG.md — Unreleased entry for 0013.
- Captures regenerated via `examples/capture.py`.

## Acceptance

- [ ] `clain classify --here` renders the new layout (orientation header, label-aligned metadata block, class-grouped subtrees with one-sentence descriptions, Next step section, Rule + meta line, Key section).
- [ ] `clain classify` in tree mode renders the existing table with an orientation header and structured meta footer; legend off by default.
- [ ] `clain plan recreate --here --dry` renders the Panel from spec 0012 with `padding=(1, 2)`, plus a Key section (legend on by default for `--here`), Rule, and Summary/Saved/Mode meta block.
- [ ] `clain plan recreate --dry` (tree mode) renders the same Panel sequence; legend off by default.
- [ ] `--legend` forces on; `--no-legend` forces off; `CLAIN_LEGEND=on|off` is the middle precedence; both flags together is a CLI error.
- [ ] On macOS, `clain.sync_detect.detect_synced_storage` returns the right provider AND matched-root prefix for each of the six patterns in the table.
- [ ] On non-macOS, the helper returns `("unknown", None, None)` and the render notes that sync placement is not autodetected on this platform.
- [ ] **`CLAIN_SYNCED_ROOT` is removed.** If set in the environment, any `clain` subcommand exits non-zero before doing anything, with a Rich error naming this spec and instructing the user to `unset CLAIN_SYNCED_ROOT`. Verified by `test_clain_synced_root_env_is_hard_error`.
- [ ] The legacy `in_sync_tree` field stays in JSON and aligns with `sync_placement.state` (`synced` ⇒ `True`, `local` ⇒ `False`, `unknown` ⇒ `null`).
- [ ] `plan_table_flat()` byte-equal snapshot from spec 0012 is unaffected.
- [ ] Persisted plan JSON is byte-identical across render modes (the spec 0012 invariant).
- [ ] CHANGELOG.md gains a 0013 entry; docs/USAGE.md captures refreshed.
- [ ] PR follows the workflow template.

## Out of scope

- Cross-platform autodetection (Linux / Windows). On those platforms, sync placement is reported `unknown`. The developer can read their workspace path themselves; reintroducing an env-var override on non-macOS would re-create exactly the confused-concern problem this spec just removed. A future spec adds Linux/Windows patterns when a non-macOS developer shows up.
- `clain doctor` for runtime tool detection (different concern; out of scope here).
- Pager / TUI / interactive collapse — Rich is render-and-print. Defer to a Textual-based future spec if developers want it.
- Theme support / colour customisation. Rich uses sensible defaults; if a developer wants custom themes, future spec.
- Localising legends / English-only strings. Future spec when a non-English contributor shows up.

## Notes

- The autodetect pattern table is short and finite. Adding a new provider (e.g. `pCloud`) is a one-line addition with a test; not a separate spec.
- Legend toggle precedence matches the pattern from spec 0010 (`--here` flag): explicit flag > env var > mode default. Worth noting so future flags reuse the same precedence rule.
- The "Key" section in classify uses one-line summaries; the plan Key is more detailed because the data has more dimensions. This asymmetry is intentional — classify is "look at what you have"; plan is "review what would happen if executed".
