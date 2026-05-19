"""Templated user-facing error messages.

Spec 0015 codifies the `what / why / fix` shape already used by the
spec-0013 `CLAIN_SYNCED_ROOT` hard-error: every error tells the user
what's wrong, why, and the literal command or change to fix it.

The helper returns a Rich-markup string. Callers print to `err_console`
and raise `typer.Exit(code=2)` themselves — keeping the helper pure makes
it trivially unit-testable.

Spec 0017: colour is sourced from theme tokens — `theme.unsafe` for the
headline, `theme.fix` for the literal-command-to-fix line. No raw Rich
colour names appear here.
"""

from __future__ import annotations

from clain.ui.theme import get_theme


def user_error(what: str, why: str | None, fix: str) -> str:
    """Build a templated error message in the spec-0015 shape.

    Args:
      what: One-sentence statement of what's wrong (the headline).
      why:  Optional second-sentence explanation. Pass `None` to omit
            the middle line entirely.
      fix:  Literal command or change the user should run/make.
            Rendered on its own indented line in `theme.fix`.

    Returns:
      A Rich-markup string. The caller is responsible for printing it
      and exiting:

          err_console.print(user_error("...", "...", "..."))
          raise typer.Exit(code=2)
    """
    theme = get_theme()
    lines: list[str] = [f"[{theme.unsafe}]Error:[/] [bold]{what}[/bold]"]
    if why is not None:
        lines.append(why)
    lines.append("")
    lines.append(f"  [dim]To proceed:[/dim] [{theme.fix}]{fix}[/]")
    return "\n".join(lines)
