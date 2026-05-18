"""Tests for spec 0009 — rule-base completeness.

Verifies:
- `.pixi` is cache-managed; the scan stops there, doesn't recurse.
- Bare `venv` is no longer matched as cache-managed; a fixture `venv/` with
  pyvenv.cfg ends up as workspace-source.
- `.git` is pruned during the walk and produces no class tag.
- The prune set in rules.toml is exposed by the loader and refuses overlap
  with class directory_names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clain import classify as cls
from clain.rules_loader import RulesLoadError, load_rules
from tests.conftest import make_pixi_workspace, write_file


@pytest.fixture(autouse=True)
def _clear_loader_cache() -> None:
    load_rules.cache_clear()


def test_default_rules_include_pixi_in_cache_managed() -> None:
    rules = load_rules()
    assert rules.class_of(".pixi") == "cache-managed"


def test_default_rules_drop_bare_venv() -> None:
    rules = load_rules()
    assert rules.class_of("venv") is None
    # .venv (with the dot) stays.
    assert rules.class_of(".venv") == "cache-managed"


def test_default_rules_prune_includes_git_family() -> None:
    rules = load_rules()
    assert ".git" in rules.prune_names
    assert ".hg" in rules.prune_names
    assert ".svn" in rules.prune_names
    assert ".jj" in rules.prune_names


def test_pixi_stops_recursion(tmp_path: Path) -> None:
    """If `.pixi` is recognised as a class, the scan must stop there and
    NOT enumerate the noise of stdlib __pycache__ etc. inside it."""
    root = tmp_path / "dev"
    root.mkdir()
    ws = root / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    deep = ws / ".pixi" / "envs" / "default" / "lib" / "python3.12" / "__pycache__"
    deep.mkdir(parents=True)
    write_file(deep / "marker.pyc", "should not be visited")

    payload = cls.run_classify(root, None)
    ws_payload = payload["workspaces"][0]
    tags = ws_payload["class_tags"]
    # Exactly one .pixi tag, no deep __pycache__ tags.
    pixi_tags = [t for t in tags if t["relative_path"] == ".pixi"]
    deep_tags = [t for t in tags if "__pycache__" in t["relative_path"]]
    assert len(pixi_tags) == 1
    assert pixi_tags[0]["class"] == "cache-managed"
    assert deep_tags == []


def test_git_is_pruned(tmp_path: Path) -> None:
    """`.git/` is pruned during the walk: no class tag, no recursion."""
    root = tmp_path / "dev"
    root.mkdir()
    ws = root / "alpha"
    ws.mkdir()
    write_file(ws / "pixi.toml", '[workspace]\nname="alpha"\n')
    deep_in_git = ws / ".git" / "objects" / "pack" / "deep"
    deep_in_git.mkdir(parents=True)
    write_file(deep_in_git / "marker", "should not be visited")
    # Also plant a class-named dir inside .git that would normally match —
    # the prune should prevent us from ever seeing it.
    inside_git = ws / ".git" / "node_modules"
    inside_git.mkdir(parents=True)

    payload = cls.run_classify(root, None)
    tags = payload["workspaces"][0]["class_tags"]
    paths = [t["relative_path"] for t in tags]
    assert all(".git" not in p for p in paths), f"`.git` leaked into class_tags: {paths}"


def test_bare_venv_with_pyvenv_cfg_is_workspace_source(tmp_path: Path) -> None:
    """Spec 0009 trade-off: a real venv/ with pyvenv.cfg is no longer detected
    as cache-managed. It classifies as workspace-source (i.e., produces no
    class tag pointing at the venv dir itself).
    """
    root = tmp_path / "dev"
    root.mkdir()
    ws = root / "ambiguous"
    ws.mkdir()
    write_file(ws / "pyproject.toml", '[project]\nname="ambiguous"\n')
    venv = ws / "venv"
    venv.mkdir()
    write_file(venv / "pyvenv.cfg", "home = /usr/local/bin\n")
    venv_lib = venv / "lib" / "python3.12" / "site-packages"
    venv_lib.mkdir(parents=True)

    payload = cls.run_classify(root, None)
    tags = payload["workspaces"][0]["class_tags"]
    # No tag for bare "venv" itself. (site-packages inside it WILL match because
    # site-packages is still in the class list — but the bare venv directory
    # name is no longer a match.)
    rels = [t["relative_path"] for t in tags]
    assert "venv" not in rels


def test_pixi_class_against_real_pixi_workspace(tmp_path: Path) -> None:
    """Combined check: a pixi workspace with .pixi/.../site-packages/.../__pycache__
    produces only the .pixi tag at top level — no deep noise."""
    root = tmp_path / "dev"
    root.mkdir()
    ws = make_pixi_workspace(root, "beta-pixi")
    # Plant a stdlib-style nested cache to simulate Pixi env contents.
    deep = ws / ".pixi" / "envs" / "default" / "lib" / "python3.12" / "venv"
    deep.mkdir(parents=True)
    write_file(deep / "__init__.py", "# stdlib venv module")

    payload = cls.run_classify(root, None)
    tags = payload["workspaces"][0]["class_tags"]
    rels = [t["relative_path"] for t in tags]
    # .pixi caught at top level; nothing inside it surfaces.
    assert ".pixi" in rels
    assert not any(r.startswith(".pixi/") for r in rels)


def test_loader_rejects_prune_overlap_with_class(tmp_path: Path) -> None:
    """Spec 0009: prune names must not overlap with class directory_names."""
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
        schema = 1

        [[classes]]
        name = "cache-managed"
        description = "x"
        default_action = "delete-and-recreate"
        directory_names = ["node_modules"]

        [prune]
        names = ["node_modules"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(RulesLoadError, match="overlap"):
        load_rules(bad)


def test_loader_rejects_prune_names_not_strings(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
        schema = 1

        [[classes]]
        name = "ephemeral"
        description = "x"
        default_action = "delete"
        directory_names = ["dist"]

        [prune]
        names = ["good", 42]
        """,
        encoding="utf-8",
    )
    with pytest.raises(RulesLoadError, match="strings"):
        load_rules(bad)
