"""Legend-toggle resolution (spec 0013).

Centralises the precedence rule so every command that renders Rich output
applies it identically:

    1. Explicit --legend / --no-legend flag (highest)
    2. CLAIN_LEGEND env var
    3. Mode default: --here ⇒ on, tree mode ⇒ off
"""

from __future__ import annotations

ENV_VAR = "CLAIN_LEGEND"

_TRUTHY = frozenset({"on", "1", "true", "yes"})
_FALSY = frozenset({"off", "0", "false", "no"})


class InvalidLegendValue(ValueError):
    """Raised when `CLAIN_LEGEND` carries an unrecognised value.

    Silently falling through to the default would mask typos; failing loudly
    surfaces them at CLI invocation time.
    """


def parse_env(value: str | None) -> bool | None:
    """Parse a CLAIN_LEGEND value to a bool.

    Returns None when unset or empty (caller should fall through to default).
    Raises InvalidLegendValue for unknown values.
    """
    if value is None or value == "":
        return None
    v = value.strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    accepted = sorted(_TRUTHY | _FALSY)
    raise InvalidLegendValue(
        f"{ENV_VAR}={value!r} is not a recognised value. Accepted (case-insensitive): {', '.join(accepted)}, or unset."
    )


def should_show_legend(here: bool, flag: bool | None, env: str | None) -> bool:
    """Resolve the legend toggle per spec 0013 § Legend toggle precedence."""
    if flag is not None:
        return flag
    parsed = parse_env(env)
    if parsed is not None:
        return parsed
    return here  # mode default: --here ⇒ on, tree ⇒ off
