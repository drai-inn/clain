"""Tests for spec 0014 — vertical rhythm + 0013 follow-through fixes.

Covers:

Part A — correctness fixes:
- Classify cache filename is schema-versioned (`<root-hash>-v<schema>.json`).
- Pre-existing legacy / older-schema cache files are ignored and cleaned up.
- No render produced by classify or plan contains the literal `CLAIN_SYNCED_ROOT`.

Part B — vertical rhythm:
- Meta lines `(cached …)` / `(dry mode …)` render with one blank above and
  indented to BODY_INDENT.
- The horizontal rule has one blank line above and below.
- The rule is the fixed-measure form (≤ RULE_WIDTH chars after the indent).
- Class headers on classify-here use the hanging-indent form.
- Key block is the multi-line block form on both classify and plan.
- Every render ends with at least one trailing empty line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

from clain import classify as cls
from clain import plan as planmod
from clain.cli import app
from clain.config import clain_state_dir
from clain.state import classify_cache_path, prune_stale_classify_caches, root_hash
from clain.ui.rhythm import BODY_INDENT, META_INDENT, RULE_WIDTH
from clain.ui.tables import classify_here_view, classify_tree_view, plan_view

runner = CliRunner()


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


def _cap(renderable: Any) -> str:
    console = Console(width=120, record=True, force_terminal=False, no_color=True)
    console.print(renderable)
    return console.export_text()


def _make_pixi_workspace(parent: Path, name: str) -> Path:
    """Minimal Pixi workspace with one cache-managed subtree (.pixi)."""
    ws = parent / name
    ws.mkdir()
    (ws / "pixi.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\nchannels = []\nplatforms = []\n', encoding="utf-8"
    )
    (ws / ".pixi").mkdir()
    return ws


def _build_here_payload(tmp_path: Path) -> dict[str, Any]:
    ws = _make_pixi_workspace(tmp_path, "alpha")
    return cls.run_classify(ws, single=True)


def _build_recreate_plan(tmp_path: Path) -> dict[str, Any]:
    parent = tmp_path / "dev"
    parent.mkdir()
    _make_pixi_workspace(parent, "alpha")
    payload = cls.run_classify(parent)
    return planmod.build_recreate_plan(payload)


# ----------------------------------------------------------------------------
# Part A.1 — cache schema-aware invalidation
# ----------------------------------------------------------------------------


def test_classify_cache_filename_includes_schema_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 0014: cache filename has a `-v<schema>` suffix so stale caches don't get read."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    fake_root = tmp_path / "root"
    fake_root.mkdir()
    path = classify_cache_path(fake_root, cls.SCHEMA_VERSION)
    assert path.name.endswith(f"-v{cls.SCHEMA_VERSION}.json")
    assert root_hash(fake_root) in path.name


def test_classify_cache_old_schema_file_is_pruned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-existing legacy unsuffixed cache file at the same root hash is removed
    when the new-style cache is written for that root."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    fake_root = tmp_path / "root"
    fake_root.mkdir()

    # Manufacture both a legacy unsuffixed and an older-schema cache file by hand.
    classify_dir = clain_state_dir() / "classify"
    classify_dir.mkdir(parents=True, exist_ok=True)
    legacy = classify_dir / f"{root_hash(fake_root)}.json"
    older = classify_dir / f"{root_hash(fake_root)}-v1.json"
    legacy.write_text("{}", encoding="utf-8")
    older.write_text("{}", encoding="utf-8")
    assert legacy.exists() and older.exists()

    removed = prune_stale_classify_caches(fake_root, cls.SCHEMA_VERSION)
    assert legacy in removed
    assert older in removed
    assert not legacy.exists()
    assert not older.exists()


def test_classify_run_writes_current_schema_and_cleans_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: an old-style cache file gets cleaned up as a side-effect of a
    fresh classify save_cache. The current-schema file exists; the stale one is gone."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    parent = tmp_path / "dev"
    parent.mkdir()
    _make_pixi_workspace(parent, "alpha")

    classify_dir = clain_state_dir() / "classify"
    classify_dir.mkdir(parents=True, exist_ok=True)
    legacy = classify_dir / f"{root_hash(parent)}.json"
    legacy.write_text("{}", encoding="utf-8")

    payload, _ = cls.get_or_run(parent, refresh=True)
    assert payload["schema"] == cls.SCHEMA_VERSION

    current = classify_cache_path(parent, cls.SCHEMA_VERSION)
    assert current.exists()
    assert not legacy.exists()


# ----------------------------------------------------------------------------
# Part A.2 — CLAIN_SYNCED_ROOT hint-text sweep
# ----------------------------------------------------------------------------


def test_no_env_var_strings_in_classify_renders(tmp_path: Path) -> None:
    """No render produced by classify (here or tree) contains CLAIN_SYNCED_ROOT.

    The startup-error path *does* and *must* mention the env var (so the user
    can see what to unset); this test targets only the render output.
    """
    here = _build_here_payload(tmp_path)
    here_text = _cap(classify_here_view(here["workspaces"][0], here, legend=True))
    assert "CLAIN_SYNCED_ROOT" not in here_text

    tree_parent = tmp_path / "tree"
    tree_parent.mkdir()
    _make_pixi_workspace(tree_parent, "one")
    tree_payload = cls.run_classify(tree_parent)
    tree_text = _cap(classify_tree_view(tree_payload, legend=True))
    assert "CLAIN_SYNCED_ROOT" not in tree_text


def test_no_env_var_strings_in_plan_renders(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    panel_text = _cap(plan_view(plan, saved_path="/x/p.json", legend=True))
    flat_text = _cap(plan_view(plan, saved_path="/x/p.json", legend=True, flat_table=True))
    assert "CLAIN_SYNCED_ROOT" not in panel_text
    assert "CLAIN_SYNCED_ROOT" not in flat_text


# ----------------------------------------------------------------------------
# Part B — vertical rhythm
# ----------------------------------------------------------------------------


def _lines(text: str) -> list[str]:
    """Strip trailing right-padding spaces but preserve leading indent."""
    return [ln.rstrip() for ln in text.splitlines()]


def test_rule_is_fixed_measure_not_full_width(tmp_path: Path) -> None:
    """The horizontal rule is RULE_WIDTH chars (modulo leading indent), not the
    terminal width. Captured at width=120 so a regression to full-width would show."""
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    rule_lines = [ln for ln in _lines(text) if set(ln.strip()) == {"─"}]
    assert rule_lines, "no rule line found in classify-here render"
    for ln in rule_lines:
        # The rule body is RULE_WIDTH characters; leading indent is BODY_INDENT.
        assert len(ln.strip()) == RULE_WIDTH
        assert ln.startswith(BODY_INDENT)


def test_rule_has_blank_line_above_and_below_on_classify_here(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    lines = _lines(text)
    rule_idx = [i for i, ln in enumerate(lines) if set(ln.strip()) == {"─"}]
    assert rule_idx, "no rule line"
    i = rule_idx[0]
    assert lines[i - 1] == "", f"expected blank above rule, got: {lines[i - 1]!r}"
    assert lines[i + 1] == "", f"expected blank below rule, got: {lines[i + 1]!r}"


def test_rule_has_blank_line_above_and_below_on_plan_view(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="/x/p.json", legend=True))
    lines = _lines(text)
    rule_idx = [i for i, ln in enumerate(lines) if set(ln.strip()) == {"─"}]
    assert rule_idx, "no rule line"
    # The rule we care about is the closing one (last rule in the render).
    i = rule_idx[-1]
    assert lines[i - 1] == ""
    assert lines[i + 1] == ""


def test_class_header_uses_hanging_indent(tmp_path: Path) -> None:
    """Spec 0014: count on its own line; description on the next line below."""
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    lines = _lines(text)
    # The line containing "cache-managed (1)" should end at the parenthesis;
    # the description starts on a subsequent indented line.
    header_idx = next(i for i, ln in enumerate(lines) if "cache-managed (1)" in ln)
    header_line = lines[header_idx]
    # No description text on the header line itself (description starts with
    # "Lives in a per-ecosystem store…").
    assert "Lives in a per-ecosystem" not in header_line
    # Description appears on the next non-empty line.
    next_nonempty = next(ln for ln in lines[header_idx + 1 :] if ln.strip())
    assert "Lives in a per-ecosystem" in next_nonempty


def test_classify_here_key_is_block_form_not_inline(tmp_path: Path) -> None:
    """Spec 0014: classify-here Key uses block form (header on its own line)
    matching the plan-view treatment. The legacy `Key:  ...` inline form is gone."""
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=True))
    lines = _lines(text)
    # Block-form: there is a line that is exactly "Key" (after indent strip).
    assert any(ln.strip() == "Key" for ln in lines)
    # No inline "Key:" one-liner — that would be a line whose stripped form
    # starts with "Key:".
    assert not any(ln.strip().startswith("Key:") for ln in lines)


def test_render_ends_with_trailing_blank_on_classify_here(tmp_path: Path) -> None:
    payload = _build_here_payload(tmp_path)
    text = _cap(classify_here_view(payload["workspaces"][0], payload, legend=False))
    assert text.endswith("\n"), "renders must end with a newline"
    # Spec 0014: at least one trailing empty line so the next shell prompt has air.
    assert _lines(text)[-1] == ""


def test_render_ends_with_trailing_blank_on_plan_view(tmp_path: Path) -> None:
    plan = _build_recreate_plan(tmp_path)
    text = _cap(plan_view(plan, saved_path="/x/p.json", legend=True))
    assert text.endswith("\n")
    assert _lines(text)[-1] == ""


# ----------------------------------------------------------------------------
# CLI-level: meta-line indent and blank-line-above
# ----------------------------------------------------------------------------


def test_meta_line_cached_is_indented_with_blank_above(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running classify --here twice triggers the (cached …) line; spec 0014 says
    it must be preceded by a blank line and indented to META_INDENT, not col 0."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    ws = _make_pixi_workspace(tmp_path, "alpha")
    # First run: writes the cache.
    runner.invoke(app, ["classify", "--here", str(ws), "--no-legend"])
    # Second run: hits the cache.
    result = runner.invoke(app, ["classify", "--here", str(ws), "--no-legend"])
    assert result.exit_code == 0, result.output

    lines = _lines(result.output)
    cached_idx = next(i for i, ln in enumerate(lines) if "(cached" in ln)
    cached_line = lines[cached_idx]
    # Indented to META_INDENT, not col 0.
    assert cached_line.startswith(META_INDENT)
    assert not cached_line.startswith("(")
    # Blank line above.
    assert lines[cached_idx - 1] == "", (
        f"expected blank line above the cached meta line, got: {lines[cached_idx - 1]!r}"
    )


def test_meta_line_dry_mode_is_indented_with_blank_above(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`plan recreate --here --dry` emits `(dry mode — execution skipped)`. Same
    rules as the cached meta line: blank above + META_INDENT."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    ws = _make_pixi_workspace(tmp_path, "alpha")
    # Run classify first to populate the plan input.
    runner.invoke(app, ["classify", "--here", str(ws), "--no-legend"])
    result = runner.invoke(app, ["plan", "recreate", "--here", str(ws), "--dry", "--no-legend"])
    assert result.exit_code == 0, result.output

    lines = _lines(result.output)
    dry_idx = next(i for i, ln in enumerate(lines) if "dry mode" in ln)
    dry_line = lines[dry_idx]
    assert dry_line.startswith(META_INDENT)
    assert not dry_line.startswith("(")
    assert lines[dry_idx - 1] == ""


# The spec-0012 plan_table_flat() byte-equal invariant is already pinned by
# tests/test_plan_presentation.py::test_plan_table_flat_snapshot_unchanged.
# Spec 0014 wraps that table; it does not modify it. We rely on the existing
# test rather than duplicate it at a different width.
