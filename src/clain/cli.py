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
        help="Root to classify. Falls back to $CLAIN_DEV_ROOT; errors if neither is set.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON to stdout (schema v1)."),
    workspace: str | None = typer.Option(None, "--workspace", help="Show the full tag list for one workspace."),
    refresh: bool = typer.Option(False, "--refresh", help="Force a fresh scan."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache for this run."),
) -> None:
    """Categorical scan: tags cache-managed / ephemeral / bytecode subtrees per workspace."""
    resolved = _resolve_or_exit(root)
    synced = resolve_synced_root(resolved)
    if not resolved.exists():
        err_console.print(f"[red]Root does not exist:[/red] {resolved}")
        raise typer.Exit(code=2)
    if not resolved.is_dir():
        err_console.print(f"[red]Root is not a directory:[/red] {resolved}")
        raise typer.Exit(code=2)

    try:
        payload, cache_hit = cls.get_or_run(resolved, synced, refresh=refresh, use_cache=not no_cache)
    except (FileNotFoundError, NotADirectoryError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if json_out:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        sys.stdout.write("\n")
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


def _emit_plan(plan: dict[str, object], json_out: bool, execute: bool) -> None:
    if execute:
        try:
            try_execute(plan)
        except ExecuteGateClosed as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from exc

    saved = planmod.persist_plan(plan)
    if json_out:
        sys.stdout.write(json.dumps(plan, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    unsafe = unsafe_actions_table(plan)
    if unsafe is not None:
        console.print(unsafe)
        console.print()
    console.print(plan_table(plan))
    console.print(plan_footer(plan, str(saved)))
    if not EXECUTE_ENABLED:
        console.print("[dim]Dry-run only — execution gate is closed (see executor.py).[/dim]")


@plan_app.command("recreate")
def plan_recreate(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    execute: bool = typer.Option(False, "--execute", help="Currently disabled by phase gate (see executor.py)."),
) -> None:
    """Delete + recreate plan for cache-managed/ephemeral/bytecode subtrees."""
    resolved = _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_recreate_plan(classify_payload)
    _emit_plan(plan, json_out, execute)


@plan_app.command("move")
def plan_move(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    destination: Path | None = typer.Option(
        None,
        "--destination",
        help="Destination root for moved workspaces. Required for plan move.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    execute: bool = typer.Option(False, "--execute", help="Currently disabled by phase gate (see executor.py)."),
) -> None:
    """Move + triage plan for workspaces sitting in the synced tree."""
    if destination is None:
        err_console.print("[red]--destination is required for plan move (e.g. --destination ~/dev/).[/red]")
        raise typer.Exit(code=2)
    resolved = _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_move_plan(classify_payload, destination.expanduser().resolve())
    _emit_plan(plan, json_out, execute)


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
