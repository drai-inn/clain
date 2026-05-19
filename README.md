# clain

**Tidy up workspace sprawl from AI-assisted coding.** A tool for developers who use AI coding agents (Claude Code, Cursor, OpenCode, Aider, Cline, …) and end up with workspaces piling up — on synced storage (Google Drive, OneDrive, Dropbox, iCloud Drive, …) where every dependency tree re-uploads forever, or just on a constrained local disk where each project's `node_modules` / `.venv` / `.pixi` quietly chews through your headroom.

`clain` does two things. It **classifies** each workspace by the kind of subtree it carries (cache-managed dependency trees, ephemeral build outputs, bytecode, workspace source). And it emits **reviewable plans** for tidying it up — *delete-and-recreate* via the right package manager (pnpm / Pixi / uv / poetry / npm / yarn), or *move-and-triage* the source code out of synced storage to a local home. Every plan is preview-only today; execution is gated until a future named spec authorises it.

The everyday entry point is one workspace at a time. Two-command demo:

```sh
pipx install git+https://github.com/drai-inn/clain.git   # one-off (or `pixi global install` — see "Three ways in")
cd ~/some/project                                        # any project with pyproject.toml / package.json / etc.
clain classify --here                                    # categorical view of THIS workspace
clain plan recreate --here --dry                         # what a clean rebuild would look like
```

Here's what the single-workspace classify looks like against a project with both a Pixi env and the usual Python tool caches:

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
```

`clain` recognised the manifests at the project root, identified the regenerable subtrees with a one-line explanation of each class, autodetected that the workspace is not in any synced-storage tree, and pointed you at the recreate command derived from `pixi.toml`. The scan stops at `.pixi/` — it doesn't recurse through every nested `__pycache__` in the bundled CPython.

See [INTENT.md](INTENT.md) for the project's mission. See [docs/USAGE.md](docs/USAGE.md) for the full walkthrough.

---

## Three ways in

The end-user install is a one-off:

```sh
pipx install git+https://github.com/drai-inn/clain.git
# or, if you already use pixi for everything:
pixi global install --git https://github.com/drai-inn/clain.git clain
```

Both produce a `clain` binary on `PATH`. The contributor path (running from a checkout) is covered separately below.

### I want to tidy one project

```sh
cd ~/some/project
clain classify --here
clain plan recreate --here --dry
```

This is the lowest-friction entry point. Walkthrough in [docs/USAGE.md](docs/USAGE.md).

### I have a tree of workspaces to triage

If your historical `dev/` directory has accumulated dozens of AI-spawned workspaces — say under a synced cloud drive — point `clain` at the tree:

```sh
export CLAIN_DEV_ROOT=~/some/dev/tree              # no personal-info default baked in
# sync placement is autodetected on macOS against known synced-storage patterns
clain classify
clain plan recreate --dry
clain plan move --dest ~/dev/ --dry
```

In tree mode `clain` enumerates each workspace under `CLAIN_DEV_ROOT` and classifies them side by side:

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

Sync placement is autodetected on macOS against known synced-storage path patterns (GDrive / OneDrive / Dropbox / Box / iCloud Drive). On non-macOS, the column shows `?`.

### I want my AI agent to drive this

`clain` ships skills in the cross-agent [Agent Skills](https://agentskills.io) format under [`skills/`](skills/). Any Agent Skills-compatible agent (Claude Code, Cursor, Aider, Cline, Continue, OpenCode, …) picks them up automatically. See [AGENTS.md](AGENTS.md) for the agent-onboarding brief.

### I want to extend or contribute

<!-- contributor-only -->
The project is spec-driven. Every non-trivial change starts as a numbered spec under [`specs/`](specs/), reaches an *aligned* goal-advisor verdict, and lands via a feature-branch + PR. The full developer workflow is in [CONTRIBUTING.md](CONTRIBUTING.md). From a checkout, contributors invoke the CLI as `pixi run clain …` rather than the global `clain` binary, so local edits are exercised without re-installing.
<!-- /contributor-only -->

---

## State location

Caches, plans, and logs live under `$XDG_STATE_HOME/clain/` (default `~/.local/state/clain/`):

- `classify/<root-hash>.json` — classification cache (24h TTL).
- `plans/<kind>-<UTC>.json` — every generated plan, timestamped.
- `logs/{classify,plan}.log` — audit lines.

Nothing is written under the scanned root. The mutation-vector ban list is enforced by tests.

## Phase-gated execution

Execution is the **default** behaviour of `clain plan`. While the development-phase gate is closed (`EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py)), default-mode invocations render the plan and then error with a pointer to `--dry`. Lifting the gate requires a future spec named *00NN — Lift the dry-run gate*, which must specify rollback, audit, and additional safety mechanisms. Use `--dry` to preview cleanly today.

## License

[MIT](LICENSE).
