from typer.testing import CliRunner

from clain import __version__
from clain.cli import app

runner = CliRunner()


def test_version_flag_exits_zero_and_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"clain {__version__}" in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # Typer exits non-zero when showing help via no_args_is_help.
    assert "Usage" in result.output


def test_classify_help_lists_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "classify" in result.output
    assert "plan" in result.output
