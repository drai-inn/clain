"""Spec 0016 — orientation identity (meter + emoji + intent + banner) + `type → action` rename."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

from clain import classify as cls
from clain import plan as planmod
from clain.cli import app
from clain.state import plan_dir, prune_stale_plan_files, write_json
from clain.ui.banner import (
    anchor_block,
    banner_marker_path,
    mark_banner_shown,
    render_banner,
    render_meter,
    should_show_banner,
)
from clain.ui.intent import COMMAND_IDENTITIES, identity_for
from clain.ui.tables import classify_here_view, plan_view
from tests.conftest import make_node_workspace, make_pixi_workspace, write_file

runner = CliRunner()
WIDTH = 100


def _cap(renderable: Any) -> str:
    buf = Console(record=True, width=WIDTH, force_terminal=False)
    buf.print(renderable)
    return buf.export_text(clear=False)


# ---------------------------------------------------------------------------
# Part A — orientation
# ---------------------------------------------------------------------------


def test_meter_glyph_count_is_5() -> None:
    """Every meter level produces exactly five glyphs, exactly `level` filled."""
    for level in range(6):
        out = _cap(__import__("rich.text", fromlist=["Text"]).Text.from_markup(render_meter(level)))
        # Plain rendering: count ▰ and ▱.
        filled = out.count("▰")
        outline = out.count("▱")
        assert filled == level, (level, filled, out)
        assert filled + outline == 5, (level, out)


def test_classify_meter_level_is_2() -> None:
    assert identity_for("classify_tree").level == 2
    assert identity_for("classify_here").level == 2


def test_plan_recreate_dry_meter_level_is_3() -> None:
    assert identity_for("plan_recreate_dry").level == 3
    assert identity_for("plan_move_dry").level == 3


def test_plan_explain_meter_level_is_4() -> None:
    assert identity_for("plan_explain").level == 4


def test_plan_recreate_exec_meter_level_is_5() -> None:
    assert identity_for("plan_recreate_exec").level == 5
    assert identity_for("plan_move_exec").level == 5


def test_classify_render_starts_with_meter_anchor(tmp_path: Path) -> None:
    """First non-blank line of a classify render is the meter + clain + emoji + name."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    (ws / ".pixi").mkdir()
    payload = cls.run_classify(ws, single=True)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    first_non_blank = next(line for line in text.splitlines() if line.strip())
    # Anchor row should contain a meter glyph, "clain", and the command name.
    assert "▰" in first_non_blank or "▱" in first_non_blank, first_non_blank
    assert "clain" in first_non_blank
    assert "classify --here" in first_non_blank


def test_intent_line_present_below_anchor(tmp_path: Path) -> None:
    """Each command's intent string appears in the rendered output."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    (ws / ".pixi").mkdir()
    payload = cls.run_classify(ws, single=True)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    # A distinctive substring of the classify_here intent line. Rich wraps the
    # line at terminal width, so we collapse whitespace before checking.
    flat = re.sub(r"\s+", " ", text)
    assert "what's regenerable, what isn't" in flat


def test_no_command_restate_header(tmp_path: Path) -> None:
    """The legacy `clain classify --here  →  one-workspace classification` is gone."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    payload = cls.run_classify(ws, single=True)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    # Old phrasing.
    assert "one-workspace classification" not in text
    assert "multi-workspace classification" not in text


