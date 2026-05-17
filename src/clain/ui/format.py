"""Formatting helpers — bytes → human, timestamps → relative."""

from __future__ import annotations

from datetime import UTC, datetime

_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def humanize_bytes(n: int | float | None) -> str:
    if n is None:
        return "?"
    f = float(n)
    if f < 1024:
        return f"{int(f)} B"
    for unit in _UNITS[1:]:
        f /= 1024
        if f < 1024:
            return f"{f:.1f} {unit}"
    return f"{f:.1f} EiB"


def humanize_age(epoch: float | None) -> str:
    if epoch is None:
        return "?"
    now = datetime.now(UTC).timestamp()
    delta = now - epoch
    if delta < 0:
        return "future"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    if delta < 30 * 86400:
        return f"{int(delta / 86400)}d ago"
    if delta < 365 * 86400:
        return f"{int(delta / (30 * 86400))}mo ago"
    return f"{int(delta / (365 * 86400))}y ago"


def months_since(epoch: float | None) -> float | None:
    if epoch is None:
        return None
    now = datetime.now(UTC).timestamp()
    return (now - epoch) / (30 * 86400)
