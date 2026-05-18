---
name: clain-plan-recreate
description: Use when the developer wants a delete-and-recreate plan for cache-managed / ephemeral / bytecode subtrees of their dev workspaces — e.g. "show me a recreate plan", "what would clain delete and rebuild?", "plan to wipe node_modules and reinstall via pnpm". Always runs in --dry mode; never executes deletions. Surfaces unsafe actions (ambiguous toolchain, missing lockfile) prominently so the developer can review before any execution is enabled.
compatibility: Requires the `clain` CLI on PATH (or via `pixi run clain`). A classify cache must already exist for the root — run the `clain-classify` skill first if it doesn't.
---

Run the `clain` CLI to produce a delete-and-recreate plan **in dry mode** for a developer-supplied root, then render the result.

## Steps

1. **Pick the mode** (matches the classify mode the developer used). Single-workspace: pass `--here`. Tree of workspaces: omit it.

2. Ensure a classify cache exists. If the developer has not run `clain classify` (or `clain classify --here`) for the path recently, do that first (or invoke the `clain-classify` skill). Without a matching cache, `clain plan recreate` exits non-zero with a clear error.

3. **Always pass `--dry`.** This is the safe-preview mode and is required for normal use until the project's development-phase gate is lifted by a future named spec.

```bash
clain plan recreate --here "$WORKSPACE_PATH" --dry      # single-workspace mode
clain plan recreate "$ROOT" --dry                       # tree mode
```

4. Or for machine-readable output:

```bash
clain plan recreate --here "$WORKSPACE_PATH" --dry --json
clain plan recreate "$ROOT" --dry --json
```

4. Surface the plan to the developer with these emphases:
   - The total action count and the **unsafe count** (look for `Unsafe:` in the footer or `summary.unsafe_count` in JSON).
   - Any actions flagged with `safe_to_execute: false` — list them, with their `unsafe_reason`, before any safe actions.
   - The plan path under `$XDG_STATE_HOME/clain/plans/recreate-<UTC>.json`. The plan is the audit artefact; tell the developer where it lives.

5. If the developer asks "can you just run it for me?", explain that execution is blocked by the project's development-phase gate. The plan is the deliverable; the developer reviews it and runs the commands themselves until the gate is lifted by a future spec.

## Notes

- **Never omit `--dry`** when invoking this skill. Without it, the command attempts execution, hits the phase gate, and emits an error.
- Unsafe actions cover real cases: a Python workspace with `pyproject.toml` but no toolchain lockfile, a Node workspace with `package.json` but no lockfile, a workspace with no recognised manifest at all. Treat each as a request for developer judgement, not a flaw in the tool.
- If the command fails (`clain: command not found`, no classify cache, root does not exist), report the failure verbatim. Do not work around it; do not invent a recreate command from your own knowledge.
