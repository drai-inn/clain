"""Rich table builders. Pure rendering — no business logic."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


def classify_table(payload: dict[str, Any]) -> Table:
    workspaces = payload.get("workspaces", [])
    table = Table(
        title="Workspace classification",
        title_style="bold cyan",
        header_style="bold",
    )
    table.add_column("Workspace", style="cyan")
    table.add_column("In sync tree", justify="center")
    table.add_column("Class tags", style="yellow")
    table.add_column("Manifests", style="magenta", overflow="fold")
    table.add_column("Errors", style="red")

    for ws in workspaces:
        counts = Counter(t.get("class") for t in ws.get("class_tags", []))
        tag_str = ", ".join(f"{cls}x{n}" for cls, n in sorted(counts.items())) or "—"
        manifests = ", ".join(ws.get("manifests", [])) or "—"
        errors = str(len(ws.get("errors", []))) if ws.get("errors") else ""
        in_sync = ws.get("in_sync_tree")
        sync_mark = "✓" if in_sync is True else ("·" if in_sync is False else "?")
        table.add_row(
            ws.get("name", "?"),
            sync_mark,
            tag_str,
            manifests,
            errors,
        )
    return table


def classify_footer(payload: dict[str, Any]) -> str:
    scan = payload.get("scan", {})
    workspaces = payload.get("workspaces", [])
    synced_root = scan.get("synced_root")
    in_sync_count = sum(1 for w in workspaces if w.get("in_sync_tree") is True)
    unknown_count = sum(1 for w in workspaces if w.get("in_sync_tree") is None)
    sync_summary = (
        "[bold]Sync placement:[/bold] unknown ([cyan]CLAIN_SYNCED_ROOT[/cyan] not set)"
        if synced_root is None
        else f"[bold]In synced tree:[/bold] {in_sync_count}/{len(workspaces)}"
    )
    footer = (
        f"[bold]Workspaces:[/bold] {len(workspaces)}  "
        f"{sync_summary}  "
        f"[bold]Class tags:[/bold] {scan.get('total_class_tags', 0)}  "
        f"[dim]scan {scan.get('duration_seconds', '?')}s[/dim]"
    )
    if synced_root is None and unknown_count > 0:
        footer += (
            "\n[dim]Pass [cyan]CLAIN_SYNCED_ROOT[/cyan] (e.g. your GDrive / OneDrive / Dropbox / iCloud "
            "Drive path) to enable in-sync detection.[/dim]"
        )
    return footer


def single_workspace_tree(workspace: dict[str, Any], payload: dict[str, Any]) -> Tree:
    """Render a single workspace as a Rich Tree (spec 0010).

    Used when `clain classify --here` produces a one-workspace payload. The
    multi-row classify_table is wrong shape for this case.
    """
    name = workspace.get("name", "?")
    path = workspace.get("path", "?")
    tree = Tree(f"[bold cyan]{name}[/bold cyan]  [dim]({path})[/dim]")

    manifests = workspace.get("manifests", [])
    manifest_str = ", ".join(manifests) if manifests else "—"
    tree.add(f"[bold]Manifests:[/bold] {manifest_str}")

    in_sync = workspace.get("in_sync_tree")
    sync_str = (
        "[green]✓ in synced tree[/green]"
        if in_sync is True
        else "[yellow]· not in synced tree[/yellow]"
        if in_sync is False
        else "[dim]? unknown (CLAIN_SYNCED_ROOT not set)[/dim]"
    )
    tree.add(f"[bold]Sync placement:[/bold] {sync_str}")

    # Group class tags by class name and add a sub-branch per class.
    by_class: dict[str, list[str]] = defaultdict(list)
    for tag in workspace.get("class_tags", []):
        by_class[tag.get("class", "?")].append(tag.get("relative_path", "?"))

    if by_class:
        for cls_name in sorted(by_class.keys()):
            style = {
                "cache-managed": "yellow",
                "ephemeral": "magenta",
                "bytecode": "blue",
            }.get(cls_name, "white")
            branch = tree.add(f"[{style} bold]{cls_name}[/]")
            for rel in sorted(by_class[cls_name]):
                branch.add(f"[{style}]{rel}[/]")
    else:
        tree.add("[dim]No class tags (workspace-source only).[/dim]")

    errors = workspace.get("errors", [])
    if errors:
        err_branch = tree.add(f"[red bold]Errors ({len(errors)})[/]")
        for err in errors[:5]:
            err_branch.add(f"[red]{err}[/]")

    return tree


def single_workspace_footer(workspace: dict[str, Any], payload: dict[str, Any]) -> str:
    """One-line narrative under the tree: what the next command would do."""
    scan = payload.get("scan", {})
    duration = scan.get("duration_seconds", "?")
    manifests = set(workspace.get("manifests", []))
    # Quick deterministic hint for the common manifest cases. (Authoritative
    # derivation lives in clain.plan; this is just a helpful pointer.)
    next_step: str
    if "pixi.toml" in manifests:
        next_step = "clain plan recreate --here --dry  →  pixi install"
    elif "uv.lock" in manifests:
        next_step = "clain plan recreate --here --dry  →  uv sync"
    elif "pnpm-lock.yaml" in manifests:
        next_step = "clain plan recreate --here --dry  →  pnpm install --frozen-lockfile"
    elif "package-lock.json" in manifests:
        next_step = "clain plan recreate --here --dry  →  npm ci"
    elif "yarn.lock" in manifests:
        next_step = "clain plan recreate --here --dry  →  yarn install --frozen-lockfile"
    elif "pyproject.toml" in manifests:
        next_step = "clain plan recreate --here --dry  →  (ambiguous Python toolchain — pin one of pixi/uv/poetry)"
    elif "package.json" in manifests:
        next_step = "clain plan recreate --here --dry  →  (no lockfile — recreate would resolve fresh versions)"
    else:
        next_step = "clain plan recreate --here --dry  →  (no recognised manifest — investigate manually)"
    return f"[bold]Next:[/bold] {next_step}  [dim]scan {duration}s[/dim]"


def workspace_detail_table(workspace: dict[str, Any]) -> Table:
    table = Table(
        title=f"Workspace: {workspace.get('name', '?')}",
        title_style="bold cyan",
        header_style="bold",
    )
    table.add_column("Class", style="yellow")
    table.add_column("Relative path", style="cyan")
    for tag in workspace.get("class_tags", []):
        table.add_row(tag.get("class", "?"), tag.get("relative_path", "?"))
    return table


def plan_table_flat(plan: dict[str, Any]) -> Table:
    """Single-table layout with absolute paths — the `--table` render mode.

    Preserves the pre-spec-0012 plan_table() output byte-for-byte for users who
    rely on it (e.g. copy-pasting to a spreadsheet). The default render is
    `plan_panels` (workspace-grouped, relative paths) per spec 0012.
    """
    actions = plan.get("actions", [])
    kind = plan.get("kind", "plan")
    table = Table(
        title=f"Plan: {kind} ({len(actions)} actions)",
        title_style="bold cyan",
        header_style="bold",
    )
    table.add_column("Workspace", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Class", style="yellow")
    table.add_column("Target", overflow="fold")
    table.add_column("Command(s)", overflow="fold")
    table.add_column("Safe?", justify="center")

    for a in actions:
        safe_mark = "✓" if a.get("safe_to_execute") else "[red]✗[/red]"
        cmds = "\n".join(a.get("commands", []) or ["—"])
        table.add_row(
            a.get("workspace", "?"),
            a.get("type", "?"),
            a.get("class", "?"),
            a.get("target", "?"),
            cmds,
            safe_mark,
        )
    return table


# Backwards-compat alias: any external code still importing `plan_table` keeps
# working with the flat layout. The default CLI render is `plan_panels` per
# spec 0012, but the function name `plan_table` is kept as an alias rather
# than removed, to avoid surprising any out-of-tree consumer.
plan_table = plan_table_flat


def _location_for_workspace(actions: list[dict[str, Any]], fallback: str) -> str:
    """Compute the common-path location of a workspace's action targets.

    Per spec 0012 § Location derivation. Falls back to `fallback` (the workspace's
    classify-cache `path`) when commonpath returns `/` or raises.
    """
    import os.path

    targets = [a.get("target", "") for a in actions if a.get("target")]
    if not targets:
        return fallback
    try:
        common = os.path.commonpath(targets)
    except ValueError:
        return fallback
    if not common or common == "/":
        return fallback
    # commonpath sometimes returns a non-prefix in edge cases — verify.
    if not all(t == common or t.startswith(common + "/") for t in targets):
        return fallback
    return str(common)


def _relativise_target(target: str, location: str) -> str:
    if target == location:
        return "."
    if target.startswith(location + "/"):
        return target[len(location) + 1 :]
    return target  # absolute fallback


def _relativise_command(cmd: str, location: str) -> str:
    """Rewrite path-bearing portions of a shell command to be relative to location.

    Recognises the two embedding shapes the plan emits: `'<location>/X'` and
    `'<location>'`. Other commands (e.g. `pixi install`) pass through unchanged.
    """
    return cmd.replace(f"'{location}/", "'").replace(f"'{location}'", "'.'")


def plan_panels(plan: dict[str, Any]) -> list[Panel]:
    """Workspace-grouped render — one Panel per workspace, relative paths inside.

    Spec 0012 § Default rendering. Returns a list of Rich Panel renderables;
    the caller prints them in order. The JSON shape behind the plan is not
    touched — relativisation is render-only.
    """
    from collections import defaultdict

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    workspace_paths: dict[str, str] = {}
    for a in plan.get("actions", []):
        ws = a.get("workspace", "?")
        grouped[ws].append(a)
        # Heuristic fallback: the recreate action's target IS the workspace root.
        if a.get("type") == "recreate" and ws not in workspace_paths:
            workspace_paths[ws] = a.get("target", "")

    panels: list[Panel] = []
    for ws_name, actions in grouped.items():
        fallback = workspace_paths.get(ws_name) or (actions[0].get("target", "") if actions else "")
        location = _location_for_workspace(actions, fallback)

        table = Table(
            box=box.SIMPLE,
            header_style="bold",
            show_header=True,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Type", style="green", no_wrap=True)
        table.add_column("Class", style="yellow", no_wrap=True)
        table.add_column("Target", style="cyan", overflow="fold")
        table.add_column("Command(s)", overflow="fold")
        table.add_column("Safe?", justify="center", no_wrap=True)

        for a in actions:
            safe_mark = "✓" if a.get("safe_to_execute") else "[red]✗[/red]"
            target = _relativise_target(a.get("target", "?"), location)
            cmds = [_relativise_command(c, location) for c in a.get("commands", [])]
            table.add_row(
                a.get("type", "?"),
                a.get("class", "?"),
                target,
                "\n".join(cmds) or "—",
                safe_mark,
            )

        panel = Panel(
            table,
            title=f"[bold cyan]{ws_name}[/]  [dim]{location}[/dim]",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
        panels.append(panel)
    return panels


def plan_header(plan: dict[str, Any]) -> str:
    """One-line title rendered above the workspace panels in default mode."""
    actions = plan.get("actions", [])
    kind = plan.get("kind", "plan")
    return f"[bold cyan]Plan: {kind} ({len(actions)} actions)[/bold cyan]"


def unsafe_actions_table(plan: dict[str, Any]) -> Table | None:
    unsafe = [a for a in plan.get("actions", []) if not a.get("safe_to_execute")]
    if not unsafe:
        return None
    table = Table(
        title=f"⚠ Unsafe actions ({len(unsafe)}) — review before lifting any gate",
        title_style="bold red",
        header_style="bold",
    )
    table.add_column("Workspace", style="cyan")
    table.add_column("Type")
    table.add_column("Reason", style="red", overflow="fold")
    for a in unsafe:
        table.add_row(
            a.get("workspace", "?"),
            a.get("type", "?"),
            a.get("unsafe_reason", "(no reason given)"),
        )
    return table


def plan_footer(plan: dict[str, Any], plan_path: str) -> str:
    s = plan.get("summary", {})
    return (
        f"[bold]Workspaces:[/bold] {s.get('workspace_count', 0)}  "
        f"[bold]Actions:[/bold] {s.get('action_count', 0)}  "
        f"[bold red]Unsafe:[/bold red] {s.get('unsafe_count', 0)}  "
        f"[dim]saved to {plan_path}[/dim]"
    )
