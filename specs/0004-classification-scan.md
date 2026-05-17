---
id: 0004
title: Categorical workspace classification scan
status: shipped
goal: Goal 1 (Categorical visibility) — establishes the categorical view that all later planning depends on
supersedes: previously-shipped 0004 (Inventory of synced tree), now retracted along with its quantitative model
---

## Problem

The previous 0004 walked every file in every workspace to compute precise sizes and heavy-subdir totals. On the real synced tree (~58 workspaces, 593 top-level heavy dirs, multi-million files) this is minutes-to-an-hour of `stat` traffic, and it produces quantitative output that the project does not actually need: every cache-managed directory routes to the same answer regardless of its size, and every ephemeral directory is reclaimable regardless of its size. Quantification was load-bearing only for ranking — and the categorical model removes the need to rank.

## Intent

A `clain classify` subcommand that walks each workspace **only down to the first directory that matches a known class, then stops** — no recursion into `node_modules`, `.venv`, `site-packages`, etc. Per workspace it records: the class-tagged subtrees found, whether the workspace itself sits inside the synced tree, and the manifests present at the workspace root (which downstream `clain plan` uses to derive recreate commands). Read-only; produces a JSON cache that the plan commands consume.

## Spec

**Classes (closed set, identified by directory name only).**

| Class | Directory names |
|---|---|
| `cache-managed` | `node_modules`, `.venv`, `venv`, `site-packages` |
| `ephemeral` | `dist`, `build`, `.next`, `.cache` |
| `bytecode` | `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache` |
| `workspace-source` | implicit — everything that is not one of the above |

The class set is exported from `clain.classes` as a single source of truth that 0005 reads. Adding or renaming a class requires a spec amendment.

**Subcommand.** `clain classify [ROOT] [OPTIONS]`.

- `ROOT` (positional, optional): the dev root to scan.
  - **No baked-in default that contains personal information.** Resolution order: explicit positional arg → `CLAIN_DEV_ROOT` env var → fail with a clear Rich error instructing the developer to set one. This is a deliberate change for the public repo — the prior code hardcoded a Google Drive path with a personal email and that does not belong in a published default.
- Optional: `CLAIN_SYNCED_ROOT` env var separately identifies "the synced tree" so the *under-synced-root* test in classification is decoupled from whichever root is being scanned. Defaults to the configured `CLAIN_DEV_ROOT` when unset.

**Scan algorithm (depth-limited, prune-at-class).**

1. Enumerate depth-1 children of `ROOT` that are directories and not dotfiles → these are workspaces.
2. For each workspace, walk it with `os.walk` but **prune any directory whose name matches a known class**. On encountering such a directory, record `(class, relative_path)` and do not recurse into it.
3. At the workspace root only, record which manifests are present (`pyproject.toml`, `package.json`, `requirements.txt`, `pixi.toml`, `uv.lock`, `pnpm-lock.yaml`, `package-lock.json`, `Pipfile`, `Dockerfile`, `docker-compose.yml`, `.envrc`). Manifests are read-on-demand by 0005, not parsed here.
4. Determine whether the workspace's absolute path is under the resolved `CLAIN_SYNCED_ROOT` → boolean `in_sync_tree`.

The walk does not stat individual files. It scandir's directories only. On the user's actual tree this should complete in **seconds, not minutes**.

**Output.**

- Default: Rich table — workspace name, class-tag counts (e.g. `cache-managed×3, ephemeral×1`), manifests present, sync placement. Sorted by workspace name.
- `--json`: schema v1 JSON document covering the full structure.
- `--workspace NAME`: drill into one workspace, showing its full class-tagged subtree list.

**Caching.** Persist to `$XDG_STATE_HOME/clain/classify/<root-hash>.json`. Same locality rule as before: never inside the project, never inside the synced tree. TTL: 24h. Flags `--refresh` and `--no-cache` behave as in the previous design.

**Read-only guarantees.** No filesystem-mutating syscall against any path derived from `ROOT`. The mutation-vector ban list from the previously-shipped 0004 carries forward unchanged: every `os.remove`/`os.unlink`/`os.rename`/`os.replace`/`os.mkdir`/`os.makedirs`/`os.rmdir`/`os.chmod`/`os.chown`/`os.symlink`/`os.link`/`shutil.rmtree`/`shutil.move`/`shutil.copy*`/`Path.unlink`/`Path.rename`/`Path.replace`/`Path.mkdir`/`Path.rmdir`/`Path.chmod`/`Path.touch`/`Path.write_text`/`Path.write_bytes`/`Path.symlink_to`/`Path.hardlink_to`/`open(..., "w"|"a"|"x"|...)` is forbidden against any path derived from `ROOT`.

**Logging.** Append per-invocation line to `$XDG_STATE_HOME/clain/logs/classify.log`: timestamp, root, workspace count, class-tag total, duration.

## Acceptance

- [ ] `clain classify <ROOT>` runs to completion on the real synced tree in well under one minute on a warm GDrive cache.
- [ ] The scan stops at every directory matching a known class — verified by counting `os.walk` directory visits and asserting it does not exceed the *pruned* directory count for a fixture tree.
- [ ] `clain classify --json` emits schema-v1 JSON with: workspace name, in-sync-tree flag, list of `(class, relative_path)` tuples, list of manifests present.
- [ ] With no `CLAIN_DEV_ROOT` set and no positional arg, the command exits non-zero with a clear Rich error.
- [ ] No personal information (email, hostname, full home path) is baked into any default constant in the source.
- [ ] Code review confirms the mutation-vector ban list holds against any path derived from `ROOT`.
- [ ] Tests cover: fixture tree with all four classes present; manifests-present detection; the pruning invariant; the no-default-personal-info rule.

## Out of scope

- Sizing anything. We do not measure, we route.
- Duplicate detection. The structural fix (consolidate to one store per ecosystem) makes duplicate counts redundant.
- The plan or recommendation surface. That is 0005.
- A Claude Code plugin skill surfacing classify results — future spec, modelled on 0003.
- Detecting custom class directories not in the closed set (e.g. `target/` for Rust, `tmp/`). Add via spec amendment when needed.
- Stale-mtime heuristics ("not touched in 6 months"). Reintroduce in a later spec only if the categorical model leaves a gap.
