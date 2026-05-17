"""State-directory helpers — cache, plan, log, and report locations.

The only place in clain that creates directories or writes files outside of test
fixtures. All writes target `$XDG_STATE_HOME/clain/` (never inside the project,
never inside the synced tree).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clain.config import clain_state_dir


def root_hash(root: Path) -> str:
    """Stable, short identifier for a resolved root path."""
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]


def classify_cache_path(root: Path) -> Path:
    return clain_state_dir() / "classify" / f"{root_hash(root)}.json"


def plan_dir() -> Path:
    return clain_state_dir() / "plans"


def log_path(name: str) -> Path:
    return clain_state_dir() / "logs" / f"{name}.log"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to a state-directory path, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        return None
    return data


def append_log(name: str, line: str) -> None:
    path = log_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def utc_now_filename_stamp() -> str:
    """Filesystem-safe UTC stamp for filenames."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
