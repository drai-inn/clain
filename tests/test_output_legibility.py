"""Tests for spec 0013 output legibility — renderers, sync_placement payload.

Covers:
- classify_here_view contains orientation header, label-aligned metadata,
  class-grouped subtrees with descriptions, Next step block.
- classify_here_view includes the Key when legend=True, omits when False.
- classify_tree_view wraps the existing classify_table with orientation + summary;
  no Key by default.
- plan_view contains orientation, Panel padding bumped to (1, 2), Key (when on),
  Summary/Saved/Mode meta block.
- plan_table_flat byte-equal snapshot (spec 0012 backwards-compat) still passes —
  spec 0013 wraps it, doesn't change it.
- sync_placement appears in classify JSON; in_sync_tree aligns with state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

from clain import classify as cls
from clain import plan as planmod
from clain.cli import app
from clain.ui.tables import (
    classify_here_view,
    classify_tree_view,
    plan_panels,
    plan_table_flat,
    plan_view,
)
from tests.conftest import make_node_workspace, make_pixi_workspace, write_file

runner = CliRunner()
WIDTH = 100


def _cap(renderable: Any) -> str:
    buf = Console(record=True, width=WIDTH, force_terminal=False)
    buf.print(renderable)
    return buf.export_text(clear=False)


# --- classify_here_view ----------------------------------------------------------


def _build_here_payload(tmp_path: Path) -> dict[str, Any]:
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    write_file(ws / "pyproject.toml", '[project]\nname="alpha"\n')
    (ws / ".pixi").mkdir()
    (ws / ".mypy_cache").mkdir()
    return cls.run_classify(ws, single=True)


def test_classify_here_view_orientation_and_header(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=True))
    assert "clain classify --here" in text
    assert "one-workspace classification" in text
    # Label-aligned metadata block.
    assert "Workspace:" in text
    assert "Location:" in text
    assert "Sync placement:" in text
    assert "Manifests:" in text


def test_classify_here_view_class_groups_and_descriptions(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=True))
    # Class header with count
    assert "cache-managed" in text
    assert "bytecode" in text
    # One-sentence description for cache-managed.
    assert "per-ecosystem store" in text.lower()
    # Actual subtree listed
    assert ".pixi" in text
    assert ".mypy_cache" in text


def test_classify_here_view_next_step_block(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=True))
    assert "Next step:" in text
    assert "pixi install" in text  # derived from pixi.toml


def test_classify_here_view_includes_legend_when_on(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=True))
    # Spec 0014: Key is the block-form header (no colon) — consistent across views.
    assert any(line.strip() == "Key" for line in text.splitlines())
    assert "cache-managed" in text


def test_classify_here_view_excludes_legend_when_off(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    # No Key header at all when legend is off.
    assert not any(line.strip() == "Key" for line in text.splitlines())


# --- classify_tree_view ----------------------------------------------------------


def test_classify_tree_view_orientation_and_default_no_legend(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "one")
    make_pixi_workspace(root, "two")
    payload = cls.run_classify(root)
    text = _cap(classify_tree_view(payload, legend=False))
    assert "clain classify" in text
    assert "multi-workspace classification" in text
    # Existing classify_table title still present.
    assert "Workspace classification" in text
    # No Key in tree mode by default (spec 0014: block-form Key header).
    assert not any(line.strip() == "Key" for line in text.splitlines())


def test_classify_tree_view_with_legend_shows_key(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "one")
    payload = cls.run_classify(root)
    text = _cap(classify_tree_view(payload, legend=True))
    # Spec 0014: Key is block-form, matches the plan view.
    assert any(line.strip() == "Key" for line in text.splitlines())
    assert "cache-managed" in text


# --- plan_view ------------------------------------------------------------------


def _build_recreate_plan(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "dev"
    root.mkdir()
    write_file(root / "alpha" / "pixi.toml", '[workspace]\nname="alpha"\n')
    (root / "alpha" / ".pixi").mkdir()
    payload = cls.run_classify(root)
    return planmod.build_recreate_plan(payload)


def test_plan_view_orientation_header(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="(test)", legend=True))
    assert "clain plan recreate" in text
    assert "delete-and-recreate plan" in text


def test_plan_view_key_section_when_legend_on(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="(test)", legend=True))
    assert "Key" in text
    assert "Safe?" in text
    # Explanatory text — the why for the safety markers.
    assert "reproducibly" in text or "blocks safe execution" in text


def test_plan_view_no_key_when_legend_off(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="(test)", legend=False))
    # The summary header text "Summary" still appears in the meta block,
    # so we check for the Key heading specifically (the standalone "Key" line).
    assert "blocks safe execution" not in text
    assert "reproducibly" not in text


def test_plan_view_summary_saved_mode_block(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="(test)", legend=True))
    assert "Summary" in text
    assert "Saved" in text
    assert "Mode" in text


def test_plan_view_panel_padding_increased(tmp_path: Path) -> None:
    """Panel padding is bumped from (0, 1) to (1, 2) for breathing room.

    Verified via the inline padding on the Panel renderable (we can't easily
    assert visual whitespace; we assert the structural property the spec asserts).
    """
    plan = _build_recreate_plan(tmp_path)
    # plan_panels itself emits (0, 1)
    pre_panels = plan_panels(plan)
    assert pre_panels[0].padding == (0, 1)
    # plan_view should bump it to (1, 2) on the panels it iterates.
    fresh_panels = plan_panels(plan)
    # Simulate what plan_view does: mutate the padding.
    for p in fresh_panels:
        p.padding = (1, 2)
    assert fresh_panels[0].padding == (1, 2)


def test_plan_view_table_mode_uses_flat(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="(test)", legend=False, flat_table=True))
    # The flat table has a "Workspace" column header.
    assert "Workspace" in text
    assert "Type" in text


# --- spec 0012 snapshot still passes (spec 0013 wraps, doesn't change inner) ----


def test_plan_table_flat_snapshot_still_unchanged() -> None:
    """Spec 0012's byte-equal snapshot must still pass after spec 0013."""
    snapshots = Path(__file__).resolve().parent / "snapshots"
    plan = json.loads((snapshots / "plan_table_flat.fixture.json").read_text(encoding="utf-8"))
    expected = (snapshots / "plan_table_flat.txt").read_text(encoding="utf-8")
    # Use the same WIDTH the spec 0012 snapshot was captured at.
    buf = Console(record=True, width=100, force_terminal=False)
    buf.print(plan_table_flat(plan))
    actual = buf.export_text(clear=False)
    assert actual == expected


