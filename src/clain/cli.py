from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from clain import __version__
from clain import classify as cls
from clain import plan as planmod
from clain.config import (
    ENV_SYNCED_ROOT_DEPRECATED,
    DevRootNotConfigured,
    resolve_dev_root,
)
from clain.console import console, err_console
from clain.executor import EXECUTE_ENABLED, ExecuteGateClosed, try_execute
from clain.state import read_json
from clain.ui.errors import user_error
from clain.ui.legend import ENV_VAR as LEGEND_ENV_VAR
from clain.ui.legend import InvalidLegendValue, should_show_legend
from clain.ui.tables import (
    classify_here_view,
    classify_tree_view,
    plan_view,
    workspace_detail_table,
)
from clain.ui.theme import ENV_VAR as THEME_ENV_VAR
from clain.ui.theme import InvalidThemeValue, resolve_theme, set_theme

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


def _check_deprecated_env() -> None:
    """Spec 0013: CLAIN_SYNCED_ROOT was removed. If set, hard-error.

    Runs in `main()` (the app callback), which fires before any subcommand.
    `--version` and `--help` use eager callbacks that exit before this runs,
    so the developer can still discover what changed even with the env var set.
    """
    import os

    if os.environ.get(ENV_SYNCED_ROOT_DEPRECATED):
        err_console.print(
            user_error(
                what=f"{ENV_SYNCED_ROOT_DEPRECATED} is set in your environment.",
                why=(
                    "It was removed in spec 0013 (specs/0013-output-legibility.md). "
                    "Sync placement is now autodetected on macOS; the env var has no "
                    "effect, and refusing to run with it set surfaces the change "
                    "rather than silently ignoring your stale config."
                ),
                fix=f"unset {ENV_SYNCED_ROOT_DEPRECATED}",
            )
        )
        raise typer.Exit(code=2)


def _apply_theme(theme: str | None) -> None:
    """Resolve and stash the active theme. Called once per invocation.

    Precedence (spec 0017 § Resolution):
        NO_COLOR set → no colour
        --theme dark|light|auto (flag)
        CLAIN_THEME env var
        COLORFGBG / OSC 11 detection
        fallback: dark
    """
    import os

    no_color = "NO_COLOR" in os.environ
    try:
        resolved = resolve_theme(
            flag=theme,
            env=os.environ.get(THEME_ENV_VAR),
            colorfgbg=os.environ.get("COLORFGBG"),
            no_color=no_color,
            osc11=True,
        )
    except InvalidThemeValue as exc:
        err_console.print(
            user_error(
                what=str(exc),
                why="`--theme` and `CLAIN_THEME` accept `dark`, `light`, or `auto` only.",
                fix="export CLAIN_THEME=auto    # or pass --theme dark|light|auto explicitly",
            )
        )
        raise typer.Exit(code=2) from exc
    set_theme(resolved)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        help="Colour theme: dark, light, or auto (default: auto — detects terminal background, falls back to dark). "
        "Also reads CLAIN_THEME; NO_COLOR strips colour entirely.",
    ),
) -> None:
    """clain — manage local AI-dev workspaces."""
    _check_deprecated_env()
    _apply_theme(theme)


def _resolve_or_exit(root: Path | None) -> Path:
    try:
        return resolve_dev_root(root)
    except DevRootNotConfigured as exc:
        err_console.print(
            user_error(
                what="CLAIN_DEV_ROOT is not set.",
                why=(
                    "Tree mode needs the parent directory of your workspaces to scan; "
                    "pass it as a positional argument or set the env var."
                ),
                fix="export CLAIN_DEV_ROOT=~/dev    # or pass --here to classify the current directory",
            )
        )
        raise typer.Exit(code=2) from exc


