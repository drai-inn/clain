"""Rich table builders. Pure rendering — no business logic."""

from __future__ import annotations

from collections import Counter
from typing import Any

from rich.table import Table


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
        table.add_row(
            ws.get("name", "?"),
            "✓" if ws.get("in_sync_tree") else "·",
            tag_str,
            manifests,
            errors,
        )
    return table


def classify_footer(payload: dict[str, Any]) -> str:
    scan = payload.get("scan", {})
    workspaces = payload.get("workspaces", [])
    in_sync = sum(1 for w in workspaces if w.get("in_sync_tree"))
    return (
        f"[bold]Workspaces:[/bold] {len(workspaces)}  "
        f"[bold]In synced tree:[/bold] {in_sync}  "
        f"[bold]Class tags:[/bold] {scan.get('total_class_tags', 0)}  "
        f"[dim]scan {scan.get('duration_seconds', '?')}s[/dim]"
    )


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


def plan_table(plan: dict[str, Any]) -> Table:
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
