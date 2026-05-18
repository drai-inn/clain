---
name: clain-classify
description: Use when the developer wants a categorical inventory of one workspace or a tree of workspaces — e.g. "classify my dev directory", "what's regenerable in this project?", "what kinds of subtrees are in this workspace tree?", "run clain classify --here". Surfaces cache-managed / ephemeral / bytecode / workspace-source tags and reports which workspaces sit inside a synced (e.g. GDrive / OneDrive / Dropbox / iCloud Drive) tree.
compatibility: Requires the `clain` CLI on PATH (or invocable via `pixi run clain` from a checked-out clain-me workspace).
---

Run the `clain` CLI to classify workspaces under a developer-supplied root and surface the result.

## Steps

1. **Pick the mode.** If the developer is talking about *one* project they're in (the common case), use single-workspace mode by passing `--here`. If they're talking about a tree of projects (e.g. their `~/dev/` directory), use the default tree mode.

2. **Single-workspace mode (recommended default for everyday use):**

```bash
clain classify --here "$WORKSPACE_PATH"      # or omit the path to use cwd
```

3. **Tree mode (for cleaning up many workspaces at once):** confirm the root with the developer. If they did not specify a path, ask for one or check whether `CLAIN_DEV_ROOT` is set in their environment. Do not invent a default — `clain` has no baked-in default in tree mode and will error if neither a positional argument nor `CLAIN_DEV_ROOT` is provided.

```bash
clain classify "$ROOT"
```

4. **Machine-readable output** (any mode): add `--json` to either form for piping or further analysis.

5. **Drill into one workspace** (tree mode only): `clain classify "$ROOT" --workspace "$WORKSPACE_NAME"`. (Not compatible with `--here`.)

6. Report the output verbatim. In single-workspace mode highlight: the manifests detected, the cache-managed subtrees, and the suggested next command shown in the "Next:" footer. In tree mode highlight: the number of workspaces under the synced tree, the most common class observed, and any rows marked with errors.

## Notes

- This command is strictly read-only against `$ROOT`. It does not modify any file under the scanned tree.
- The result is cached for 24 hours under `$XDG_STATE_HOME/clain/classify/<root-hash>.json`. Pass `--refresh` to force a fresh scan.
- If the command fails (`clain: command not found`, root does not exist, etc.), report the failure verbatim. Do not attempt workarounds or guess a different command.