def test_meter_renders_without_color_in_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Meter glyphs remain readable when NO_COLOR strips colour."""
    monkeypatch.setenv("NO_COLOR", "1")
    # Rich honours NO_COLOR at render time; we capture without force_terminal.
    out = _cap(__import__("rich.text", fromlist=["Text"]).Text.from_markup(render_meter(3)))
    assert out.count("▰") == 3
    assert out.count("▱") == 2


# Per-command emoji presence — sanity check the mapping isn't truncated.
def test_command_emoji_mapping_complete() -> None:
    required = {
        "classify_tree",
        "classify_here",
        "plan_recreate_dry",
        "plan_recreate_exec",
        "plan_move_dry",
        "plan_move_exec",
        "plan_explain",
    }
    assert required <= set(COMMAND_IDENTITIES.keys())
    for ident in COMMAND_IDENTITIES.values():
        assert ident.emoji
        assert ident.intent
        assert 1 <= ident.level <= 5


# ---------------------------------------------------------------------------
# First-run banner
# ---------------------------------------------------------------------------


def test_first_run_banner_shown_when_marker_absent(tmp_path: Path) -> None:
    """No marker → banner shows, marker gets created."""
    assert not banner_marker_path().exists()
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-cache"])
    assert result.exit_code == 0, result.output
    # Banner ASCII art contains a distinctive sequence.
    assert "██████╗" in result.output or "Categorical visibility" in result.output
    # Marker is now present.
    assert banner_marker_path().exists()


def test_first_run_banner_skipped_when_marker_present(tmp_path: Path) -> None:
    """Marker present → banner suppressed."""
    mark_banner_shown()
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-cache"])
    assert result.exit_code == 0, result.output
    assert "██████╗" not in result.output


def test_first_run_banner_skipped_in_json_mode(tmp_path: Path) -> None:
    """--json never emits the banner regardless of marker state."""
    assert not banner_marker_path().exists()
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--json", "--no-cache"])
    assert result.exit_code == 0
    assert "██████╗" not in result.output
    # And the marker isn't consumed by a JSON run.
    assert not banner_marker_path().exists()


def test_no_banner_flag_force_suppresses(tmp_path: Path) -> None:
    """--no-banner suppresses even when marker absent."""
    assert not banner_marker_path().exists()
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-banner", "--no-cache"])
    assert result.exit_code == 0
    assert "██████╗" not in result.output
    # --no-banner doesn't consume the first-run marker either.
    assert not banner_marker_path().exists()


def test_banner_flag_force_shows(tmp_path: Path) -> None:
    """--banner shows even when marker present, and does NOT touch the marker timestamp."""
    mark_banner_shown()
    marker = banner_marker_path()
    before = marker.stat().st_mtime
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--banner", "--no-cache"])
    assert result.exit_code == 0
    assert "██████╗" in result.output or "Categorical visibility" in result.output
    # --banner is for screenshots; it shouldn't rewrite the user's marker.
    assert marker.stat().st_mtime == before


def test_clain_banner_env_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAIN_BANNER=off suppresses; CLAIN_BANNER=on forces show."""
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")

    monkeypatch.setenv("CLAIN_BANNER", "off")
    r1 = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-cache"])
    assert r1.exit_code == 0
    assert "██████╗" not in r1.output

    monkeypatch.setenv("CLAIN_BANNER", "on")
    r2 = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-cache"])
    assert r2.exit_code == 0
    assert "██████╗" in r2.output or "Categorical visibility" in r2.output


def test_banner_and_no_banner_are_mutex(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--banner", "--no-banner"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_clain_banner_env_invalid_value_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAIN_BANNER", "maybe")
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")
    result = runner.invoke(app, ["classify", "--here", str(root / "alpha"), "--no-cache"])
    assert result.exit_code != 0
    assert "on" in result.output and "off" in result.output


def test_should_show_banner_pure_function() -> None:
    """Direct unit test of the resolver — no CLI roundtrip."""
    # JSON mode → off, regardless of everything else.
    assert should_show_banner(flag=True, env="on", json_mode=True) is False
    # Flag overrides env.
    assert should_show_banner(flag=True, env="off", json_mode=False) is True
    assert should_show_banner(flag=False, env="on", json_mode=False) is False
    # Env overrides marker.
    assert should_show_banner(flag=None, env="off", json_mode=False) is False
    # Default: marker absent → True; marker present → False.
    assert not banner_marker_path().exists()
    assert should_show_banner(flag=None, env=None, json_mode=False) is True
    mark_banner_shown()
    assert should_show_banner(flag=None, env=None, json_mode=False) is False


def test_render_banner_is_renderable() -> None:
    """render_banner() returns a Rich renderable that produces non-empty output."""
    out = _cap(render_banner())
    assert "Categorical visibility" in out
    assert "github.com/drai-inn/clain" in out


def test_anchor_block_includes_meter_clain_emoji_name() -> None:
    """Anchor block layout: meter, then `clain`, then emoji, then command name."""
    text = _cap(anchor_block(identity_for("plan_explain")))
    # Order: meter glyphs precede 'clain' precedes 'plan explain' on the same line.
    line = next(ln for ln in text.splitlines() if "clain" in ln)
    meter_idx = line.find("▰") if "▰" in line else line.find("▱")
    clain_idx = line.find("clain")
    cmd_idx = line.find("plan explain")
    assert 0 <= meter_idx < clain_idx < cmd_idx, line


# ---------------------------------------------------------------------------
# Part B — `type → action` rename + schema bump + filename pattern
# ---------------------------------------------------------------------------


