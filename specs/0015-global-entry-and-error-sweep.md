---
id: 0015
title: Global installability + error-message sweep
status: draft
goal: Goal 2 (Deliberate execution — every error should tell the user what happened and what to do next); Goal 8 (Reviewable evolution — the documented "tree of workspaces" entry point should actually work the way the docs claim)
---

## Problem

Two first-contact failure modes the dogfood loop surfaced:

### A — Tree mode is documented but doesn't work the way the docs say

The README/USAGE tell users to do this for the tree-mode workflow:

```sh
cd ~/some/dev/tree              # parent of workspaces
pixi run clain classify
```

It doesn't work. `pixi run` requires a pixi manifest in the directory it's invoked from. `~/dev/` (or any other workspace parent) doesn't have one — that's the whole point; it's a tree of workspaces, not itself a workspace. The user gets pixi's own error:

```
Error:   × could not find pixi.toml or pyproject.toml with tool.pixi
        at directory /Users/njon001/dev
```

…which is a **pixi** error, not a `clain` error. Pixi never let `clain` run, so clain never got the chance to produce a helpful message.

The workaround is to `cd` into a directory that does have a pixi manifest (e.g. the `clain-me` checkout itself) and pass the tree as an argument:

```sh
cd ~/dev/clain-me
pixi run clain classify ~/dev
```

This works but it's not what the docs say, and it's the wrong mental model: `pixi run` is the contributor's tool for working on `clain`, not the user's tool for *using* `clain`.

The `pyproject.toml` already declares `[project.scripts] clain = "clain.cli:app"`, so a normal pip / pipx install produces a system-wide `clain` binary. We just don't tell people that's the supported install path for end users.

### B — Our own error strings could work harder

Errors clain emits today (the catalogue lives in `src/clain/cli.py` and `src/clain/config.py`):

| Where | Current text | What's missing |
|---|---|---|
| `_resolve_or_exit` (CLAIN_DEV_ROOT unset, tree mode) | `CLAIN_DEV_ROOT is not set; pass a ROOT argument or set the env var.` | Doesn't show the `export` line; doesn't suggest `--here` for the single-workspace path. |
| `classify` ROOT does not exist | `Root does not exist: /path` | No suggestion (check the path, cd back to a known dir, etc.). |
| `classify` ROOT is not a directory | `Root is not a directory: /path` | Same. |
| `_load_classify_or_exit` (no cache) | `No classify cache for {resolved}. Run \`clain classify\` first.` | Doesn't say *why* the cache is missing (likely: you ran `plan` without classifying first; or the path you're running plan against differs from the path you classified). |
| `plan_explain` action-id not found | `Action id not found in {plan_file}: {action_id}` | Doesn't suggest checking the saved plan file or listing valid IDs. |
| `--dest` missing on `plan move` | `--dest is required for plan move (e.g. --dest ~/dev/).` | Already pretty good — keep as template. |
| `CLAIN_SYNCED_ROOT` set (spec 0013 hard-error) | Multi-line, names the spec, gives the unset command. | The template we want everyone else to converge on. |

The spec-0013 `CLAIN_SYNCED_ROOT` error is the template: state what's wrong, state why it's wrong, give the literal command to fix it.

## Intent

Two coordinated changes, one PR:

**A — Global entry as the supported user install path.**
Document `pipx install` (and `pixi global install` as the pixi-native alternative) as the supported install for end users. Sweep README + USAGE so the tree-mode invocation no longer routes through `pixi run` from a directory that won't have a manifest. The dev/contributor workflow (`pixi run -e dev test` etc.) stays unchanged — that's the right tool for that audience.

**B — Error-message sweep.**
Audit every `err_console.print` and `typer.Exit` call site. Each error must tell the user (1) what's wrong, (2) why, (3) the literal command or change that fixes it. The spec-0013 `CLAIN_SYNCED_ROOT` error is the template.

No JSON schema change. No new CLI flags. No behaviour change in plan / executor / phase gate.

## Spec

### Part A — Global install paths

The end-user install matrix:

