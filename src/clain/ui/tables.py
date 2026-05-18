"""Rich table builders. Pure rendering — no business logic."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

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
