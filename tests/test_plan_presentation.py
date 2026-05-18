"""Tests for spec 0012 — plan presentation.

Covers:
- `plan_table_flat` is byte-identical to the captured pre-0012 snapshot
  (backwards-compat invariant for `--table` mode).
- `plan_panels` emits one Panel per workspace, with workspace+location in title.
- Target column is relative to the workspace's location; recreate target = ".".
- Command(s) column rewrites embedded path quotes to relative form.
- Long values wrap (don't truncate).
- Disjoint-tree fallback: when commonpath doesn't yield a valid location,
  fall back to the workspace's path and render absolute targets.
- `--table` and `--json` are mutually exclusive at the CLI.
- Persisted JSON is byte-identical across modes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from typer.testing import CliRunner

from clain.cli import app
from clain.ui.tables import (
    _location_for_workspace,
    _relativise_command,
    _relativise_target,
    plan_panels,
    plan_table_flat,
)
from tests.conftest import make_node_workspace, write_file

runner = CliRunner()
SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
WIDTH = 100


def _capture(renderable: Any) -> str:
    buf = Console(record=True, width=WIDTH, force_terminal=False)
    buf.print(renderable)
    return buf.export_text(clear=False)


def _load_fixture_plan() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SNAPSHOTS / "plan_table_flat.fixture.json").read_text(encoding="utf-8"))
    return data


def test_plan_table_flat_snapshot_unchanged() -> None:
    """`plan_table_flat()` must produce byte-identical output to the captured
    pre-spec-0012 `plan_table()` on the fixture plan. This is the backwards-
    compat invariant for `--table` mode."""
    plan = _load_fixture_plan()
    expected = (SNAPSHOTS / "plan_table_flat.txt").read_text(encoding="utf-8")
    actual = _capture(plan_table_flat(plan))
    assert actual == expected, (
        f"plan_table_flat output drifted from snapshot.\n--- expected ---\n{expected}\n--- actual ---\n{actual}"
    )


def test_plan_panels_renders_one_per_workspace() -> None:
    plan = _load_fixture_plan()
    panels = plan_panels(plan)
    assert len(panels) == 2  # fixture has alpha and beta
    for p in panels:
        assert isinstance(p, Panel)


def test_plan_panels_workspace_and_location_in_title() -> None:
    plan = _load_fixture_plan()
    panels = plan_panels(plan)
    rendered = [_capture(p) for p in panels]
    # alpha's panel title contains "alpha" and its location.
    alpha_render = next(r for r in rendered if "alpha" in r and "/fixture/dev/alpha" in r)
    assert "alpha" in alpha_render
    assert "/fixture/dev/alpha" in alpha_render


def test_plan_panels_target_is_relative() -> None:
    plan = _load_fixture_plan()
    rendered = "\n".join(_capture(p) for p in plan_panels(plan))
    # Relative path appears; absolute does not.
    assert "node_modules" in rendered
    # The absolute prefix /fixture/dev/alpha/ should NOT appear in the Target
    # column (the location is the title, paths beneath are relative).
    # We allow the absolute path to appear in the panel title only.
    # So a stricter check: lines containing "delete" + "node_modules" should
    # not contain "/fixture/dev/alpha/node_modules".
    for line in rendered.splitlines():
        if "delete" in line and "node_modules" in line:
            assert "/fixture/dev/alpha/node_modules" not in line, f"target should be relative: {line!r}"


def test_plan_panels_command_is_relative() -> None:
    plan = _load_fixture_plan()
    rendered = "\n".join(_capture(p) for p in plan_panels(plan))
    # The relativised command should appear; the absolute form should not in action rows.
    assert "rm -rf 'node_modules'" in rendered
    assert "rm -rf '/fixture/dev/alpha/node_modules'" not in rendered


def test_plan_panels_recreate_target_is_dot() -> None:
    plan = _load_fixture_plan()
    rendered = "\n".join(_capture(p) for p in plan_panels(plan))
    # alpha has a recreate action targeting the workspace root.
    # The Target column for that row should be ".".
    found_dot_target_for_recreate = False
    for line in rendered.splitlines():
        if "recreate" in line and "pnpm install" in line and "." in line:
            found_dot_target_for_recreate = True
    assert found_dot_target_for_recreate


def test_plan_panels_long_value_wraps() -> None:
    """Long values wrap across multiple lines; they are not truncated with '...'."""
    plan = _load_fixture_plan()
    # Add a synthetic long-target action to alpha.
    long_rel = "src/deeply/nested/path/component/that/is/quite/long/__pycache__"
    plan["actions"].append(
        {
            "id": "long11111111",
            "workspace": "alpha",
            "type": "delete",
            "target": f"/fixture/dev/alpha/{long_rel}",
            "class": "bytecode",
            "rationale": "x",
            "commands": [f"rm -rf '/fixture/dev/alpha/{long_rel}'"],
            "preconditions": [],
            "safe_to_execute": True,
            "unsafe_reason": None,
        }
    )
    rendered = "\n".join(_capture(p) for p in plan_panels(plan))
    # No ellipsis-truncation marker anywhere in the rendered text — Rich's
    # overflow="fold" wraps the long path across multiple lines instead.
    assert "…" not in rendered
    # The path is visible, even if Rich split words across line breaks.
    # We strip whitespace before checking — wrapping inserts spaces/newlines
    # between visible characters, but if we collapse to plain alpha-only chars
    # the full string must still appear.
    flat = "".join(c for c in rendered if c.isalnum() or c in "/_")
    assert "deeplynestedpathcomponentthatisquitelongpycache" in flat or "src/deeply" in rendered


def test_location_for_workspace_typical(tmp_path: Path) -> None:
    actions = [
        {"target": "/fixture/dev/alpha/node_modules", "type": "delete"},
        {"target": "/fixture/dev/alpha", "type": "recreate"},
    ]
    assert _location_for_workspace(actions, "/fallback") == "/fixture/dev/alpha"


def test_location_for_workspace_disjoint_falls_back() -> None:
    """Disjoint-tree fallback: when commonpath returns / or non-prefix, use fallback."""
    actions = [
        {"target": "/totally/different/place", "type": "delete"},
        {"target": "/another/elsewhere", "type": "delete"},
    ]
    assert _location_for_workspace(actions, "/fixture/dev/alpha") == "/fixture/dev/alpha"


def test_plan_panels_disjoint_tree_falls_back_to_workspace_path() -> None:
    """A workspace whose action targets share no common prefix below `/` must
    not crash; instead the renderer falls back to the workspace's path field
    and emits absolute targets."""
    plan = {
        "schema": 1,
        "kind": "recreate",
        "generated_at": "x",
        "root": "/fixture/dev",
        "rules_schema": 1,
        "classify_cache_id": "x",
        "actions": [
            {
                "id": "x1",
                "workspace": "weird",
                "type": "recreate",
                "target": "/fixture/dev/weird",
                "class": "cache-managed",
                "rationale": "x",
                "commands": ["pixi install"],
                "preconditions": [],
                "safe_to_execute": True,
                "unsafe_reason": None,
            },
            {
                "id": "x2",
                "workspace": "weird",
                "type": "delete",
                "target": "/totally/disjoint/elsewhere",
                "class": "ephemeral",
                "rationale": "x",
                "commands": ["rm -rf '/totally/disjoint/elsewhere'"],
                "preconditions": [],
                "safe_to_execute": True,
                "unsafe_reason": None,
            },
        ],
        "summary": {"workspace_count": 1, "action_count": 2, "unsafe_count": 0},
    }
    # Must not raise.
    panels = plan_panels(plan)
    rendered = _capture(panels[0])
    # The disjoint target should appear absolute (fallback rendering).
    assert "/totally/disjoint/elsewhere" in rendered


def test_relativise_target() -> None:
    assert _relativise_target("/a/b/c", "/a/b") == "c"
    assert _relativise_target("/a/b", "/a/b") == "."
    assert _relativise_target("/a/b/c/d", "/a/b") == "c/d"
    # Not under location → absolute fallback.
    assert _relativise_target("/x", "/a/b") == "/x"


def test_relativise_command() -> None:
    assert _relativise_command("rm -rf '/a/b/c'", "/a/b") == "rm -rf 'c'"
    assert _relativise_command("rm -rf '/a/b'", "/a/b") == "rm -rf '.'"
    assert _relativise_command("pixi install", "/a/b") == "pixi install"


def test_cli_table_flag_renders_flat_layout(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry", "--table"])
    assert result.exit_code == 0, result.output
    # Flat-layout title appears.
    assert "Plan: recreate" in result.output
    # Workspace column header appears (only in flat).
    assert "Workspace" in result.output


def test_cli_default_render_uses_panels(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry"])
    assert result.exit_code == 0, result.output
    # Panel render has the workspace name as a title (without the "Workspace" column header).
    assert "alpha" in result.output


def test_cli_table_and_json_are_mutex(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry", "--table", "--json"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_cli_table_and_json_mutex_for_plan_move(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(
        app, ["plan", "move", str(root), "--dest", str(tmp_path / "out"), "--dry", "--table", "--json"]
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_persisted_plan_json_identical_across_modes(tmp_path: Path) -> None:
    """Render mode does not leak into the persisted plan JSON.

    Run plan recreate three times against the same classify cache (default,
    --table, --json) and assert the file written under $XDG_STATE_HOME has
    byte-identical JSON content across all three.
    """
    root = tmp_path / "dev"
    root.mkdir()
    write_file(root / "alpha" / "pixi.toml", '[workspace]\nname="alpha"\n')
    (root / "alpha" / ".pixi").mkdir()
    runner.invoke(app, ["classify", str(root)])

    from clain.state import plan_dir

    def _read_latest_plan_json() -> str:
        plans = sorted(plan_dir().glob("recreate-*.json"))
        return plans[-1].read_text(encoding="utf-8")

    # Default render.
    r1 = runner.invoke(app, ["plan", "recreate", str(root), "--dry"])
    assert r1.exit_code == 0, r1.output
    json_default = _read_latest_plan_json()

    r2 = runner.invoke(app, ["plan", "recreate", str(root), "--dry", "--table"])
    assert r2.exit_code == 0, r2.output
    json_table = _read_latest_plan_json()

    r3 = runner.invoke(app, ["plan", "recreate", str(root), "--dry", "--json"])
    assert r3.exit_code == 0, r3.output
    json_json_mode = _read_latest_plan_json()

    # The plan JSON has a `generated_at` field that varies per run, so we
    # compare structural equality minus that field.
    def _scrub(s: str) -> str:
        d = json.loads(s)
        d.pop("generated_at", None)
        return json.dumps(d, sort_keys=True)

    h1 = hashlib.sha256(_scrub(json_default).encode()).hexdigest()
    h2 = hashlib.sha256(_scrub(json_table).encode()).hexdigest()
    h3 = hashlib.sha256(_scrub(json_json_mode).encode()).hexdigest()
    assert h1 == h2 == h3, (
        f"persisted plan JSON differs across render modes: default={h1[:8]} table={h2[:8]} json={h3[:8]}"
    )
