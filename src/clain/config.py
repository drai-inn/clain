"""Configuration constants and path resolution for clain.

No code in this module may write to the filesystem. It only resolves paths.

Per spec 0004 § Subcommand: there is **no baked-in default for the dev root that
contains personal information**. The root must come from either an explicit
positional argument or the `CLAIN_DEV_ROOT` environment variable. If neither is
set, callers must error rather than fall back to a personal path.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DEV_ROOT = "CLAIN_DEV_ROOT"

# Spec 0013 removed CLAIN_SYNCED_ROOT. The name lives on as a constant only so
# the deprecation check in `clain.cli` can refer to it without re-typing the
# string. There is no `resolve_synced_root()` — sync placement is now resolved
# by `clain.sync_detect.detect_synced_storage` against the workspace path.
ENV_SYNCED_ROOT_DEPRECATED = "CLAIN_SYNCED_ROOT"

CACHE_TTL_SECONDS = 24 * 60 * 60


class DevRootNotConfigured(RuntimeError):
    """Raised when no explicit root was given and CLAIN_DEV_ROOT is unset."""


def resolve_dev_root(explicit: Path | None) -> Path:
    """Resolve the dev root.

    Order: explicit positional arg → CLAIN_DEV_ROOT env var → raise.
    """
    if explicit is not None:
        return explicit.expanduser().resolve()
    env = os.environ.get(ENV_DEV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    raise DevRootNotConfigured(f"No dev root configured. Pass a positional argument or set ${ENV_DEV_ROOT}.")


def xdg_state_home() -> Path:
    raw = os.environ.get("XDG_STATE_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "state"


def xdg_cache_home() -> Path:
    raw = os.environ.get("XDG_CACHE_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache"


def clain_state_dir() -> Path:
    return xdg_state_home() / "clain"