def _resolve_legend(here: bool, legend: bool, no_legend: bool) -> bool:
    """Resolve the legend toggle per spec 0013 precedence.

    --legend / --no-legend mutex → CLI error. Otherwise: explicit flag wins,
    then CLAIN_LEGEND env, then mode default (--here on, tree off).
    """
    import os

    if legend and no_legend:
        # error template OK — mutex callout; no separate why/fix worth splitting.
        err_console.print("[red]--legend and --no-legend are mutually exclusive.[/red]")
        raise typer.Exit(code=2)
    flag: bool | None
    if legend:
        flag = True
    elif no_legend:
        flag = False
    else:
        flag = None
    try:
        return should_show_legend(here=here, flag=flag, env=os.environ.get(LEGEND_ENV_VAR))
    except InvalidLegendValue as exc:
        # error template OK — `InvalidLegendValue.__str__` produces a single,
        # already-clear sentence ("invalid value 'X' for CLAIN_LEGEND; expected …").
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
    legend: bool = typer.Option(False, "--legend", help="Force the legend on (default for --here)."),
    no_legend: bool = typer.Option(False, "--no-legend", help="Force the legend off (default for tree mode)."),
    refresh: bool = typer.Option(False, "--refresh", help="Force a fresh scan."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache for this run."),
) -> None:
    """Categorical scan: tags cache-managed / ephemeral / bytecode subtrees per workspace.

    Default mode treats ROOT as a parent of workspaces (depth-1 children).
    Pass --here to treat ROOT (or cwd) as a single workspace itself.
    """
    if here and workspace is not None:
        # error template OK — already what/why/fix shape with mutex callout.
        err_console.print(
            "[red]--here and --workspace are mutually exclusive.[/red] "
            "--workspace NAME drills into one child of ROOT in tree mode; "
            "--here treats ROOT itself as the workspace."
        )
        raise typer.Exit(code=2)

    legend_on = _resolve_legend(here=here, legend=legend, no_legend=no_legend)

    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)

    if not resolved.exists():
        err_console.print(
            user_error(
                what=f"{resolved} does not exist.",
                why="Tree-mode classify needs the directory that contains your workspaces.",
                fix="check the path, or pass --here to classify the current directory",
            )
        )
        raise typer.Exit(code=2)
    if not resolved.is_dir():
        err_console.print(
            user_error(
                what=f"{resolved} is a file, not a directory.",
                why="Tree-mode classify needs the directory that contains your workspaces.",
                fix="check the path, or pass --here to classify the current directory",
            )
        )
        raise typer.Exit(code=2)

    try:
        payload, cache_hit = cls.get_or_run(resolved, refresh=refresh, use_cache=not no_cache, single=here)
    except (FileNotFoundError, NotADirectoryError) as exc:
        # error template OK — these are filesystem races (path vanished between
        # existence check and scan); the OS message identifies the path itself.
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if json_out:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
        sys.stdout.write("\n")
        return

    if here:
        ws_payload = payload["workspaces"][0]
        console.print(classify_here_view(ws_payload, payload, legend=legend_on))
        if cache_hit:
            # Meta line: deliberate aside, indented to body (spec 0014).
            console.print("  [dim](cached — pass --refresh to rescan)[/dim]")
            console.print("")
        return

    if workspace is not None:
        match = next(
            (w for w in payload.get("workspaces", []) if w.get("name") == workspace),
            None,
        )
        if match is None:
            err_console.print(
                user_error(
                    what=f"Workspace not found: {workspace}.",
                    why="--workspace NAME drills into one child of ROOT in tree mode.",
                    fix="run `clain classify` without --workspace to list available workspaces",
                )
            )
            raise typer.Exit(code=2)
        console.print(workspace_detail_table(match))
        return

    console.print(classify_tree_view(payload, legend=legend_on))
    if cache_hit:
        # Meta line: deliberate aside, indented to body (spec 0014).
        console.print("  [dim](cached — pass --refresh to rescan)[/dim]")
        console.print("")


def _load_classify_or_exit(resolved: Path) -> dict[str, object]:
    payload = cls.load_cached(resolved)
    if payload is None:
        err_console.print(
            user_error(
                what=f"No classify cache for {resolved}.",
                why=(
                    "Plans read from the cache that classify writes; you may have "
                    "skipped that step, or classified a different path."
                ),
                fix=f"clain classify {resolved}    # or `clain classify --here` if you meant the current directory",
            )
        )
        raise typer.Exit(code=2)
    return payload


