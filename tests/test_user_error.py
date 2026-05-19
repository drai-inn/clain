"""Spec 0015 — error-template helper + docs hygiene + console-script entry."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import re
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from clain.cli import app
from clain.ui.errors import user_error

REPO_ROOT = Path(__file__).resolve().parents[1]

runner = CliRunner()


def _render(markup: str) -> str:
    """Render Rich markup to plain text (style codes stripped)."""
    buf = Console(record=True, width=120, force_terminal=False)
    buf.print(markup)
    return buf.export_text(clear=False)


def test_user_error_template_shape() -> None:
    text = _render(user_error("X-headline", "Y-because", "Z-fix"))
    # Order is what / why / fix.
    i_what = text.find("X-headline")
    i_why = text.find("Y-because")
    i_fix = text.find("Z-fix")
    assert -1 < i_what < i_why < i_fix, text

    # Fix line is on its own indented line, prefixed by "To proceed:".
    fix_line = next(line for line in text.splitlines() if "Z-fix" in line)
    assert fix_line.startswith("  "), repr(fix_line)
    assert "To proceed:" in fix_line


def test_user_error_no_why_omits_middle_line() -> None:
    text = _render(user_error("X-headline", None, "Z-fix"))
    # No spurious middle content; the rendered output has just the headline
    # block and the fix line (plus a blank separator).
    assert "X-headline" in text
    assert "Z-fix" in text
    # Between the headline and the fix line, there should be exactly the
    # blank-separator line — no orphan "None" or stray content.
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2, lines
    assert "X-headline" in lines[0]
    assert "Z-fix" in lines[1]


def test_user_error_markup_parses_cleanly() -> None:
    # Render should not leave any unrendered "[red]" / "[/red]" markup behind.
    text = _render(user_error("X", "Y", "Z"))
    assert "[red]" not in text
    assert "[/red]" not in text
    assert "[bold]" not in text
    assert "[cyan]" not in text


def test_console_script_entry_resolves() -> None:
    """The packaged `clain` console script must resolve to clain.cli:app.

    Guards against a refactor that breaks the documented global install path
    (pipx / pixi global install) silently.
    """
    entries = importlib_metadata.entry_points(group="console_scripts")
    matches = [ep for ep in entries if ep.name == "clain"]
    assert matches, "no `clain` console_scripts entry found"
    ep = matches[0]
    assert ep.value.replace(" ", "") == "clain.cli:app", ep.value


def test_classify_no_root_error_includes_export_hint() -> None:
    """Spec 0015: CLAIN_DEV_ROOT unset error must show the export line."""
    result = runner.invoke(app, ["classify"])
    assert result.exit_code != 0
    assert "CLAIN_DEV_ROOT" in result.output
    assert "export" in result.output
    # --here is the documented alternative; the error must mention it.
    assert "--here" in result.output


def test_classify_bad_root_error_mentions_here_flag(tmp_path: Path) -> None:
    """A non-existent / non-directory root error must suggest --here."""
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["classify", str(missing)])
    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert "--here" in result.output

    # And the not-a-directory branch.
    file_path = tmp_path / "i-am-a-file"
    file_path.write_text("hi")
    result = runner.invoke(app, ["classify", str(file_path)])
    assert result.exit_code != 0
    assert "file, not a directory" in result.output
    assert "--here" in result.output


def test_plan_no_cache_error_mentions_classify_command(tmp_path: Path) -> None:
    """plan recreate with no cache must suggest `clain classify`."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    result = runner.invoke(app, ["plan", "recreate", "--here", str(ws), "--dry"])
    assert result.exit_code != 0
    assert "No classify cache" in result.output
    assert "clain classify" in result.output


# Sentinel-block convention for contributor-only Markdown blocks.
_OPEN = re.compile(r"<!--\s*contributor-only\s*-->")
_CLOSE = re.compile(r"<!--\s*/contributor-only\s*-->")


def _strip_contributor_blocks(text: str) -> str:
    """Return text with every <!-- contributor-only --> ... <!-- /contributor-only -->
    block (inclusive) replaced by blank lines, so we can grep the *end-user* portion.
    """
    out: list[str] = []
    in_block = False
    for line in text.splitlines():
        if not in_block and _OPEN.search(line):
            in_block = True
            out.append("")
            continue
        if in_block:
            out.append("")
            if _CLOSE.search(line):
                in_block = False
            continue
        out.append(line)
    return "\n".join(out)


def test_no_pixi_run_in_user_facing_docs() -> None:
    """`pixi run clain` is contributor surface, not end-user surface.

    Spec 0015 part A: docs that target end users must invoke the bare
    `clain` binary. `pixi run clain` is allowed only inside explicitly
    marked `<!-- contributor-only -->` sentinel blocks.
    """
    for rel in ("README.md", "docs/USAGE.md", "AGENTS.md"):
        path = REPO_ROOT / rel
        cleaned = _strip_contributor_blocks(path.read_text(encoding="utf-8"))
        assert "pixi run clain" not in cleaned, (
            f"{rel}: `pixi run clain` appears outside a "
            "`<!-- contributor-only -->` block (end users install via pipx / "
            "pixi global and invoke the bare `clain` binary)."
        )
