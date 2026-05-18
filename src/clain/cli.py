from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from clain import __version__
from clain import classify as cls
from clain import plan as planmod
from clain.config import DevRootNotConfigured, resolve_dev_root, resolve_synced_root
from clain.console import console, err_console
from clain.executor import EXECUTE_ENABLED, ExecuteGateClosed, try_execute
from clain.state import read_json
from clain.ui.tables import (
    classify_footer,
    classify_table,
    plan_footer,
    plan_table,
    single_workspace_footer,
    single_workspace_tree,
    unsafe_actions_table,
    workspace_detail_table,
)

app = typer.Typer(
    name="clain",
    help="Manage local AI-dev workspaces — categorical visibility, deliberate execution.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)
plan_app = typer.Typer(
    name="plan",
    help="Generate executable plans. Dry-run by default; execute is phase-gated.",
    no_args_is_help=True,
)
app.add_typer(plan_app, name="plan")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"clain {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """clain — manage local AI-dev workspaces."""


def _resolve_or_exit(root: Path | None) -> Path:
    try:
        return resolve_dev_root(root)
    except DevRootNotConfigured as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


@app.command()
def classify(
    root: Path | None = typer.Argument(
        None,
        help="Root to classify. In tree mode (default), falls back to $CLAIN_DEV_ROOT. "
        "With --here, falls back to the current working directory.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON to stdout (schema v1)."),
    workspace: str | None = typer.Option(
        None, "--workspace", help="Show the full tag list for one workspace (tree mode only)."
    ),
    here: bool = typer.Option(
        False,
        "--here",
        help="Treat ROOT (or cwd) as a single workspace, not as a parent of workspaces. "
        "Useful for tidying the project you're currently in.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Force a fresh scan."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache for this run."),
) -> None:
    """Categorical scan: tags cache-managed / ephemeral / bytecode subtrees per workspace.

    Default mode treats ROOT as a parent of workspaces (depth-1 children).
    Pass --here to treat ROOT (or cwd) as a single workspace itself.
    """
    if here and workspace is not None:
        err_console.print(
            "[red]--here and --workspace are mutually exclusive.[/red] "
            "--workspace NAME drills into one child of ROOT in tree mode; "
            "--here treats ROOT itself as the workspace."
        )
        raise typer.Exit(code=2)

    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)
    synced = resolve_synced_root()

    if not resolved.exists():
        err_console.print(f"[red]Root does not exist:[/red] {resolved}")
        raise typer.Exit(code=2)
    if not resolved.is_dir():
        err_console.print(f"[red]Root is not a directory:[/red] {resolved}")
        raise typer.Exit(code=2)

    try:
        payload, cache_hit = cls.get_or_run(resolved, synced, refresh=refresh, use_cache=not no_cache, single=here)
    except (FileNotFoundError, NotADirectoryError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if json_out:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    if here:
        # Single-workspace render uses a Rich Tree, not the multi-row table.
        ws_payload = payload["workspaces"][0]
        console.print(single_workspace_tree(ws_payload, payload))
        console.print(single_workspace_footer(ws_payload, payload))
        if cache_hit:
            console.print("[dim](cached — pass --refresh to rescan)[/dim]")
        return

    if workspace is not None:
        match = next(
            (w for w in payload.get("workspaces", []) if w.get("name") == workspace),
            None,
        )
        if match is None:
            err_console.print(f"[red]Workspace not found: {workspace}[/red]")
            raise typer.Exit(code=2)
        console.print(workspace_detail_table(match))
        return

    console.print(classify_table(payload))
    console.print(classify_footer(payload))
    if cache_hit:
        console.print("[dim](cached — pass --refresh to rescan)[/dim]")


def _load_classify_or_exit(resolved: Path) -> dict[str, object]:
    payload = cls.load_cached(resolved)
    if payload is None:
        err_console.print(f"[red]No classify cache for {resolved}. Run `clain classify` first.[/red]")
        raise typer.Exit(code=2)
    return payload


def _emit_plan(plan: dict[str, object], json_out: bool, dry: bool) -> None:
    """Render + persist the plan, then attempt execution unless --dry was passed.

    Execution is the default behaviour. The phase gate in `clain.executor`
    blocks it for now and raises ExecuteGateClosed, which we surface as a Rich
    error with a pointer to --dry.
    """
    saved = planmod.persist_plan(plan)

    if json_out:
        sys.stdout.write(json.dumps(plan, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        unsafe = unsafe_actions_table(plan)
        if unsafe is not None:
            console.print(unsafe)
            console.print()
        console.print(plan_table(plan))
        console.print(plan_footer(plan, str(saved)))

    if dry:
        if not json_out:
            console.print("[dim](dry mode — execution skipped)[/dim]")
        return

    # Execution path. Currently always blocked by the phase gate.
    try:
        try_execute(plan)
    except ExecuteGateClosed as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if not EXECUTE_ENABLED:
        # Defensive: try_execute should have raised already.
        console.print("[dim](execution gate closed — no actions taken)[/dim]")


@plan_app.command("recreate")
def plan_recreate(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    dry: bool = typer.Option(False, "--dry", help="Preview only — render the plan and stop before any execution."),
    here: bool = typer.Option(
        False,
        "--here",
        help="Single-workspace mode: ROOT (or cwd) IS the workspace, not a parent of workspaces. "
        "Requires a prior `clain classify --here` against the same path.",
    ),
) -> None:
    """Delete + recreate plan for cache-managed/ephemeral/bytecode subtrees.

    Default behaviour is to attempt execution; --dry stops after rendering.
    Execution is currently blocked by the development-phase gate
    (src/clain/executor.py:EXECUTE_ENABLED) and will error until a future
    spec lifts the gate.
    """
    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_recreate_plan(classify_payload)
    _emit_plan(plan, json_out, dry)


@plan_app.command("move")
def plan_move(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        help="Destination root for moved workspaces. Required.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    dry: bool = typer.Option(False, "--dry", help="Preview only — render the plan and stop before any execution."),
    here: bool = typer.Option(
        False,
        "--here",
        help="Single-workspace mode: ROOT (or cwd) IS the workspace. The plan will move this one workspace, "
        "if it's in the synced tree, to <DEST>/<workspace-name>/.",
    ),
) -> None:
    """Move + triage plan for workspaces sitting in the synced tree.

    Default behaviour is to attempt execution; --dry stops after rendering.
    Execution is currently blocked by the development-phase gate
    (src/clain/executor.py:EXECUTE_ENABLED) and will error until a future
    spec lifts the gate.
    """
    if dest is None:
        err_console.print("[red]--dest is required for plan move (e.g. --dest ~/dev/).[/red]")
        raise typer.Exit(code=2)
    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_move_plan(classify_payload, dest.expanduser().resolve())
    _emit_plan(plan, json_out, dry)


@plan_app.command("explain")
def plan_explain(
    action_id: str = typer.Argument(..., help="12-char action id from a saved plan."),
    plan_file: Path | None = typer.Option(
        None,
        "--plan",
        help="Specific plan file to read. Defaults to the most recent in $XDG_STATE_HOME/clain/plans/.",
    ),
) -> None:
    """Print the full action record for one action by id."""
    from clain.state import plan_dir as plan_state_dir

    if plan_file is None:
        candidates = sorted(plan_state_dir().glob("*.json"))
        if not candidates:
            err_console.print("[red]No plans found under $XDG_STATE_HOME/clain/plans/.[/red]")
            raise typer.Exit(code=2)
        plan_file = candidates[-1]

    data = read_json(plan_file)
    if data is None:
        err_console.print(f"[red]Could not read plan: {plan_file}[/red]")
        raise typer.Exit(code=2)
    for action in data.get("actions", []):
        if action.get("id") == action_id:
            console.print_json(data=action)
            return
    err_console.print(f"[red]Action id not found in {plan_file}: {action_id}[/red]")
    raise typer.Exit(code=2)
