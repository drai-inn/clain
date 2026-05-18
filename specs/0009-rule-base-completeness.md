---
id: 0009
title: Rule base completeness — `.pixi/` class, bare-`venv` removal, `.git`-style prune, honest `in_sync_tree`
status: shipped
goal: Goal 1 (Categorical visibility) — fixes for the categorical view to be *correct* not *noisy*; Goal 7 (Honest sync hygiene) — make `in_sync_tree` mean something
---

## Problem

Dogfooding `clain classify` against `~/dev/` (which contains this project plus `cognee-me` and `clain-it-up`) produced output that's noisy and partially dishonest. Specifically:

- **`clain-me` itself emitted 106 `bytecode` tags.** Every one of them was a `__pycache__` directory nested deep inside `.pixi/envs/default/lib/python3.12/.../`. The signal "this workspace has bytecode caches" is real; surfacing 106 individual paths inside a single Pixi env is noise.
- **`venv` matched as cache-managed at `.pixi/envs/default/lib/python3.12/venv`.** That path is CPython's stdlib `venv` *module*, not a Python virtual environment. The rule `venv ∈ cache-managed` is too aggressive without a marker check.
- **`In sync tree: ✓` for every workspace under `~/dev/`.** `~/dev/` is the *local* tree; the cleanup target is the GDrive path. The current default — `CLAIN_SYNCED_ROOT` falls back to `CLAIN_DEV_ROOT` when unset — makes the column always-true and therefore meaningless.
- **`.git/` is walked into pointlessly.** It carries no class-named subtrees, but it's deep and slow. The scan time on three workspaces was ~0.5s, dominated by `.git/` and `.pixi/`.

These are bugs against INTENT goal 1 (categorical visibility — the view should be correct, not noisy) and goal 7 (honest sync hygiene — `in_sync_tree` should be meaningful, or absent). They're all addressable in the rule base.

## Intent

Make classify produce a clean, correct categorical view against any tree:

- `.pixi/` is its own cache-managed directory; the scan stops there, doesn't enumerate its insides.
- Bare `venv` is removed from cache-managed (it produces false positives against the stdlib module of the same name). `.venv` stays — it's the conventional name and it isn't ambiguous.
- `.git/` (and other VCS metadata directories) are pruned during the walk *without being reported as a class*. This is presentation-level pruning, not a new class.
- `CLAIN_SYNCED_ROOT` defaults to *unset* rather than to `CLAIN_DEV_ROOT`. When unset, `in_sync_tree` is `null` and the rendered column shows that explicitly with a footer note pointing the user at the env var.

All of this is rule-base + tiny classify-side changes. No behaviour change to plan, executor, or skills.

## Spec

### Rule base (`src/clain/rules.toml`)

- **Add `.pixi` to the `cache-managed` class**, alongside `node_modules`, `.venv`, `site-packages`. Pixi's `.pixi/` directory is regenerable via `pixi install`; treating it as a single cache-managed unit (and stopping the walk there) is the correct framing.
- **Remove bare `venv` from `cache-managed`.** The `.venv` entry remains. Document the removal in a top-of-file comment so a future contributor doesn't reintroduce it.

  **Trade-off, named explicitly:** a workspace that uses a legitimate, conventional Python virtual environment named `venv/` (with `pyvenv.cfg` inside) will no longer be detected as cache-managed. Such a `venv/` directory now classifies as workspace-source — which means it would be *included* in the move plan's rsync rather than excluded as a cache-managed subtree. The user-visible consequence: if you run `clain plan move` on a workspace with a bare `venv/`, that env directory will travel with the move and break (absolute paths in `pyvenv.cfg`). The mitigation is the workflow rule in [docs/USAGE.md](../docs/USAGE.md): "rename `venv/` → `.venv/` before running `clain plan move`", or open a follow-up spec proposing marker-based detection. The trade-off is acceptable because the false-positive cost (stdlib `venv` module inside every Pixi env) is large and immediate, while the false-negative cost (legitimate bare `venv/`) is rare and named.
- **Add a new top-level `[prune]` table** with a `names` array. Loader exposes this as `Rules.prune_names`. Directories matching prune names are skipped at walk time and *not* reported in `class_tags`. The symmetric invariant — stated here so it's testable: pruned names also never appear in `manifests` (they're directories, not files, so they couldn't anyway, but the test surface should make this explicit). Initial entries:

  ```toml
  [prune]
  # Pruned during walks for performance and quietness. Not reported as a class
  # because they aren't actionable subjects of any plan — they're just metadata
  # the scan should skip. Adding to this list requires a spec amendment.
  names = [".git", ".hg", ".svn", ".jj"]
  ```

### Loader (`src/clain/rules_loader.py`)

- Add `prune_names: frozenset[str]` to the `Rules` dataclass.
- Parse the new `[prune]` table. Empty/missing section is fine (yields an empty frozenset).
- Validation: prune names must be strings; they must not overlap with any class's `directory_names` (a name can't be both classified and pruned).

