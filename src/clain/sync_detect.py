"""Synced-storage autodetection (spec 0013).

On macOS, recognises a fixed list of standard synced-storage path patterns and
returns the provider name plus the matched-root prefix (evidence). On
non-macOS, returns ("unknown", None, None) — sync placement is not autodetected
on those platforms (a future spec adds Linux/Windows detection).

Spec 0013 removed the `CLAIN_SYNCED_ROOT` env-var override. The CLI hard-errors
on startup if that env var is still set in the environment.

The provider-name strings here are generic service brand names, not personal
information. Spec 0008's anonymisation discipline is not implicated.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

# (prefix-with-tilde, provider-name) pairs. Order is irrelevant — patterns are
# disjoint by construction. Adding a new provider is a one-line addition with a
# test; not a separate spec.
SYNCED_STORAGE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("~/Library/CloudStorage/GoogleDrive-", "Google Drive"),
    ("~/Library/CloudStorage/OneDrive-", "OneDrive"),
    ("~/Library/CloudStorage/Dropbox", "Dropbox"),
    ("~/Library/CloudStorage/Box-Box", "Box"),
    ("~/Library/Mobile Documents/com~apple~CloudDocs", "iCloud Drive"),
    ("~/Dropbox", "Dropbox (classic)"),
)

SyncState = Literal["synced", "local", "unknown"]


def _is_macos() -> bool:
    return sys.platform == "darwin"


def detect_synced_storage(
    workspace_path: Path, *, _platform: str | None = None
) -> tuple[SyncState, str | None, str | None]:
    """Detect whether a workspace path sits inside a recognised synced-storage tree.

    Returns:
        ("synced", provider, matched_root) — path matches a known pattern; matched_root
                                             is the prefix path that triggered detection
                                             (evidence; useful for disambiguation).
        ("local", None, None)              — path doesn't match any pattern (macOS only).
        ("unknown", None, None)            — non-macOS platform; we don't claim to know.

    The `_platform` parameter is for testing only; production callers should
    not pass it.
    """
    platform = _platform if _platform is not None else sys.platform
    if platform != "darwin":
        return ("unknown", None, None)

    p = str(workspace_path)
    home = str(Path.home())
    for tilde_prefix, provider in SYNCED_STORAGE_PATTERNS:
        prefix = tilde_prefix.replace("~", home, 1)
        if p.startswith(prefix):
            return ("synced", provider, prefix)
    return ("local", None, None)