def test_plan_json_uses_action_not_type(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    payload = cls.run_classify(root)
    plan = planmod.build_recreate_plan(payload)
    for a in plan["actions"]:
        assert "action" in a, a
        assert "type" not in a, a


def test_plan_schema_version_is_2(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    payload = cls.run_classify(root)
    plan = planmod.build_recreate_plan(payload)
    assert plan["schema"] == 2
    assert planmod.SCHEMA_VERSION == 2


def test_plan_file_name_includes_schema_version(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry"])
    assert result.exit_code == 0, result.output
    plans = list(plan_dir().glob("recreate-*-v2.json"))
    assert plans, list(plan_dir().glob("*.json"))
    # Filename pattern: <kind>-<UTC stamp>-v<schema>.json
    assert re.match(r"^recreate-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z-v2\.json$", plans[0].name), plans[0].name


def test_plan_explain_rejects_stale_schema(tmp_path: Path) -> None:
    """A pre-written schema-1 plan file is refused with a clear regenerate prompt."""
    stale_path = plan_dir() / "recreate-2025-01-01T00-00-00Z-v1.json"
    write_json(
        stale_path,
        {
            "schema": 1,
            "kind": "recreate",
            "generated_at": "2025-01-01T00:00:00+00:00",
            "actions": [
                {
                    "id": "aaaaaaaaaaaa",
                    "workspace": "stale",
                    "type": "delete",  # old field name
                    "target": "/x",
                    "class": "cache-managed",
                    "rationale": "x",
                    "commands": [],
                    "preconditions": [],
                    "safe_to_execute": True,
                    "unsafe_reason": None,
                }
            ],
            "summary": {"workspace_count": 1, "action_count": 1, "unsafe_count": 0},
        },
    )
    result = runner.invoke(app, ["plan", "explain", "aaaaaaaaaaaa"])
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "schema" in combined.lower()
    assert "regenerate" in combined.lower() or "plan recreate" in combined


def test_prune_stale_plan_files_removes_old_schema_after_grace(tmp_path: Path) -> None:
    """A 10-day-old schema-1 plan is removed; a recent one is kept."""
    import os
    import time

    pdir = plan_dir()
    pdir.mkdir(parents=True, exist_ok=True)

    old = pdir / "recreate-2020-01-01T00-00-00Z.json"
    write_json(old, {"schema": 1, "kind": "recreate", "actions": []})
    old_mtime = time.time() - 10 * 86400
    os.utime(old, (old_mtime, old_mtime))

    fresh = pdir / "recreate-2030-01-01T00-00-00Z.json"
    write_json(fresh, {"schema": 1, "kind": "recreate", "actions": []})
    fresh_mtime = time.time()
    os.utime(fresh, (fresh_mtime, fresh_mtime))

    removed = prune_stale_plan_files(current_schema=2)
    assert old in removed
    assert fresh not in removed
    assert not old.exists()
    assert fresh.exists()


def test_plan_table_flat_snapshot_action_column() -> None:
    """The flat-table snapshot text contains 'Action' as the column header (post-rename)."""
    snap = Path(__file__).resolve().parent / "snapshots" / "plan_table_flat.txt"
    text = snap.read_text(encoding="utf-8")
    assert "Action" in text
    # Smoke check: the legacy header is gone.
    assert "┃ Type     ┃" not in text


def test_renderer_uses_action_field(tmp_path: Path) -> None:
    """A plan-table render reads from `action`, not `type`. Crafted plan with only `action` keys."""
    plan = {
        "schema": 2,
        "kind": "recreate",
        "generated_at": "x",
        "root": "/x",
        "rules_schema": 1,
        "classify_cache_id": "x",
        "actions": [
            {
                "id": "x1",
                "workspace": "alpha",
                "action": "recreate",
                "target": "/x/alpha",
                "class": "cache-managed",
                "rationale": "x",
                "commands": ["pixi install"],
                "preconditions": [],
                "safe_to_execute": True,
                "unsafe_reason": None,
            },
        ],
        "summary": {"workspace_count": 1, "action_count": 1, "unsafe_count": 0},
    }
    text = _cap(plan_view(plan, saved_path="(t)", legend=False))
    # "recreate" appears as the action label in the rendered table row.
    assert "recreate" in text


def test_persisted_plan_json_uses_action(tmp_path: Path) -> None:
    """End-to-end: persisted JSON file contains `action`, not `type`."""
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    runner.invoke(app, ["plan", "recreate", str(root), "--dry"])
    files = sorted(plan_dir().glob("recreate-*-v2.json"))
    assert files
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    assert data["schema"] == 2
    for a in data["actions"]:
        assert "action" in a
        assert "type" not in a