| Audience | Install command | Invocation |
|---|---|---|
| End user (pipx) | `pipx install git+https://github.com/drai-inn/clain.git` | `clain classify ~/dev` |
| End user (pixi) | `pixi global install --git https://github.com/drai-inn/clain.git clain` | `clain classify ~/dev` |
| Contributor | `git clone … && pixi install` | `pixi run clain …` |

The console-script entry point `clain = "clain.cli:app"` already exists in `pyproject.toml`. **No code change needed** for the install path itself. This is purely documentation + verification:

1. **README.md sweep.** The "Three ways in" section currently shows `pixi run clain …` for all three audiences. Restructure so the end-user paths use the bare `clain` binary and the contributor path stays `pixi run`. Lead with pipx; mention `pixi global` as alternative; relegate `pixi run clain …` to the contributor section.
2. **docs/USAGE.md sweep.** The "Tree mode" walkthrough and the "I have 30 Node workspaces" scenario both currently say `cd ~/some/dev/tree && pixi run clain classify`. Replace with `cd ~/some/dev/tree && clain classify` (no `pixi run`), with a one-line note that contributors hacking on `clain` itself prefix `pixi run` from inside their checkout.
3. **AGENTS.md sweep.** Same correction; agent runs are end-user runs.
4. **Plugin manifest check.** The Claude Code plugin under `plugin/` shells out to `clain`; verify it doesn't hardcode `pixi run clain` anywhere.

**Acceptance test for Part A:**

A new test `test_console_script_entry_resolves` confirms the `clain` console-script entry resolves to `clain.cli:app` (introspect via `importlib.metadata.entry_points`). This guards against a future refactor that breaks the install path silently.

### Part B — Error-message sweep

A single helper `clain.ui.errors.user_error(what: str, why: str | None, fix: str)` builds a consistent Rich-formatted error in the spec-0013 shape:

```python
def user_error(what: str, why: str | None, fix: str) -> str:
    """Build a templated error message.

    Args:
      what: One-sentence statement of what's wrong (the headline).
      why:  Optional second-sentence explanation (often the cause).
      fix:  Literal command or change the user should run/make. Rendered
            on its own indented line in a recognisable colour.

    Returns a Rich markup string. Caller does:
        err_console.print(user_error("…", "…", "…"))
        raise typer.Exit(code=2)
    """
```

Every `err_console.print` call site in `cli.py` migrates to call `user_error(...)` or — for the cases where the existing message is already good (e.g. `--here` / `--workspace` mutex) — gets a brief review and leaves it alone with a comment "matches user_error template".

**Specific rewrites:**

| Site | New shape |
|---|---|
| `CLAIN_DEV_ROOT` unset | what: "`CLAIN_DEV_ROOT` is not set." · why: "Tree mode needs the parent of your workspaces to scan." · fix: `export CLAIN_DEV_ROOT=~/dev` (or use `--here` for a single workspace). |
| `Root does not exist` | what: "`{path}` does not exist." · why: "Tree-mode classify needs the directory that contains your workspaces." · fix: "Check the path; or pass `--here` to classify the current directory." |
| `Root is not a directory` | what: "`{path}` is a file, not a directory." · why: same as above. · fix: same. |
| `No classify cache` | what: "No classify cache for `{path}`." · why: "Plans read from the cache that `classify` writes; you may have skipped that step, or classified a different path." · fix: `clain classify {path}` (or `clain classify --here` if you meant the current directory). |
| `Action id not found` | what: "Action id `{id}` not found in `{plan_file}`." · why: "Action IDs are 12 hex chars; check the plan render for the right one." · fix: `cat {plan_file} \| jq '.actions[].id'` (list all valid IDs). |
| `--legend` + `--no-legend` mutex | (already templated — leave) |
| `--here` + `--workspace` mutex | (already templated — leave) |
| `--dest` missing on plan move | (already templated — leave) |
| `CLAIN_SYNCED_ROOT` hard-error (spec 0013) | (already the template — refactor to use `user_error` to confirm shape) |

