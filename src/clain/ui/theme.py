"""Tokyo Night theme — dark + light — with terminal-background detection.

Spec 0017. The palette is expressed as named tokens on a `Theme` dataclass;
renderers never name a Rich colour directly. Two `Theme` instances ship —
`TOKYO_NIGHT_DARK` and `TOKYO_NIGHT_LIGHT` — both lifted from the upstream
tokyonight palette files.

Resolution precedence (cli.py wires this in its `@app.callback()`):

    1. `NO_COLOR` env var set      → no colour (returns None)
    2. Explicit `--theme dark|light`
    3. `--theme auto`              → fall through to detection
    4. `CLAIN_THEME=dark|light`    → explicit override
    5. `CLAIN_THEME=auto` or unset → detection:
        a. `COLORFGBG` env var (`fg;bg` or `fg;ig;bg`)
        b. OSC 11 query against the terminal (best-effort, 50 ms timeout)
        c. fallback → dark

Unknown explicit values raise `InvalidThemeValue`. The CLI surfaces that as
a user_error with the accepted vocabulary.

The module exposes `get_theme()` / `set_theme()` as a process-wide singleton.
Renderers call `get_theme()` and interpolate `[{theme.brand}]…[/]` etc.
"""

from __future__ import annotations

import contextlib
import os
import re
import select
import sys
from dataclasses import dataclass, fields

ENV_VAR = "CLAIN_THEME"


class InvalidThemeValue(ValueError):
    """Raised when `--theme` or `CLAIN_THEME` carries an unrecognised value.

    Silently falling through to detection would mask typos; failing loudly
    surfaces them at CLI invocation time (same rule as `CLAIN_LEGEND` in
    spec 0013).
    """


@dataclass(frozen=True)
class Theme:
    """Named colour tokens. Every value is a 24-bit hex string (e.g. `#bb9af7`).

    Renderers reference tokens by name. The mapping from token to hex lives in
    `TOKYO_NIGHT_DARK` and `TOKYO_NIGHT_LIGHT` below. Adding a new token here
    forces the type checker to flag any theme instance that's missing it.
    """

    # Brand identity (spec 0016 five-step meter + wordmark).
    brand: str
    brand_step1: str  # cyan-most
    brand_step2: str
    brand_step3: str  # core brand
    brand_step4: str
    brand_step5: str  # warmest, used for the highest-stakes (execute) step

    # Semantic status.
    safe: str  # ✓ marks; "this is safe to execute"
    unsafe: str  # ✗ marks; "this blocks safe execution"
    warning: str  # ⚠ in synced storage
    fix: str  # literal-command-to-fix line in user_error (spec 0015)

    # Body and meta.
    fg: str  # default foreground
    dim: str  # dim-styled text (status asides, etc.)
    accent: str  # subtle accent (table headers, key column)

    # Per-class colours (class tags in classify; class column in plan).
    class_cache_managed: str
    class_bytecode: str
    class_ephemeral: str
    class_unknown: str  # any future class not in the spec-0009 set


# ----------------------------------------------------------------------------
# The two shipped palettes.
# ----------------------------------------------------------------------------

TOKYO_NIGHT_DARK = Theme(
    brand="#bb9af7",
    brand_step1="#7dcfff",
    brand_step2="#7aa2f7",
    brand_step3="#bb9af7",
    brand_step4="#ff9e64",
    brand_step5="#f7768e",
    safe="#9ece6a",
    unsafe="#f7768e",
    warning="#e0af68",
    fix="#7dcfff",
    fg="#c0caf5",
    dim="#565f89",
    accent="#bb9af7",
    class_cache_managed="#e0af68",
    class_bytecode="#7aa2f7",
    class_ephemeral="#bb9af7",
    class_unknown="#9aa5ce",
)

TOKYO_NIGHT_LIGHT = Theme(
    brand="#5a4a78",
    brand_step1="#007197",
    brand_step2="#34548a",
    brand_step3="#5a4a78",
    brand_step4="#b15c00",
    brand_step5="#8c4351",
    safe="#485e30",
    unsafe="#8c4351",
    warning="#8f5e15",
    fix="#007197",
    fg="#343b58",
    dim="#9699a3",
    accent="#5a4a78",
    class_cache_managed="#8f5e15",
    class_bytecode="#34548a",
    class_ephemeral="#5a4a78",
    class_unknown="#6c6e75",
)


# ----------------------------------------------------------------------------
# Resolution.
# ----------------------------------------------------------------------------

_VALID = ("dark", "light", "auto")


