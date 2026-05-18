from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from clain import classify as cls
from clain.cli import app
from clain.state import classify_cache_path
from tests.conftest import (
    make_ephemeral_workspace,
    make_node_workspace,
    make_pixi_workspace,
    make_uv_workspace,
    write_file,
)

runner = CliRunner()


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha-node", lockfile="pnpm-lock.yaml")
    make_pixi_workspace(root, "beta-pixi")
    make_uv_workspace(root, "gamma-uv")
    make_ephemeral_workspace(root, "delta-build")
    return root


def test_classify_finds_all_four_classes(fake_root: Path) -> None:
    payload = cls.run_classify(fake_root, fake_root)
    workspaces = {w["name"]: w for w in payload["workspaces"]}

    alpha_tags = {(t["class"], t["relative_path"]) for t in workspaces["alpha-node"]["class_tags"]}
    assert ("cache-managed", "node_modules") in alpha_tags

    beta_tags = {(t["class"], t["relative_path"]) for t in workspaces["beta-pixi"]["class_tags"]}
    assert any(rel == ".venv" for _, rel in beta_tags)

    delta_tags = {(t["class"], t["relative_path"]) for t in workspaces["delta-build"]["class_tags"]}
    assert ("ephemeral", "dist") in delta_tags


def test_classify_records_manifests_at_workspace_root(fake_root: Path) -> None:
    payload = cls.run_classify(fake_root, fake_root)
    workspaces = {w["name"]: w for w in payload["workspaces"]}
    assert "pnpm-lock.yaml" in workspaces["alpha-node"]["manifests"]
    assert "pixi.toml" in workspaces["beta-pixi"]["manifests"]
    assert "uv.lock" in workspaces["gamma-uv"]["manifests"]


def test_classify_in_sync_tree_flag(tmp_path: Path) -> None:
    synced = tmp_path / "synced-root"
    synced.mkdir()
    local = tmp_path / "local-dev"
    local.mkdir()
    make_node_workspace(synced, "inside", lockfile="pnpm-lock.yaml")
    make_node_workspace(local, "outside", lockfile="pnpm-lock.yaml")

    payload_synced = cls.run_classify(synced, synced)
    assert payload_synced["workspaces"][0]["in_sync_tree"] is True

    payload_local = cls.run_classify(local, synced)
    assert payload_local["workspaces"][0]["in_sync_tree"] is False


def test_classify_in_sync_tree_is_null_when_synced_root_unset(tmp_path: Path) -> None:
    """Spec 0009: synced_root=None ⇒ in_sync_tree is None (unknown)."""
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    payload = cls.run_classify(root, None)
    assert payload["workspaces"][0]["in_sync_tree"] is None
    assert payload["scan"]["synced_root"] is None


def test_classify_prunes_class_dirs(tmp_path: Path) -> None:
    """The class directories must not be recursed into."""
    root = tmp_path / "dev"
    root.mkdir()
    ws = make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    # Plant a marker deep inside node_modules — classify must not see it.
    deep = ws / "node_modules" / "lodash" / "deep" / "deeper"
    deep.mkdir(parents=True)
    write_file(deep / "marker.txt", "should not be visited")

    payload = cls.run_classify(root, root)
    tags = [t["relative_path"] for t in payload["workspaces"][0]["class_tags"]]
    # Only the top-level node_modules should be tagged; no recursion into it.
    assert tags == ["node_modules"]


def test_classify_cli_requires_root(tmp_path: Path) -> None:
    result = runner.invoke(app, ["classify"])
    assert result.exit_code != 0
    assert "CLAIN_DEV_ROOT" in result.output or "dev root" in result.output.lower()


def test_classify_cli_json(fake_root: Path) -> None:
    result = runner.invoke(app, ["classify", str(fake_root), "--json", "--no-cache"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema"] == 1
    assert len(payload["workspaces"]) == 4


def test_classify_cli_caches_to_xdg_state(fake_root: Path) -> None:
    result = runner.invoke(app, ["classify", str(fake_root), "--json"])
    assert result.exit_code == 0
    assert classify_cache_path(fake_root.resolve()).exists()


def test_classify_cli_workspace_drilldown(fake_root: Path) -> None:
    runner.invoke(app, ["classify", str(fake_root), "--no-cache"])
    result = runner.invoke(app, ["classify", str(fake_root), "--workspace", "beta-pixi"])
    assert result.exit_code == 0
    assert "beta-pixi" in result.output


def test_no_personal_info_in_config_defaults() -> None:
    """Spec 0004 acceptance: no email, hostname, or personal home path in defaults."""
    cfg_src = Path("src/clain/config.py").read_text(encoding="utf-8")
    tree = ast.parse(cfg_src)
    forbidden_substrings = (
        "GoogleDrive-",  # Google Drive folder format embeds the email
        "@",  # email addresses (broad)
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for needle in forbidden_substrings:
                assert needle not in node.value, (
                    f"Personal-info leak in config.py constant: {node.value!r} contains {needle!r}"
                )


def test_classify_module_does_not_modify_root(fake_root: Path) -> None:
    def tree_signature(p: Path) -> str:
        h = hashlib.sha256()
        for path in sorted(p.rglob("*")):
            rel = path.relative_to(p)
            st = path.lstat()
            h.update(str(rel).encode())
            h.update(str(st.st_size).encode())
            h.update(str(st.st_mode).encode())
        return h.hexdigest()

    before = tree_signature(fake_root)
    cls.run_classify(fake_root, fake_root)
    after = tree_signature(fake_root)
    assert before == after