**Helper colour token:** `user_error` uses a single named colour for the fix line (Tokyo Night `accent.fix` once spec 0017 lands; until then, Rich `cyan` is fine). The colour signals "this is the literal thing to type" — distinct from the `red` of the error itself.

**No silent error path changes.** Every existing test that asserts on error text gets updated to the new wording. Pinning current wording in a test means a future drift gets caught.

### Tests

- `test_console_script_entry_resolves` — `importlib.metadata.entry_points(group="console_scripts")` includes a `clain` entry pointing at `clain.cli:app`.
- `test_user_error_template_shape` — `user_error("X", "Y", "Z")` produces a string containing "X", "Y", "Z" in that order; the fix line is on its own indented line; markup parses cleanly.
- `test_user_error_no_why_omits_middle_line` — when `why=None`, the rendered output skips the middle line cleanly.
- Per-site rewrite tests (in `test_cli.py` / `test_classify.py` / `test_plan.py`):
  - `test_classify_no_root_error_includes_export_hint` — asserts the `export CLAIN_DEV_ROOT=` line appears.
  - `test_classify_bad_root_error_mentions_here_flag` — asserts the `--here` suggestion is in the output.
  - `test_plan_no_cache_error_mentions_classify_command` — asserts `clain classify` is in the suggestion.
- `test_no_pixi_run_in_user_facing_docs` — grep README.md, docs/USAGE.md, AGENTS.md; assert `pixi run clain` appears only in clearly-marked contributor sections (defined by a sentinel comment in each file, e.g. `<!-- contributor-only -->` blocks).

### Documentation updates

- **README.md** — restructure "Three ways in" so end-user invocations use bare `clain`; move `pixi run` to a contributor subsection.
- **docs/USAGE.md** — first-time setup section: `pipx install git+…` or `pixi global install …` first; tree-mode walkthrough updated.
- **AGENTS.md** — agent invocation uses bare `clain`.
- **CHANGELOG.md** — Unreleased entry for spec 0015 noting the user-install rename (no functional break) and the error-message sweep.

## Acceptance

- [ ] `pipx install git+https://github.com/drai-inn/clain.git` produces a working `clain` on PATH; `clain --version` matches `pyproject.toml`.
- [ ] `pixi global install --git https://github.com/drai-inn/clain.git clain` ditto. (Smoke-test by hand; this is install-pathway, not a unit-testable assertion.)
- [ ] README.md "Three ways in" leads with the bare `clain` invocation; `pixi run clain …` appears only in the contributor section.
- [ ] docs/USAGE.md tree-mode walkthrough no longer tells the user to `cd` into a non-pixi-managed directory and run `pixi run clain`.
- [ ] `test_no_pixi_run_in_user_facing_docs` passes.
- [ ] `src/clain/ui/errors.py` exists and exports `user_error(what, why, fix)`.
- [ ] Every `err_console.print` call site in `cli.py` either uses `user_error` or has an `# error template OK` comment explaining why it's already fine.
- [ ] All per-site rewrite tests pass; old error-text assertions updated.
- [ ] CHANGELOG entry added.
- [ ] PR follows the workflow template.

## Out of scope

- A Homebrew / Nix / Debian packaging recipe. pipx + pixi-global cover the audience for now; package-manager recipes belong in a future spec when there's demonstrated demand.
- A self-update mechanism (`clain self update`). Defer.
- Localising error messages. English-only until a non-English contributor shows up (same as spec 0013).
- Telemetry on which errors fire most. Out of scope; would need its own privacy spec first.

## Notes

- The console-script entry point already works today — anyone who runs `pip install -e .` from the checkout gets a `clain` binary. This spec is about *telling* users that, and making it the headline path.
- The error-template shape (`what / why / fix`) is the same shape the spec-0013 `CLAIN_SYNCED_ROOT` error already uses. We're codifying an existing-but-undocumented convention.
- Open question worth pinning down during implementation: should `user_error` raise the `typer.Exit` itself? Pro: removes boilerplate (`raise typer.Exit(code=2)` after every `print`). Con: harder to test (the function side-effects on `err_console`, not just returns a string). Lean: keep it pure (returns string), caller raises. Easier to unit-test.