def _emit_plan(
    plan: dict[str, object],
    json_out: bool,
    dry: bool,
    flat_table: bool = False,
    legend: bool = False,
) -> None:
    """Render + persist the plan, then attempt execution unless --dry was passed.

    Render modes (spec 0012):
    - `flat_table=False, json_out=False` (default): workspace-grouped Panels with
      relative paths.
    - `flat_table=True`: single-table layout with absolute paths (the pre-spec-0012
      shape), preserved for copy-paste/spreadsheet use.
    - `json_out=True`: emit JSON to stdout; no Rich rendering.

    Execution is the default behaviour. The phase gate in `clain.executor`
    blocks it and raises ExecuteGateClosed, which we surface as a Rich error
    with a pointer to --dry. The persisted JSON under $XDG_STATE_HOME is
    byte-identical across all three render modes — rendering is render-only.
    """
    saved = planmod.persist_plan(plan)

    if json_out:
        sys.stdout.write(json.dumps(plan, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        # Spec 0013: plan_view wraps the spec-0012 panels (or flat table) with
        # orientation header, optional legend, structured Summary/Saved/Mode.
        console.print(
            plan_view(
                plan,
                saved_path=str(saved),
                legend=legend,
                flat_table=flat_table,
                mode="dry-run" if dry else "execute (gated)",
            )
        )

    if dry:
        if not json_out:
            # Meta line: deliberate aside, indented to body (spec 0014).
            console.print("  [dim](dry mode — execution skipped)[/dim]")
            console.print("")
        return

    # Execution path. Currently always blocked by the phase gate.
    try:
        try_execute(plan)
    except ExecuteGateClosed as exc:
        # error template OK — `ExecuteGateClosed.__str__` is the spec-0005
        # gate-closed message and already names the --dry workaround.
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if not EXECUTE_ENABLED:
        # Defensive: try_execute should have raised already.
        console.print("[dim](execution gate closed — no actions taken)[/dim]")


@plan_app.command("recreate")
def plan_recreate(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    flat_table: bool = typer.Option(
        False,
        "--table",
        help="Use the single-table layout with absolute paths (pre-0012 shape). "
        "Useful for copy-paste into a spreadsheet. Mutually exclusive with --json.",
    ),
    dry: bool = typer.Option(False, "--dry", help="Preview only — render the plan and stop before any execution."),
    here: bool = typer.Option(
        False,
        "--here",
        help="Single-workspace mode: ROOT (or cwd) IS the workspace, not a parent of workspaces. "
        "Requires a prior `clain classify --here` against the same path.",
    ),
    legend: bool = typer.Option(False, "--legend", help="Force the legend on (default for --here)."),
    no_legend: bool = typer.Option(False, "--no-legend", help="Force the legend off (default for tree mode)."),
) -> None:
    """Delete + recreate plan for cache-managed/ephemeral/bytecode subtrees.

    Default behaviour is to attempt execution; --dry stops after rendering.
    Execution is currently blocked by the development-phase gate
    (src/clain/executor.py:EXECUTE_ENABLED) and will error until a future
    spec lifts the gate.
    """
    if flat_table and json_out:
        # error template OK — mutex callout with embedded why.
        err_console.print(
            "[red]--table and --json are mutually exclusive.[/red] Both write the plan "
            "to stdout in a single format; only one stdout format may be selected."
        )
        raise typer.Exit(code=2)
    legend_on = _resolve_legend(here=here, legend=legend, no_legend=no_legend)
    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_recreate_plan(classify_payload)
    _emit_plan(plan, json_out, dry, flat_table=flat_table, legend=legend_on)


@plan_app.command("move")
def plan_move(
    root: Path | None = typer.Argument(None, help="Root previously classified."),
    dest: Path | None = typer.Option(
        None,
        "--dest",
        help="Destination root for moved workspaces. Required.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit plan JSON to stdout."),
    flat_table: bool = typer.Option(
        False,
        "--table",
        help="Use the single-table layout with absolute paths. Mutually exclusive with --json.",
    ),
    dry: bool = typer.Option(False, "--dry", help="Preview only — render the plan and stop before any execution."),
    here: bool = typer.Option(
        False,
        "--here",
        help="Single-workspace mode: ROOT (or cwd) IS the workspace. The plan will move this one workspace, "
        "if it's in the synced tree, to <DEST>/<workspace-name>/.",
    ),
    legend: bool = typer.Option(False, "--legend", help="Force the legend on (default for --here)."),
    no_legend: bool = typer.Option(False, "--no-legend", help="Force the legend off (default for tree mode)."),
) -> None:
    """Move + triage plan for workspaces sitting in the synced tree.

    Default behaviour is to attempt execution; --dry stops after rendering.
    Execution is currently blocked by the development-phase gate
    (src/clain/executor.py:EXECUTE_ENABLED) and will error until a future
    spec lifts the gate.
    """
    if flat_table and json_out:
        # error template OK — mutex callout with embedded why.
        err_console.print(
            "[red]--table and --json are mutually exclusive.[/red] Both write the plan "
            "to stdout in a single format; only one stdout format may be selected."
        )
        raise typer.Exit(code=2)
    if dest is None:
        # error template OK — already templated with example value.
        err_console.print("[red]--dest is required for plan move (e.g. --dest ~/dev/).[/red]")
        raise typer.Exit(code=2)
    legend_on = _resolve_legend(here=here, legend=legend, no_legend=no_legend)
    resolved = (root or Path.cwd()).expanduser().resolve() if here else _resolve_or_exit(root)
    classify_payload = _load_classify_or_exit(resolved)
    plan = planmod.build_move_plan(classify_payload, dest.expanduser().resolve())
    _emit_plan(plan, json_out, dry, flat_table=flat_table, legend=legend_on)


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
            err_console.print(
                user_error(
                    what="No plans found under $XDG_STATE_HOME/clain/plans/.",
                    why=(
                        "plan explain reads from the JSON artefact that "
                        "`clain plan recreate` / `plan move` writes; none exist yet."
                    ),
                    fix="clain plan recreate --here --dry    # or `clain plan move --dest …` to write a plan",
                )
            )
            raise typer.Exit(code=2)
        plan_file = candidates[-1]

    data = read_json(plan_file)
    if data is None:
        err_console.print(
            user_error(
                what=f"Could not read plan: {plan_file}.",
                why="The file is missing, unreadable, or not valid JSON.",
                fix=f"ls -la {plan_file.parent}    # confirm the file exists; re-run plan if it's gone",
            )
        )
        raise typer.Exit(code=2)
    for action in data.get("actions", []):
        if action.get("id") == action_id:
            console.print_json(data=action)
            return
    err_console.print(
        user_error(
            what=f"Action id {action_id} not found in {plan_file}.",
            why="Action IDs are 12 hex chars; check the plan render for the right one.",
            fix=f"cat {plan_file} | jq '.actions[].id'    # list all valid IDs",
        )
    )
    raise typer.Exit(code=2)
