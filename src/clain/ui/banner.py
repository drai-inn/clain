"""First-run ASCII banner and the brand-meter renderer (spec 0016).

The meter and anchor row open every primary render; the banner opens the
user's first-ever `classify` invocation (per-machine state). The banner is a
hand-off — "welcome / here's where to read more" — not a tutorial.

Resolution for whether to show the banner on a given `classify` invocation:

    1. `--no-banner` flag                          → off
    2. `--banner` flag                             → on
    3. (`--banner` and `--no-banner` together)     → CLI error, handled in cli.py
    4. `CLAIN_BANNER=off`                          → off
    5. `CLAIN_BANNER=on`                           → on
    6. `--json` mode                               → off (handled in cli.py)
    7. marker file at $XDG_STATE_HOME/clain/banner-shown:
         exists → off
         absent → on, and create the marker
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text

from clain.config import clain_state_dir
from clain.ui.intent import CommandIdentity
from clain.ui.theme import get_theme

ENV_VAR = "CLAIN_BANNER"

# Five rows; one for each brand-step colour. Width is 38 columns so it sits
# comfortably below 72 (the spec-0014 RULE_WIDTH).
_BANNER_ROWS: tuple[str, ...] = (
    " ██████╗██╗      █████╗ ██╗███╗   ██╗",
    "██╔════╝██║     ██╔══██╗██║████╗  ██║",
    "██║     ██║     ███████║██║██╔██╗ ██║",
    "██║     ██║     ██╔══██║██║██║╚██╗██║",
    "╚██████╗███████╗██║  ██║██║██║ ╚████║",
    " ╚═════╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝",
)

_TAGLINE = "Categorical visibility, deliberate execution."
_REPO_URL = "https://github.com/drai-inn/clain"


class InvalidBannerValue(ValueError):
    """Raised when `CLAIN_BANNER` carries something other than on/off."""


def _normalise(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    v = value.strip().lower()
    if v in ("on", "1", "true", "yes"):
        return True
    if v in ("off", "0", "false", "no"):
        return False
    raise InvalidBannerValue(f"banner value {value!r} is not recognised. Accepted: on, off (case-insensitive).")


def banner_marker_path() -> Path:
    """Per-machine marker. Presence means the banner has been shown before."""
    return clain_state_dir() / "banner-shown"


def should_show_banner(*, flag: bool | None, env: str | None, json_mode: bool) -> bool:
    """Resolve the banner toggle per the precedence above.

    `flag`: True ⇒ force-on, False ⇒ force-off, None ⇒ defer to env/marker.
    `env`: raw $CLAIN_BANNER value (or None).
    `json_mode`: True ⇒ always off (pipelines don't want splash).
    """
    if json_mode:
        return False
    if flag is True:
        return True
    if flag is False:
        return False
    env_resolved = _normalise(env)
    if env_resolved is True:
        return True
    if env_resolved is False:
        return False
    return not banner_marker_path().exists()


def mark_banner_shown() -> None:
    """Create the marker file. Best-effort; permission errors propagate."""
    marker = banner_marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch(exist_ok=True)


def render_banner() -> RenderableType:
    """The full-width ASCII art banner, coloured row-by-row in brand-step gradient."""
    theme = get_theme()
    steps = (
        theme.brand_step1,
        theme.brand_step2,
        theme.brand_step3,
        theme.brand_step4,
        theme.brand_step5,
    )
    items: list[RenderableType] = []
    items.append(Text(""))
    for i, row in enumerate(_BANNER_ROWS):
        colour = steps[min(i, 4)]
        items.append(Padding(Text.from_markup(f"[{colour}]{row}[/]"), (0, 2)))
    items.append(Text(""))
    items.append(Padding(Text.from_markup(f"[{theme.fg}]{_TAGLINE}[/]"), (0, 2)))
    items.append(Padding(Text.from_markup(f"[dim]{_REPO_URL}[/dim]"), (0, 2)))
    items.append(Text(""))
    return Group(*items)


def render_meter(level: int) -> str:
    """Markup for the five-block brand meter at `level` (1..5).

    Returns a Rich markup string (not a Text) so callers can interpolate it
    into a single anchor-row line. Filled blocks use `brand_step{i+1}`;
    outline blocks use `dim`. NO_COLOR strips colour automatically (Rich
    handles that at render time) — the glyphs stay readable.
    """
    theme = get_theme()
    if level < 0 or level > 5:
        raise ValueError(f"meter level out of range: {level} (expected 0..5)")
    steps = (
        theme.brand_step1,
        theme.brand_step2,
        theme.brand_step3,
        theme.brand_step4,
        theme.brand_step5,
    )
    parts: list[str] = []
    for i in range(5):
        if i < level:
            parts.append(f"[{steps[i]}]▰[/]")
        else:
            parts.append(f"[{theme.dim}]▱[/]")
    return "".join(parts)


def anchor_block(identity: CommandIdentity) -> RenderableType:
    """Spec 0016 anchor: meter + clain + emoji + command name, then intent line.

    Returns a Group with the spec-required spacing baked in: blank line above
    the anchor row, blank line between the anchor row and the intent line,
    blank line below the intent line. The caller does not need to pad.
    """
    theme = get_theme()
    meter = render_meter(identity.level)
    anchor = Text.from_markup(f"{meter}  [bold {theme.brand}]clain[/]  {identity.emoji}  [dim]{identity.name}[/dim]")
    intent = Text.from_markup(f"[{theme.fg}]{identity.intent}[/]")
    return Group(
        Text(""),
        Padding(anchor, (0, 2)),
        Text(""),
        Padding(intent, (0, 2)),
        Text(""),
    )


def env_banner_value() -> str | None:
    return os.environ.get(ENV_VAR)
