from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect XDG_STATE_HOME so tests never write to the real ~/.local/state."""
    state = tmp_path / "xdg-state"
    state.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.delenv("CLAIN_DEV_ROOT", raising=False)
    monkeypatch.delenv("CLAIN_SYNCED_ROOT", raising=False)
    yield state


def write_file(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_node_workspace(root: Path, name: str, *, lockfile: str | None = None) -> Path:
    """Build a fake Node workspace with manifest + lockfile + a node_modules dir."""
    ws = root / name
    ws.mkdir(parents=True)
    write_file(ws / "package.json", f'{{"name":"{name}","version":"1.0.0"}}')
    if lockfile is not None:
        write_file(ws / lockfile, "{}\n")
    nm = ws / "node_modules" / "lodash"
    nm.mkdir(parents=True)
    write_file(nm / "package.json", '{"name":"lodash","version":"4.17.0"}')
    return ws


def make_pixi_workspace(root: Path, name: str) -> Path:
    ws = root / name
    ws.mkdir(parents=True)
    write_file(ws / "pixi.toml", '[workspace]\nname="' + name + '"\n')
    venv = ws / ".venv" / "lib" / "python3.12" / "site-packages"
    venv.mkdir(parents=True)
    write_file(venv / "marker", "x")
    return ws


def make_uv_workspace(root: Path, name: str) -> Path:
    ws = root / name
    ws.mkdir(parents=True)
    write_file(ws / "pyproject.toml", '[project]\nname="' + name + '"\n')
    write_file(ws / "uv.lock", "version = 1\n")
    venv = ws / ".venv" / "lib" / "python3.12" / "site-packages"
    venv.mkdir(parents=True)
    write_file(venv / "marker", "x")
    return ws


def make_ephemeral_workspace(root: Path, name: str) -> Path:
    """Workspace with a build dir but no recognised manifest."""
    ws = root / name
    ws.mkdir(parents=True)
    dist = ws / "dist"
    dist.mkdir()
    write_file(dist / "bundle.js", "x" * 100)
    return ws


def make_ambiguous_python_workspace(root: Path, name: str) -> Path:
    """pyproject.toml but no pixi/uv/poetry lockfile — should be unsafe."""
    ws = root / name
    ws.mkdir(parents=True)
    write_file(ws / "pyproject.toml", '[project]\nname="' + name + '"\n')
    venv = ws / ".venv" / "lib" / "python3.12" / "site-packages"
    venv.mkdir(parents=True)
    write_file(venv / "marker", "x")
    return ws
