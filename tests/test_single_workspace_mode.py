"""Tests for spec 0010 — single-workspace mode.

Verifies:
- `clain classify --here` returns exactly one workspace.
- `cwd` is used when no path is given to `--here`.
- `scan.mode == "single"` in JSON.
- The Tree renderer is invoked instead of the multi-row table.
- Tree-mode behaviour is unchanged.
- `--here` and `--workspace` together is a CLI error.
- A fixture mirroring `clain-me`'s structure produces a clean tree with `.pixi`
  cache-managed and the three tool caches as bytecode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clain import classify as cls
from clain.cli import app
from tests.conftest import make_pixi_workspace, make_uv_workspace, write_file

runner = CliRunner()


def test_classify_single_workspace_basic(tmp_path: Path) -> None:
    """`classify --here PATH` returns one workspace."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    (ws / ".pixi").mkdir()

    result = runner.invoke(app, ["classify", str(ws), "--here", "--json", "--no-cache"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["name"] == "alpha"
    assert payload["scan"]["mode"] == "single"


def test_classify_single_workspace_uses_cwd_when_no_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "beta"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="beta"\n')
    monkeypatch.chdir(ws)

    result = runner.invoke(app, ["classify", "--here", "--json", "--no-cache"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["workspaces"][0]["name"] == "beta"


def test_classify_tree_mode_unchanged(tmp_path: Path) -> None:
    """Without `--here`, behaviour is the existing tree mode."""
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "one")
    make_uv_workspace(root, "two")

    result = runner.invoke(app, ["classify", str(root), "--json", "--no-cache"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["workspaces"]) == 2
    assert payload["scan"]["mode"] == "tree"


def test_classify_here_and_workspace_are_mutex(tmp_path: Path) -> None:
    """`--here` and `--workspace NAME` together is a CLI error."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')

    result = runner.invoke(app, ["classify", str(ws), "--here", "--workspace", "alpha"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_classify_here_renders_tree(tmp_path: Path) -> None:
    """Rendered output uses the Tree renderer, not the multi-row classify table."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    (ws / ".pixi").mkdir()
    (ws / ".mypy_cache").mkdir()

    result = runner.invoke(app, ["classify", str(ws), "--here", "--no-cache"])
    assert result.exit_code == 0, result.output
    # Tree renderer marker: "Manifests:" appears as a tree branch text.
    assert "Manifests:" in result.output
    # The multi-row classify table is NOT used.
    assert "Workspace classification" not in result.output


def test_classify_here_on_clain_me_fixture(tmp_path: Path) -> None:
    """Spec 0010 acceptance: a fixture mirroring clain-me's structure produces
    a clean tree with .pixi cache-managed and the tool caches as bytecode.
    No `docs/`/`tests/` false positives.
    """
    ws = tmp_path / "clain-me"
    ws.mkdir()
    # Manifests
    write_file(ws / "pyproject.toml", '[project]\nname="clain"\nversion="0.0.1"\n')
    write_file(ws / "pixi.toml", '[workspace]\nname="clain"\n')
    # Cache-managed
    (ws / ".pixi").mkdir()
    # Bytecode caches
    (ws / ".mypy_cache").mkdir()
    (ws / ".pytest_cache").mkdir()
    (ws / ".ruff_cache").mkdir()
    src = ws / "src" / "clain"
    src.mkdir(parents=True)
    write_file(src / "__init__.py", "")
    (src / "__pycache__").mkdir()
    tests = ws / "tests"
    tests.mkdir()
    write_file(tests / "test_x.py", "")
    (tests / "__pycache__").mkdir()
    # Non-class subdirs (these must NOT appear as separate workspaces).
    (ws / "docs").mkdir()
    (ws / "examples").mkdir()
    (ws / "specs").mkdir()

    result = runner.invoke(app, ["classify", str(ws), "--here", "--json", "--no-cache"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(payload["workspaces"]) == 1
    ws_payload = payload["workspaces"][0]
    assert ws_payload["name"] == "clain-me"
    assert "pyproject.toml" in ws_payload["manifests"]
    assert "pixi.toml" in ws_payload["manifests"]

    tags = {(t["class"], t["relative_path"]) for t in ws_payload["class_tags"]}
    assert ("cache-managed", ".pixi") in tags
    assert ("bytecode", ".mypy_cache") in tags
    assert ("bytecode", ".pytest_cache") in tags
    assert ("bytecode", ".ruff_cache") in tags
    assert ("bytecode", "src/clain/__pycache__") in tags
    assert ("bytecode", "tests/__pycache__") in tags
    # docs/, examples/, specs/ must NOT appear as workspaces (single mode) or class tags.
    rels = [t["relative_path"] for t in ws_payload["class_tags"]]
    assert not any(r.startswith("docs") for r in rels)
    assert not any(r.startswith("examples") for r in rels)
    assert not any(r.startswith("specs") for r in rels)


def test_plan_recreate_here_consumes_single_workspace_cache(tmp_path: Path) -> None:
    """`plan recreate --here` uses the single-workspace cache and produces a plan
    with exactly one workspace's actions."""
    ws = tmp_path / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    (ws / ".pixi").mkdir()

    # First classify with --here so the cache exists.
    classify_result = runner.invoke(app, ["classify", str(ws), "--here", "--json"])
    assert classify_result.exit_code == 0

    # Now plan recreate --here against the same path.
    plan_result = runner.invoke(app, ["plan", "recreate", str(ws), "--here", "--dry", "--json"])
    assert plan_result.exit_code == 0, plan_result.output
    plan = json.loads(plan_result.stdout)
    workspaces_in_plan = {a["workspace"] for a in plan["actions"]}
    assert workspaces_in_plan == {"alpha"}
    recreate_actions = [a for a in plan["actions"] if a["type"] == "recreate"]
    assert recreate_actions, "expected at least one recreate action"
    assert recreate_actions[0]["commands"] == ["pixi install"]


def test_run_classify_single_mode_directly(tmp_path: Path) -> None:
    """Direct API call: run_classify(single=True) returns one workspace and mode='single'."""
    ws = tmp_path / "solo"
    ws.mkdir()
    write_file(ws / "pyproject.toml", '[project]\nname="solo"\nversion="0.0.1"\n')
    (ws / ".pixi").mkdir()

    payload = cls.run_classify(ws, None, single=True)
    assert payload["scan"]["mode"] == "single"
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["name"] == "solo"


def test_run_classify_default_mode_remains_tree(tmp_path: Path) -> None:
    """The default of run_classify is tree mode; the field is now explicit."""
    root = tmp_path / "dev"
    root.mkdir()
    make_pixi_workspace(root, "alpha")

    payload = cls.run_classify(root, None)
    assert payload["scan"]["mode"] == "tree"
