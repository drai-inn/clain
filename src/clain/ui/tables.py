"""Rich table builders. Pure rendering — no business logic."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from rich import box
from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
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


# ============================================================================
# Spec 0013 — orientation headers, inline legends, breathing room
# ============================================================================

# Class display order in the new --here view. Future classes fall through to
# alphabetical sort.
_CLASS_DISPLAY_ORDER = ("cache-managed", "ephemeral", "bytecode")

_CLASS_DESCRIPTIONS = {
    "cache-managed": (
        "Lives in a per-ecosystem store. Safe to delete if you can re-install — your manifest tells clain how."
    ),
    "ephemeral": "Build output. Regenerable by the normal build step.",
    "bytecode": "Regenerated automatically on the next run.",
}

# Manifest → recreate-command hint, used in the "Next step" block of the
# single-workspace classify view. Authoritative derivation lives in clain.plan;
# this is a presentation pointer.
_NEXT_STEP_HINTS: tuple[tuple[str, str], ...] = (
    ("pixi.toml", "pixi install"),
    ("uv.lock", "uv sync"),
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
    ("package-lock.json", "npm ci"),
    ("yarn.lock", "yarn install --frozen-lockfile"),
)


def _sync_placement_line(sp: dict[str, Any] | None) -> str:
    """Render the single Sync placement line from the sync_placement record."""
    if sp is None:
        return "[dim]? unknown[/dim]"
    state = sp.get("state")
    source = sp.get("source")
    if state == "synced":
        provider = sp.get("provider") or sp.get("synced_root") or "synced storage"
        if source == "env":
            return f"[yellow]⚠ in CLAIN_SYNCED_ROOT[/yellow]  [dim]({sp.get('synced_root')})[/dim]"
        return f"[yellow]⚠ in synced storage[/yellow]  [dim]({provider}; autodetected)[/dim]"
    if state == "local":
        if source == "env":
            return f"[green]✓ not in CLAIN_SYNCED_ROOT[/green]  [dim]({sp.get('synced_root')})[/dim]"
        return "[green]✓ local[/green]  [dim](no synced-storage pattern detected)[/dim]"
    return "[dim]? unknown[/dim]  [dim](set CLAIN_SYNCED_ROOT to enable in-sync detection)[/dim]"


def _orientation(line: str) -> Text:
    """One-line orientation header above every primary output."""
    return Text.from_markup(f"[bold cyan]{line}[/]")


def _ordered_class_keys(by_class: dict[str, list[str]]) -> list[str]:
    known = [c for c in _CLASS_DISPLAY_ORDER if c in by_class]
    others = sorted(k for k in by_class if k not in _CLASS_DISPLAY_ORDER)
    return known + others


def _next_step_block(workspace: dict[str, Any]) -> RenderableType:
    """Render the 'Next step:' block for the --here classify view."""
    manifests = set(workspace.get("manifests", []))
    cmd = None
    evidence = None
    for manifest, hint in _NEXT_STEP_HINTS:
        if manifest in manifests:
            cmd = hint
            evidence = manifest
            break
    if cmd is None:
        if "pyproject.toml" in manifests:
            cmd = "(ambiguous Python toolchain — pin pixi/uv/poetry)"
            evidence = "pyproject.toml"
        elif "package.json" in manifests:
            cmd = "(no lockfile — recreate would resolve fresh versions)"
            evidence = "package.json"
        else:
            cmd = "(no recognised manifest)"
            evidence = "—"
    body = Text.from_markup(
        f"[cyan]clain plan recreate --here --dry[/cyan]\n"
        f"[dim]→ would run: [bold]{cmd}[/bold]  (derived from {evidence})[/dim]"
    )
    return Padding(body, (0, 4))


def _classify_legend_block() -> RenderableType:
    """Compact one-liner key for the --here classify view."""
    return Padding(
        Text.from_markup(
            "[bold dim]Key:[/]  "
            "[yellow]cache-managed[/] regenerable from a manifest  ·  "
            "[yellow]bytecode[/] regenerated on use  ·  "
            "[yellow]ephemeral[/] build output"
        ),
        (0, 2),
    )


def classify_here_view(workspace: dict[str, Any], payload: dict[str, Any], *, legend: bool) -> Group:
    """Spec 0013 single-workspace classify renderable.

    Replaces the bare single_workspace_tree + footer call sequence with a
    grouped layout: orientation, header block, class groups, next step, meta
    line, optional legend.
    """
    items: list[RenderableType] = []
    items.append(_orientation("clain classify --here  →  one-workspace classification"))
    items.append(Text(""))

    header = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
    header.add_column(style="dim", no_wrap=True)
    header.add_column(overflow="fold")
    header.add_row("Workspace:", f"[bold]{workspace.get('name', '?')}[/bold]")
    header.add_row("Location:", workspace.get("path", "?"))
    header.add_row("Sync placement:", _sync_placement_line(workspace.get("sync_placement")))
    manifests = ", ".join(workspace.get("manifests", [])) or "—"
    header.add_row("Manifests:", manifests)
    items.append(Padding(header, (0, 2)))
    items.append(Text(""))

    by_class: dict[str, list[str]] = defaultdict(list)
    for tag in workspace.get("class_tags", []):
        by_class[tag.get("class", "?")].append(tag.get("relative_path", "?"))

    if by_class:
        total = sum(len(v) for v in by_class.values())
        items.append(Padding(Text.from_markup(f"[bold]Regenerable subtrees ({total}):[/bold]"), (0, 2)))
        items.append(Text(""))
        for cls_name in _ordered_class_keys(by_class):
            count = len(by_class[cls_name])
            desc = _CLASS_DESCRIPTIONS.get(cls_name, "")
            items.append(
                Padding(
                    Text.from_markup(f"[bold yellow]{cls_name}[/] [dim]({count})[/]   [dim]{desc}[/]"),
                    (0, 4),
                )
            )
            for rel in sorted(by_class[cls_name]):
                items.append(Padding(Text.from_markup(f"[cyan]{rel}[/]"), (0, 6)))
            items.append(Text(""))
    else:
        items.append(
            Padding(
                Text.from_markup("[dim]No regenerable subtrees found (workspace-source only).[/dim]"),
                (0, 2),
            )
        )
        items.append(Text(""))

    items.append(Padding(Text.from_markup("[bold]Next step:[/bold]"), (0, 2)))
    items.append(_next_step_block(workspace))
    items.append(Text(""))

    items.append(Padding(Rule(style="dim"), (0, 2)))

    scan = payload.get("scan", {})
    duration = scan.get("duration_seconds", "?")
    meta_str = f"[dim]scan {duration}s[/dim]"
    items.append(Padding(Text.from_markup(meta_str), (0, 2)))

    if legend:
        items.append(Text(""))
        items.append(_classify_legend_block())

    return Group(*items)


def _classify_tree_summary(payload: dict[str, Any]) -> str:
    """One-line orientation/summary above the tree-mode table."""
    workspaces = payload.get("workspaces", [])
    in_sync = sum(1 for w in workspaces if w.get("in_sync_tree") is True)
    unknown = sum(1 for w in workspaces if w.get("in_sync_tree") is None)
    scan = payload.get("scan", {})
    sync_summary = (
        f"[bold]In synced tree:[/bold] {in_sync}/{len(workspaces)}"
        if not unknown
        else f"[dim]Sync placement unknown for {unknown}/{len(workspaces)} (autodetect / CLAIN_SYNCED_ROOT)[/dim]"
    )
    return (
        f"[bold]Workspaces:[/bold] {len(workspaces)}  "
        f"{sync_summary}  "
        f"[bold]Class tags:[/bold] {scan.get('total_class_tags', 0)}  "
        f"[dim]scan {scan.get('duration_seconds', '?')}s[/dim]"
    )


def classify_tree_view(payload: dict[str, Any], *, legend: bool) -> Group:
    """Spec 0013 tree-mode classify renderable.

    Wraps the existing classify_table (unchanged) with an orientation header
    and structured meta footer; optional legend.
    """
    items: list[RenderableType] = []
    items.append(_orientation("clain classify  →  multi-workspace classification"))
    items.append(Text(""))
    items.append(Padding(classify_table(payload), (0, 1)))
    items.append(Padding(Text.from_markup(_classify_tree_summary(payload)), (0, 2)))
    if legend:
        items.append(Text(""))
        items.append(_classify_legend_block())
    return Group(*items)


def _plan_legend_block() -> RenderableType:
    """Detailed key for the plan view. Explains every column and the safe-glyph semantics."""
    legend = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
    legend.add_column(style="bold dim", no_wrap=True)
    legend.add_column(overflow="fold")
    legend.add_row(
        "Type",
        "[green]delete[/] · [green]recreate[/] · [green]move[/] · [green]smoke-test[/]",
    )
    legend.add_row(
        "Class",
        "[yellow]cache-managed[/]   regenerable from a manifest (your real win)\n"
        "[yellow]bytecode[/]        regenerated automatically on use\n"
        "[yellow]ephemeral[/]       build output, regenerable by the build step",
    )
    legend.add_row("Target", "path being acted on, relative to the workspace location")
    legend.add_row("Command", "the actual shell command this action represents")
    legend.add_row(
        "Safe?",
        "[green]✓[/] — clain has all it needs to run this reproducibly\n"
        "[red]✗[/] — something blocks safe execution; run `clain plan explain <ACTION_ID>` for the reason",
    )
    return Group(
        Padding(Text.from_markup("[bold]Key[/]"), (0, 2)),
        Padding(legend, (0, 4)),
    )


def _plan_meta_block(plan: dict[str, Any], saved_path: str, *, mode: str) -> RenderableType:
    """Structured Summary / Saved / Mode rows replacing the single-line footer."""
    s = plan.get("summary", {})
    meta = Table(box=None, show_header=False, padding=(0, 1), pad_edge=False)
    meta.add_column(style="bold dim", no_wrap=True)
    meta.add_column(overflow="fold")
    meta.add_row(
        "Summary",
        f"{s.get('workspace_count', 0)} workspace  ·  "
        f"{s.get('action_count', 0)} actions  ·  "
        f"[red]{s.get('unsafe_count', 0)} unsafe[/red]",
    )
    meta.add_row("Saved", f"[dim]{saved_path}[/dim]")
    meta.add_row(
        "Mode",
        f"{mode} [dim](execution gate is closed — see executor.py)[/dim]",
    )
    return Padding(meta, (0, 2))


def plan_view(
    plan: dict[str, Any],
    *,
    saved_path: str,
    legend: bool,
    flat_table: bool = False,
    mode: str = "dry-run",
) -> Group:
    """Spec 0013 plan renderable.

    Wraps spec 0012's plan_panels (default) or plan_table_flat (--table mode)
    with orientation header, optional unsafe banner, optional legend, and a
    structured Summary/Saved/Mode meta block. The inner Panel/Table bodies
    are unchanged.
    """
    items: list[RenderableType] = []
    kind = plan.get("kind", "plan")
    here_part = " --here" if plan.get("summary", {}).get("workspace_count", 0) == 1 else ""
    label = {
        "recreate": "delete-and-recreate plan",
        "move": "move-and-triage plan",
    }.get(kind, f"{kind} plan")
    items.append(_orientation(f"clain plan {kind}{here_part} --dry  →  {label}"))
    items.append(Text(""))

    unsafe = unsafe_actions_table(plan)
    if unsafe is not None:
        items.append(Padding(unsafe, (0, 2)))
        items.append(Text(""))

    if flat_table:
        items.append(Padding(plan_table_flat(plan), (0, 1)))
    else:
        for panel in plan_panels(plan):
            # Increase the inner padding for breathing room (was (0, 1); now (1, 2)).
            panel.padding = (1, 2)
            items.append(Padding(panel, (0, 2)))

    items.append(Text(""))

    if legend:
        items.append(_plan_legend_block())
        items.append(Text(""))

    items.append(Padding(Rule(style="dim"), (0, 2)))
    items.append(_plan_meta_block(plan, saved_path, mode=mode))
    return Group(*items)
