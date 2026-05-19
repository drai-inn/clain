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


def classify_cache_path(root: Path, schema: int) -> Path:
    """Schema-versioned cache filename (spec 0014).

    The schema version is part of the filename so a binary that bumped the
    classify schema doesn't read stale caches written by an older binary.
    Old-schema files at the same `<root-hash>` are cleaned up by
    `prune_stale_classify_caches` when the new path is accessed.
    """
    return clain_state_dir() / "classify" / f"{root_hash(root)}-v{schema}.json"


def prune_stale_classify_caches(root: Path, current_schema: int) -> list[Path]:
    """Remove any classify cache files for `root` whose schema isn't current.

    Returns the list of removed paths (caller may log; tests use it as a
    machine-checkable signal). Best-effort: missing-file races are ignored,
    other OSError surfaces (so a permission problem becomes visible).
    """
    classify_dir = clain_state_dir() / "classify"
    if not classify_dir.exists():
        return []
    h = root_hash(root)
    current = classify_dir / f"{h}-v{current_schema}.json"
    removed: list[Path] = []
    # Match both the legacy unsuffixed file and any other -v<N>.json file
    # for this root hash.
    candidates = [classify_dir / f"{h}.json", *classify_dir.glob(f"{h}-v*.json")]
    for path in candidates:
        if path == current or not path.exists():
            continue
        try:
            path.unlink()
            removed.append(path)
        except FileNotFoundError:
            pass
    return removed


def plan_dir() -> Path:
    return clain_state_dir() / "plans"


# Grace window before stale-schema plan files are deleted. Plans are throwaway
# (re-derivable from a fresh classify), so a week of retention is generous.
_PLAN_STALE_GRACE_DAYS = 7


def prune_stale_plan_files(current_schema: int, *, grace_days: int = _PLAN_STALE_GRACE_DAYS) -> list[Path]:
    """Remove plan files older than `grace_days` whose embedded schema isn't current.

    Spec 0016. Inspects each `*.json` under `plan_dir()`; if its `schema` field
    differs from `current_schema` and its mtime is older than the grace window,
    it's deleted. Returns the list of removed paths (caller may log; tests use
    it as a machine-checkable signal).
    """
    import time

    pdir = plan_dir()
    if not pdir.exists():
        return []
    cutoff = time.time() - (grace_days * 86400)
    removed: list[Path] = []
    for path in pdir.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime > cutoff:
            continue
        data = read_json(path)
        if data is None:
            continue
        schema = data.get("schema")
        if isinstance(schema, int) and schema != current_schema:
            try:
                path.unlink()
                removed.append(path)
            except FileNotFoundError:
                pass
    return removed


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
