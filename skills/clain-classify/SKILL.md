---
name: clain-classify
description: Use when the developer wants a categorical inventory of workspaces under a dev tree — e.g. "classify my dev directory", "scan ~/dev/ with clain", "what kinds of subtrees are in this workspace tree?", "run clain classify". Surfaces cache-managed / ephemeral / bytecode / workspace-source tags per workspace and reports which workspaces sit inside a synced (e.g. Google Drive) tree.
compatibility: Requires the `clain` CLI on PATH (or invocable via `pixi run clain` from a checked-out clain-me workspace).
---

Run the `clain` CLI to classify workspaces under a developer-supplied root and surface the result.

## Steps

1. Confirm the root with the developer. If they did not specify a path, ask for one or check whether `CLAIN_DEV_ROOT` is set in their environment. **Do not invent a default** — `clain` has no baked-in default and will error if neither a positional argument nor `CLAIN_DEV_ROOT` is provided.

2. If the developer wants a rendered table (the usual case), run:

```bash
clain classify "$ROOT"
```

3. If the developer wants machine-readable output (for piping or further analysis), run:

```bash
clain classify "$ROOT" --json
```

4. If they want to drill into one workspace's full class-tag list, run:

```bash
clain classify "$ROOT" --workspace "$WORKSPACE_NAME"
```

5. Report the output verbatim. Highlight: the number of workspaces under the synced tree, the most common class observed, and any rows marked with errors.

## Notes

- This command is strictly read-only against `$ROOT`. It does not modify any file under the scanned tree.
- The result is cached for 24 hours under `$XDG_STATE_HOME/clain/classify/<root-hash>.json`. Pass `--refresh` to force a fresh scan.
- If the command fails (`clain: command not found`, root does not exist, etc.), report the failure verbatim. Do not attempt workarounds or guess a different command.
