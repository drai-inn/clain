"""Spec 0017 — Tokyo Night theme + resolution + renderer migration."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from clain import classify as cls
from clain.cli import app
from clain.ui.theme import (
    THEME_TOKENS,
    TOKYO_NIGHT_DARK,
    TOKYO_NIGHT_LIGHT,
    InvalidThemeValue,
    Theme,
    get_theme,
    resolve_theme,
    set_theme,
)
from tests.conftest import make_pixi_workspace

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# The token surface.
# ---------------------------------------------------------------------------


def test_theme_token_set_complete() -> None:
    """Both theme instances populate every field on `Theme`."""
    expected = {f.name for f in fields(Theme)}
    for theme in (TOKYO_NIGHT_DARK, TOKYO_NIGHT_LIGHT):
        actual = {f.name for f in fields(theme)}
        assert actual == expected
        for name in expected:
            value = getattr(theme, name)
            assert isinstance(value, str) and value.startswith("#") and len(value) == 7, (
                f"{theme!r}.{name} = {value!r} is not a 7-char hex string"
            )
    # Sanity check: THEME_TOKENS reflects the dataclass.
    assert set(THEME_TOKENS) == expected


# ---------------------------------------------------------------------------
# resolve_theme — precedence and detection.
# ---------------------------------------------------------------------------


def test_no_color_returns_none() -> None:
    assert resolve_theme(flag=None, env=None, colorfgbg=None, no_color=True) is None


def test_explicit_flag_overrides_env_and_detection() -> None:
    # flag=dark beats env=light beats colorfgbg=light-bg.
    out = resolve_theme(flag="dark", env="light", colorfgbg="0;15", no_color=False)
    assert out is TOKYO_NIGHT_DARK
    out = resolve_theme(flag="light", env="dark", colorfgbg="15;0", no_color=False)
    assert out is TOKYO_NIGHT_LIGHT


def test_env_overrides_detection_when_no_flag() -> None:
    out = resolve_theme(flag=None, env="light", colorfgbg="0;0", no_color=False)
    assert out is TOKYO_NIGHT_LIGHT
    out = resolve_theme(flag=None, env="dark", colorfgbg="15;15", no_color=False)
    assert out is TOKYO_NIGHT_DARK


def test_colorfgbg_dark_detection() -> None:
    out = resolve_theme(flag=None, env=None, colorfgbg="15;0", no_color=False)
    assert out is TOKYO_NIGHT_DARK


def test_colorfgbg_light_detection() -> None:
    out = resolve_theme(flag=None, env=None, colorfgbg="0;15", no_color=False)
    assert out is TOKYO_NIGHT_LIGHT


def test_colorfgbg_three_segment_form() -> None:
    """Some terminals report `fg;ig;bg` (three segments)."""
    out = resolve_theme(flag=None, env=None, colorfgbg="0;15;15", no_color=False)
    assert out is TOKYO_NIGHT_LIGHT
    out = resolve_theme(flag=None, env=None, colorfgbg="15;7;0", no_color=False)
    assert out is TOKYO_NIGHT_DARK


def test_colorfgbg_unparseable_falls_back_to_dark() -> None:
    out = resolve_theme(flag=None, env=None, colorfgbg="garbage", no_color=False)
    assert out is TOKYO_NIGHT_DARK


def test_default_when_nothing_set() -> None:
    out = resolve_theme(flag=None, env=None, colorfgbg=None, no_color=False)
    assert out is TOKYO_NIGHT_DARK


def test_auto_flag_falls_through_to_detection() -> None:
    out = resolve_theme(flag="auto", env=None, colorfgbg="0;15", no_color=False)
    assert out is TOKYO_NIGHT_LIGHT
    out = resolve_theme(flag="auto", env="light", colorfgbg=None, no_color=False)
    # auto flag does NOT consult env — it explicitly opts into detection.
    # With no detection signal, fall back to dark.
    assert out is TOKYO_NIGHT_DARK


def test_unknown_theme_value_raises() -> None:
    with pytest.raises(InvalidThemeValue):
        resolve_theme(flag="blue", env=None, colorfgbg=None, no_color=False)
    with pytest.raises(InvalidThemeValue):
        resolve_theme(flag=None, env="midnight", colorfgbg=None, no_color=False)


def test_case_insensitive_theme_values() -> None:
    assert resolve_theme(flag="DARK", env=None, colorfgbg=None, no_color=False) is TOKYO_NIGHT_DARK
    assert resolve_theme(flag=None, env="Light", colorfgbg=None, no_color=False) is TOKYO_NIGHT_LIGHT


# ---------------------------------------------------------------------------
# Renderer migration: grep + integration.
# ---------------------------------------------------------------------------

# Match Rich colour-name markup like `[red]`, `[bold red]`, `[bold red on yellow]`.
_RAW_COLOUR_NAMES = ("red", "green", "yellow", "cyan", "magenta", "blue")
_MARKUP_TAG = re.compile(r"\[([^\[\]]+?)\]")


def _runtime_strings(source: str) -> list[tuple[int, str]]:
    """Return (lineno, contents) for every non-docstring string literal in source.

    Uses `ast` to walk the module: any `Constant(str)` inside a function /
    method / class body counts as runtime; bare module-level / function-level
    docstrings are excluded.
    """
    import ast

    tree = ast.parse(source)
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_nodes.add(id(body[0].value))

    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_nodes:
            out.append((node.lineno, node.value))
    return out


def test_no_raw_color_names_in_renderers() -> None:
    """Every renderer module migrates raw colour names to theme tokens.

    Spec 0017 acceptance criterion. The grep scope is `src/clain/ui/*.py`
    minus `theme.py` itself (the palette definitions live there). Module-level
    docstrings and comments are excluded — only runtime string literals are
    inspected. Style modifiers like `bold`, `dim`, `italic` are not colour
    names; they may appear raw.
    """
    ui_dir = REPO_ROOT / "src" / "clain" / "ui"
    offenders: list[str] = []
    for path in sorted(ui_dir.glob("*.py")):
        if path.name == "theme.py":
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, literal in _runtime_strings(text):
            for match in _MARKUP_TAG.finditer(literal):
                inner = match.group(1)
                tokens = inner.replace(" on ", " ").split()
                for tok in tokens:
                    if tok in _RAW_COLOUR_NAMES:
                        offenders.append(f"{path.name}:{lineno}: [{inner}]")
    assert not offenders, (
        "Raw Rich colour names found in renderer modules — migrate to theme tokens:\n  " + "\n  ".join(offenders)
    )


def test_renderer_uses_theme_tokens_e2e(tmp_path: Path) -> None:
    """A classify render under TOKYO_NIGHT_DARK contains the Tokyo Night hexes.

    Captures with a forced terminal so Rich emits ANSI; assert at least one of
    the dark-palette hexes resolves through to the styled output.
    """
    # Force the active theme to dark.
    set_theme(TOKYO_NIGHT_DARK)
    assert get_theme() is TOKYO_NIGHT_DARK

    root = tmp_path / "ws"
    root.mkdir()
    make_pixi_workspace(root, "demo")
    payload = cls.run_classify(root, single=True)

    from clain.ui.tables import classify_here_view

    view = classify_here_view(payload["workspaces"][0], payload, legend=True)
    console = Console(
        record=True,
        width=120,
        force_terminal=True,
        color_system="truecolor",
        no_color=False,
    )
    console.print(view)
    raw = console.export_text(clear=False, styles=True)
    # The brand colour (`#bb9af7`) renders to its truecolor ANSI; assert the
    # hex's RGB components appear in the ANSI escape sequence (187;154;247).
    assert "187;154;247" in raw, raw[:1000]


# ---------------------------------------------------------------------------
# CLI integration: --theme flag wiring.
# ---------------------------------------------------------------------------


def test_cli_theme_unknown_value_errors() -> None:
    result = runner.invoke(app, ["--theme", "midnight", "classify", "--here", "."])
    assert result.exit_code != 0
    assert "dark" in result.output and "light" in result.output and "auto" in result.output


def test_cli_theme_env_unknown_value_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAIN_THEME", "midnight")
    result = runner.invoke(app, ["classify", "--here", str(tmp_path)])
    assert result.exit_code != 0
    assert "dark" in result.output and "light" in result.output and "auto" in result.output


def test_cli_theme_dark_works(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    make_pixi_workspace(ws, "demo")
    result = runner.invoke(app, ["--theme", "dark", "classify", "--here", str(ws), "--no-cache"])
    assert result.exit_code == 0, result.output


def test_cli_theme_light_works(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    make_pixi_workspace(ws, "demo")
    result = runner.invoke(app, ["--theme", "light", "classify", "--here", str(ws), "--no-cache"])
    assert result.exit_code == 0, result.output


@pytest.mark.skip(reason="manual-only: needs a real TTY for OSC 11 query")
def test_osc11_query_with_real_terminal() -> None:
    """Smoke test for the OSC 11 detector. Run manually in an interactive shell.

    From a clain checkout:
        pixi run -e dev pytest tests/test_theme.py::test_osc11_query_with_real_terminal -s
    """
    from clain.ui.theme import _detect_from_osc11

    out = _detect_from_osc11()
    # Either resolves to dark/light, or returns None if the terminal doesn't
    # respond. All three are acceptable outcomes for this smoke test.
    assert out in (None, "dark", "light")
