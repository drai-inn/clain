"""Tests for spec 0013 legend-toggle resolution.

Covers:
- Precedence: explicit flag > env var > mode default.
- CLAIN_LEGEND accepted vocabulary (case-insensitive).
- Unknown values raise InvalidLegendValue.
- Empty / unset env falls through to default.
- CLI mutex: --legend and --no-legend together is an error.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from clain.cli import app
from clain.ui.legend import InvalidLegendValue, parse_env, should_show_legend
from tests.conftest import make_node_workspace

runner = CliRunner()


# --- parse_env --------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("on", True),
        ("ON", True),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("YES", True),
        ("off", False),
        ("OFF", False),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("NO", False),
    ],
)
def test_parse_env_accepts_documented_vocabulary(value: str, expected: bool) -> None:
    assert parse_env(value) is expected


@pytest.mark.parametrize("value", [None, ""])
def test_parse_env_unset_or_empty_returns_none(value: str | None) -> None:
    assert parse_env(value) is None


@pytest.mark.parametrize("value", ["maybe", "kinda", "2", "T", "F"])
def test_parse_env_rejects_unknown_values(value: str) -> None:
    with pytest.raises(InvalidLegendValue):
        parse_env(value)


# --- should_show_legend precedence -------------------------------------------------


def test_explicit_flag_beats_env_and_default() -> None:
    # flag=True overrides env=off and any default
    assert should_show_legend(here=False, flag=True, env="off") is True
    # flag=False overrides env=on and any default
    assert should_show_legend(here=True, flag=False, env="on") is False


def test_env_beats_default_when_no_flag() -> None:
    # No flag, env=on, default would be off → on
    assert should_show_legend(here=False, flag=None, env="on") is True
    # No flag, env=off, default would be on → off
    assert should_show_legend(here=True, flag=None, env="off") is False


def test_mode_default_when_no_flag_no_env() -> None:
    # --here → on
    assert should_show_legend(here=True, flag=None, env=None) is True
    # tree mode → off
    assert should_show_legend(here=False, flag=None, env=None) is False


# --- CLI flag mutex ----------------------------------------------------------------


def test_cli_legend_and_no_legend_are_mutex(tmp_path) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    result = runner.invoke(app, ["classify", str(root), "--legend", "--no-legend"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_cli_legend_resolves_env_invalid_value(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An unknown CLAIN_LEGEND value surfaces the parse error at CLI invocation time."""
    monkeypatch.setenv("CLAIN_LEGEND", "maybe")
    root = tmp_path / "dev"
    root.mkdir()
    make_node_workspace(root, "alpha", lockfile="pnpm-lock.yaml")
    result = runner.invoke(app, ["classify", str(root)])
    assert result.exit_code != 0
    assert "CLAIN_LEGEND" in result.output
    assert "not a recognised value" in result.output.lower() or "accepted" in result.output.lower()
