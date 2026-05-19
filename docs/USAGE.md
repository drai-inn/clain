# Using clain

A walkthrough for the standard CLI user. For the agent perspective, see [../AGENTS.md](../AGENTS.md). For the contributor perspective, see [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Prerequisites

- macOS or Linux. The synced-storage concern is more acute on macOS (Google Drive / iCloud Drive / OneDrive / Dropbox all surface as `~/Library/CloudStorage/...` or similar) but the tool is portable.
- Either [pipx](https://pipx.pypa.io/) or [Pixi](https://pixi.sh/) — both manage isolated Python tool installs.
- Python 3.12+ (pipx / pixi will install or pick this up for you).

## First-time setup

Install `clain` as a global binary on `PATH`. Either of:

```sh
pipx install git+https://github.com/drai-inn/clain.git
# or, if you already use pixi for everything:
pixi global install --git https://github.com/drai-inn/clain.git clain
```

Verify with `clain --version`.

<!-- contributor-only -->
If you're hacking on `clain` itself, clone the repo and use the Pixi dev environment from inside the checkout instead — every `clain …` invocation below becomes `pixi run clain …`:

```sh
git clone https://github.com/drai-inn/clain.git
cd clain
pixi install
pixi run clain --version
```
<!-- /contributor-only -->

There are two ways to use `clain`, depending on what you're trying to do:

- **Single-workspace mode** (`--here`) — for "I want to tidy *this* project". This is the everyday entry point.
- **Tree mode** (default) — for "I have a whole `dev/` directory full of accumulated workspaces and want to triage them". Set `CLAIN_DEV_ROOT` to the tree.

Start with single-workspace mode unless you specifically need the tree view.

---

## Single-workspace mode

Run `clain` inside the project you want to inspect. No env vars needed — `--here` defaults to the current working directory.

```sh
cd ~/some/project
clain classify --here
```

`clain` looks at the project root, identifies which manifests are present (`pyproject.toml`, `pixi.toml`, `package.json`, `pnpm-lock.yaml`, `uv.lock`, …), walks the project tree stopping at every class boundary (`node_modules/`, `.venv/`, `.pixi/`, `dist/`, `__pycache__/`, etc.), and produces this:

```text
clain classify --here  →  one-workspace classification

  Workspace:       example-workspace
  Location:        ~/dev/example-workspace
  Sync placement:  ✓ local  (no synced-storage pattern detected)
  Manifests:       pixi.toml, pyproject.toml

  Regenerable subtrees (6):

    cache-managed (1)
      Lives in a per-ecosystem store. Safe to delete if you can
      re-install — your manifest tells clain how.
      .pixi

    bytecode (5)
      Regenerated automatically on the next run.
      .mypy_cache
      .pytest_cache
      .ruff_cache
      src/example/__pycache__
      tests/__pycache__

  Next step:
    clain plan recreate --here --dry
    → would run: pixi install  (derived from pixi.toml)

  ────────────────────────────────────────────────────────────────────────

  scan 0.001s

  Key
    cache-managed  regenerable from a manifest
    bytecode       regenerated automatically on use
    ephemeral      build output, regenerable by the build step
```

A few things to notice:

- **Header block** (Workspace / Location / Sync placement / Manifests) summarises the workspace before we look at its insides.
- **Sync placement** is autodetected on macOS against six known synced-storage path patterns (Google Drive, OneDrive, Dropbox, Box, iCloud Drive). On non-macOS, sync placement is reported `? unknown` — read your workspace path yourself. (There used to be a `CLAIN_SYNCED_ROOT` env var override; spec 0013 removed it because autodetect covers the real cases and the env var conflated two orthogonal concerns. If you have it set in your shell, `clain` hard-errors on startup with a pointer to unset it.)
- **Manifests** drive the recreate command derivation (here: `pixi install` from `pixi.toml`).
- The **Regenerable subtrees** section names each class with a one-line description of what that class *means* before listing its members. The scan stops at every class boundary — `.pixi/` is one entry, not 100 nested `__pycache__` directories.
- The **Next step** block names the command and what it would run.
- The **Key** block at the bottom is a quick reminder of class semantics — same shape as the plan-view Key, so the same reading habit works on both. Use `--no-legend` to suppress it (or set `CLAIN_LEGEND=off`).

A note on typography (spec 0014): the horizontal rule is a fixed-measure line that separates the body content from the run-meta footer; meta lines like `(cached — pass --refresh to rescan)` and `(dry mode — execution skipped)` sit indented below the rule with one blank line of breathing room above them.

Then ask for the plan:

```sh
clain plan recreate --here --dry
```

```text
clain plan recreate --here --dry  →  delete-and-recreate plan

  ╭─ example-workspace  ~/dev/example-workspace ───────────────────────────╮
  │                                                                        │
  │    Type       Class           Target          Command(s)      Safe?    │
  │   ──────────────────────────────────────────────────────────────────   │
  │    delete     cache-managed   .pixi           rm -rf '.pixi'    ✓      │
  │    recreate   cache-managed   .               pixi install      ✓      │
  │    delete     bytecode        .pytest_cache   rm -rf            ✓      │
  │                                               '.pytest_cache'          │
  │    ... (4 more bytecode rows)                                          │
  │                                                                        │
  ╰────────────────────────────────────────────────────────────────────────╯

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

  ──────────────────────────────────────────────────────────────────────────
  Summary  1 workspace  ·  7 actions  ·  0 unsafe
  Saved    $XDG_STATE_HOME/clain/plans/recreate-<UTC>.json
  Mode     dry-run (execution gate is closed — see executor.py)
```

Read this top-down. The plan is **7 actions, 0 unsafe**, with `pixi install` as the single recreate step. The workspace name and its absolute location live in the panel title (once); inside the panel, `Target` and `Command(s)` are **relative to that location**, so paths like `.pixi` and `tests/__pycache__` don't repeat the workspace prefix on every row.

If you'd rather have a single flat table with absolute paths (useful for copy-pasting into a spreadsheet), pass `--table`:

```sh
clain plan recreate --here --dry --table
```

`--table` and `--json` are mutually exclusive (both write the plan to stdout in a single format).

A full plan JSON also lands in `$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json` — that's your audit artefact.

Use `--json` to pipe machine-readable output:

```sh
clain plan recreate --here --dry --json > my-plan.json
```

## Tree mode

For "I have a whole `dev/` directory full of stuff":

```sh
export CLAIN_DEV_ROOT=~/some/dev/tree
clain classify
```

In tree mode `clain` enumerates each workspace at depth-1 under `CLAIN_DEV_ROOT`:

```text
                           Workspace classification                           
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Workspace       ┃ In sync tree ┃ Class tags     ┃ Manifests       ┃ Errors ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ example-ambigu… │      ?       │ cache-managed… │ pyproject.toml  │        │
│ example-fronte… │      ?       │ cache-managed… │ package.json,   │        │
│                 │              │ ephemeralx1    │ pnpm-lock.yaml  │        │
│ example-pipeli… │      ?       │ cache-managed… │ pixi.toml,      │        │
│                 │              │                │ pyproject.toml  │        │
│ example-uv-pro… │      ?       │ cache-managed… │ pyproject.toml, │        │
│                 │              │                │ uv.lock         │        │
└─────────────────┴──────────────┴────────────────┴─────────────────┴────────┘
```

The `In sync tree` column reports `✓` / `·` / `?` based on macOS autodetection against known synced-storage path patterns (Google Drive, OneDrive, Dropbox, Box, iCloud Drive):
- `⚠` — workspace is under a recognised synced-storage tree (likely candidate for `clain plan move`)
- `✓` — workspace is local (no synced-storage pattern matched)
- `?` — sync placement is not autodetected on this platform (non-macOS)

Drill into one workspace's full class-tag listing with `--workspace NAME`. Note that `--workspace` is tree-mode only — `--here` and `--workspace` are mutually exclusive.

The two plan commands in tree mode are:

- `clain plan recreate --dry` — per workspace, the delete-and-recreate actions across the tree.
- `clain plan move --dest ~/dev/ --dry` — for workspaces marked `in_sync_tree: true`, the rsync-out + smoke-test plan.

## Reading the output

What `safe_to_execute: false` means (look for it in `--json` output or the red "Unsafe" footer):

- `ambiguous Python toolchain — workspace has pyproject.toml but no pixi.toml / uv.lock / poetry.lock` — pick a toolchain and add its lockfile, then re-run.
- `package.json without a lockfile — recreate would resolve fresh versions` — non-reproducible. Commit a lockfile first.
- `no recognised manifest — investigate manually` — workspace has cache-managed subtrees but no manifest `clain` understands.

## Orientation: the brand meter, command emoji, intent line, and first-run banner

Every primary `clain` render opens with a fixed anchor row and a plain-English intent line:

```
▰▰▱▱▱  clain  🏷  classify --here

  Categorical scan of this workspace — what's regenerable, what isn't, and
  the recreate command derived from your manifest.
```

The five-block meter shows where the command sits in the conceptual workflow — `classify` is **2/5** (look at what's there), `plan recreate --dry` / `plan move --dry` is **3/5** (preview), `plan explain` is **4/5** (drill in), and the (currently gate-blocked) execute path is **5/5**. The filled blocks pick up the Tokyo Night brand-gradient colours; empty blocks render dim.

The emoji disambiguates per command: 🏷 `classify`, ♻️ `plan recreate`, 📦 `plan move`, 💬 `plan explain`. The intent line below describes what the command is *for*, not what was typed — restating the command is the shell's job.

On your first ever `classify` invocation per machine, `clain` prepends a one-shot ASCII-art banner with the project tagline and repo URL. The marker file lives at `$XDG_STATE_HOME/clain/banner-shown`. To force the banner on (e.g. for screenshots) or off:

```sh
clain classify --here --banner       # force show
clain classify --here --no-banner    # force hide
CLAIN_BANNER=off clain classify --here
```

`--json` mode never emits the banner; pipelines stay clean. `--banner` (the force-show flag) deliberately does **not** consume the first-run marker, so a screenshot run doesn't "eat" the user's real first contact.

## Plan JSON: the `action` field

The plan JSON identifies each entry's action category in an `action` field (delete / recreate / move / smoke-test):

```json
{ "action": "delete", "class": "cache-managed", "target": "...", "commands": [...] }
```

The schema version is **2** (spec 0016 bumped from 1 along with the `type → action` rename). Persisted plan files live at `$XDG_STATE_HOME/clain/plans/<kind>-<UTC>-v<schema>.json`; older schema-1 files are no longer loadable by `plan explain` — regenerate with `clain plan recreate` (or `plan move --dest …`) when you see the regenerate prompt. Stale-schema plans older than 7 days are pruned automatically on the next plan save.

## Theme

`clain` ships a Tokyo Night palette in two variants — **dark** (default) and **light**. The renderer never names a colour directly; every reference goes through a named token in [`src/clain/ui/theme.py`](../src/clain/ui/theme.py) (`brand`, `safe`, `unsafe`, `warning`, `fix`, `dim`, `accent`, plus per-class colours), so the dark↔light swap is a single resolution call.

Selection precedence (highest first):

1. `NO_COLOR` env var set — colour stripped entirely (Rich's standard behaviour, codified).
2. `--theme dark|light|auto` — explicit flag on the `clain` invocation.
3. `CLAIN_THEME=dark|light|auto` — same vocabulary as the flag.
4. Auto-detection from `COLORFGBG` (`fg;bg`, sometimes `fg;ig;bg`).
5. Best-effort OSC 11 query of the terminal background (50 ms timeout; skipped when stdout/stdin aren't TTYs).
6. Fallback: **dark**.

Unknown values for `--theme` or `CLAIN_THEME` are CLI errors naming the valid vocabulary (`dark`, `light`, `auto`).

```sh
clain --theme light classify --here
CLAIN_THEME=dark clain plan recreate --here --dry
NO_COLOR=1 clain classify --here    # plain text, no ANSI
```

## Customising the rule base

Class membership, manifest→recreate command mappings, and ecosystem placement advice live in [`src/clain/rules.toml`](../src/clain/rules.toml). It's a hand-editable (or genAI-editable) TOML file with a schema-version field.

You can fork the repo and adjust this file to suit your environment — adding a class for Rust's `target/` directories, for example, or a recreate rule for an internal package manager. The loader validates structure on load; duplicate directory names across classes or between classes and `[prune]` will refuse to load.

For the PR-side workflow of contributing such a change back, see [../CONTRIBUTING.md § Extending the rule base](../CONTRIBUTING.md#extending-the-rule-base-srcclainrulestoml).

## Common scenarios

### "I'm in a project and just want to know what's regenerable"

```sh
cd ~/some/project && clain classify --here
```

Done. The output tells you what's a regenerable cache and what's source. The `Next:` line tells you the recreate command.

### "I have 30 Node workspaces under a synced drive — what's the right sequence?"

1. `clain classify --refresh` — see which workspaces are in the sync tree. On macOS, this is autodetected against known synced-storage path patterns.
3. `clain plan move --dest ~/dev/ --dry` — preview moves out of the sync tree.
4. For each workspace you want to migrate: run the rsync command from the plan by hand.
5. `clain classify ~/dev/` — re-classify against the new local root.
6. `clain plan recreate ~/dev/ --dry` — preview the dependency rehydration.
7. For each workspace: run the recreate command by hand.

The `rationale` field on each recreate action includes placement advice (e.g. pnpm's store should live at `~/Library/pnpm/store`, not in-project). Apply that once, globally, before running any recreate commands.

### "My venv just got broken — what happened?"

If you moved a workspace containing `.venv` without first deleting and recreating: the venv's internal `pyvenv.cfg` and `bin/*` shebangs embed the old absolute path. The fix is `rm -rf .venv` followed by `pixi install` (or `uv sync` / `poetry install`, depending on the toolchain).

The move plan flags this in `preconditions` precisely so you don't move venvs by accident.

### "How do I know if a plan is safe to act on?"

Two signals:

- `summary.unsafe_count == 0` in the JSON, or no red Unsafe actions table at the head of the rendered output.
- Every action's `safe_to_execute: true`.

If anything is `false`, the `unsafe_reason` tells you what's missing. Fix it (pick a toolchain, add a lockfile, etc.) and re-run.

## Where things live

| What | Where |
|---|---|
| Classify caches | `~/.local/state/clain/classify/<root-hash>.json` |
| Plan artefacts | `~/.local/state/clain/plans/<kind>-<UTC>.json` |
| Run logs | `~/.local/state/clain/logs/{classify,plan}.log` |
| Rule base | `src/clain/rules.toml` (in the repo) |

Nothing is ever written under your scanned root. That is enforced by tests, not just convention.

## Captures and reproducibility

The terminal outputs shown above are real Rich captures generated by [`examples/capture.py`](../examples/capture.py) against anonymised fixture workspaces. Re-running that script after a CLI change regenerates the captures — they're not screenshots and they don't go stale silently.