### Classify (`src/clain/classify.py`)

- During the walk, pruning logic extends: a directory whose name is in `rules.prune_names` is removed from `dirnames[:]` exactly like a class-named directory, but **no `ClassTag` is recorded**.
- `in_sync_tree` becomes `bool | None`. When `synced_root` is `None`, the field is `None`; otherwise the existing `_is_under` check applies.

### Config (`src/clain/config.py`)

- `resolve_synced_root` no longer defaults to the dev root. Signature changes to `resolve_synced_root() -> Path | None`. Returns `None` if `CLAIN_SYNCED_ROOT` is unset.
- `resolve_dev_root` unchanged.

### CLI (`src/clain/cli.py`) and tables (`src/clain/ui/tables.py`)

- The `classify` command passes `synced_root` (possibly `None`) through to `run_classify`.
- The table renderer shows `In sync tree` as:
  - `✓` when `in_sync_tree` is `True`
  - `·` when `in_sync_tree` is `False`
  - `?` when `in_sync_tree` is `None`
- The footer adds a one-line note when *any* workspace's `in_sync_tree` is `None`: `[dim]CLAIN_SYNCED_ROOT not set — pass it to enable in-sync detection.[/dim]`

### JSON schema

`in_sync_tree` becomes nullable in the classify v1 schema. Existing consumers that treated it as `bool` should handle `null` as "unknown". The schema version stays at 1 because the only in-repo consumer (`build_move_plan`) already uses falsy semantics (`if not ws.get("in_sync_tree"): continue`), which treats `null` and `False` identically — exclusion from move plans, which is the correct behaviour. The `scan` block now also records `synced_root` as nullable.

**Schema-notes discipline (load-bearing).** When a schema gains a nullable field, the change is recorded as a line in this spec's Notes section and in `CHANGELOG.md`'s Unreleased entry. A future external consumer that relies on `isinstance(in_sync_tree, bool)` will need to read those notes. Schema version `1` continues to apply to both `null` and `bool` cases.

### Plan side

`build_move_plan` already filters on truthy `in_sync_tree`. With `None` workspaces, they are excluded from move plans — which is the correct behaviour ("we don't know if you want to move them; configure `CLAIN_SYNCED_ROOT` if you do").

## Acceptance

- [ ] `rules.toml` has `.pixi` in `cache-managed`, no bare `venv` in any class, and a `[prune]` section.
- [ ] `Rules.prune_names` is exposed by the loader and validated against class overlap.
- [ ] Running `CLAIN_DEV_ROOT=<this repo's parent> clain classify --refresh` against the live `~/dev/` produces, for `clain-me`, fewer than 10 class tags total (down from 110+ today). The exact target is "no recursion into `.pixi/`"; the count is the proxy.
- [ ] `.git/` is not recursed into. A fixture-based test plants a deep marker file inside `.git/` and asserts the scan does not see it (mirrors the existing `test_classify_prunes_class_dirs`).
- [ ] `CLAIN_SYNCED_ROOT` unset → `in_sync_tree` is `null` in JSON; rendered as `?` with footer note.
- [ ] `CLAIN_SYNCED_ROOT` set to a real path → in-sync detection works as before.
- [ ] All existing tests continue to pass after the in_sync_tree type change.
- [ ] New tests: prune-pruning (`.git` deep marker invisible), `.pixi` class membership, removal of bare `venv` matching (fixture with `venv/pyvenv.cfg` classifies as workspace-source, not cache-managed), nullable `in_sync_tree`, footer note when any workspace has unknown sync state, prune-names-don't-collide-with-class-dirs (loader validation).
- [ ] PR follows the spec 0006 template (auto-populated from `.github/PULL_REQUEST_TEMPLATE.md`).

## Out of scope

- pyvenv.cfg-based marker detection for bare `venv` (or other ambiguous names). Future spec if it bites.
- Adding a class for `.tox`, Rust `target/`, Java `.gradle/`, etc. Each is a small additive change once the rule-base extension pattern is exercised — defer until a real workspace tree hits the gap.
- Plan-side rendering improvements (tree-grouped workspaces, `Location` column, relative paths). That is spec 0011's job.
- Doc generalisation away from GDrive-specific framing. That is spec 0010's job.
- Cleaning up the stale `~/.local/state/clain/{duplicates,inventory,reports}/` directories left over from before specs 0004/0005 were rewritten. Cosmetic; a one-line note in CONTRIBUTING.md is enough.

## Notes

- Spec 0011 (output presentation) will additionally compress repetition in the plan table (tree-grouped workspaces + `Location` column + relative `Target`/`Commands`). That's separate from this spec.
- Spec 0010 (doc generalisation) is the right place to mention `CLAIN_SYNCED_ROOT` as the general handle for "wherever your synced storage is (GDrive, OneDrive, Dropbox, iCloud Drive)" — and to make examples speak to the general case, not the GDrive-specific one.
