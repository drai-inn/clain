from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from clain import classify as cls
from clain import plan as planmod
from clain.cli import app
from tests.conftest import (
    make_ambiguous_python_workspace,
    make_ephemeral_workspace,
    make_node_workspace,
    make_pixi_workspace,
    make_uv_workspace,
)

runner = CliRunner()


@pytest.fixture
def classified(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "with-pnpm", lockfile="pnpm-lock.yaml")
    make_node_workspace(root, "without-lock", lockfile=None)
    make_pixi_workspace(root, "with-pixi")
    make_uv_workspace(root, "with-uv")
    make_ambiguous_python_workspace(root, "ambiguous-py")
    make_ephemeral_workspace(root, "build-only")
    return cls.run_classify(root)


def _actions_by_workspace(plan: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [a for a in plan["actions"] if a["workspace"] == name]


def test_recreate_plan_pnpm_safe(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "with-pnpm")
    recreate = next(a for a in actions if a["type"] == "recreate")
    assert recreate["safe_to_execute"] is True
    assert recreate["commands"] == ["pnpm install --frozen-lockfile"]


def test_recreate_plan_pixi_safe(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "with-pixi")
    recreate = next(a for a in actions if a["type"] == "recreate")
    assert recreate["safe_to_execute"] is True
    assert recreate["commands"] == ["pixi install"]


def test_recreate_plan_uv_safe(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "with-uv")
    recreate = next(a for a in actions if a["type"] == "recreate")
    assert recreate["safe_to_execute"] is True
    assert recreate["commands"] == ["uv sync"]


def test_recreate_plan_ambiguous_python_unsafe(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "ambiguous-py")
    recreate = next(a for a in actions if a["type"] == "recreate")
    assert recreate["safe_to_execute"] is False
    assert "ambiguous Python toolchain" in (recreate["unsafe_reason"] or "")


def test_recreate_plan_no_lockfile_unsafe(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "without-lock")
    recreate = next(a for a in actions if a["type"] == "recreate")
    assert recreate["safe_to_execute"] is False
    assert "lockfile" in (recreate["unsafe_reason"] or "")


def test_recreate_plan_ephemeral_has_delete_only(classified: dict[str, Any]) -> None:
    plan = planmod.build_recreate_plan(classified)
    actions = _actions_by_workspace(plan, "build-only")
    assert any(a["type"] == "delete" for a in actions)
    # No recreate action for ephemeral.
    assert not any(a["type"] == "recreate" for a in actions)


def test_move_plan_only_in_sync_workspaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 0013: in_sync_tree is set by autodetect, monkeypatched here.

    Sites under tmp_path are never under a real synced-storage prefix, so we
    flip the detector by path to simulate the synced vs local case.
    """
    synced = tmp_path / "synced"
    synced.mkdir()
    local = tmp_path / "local"
    local.mkdir()
    make_node_workspace(synced, "inside", lockfile="pnpm-lock.yaml")
    make_node_workspace(local, "outside", lockfile="pnpm-lock.yaml")

    def fake_detect(path, **_kw):  # type: ignore[no-untyped-def]
        return ("synced", "Google Drive", str(synced)) if str(path).startswith(str(synced)) else ("local", None, None)

    monkeypatch.setattr("clain.classify.detect_synced_storage", fake_detect)

    classified_synced = cls.run_classify(synced)
    classified_local = cls.run_classify(local)

    plan_inside = planmod.build_move_plan(classified_synced, tmp_path / "dest")
    plan_outside = planmod.build_move_plan(classified_local, tmp_path / "dest")

    assert any(a["workspace"] == "inside" for a in plan_inside["actions"])
    assert not plan_outside["actions"]


def test_move_plan_flags_venv_in_preconditions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Move plan needs the workspace marked synced to include it; monkeypatch detect."""
    synced = tmp_path / "synced"
    synced.mkdir()
    make_uv_workspace(synced, "py-ws")
    monkeypatch.setattr(
        "clain.classify.detect_synced_storage",
        lambda _p, **_kw: ("synced", "Google Drive", str(synced)),
    )
    classified = cls.run_classify(synced)
    plan = planmod.build_move_plan(classified, tmp_path / "dest")
    move_action = next(a for a in plan["actions"] if a["type"] == "move")
    assert any("venv" in pre.lower() and "pyvenv.cfg" in pre.lower() for pre in move_action["preconditions"])


def test_cli_plan_recreate_requires_classify(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plan", "recreate", str(tmp_path / "dev")])
    assert result.exit_code != 0


def test_cli_plan_recreate_persists(tmp_path: Path) -> None:
    """--dry --json: produces JSON output, persists the plan, exits 0."""
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root), "--json"])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry", "--json"])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.stdout)
    assert plan["kind"] == "recreate"
    assert plan["summary"]["action_count"] > 0


def test_cli_plan_recreate_default_attempts_execute_and_is_gated(tmp_path: Path) -> None:
    """Default behaviour (no --dry) attempts execution; the gate must block it
    and point the user at --dry.
    """
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root)])
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "00NN" in combined or "Lift the dry-run gate" in combined
    assert "--dry" in combined


def test_cli_plan_recreate_dry_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    runner.invoke(app, ["classify", str(root)])
    result = runner.invoke(app, ["plan", "recreate", str(root), "--dry"])
    assert result.exit_code == 0, result.output


def test_executor_module_imports_no_banned_modules() -> None:
    """While EXECUTE_ENABLED is False, executor must not import process/network/clipboard modules."""
    src = Path("src/clain/executor.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned_prefixes = {
        "subprocess",
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "pyperclip",
        "shutil",
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in banned_prefixes:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in banned_prefixes:
                found.append(node.module or "")
    assert not found, f"banned imports in executor.py: {found}"