def _normalise(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    v = value.strip().lower()
    if v not in _VALID:
        raise InvalidThemeValue(
            f"theme value {value!r} is not recognised. Accepted: {', '.join(_VALID)} (case-insensitive)."
        )
    return v


_COLORFGBG_BG = re.compile(r"^(?:\d+;)+(?P<bg>\d+|default)$")


def _detect_from_colorfgbg(colorfgbg: str | None) -> str | None:
    """Map COLORFGBG to "dark" / "light" / None (unparseable).

    Format: `fg;bg` or `fg;ig;bg`. Index ≤ 7 → dark; ≥ 8 (or `default`) → light.
    """
    if not colorfgbg:
        return None
    match = _COLORFGBG_BG.match(colorfgbg.strip())
    if match is None:
        return None
    bg = match.group("bg")
    if bg == "default":
        # `default` typically means the terminal's own background — most modern
        # terminals report this on light themes. Treat as light; the user can
        # override via CLAIN_THEME if their default is dark.
        return "light"
    try:
        idx = int(bg)
    except ValueError:
        return None
    return "dark" if idx <= 7 else "light"


_OSC11_RE = re.compile(rb"rgb:([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})/([0-9a-fA-F]{1,4})")


def _detect_from_osc11(timeout: float = 0.05) -> str | None:
    """Query the terminal for its background colour via OSC 11. Best-effort.

    Returns "dark" / "light" / None. Skipped when stdout/stdin aren't TTYs;
    times out cleanly when the terminal doesn't answer.
    """
    try:
        if not (sys.stdout.isatty() and sys.stdin.isatty()):
            return None
    except (AttributeError, ValueError):
        return None
    try:
        import termios
        import tty
    except ImportError:  # non-POSIX
        return None

    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        return None
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b]11;?\x07")
        sys.stdout.flush()
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            return None
        # Drain available bytes (terminator is BEL or ST).
        chunks: list[bytes] = []
        while True:
            ready, _, _ = select.select([fd], [], [], 0.01)
            if not ready:
                break
            chunks.append(os.read(fd, 64))
        data = b"".join(chunks)
    finally:
        with contextlib.suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    m = _OSC11_RE.search(data)
    if m is None:
        return None
    # Each component is up to 4 hex chars (16-bit). Normalise to [0,1].
    r, g, b = (int(c, 16) / (16 ** len(c) - 1) for c in m.groups())
    # Relative luminance (Rec. 709, gamma-naive — fine for a dark/light split).
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "light" if lum > 0.5 else "dark"


def resolve_theme(
    flag: str | None,
    env: str | None,
    colorfgbg: str | None,
    no_color: bool,
    *,
    osc11: bool = False,
) -> Theme | None:
    """Resolve a Theme per spec 0017 § Resolution.

    `osc11=False` by default: the OSC 11 query is only run when the caller
    opts in (cli.py does, tests don't — terminals in CI hang or echo garbage).
    """
    if no_color:
        return None

    chosen_flag = _normalise(flag)
    if chosen_flag in ("dark", "light"):
        return TOKYO_NIGHT_DARK if chosen_flag == "dark" else TOKYO_NIGHT_LIGHT

    if chosen_flag is None:
        chosen_env = _normalise(env)
        if chosen_env in ("dark", "light"):
            return TOKYO_NIGHT_DARK if chosen_env == "dark" else TOKYO_NIGHT_LIGHT

    # Either flag/env is `auto`, or both are unset — detect.
    detected = _detect_from_colorfgbg(colorfgbg)
    if detected is None and osc11:
        detected = _detect_from_osc11()
    if detected == "light":
        return TOKYO_NIGHT_LIGHT
    # Fallback: dark.
    return TOKYO_NIGHT_DARK


# ----------------------------------------------------------------------------
# Process-wide singleton.
# ----------------------------------------------------------------------------

_active_theme: Theme = TOKYO_NIGHT_DARK


def set_theme(theme: Theme | None) -> None:
    """Set the process-wide active theme. `None` keeps the previous theme.

    Called once from cli.py's `@app.callback()` after `resolve_theme`. The
    `None` case (NO_COLOR) is a no-op here because Rich's own NO_COLOR support
    strips colour at render time — the renderers can keep interpolating tokens
    safely.
    """
    global _active_theme
    if theme is not None:
        _active_theme = theme


def get_theme() -> Theme:
    """Return the active theme. Defaults to `TOKYO_NIGHT_DARK` before any set."""
    return _active_theme


# ----------------------------------------------------------------------------
# Convenience: list of all token field names. Used by the
# `test_theme_token_set_complete` test and by anyone who wants to iterate.
# ----------------------------------------------------------------------------

THEME_TOKENS = tuple(f.name for f in fields(Theme))