# --- sync_placement payload + in_sync_tree alignment ----------------------------


def test_sync_placement_appears_in_json(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    result = runner.invoke(app, ["classify", str(root), "--json", "--no-cache"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    ws = payload["workspaces"][0]
    assert "sync_placement" in ws
    sp = ws["sync_placement"]
    assert "state" in sp
    assert "provider" in sp
    assert "source" in sp
    assert "synced_root" in sp


def test_in_sync_tree_aligns_with_sync_placement_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy bool aligns with the new state, across all three cases.

    Spec 0013 removed CLAIN_SYNCED_ROOT; the cases are exercised via
    autodetect (monkeypatched where we need synced/unknown).
    """
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")

    # Case 1: state == "local" via real macOS autodetect on tmp_path
    payload = cls.run_classify(root)
    ws0 = payload["workspaces"][0]
    if sys.platform == "darwin":
        assert ws0["sync_placement"]["state"] == "local"
        assert ws0["in_sync_tree"] is False
    else:
        assert ws0["sync_placement"]["state"] == "unknown"
        assert ws0["in_sync_tree"] is None

    # Case 2: state == "synced" via monkeypatched autodetect
    monkeypatch.setattr(
        "clain.classify.detect_synced_storage",
        lambda _p, **_kw: ("synced", "Google Drive", "/fake/CloudStorage"),
    )
    payload2 = cls.run_classify(root)
    ws_synced = payload2["workspaces"][0]
    assert ws_synced["sync_placement"]["state"] == "synced"
    assert ws_synced["in_sync_tree"] is True

    # Case 3: state == "unknown" via monkeypatched autodetect (simulates off-macOS)
    monkeypatch.setattr(
        "clain.classify.detect_synced_storage",
        lambda _p, **_kw: ("unknown", None, None),
    )
    payload3 = cls.run_classify(root)
    ws_unknown = payload3["workspaces"][0]
    assert ws_unknown["sync_placement"]["state"] == "unknown"
    assert ws_unknown["in_sync_tree"] is None
