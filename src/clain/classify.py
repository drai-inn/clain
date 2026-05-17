"""Categorical classification scan (spec 0004).

Walks each workspace only down to the first directory matching a known class,
then prunes. Records (class, relative_path) tuples plus the manifests present
at the workspace root. Never stats individual files; never recurses into
class-tagged subtrees.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clain.classes import ALL_CLASS_DIRS, MANIFEST_FILES, classify_dirname
from clain.config import CACHE_TTL_SECONDS
from clain.state import (
    append_log,
    classify_cache_path,
    read_json,
    write_json,
)

SCHEMA_VERSION = 1


@dataclass
class ClassTag:
    cls: str
    relative_path: str

    def to_dict(self) -> dict[str, str]:
        return {"class": self.cls, "relative_path": self.relative_path}


@dataclass
class WorkspaceClass:
    name: str
    path: str
    in_sync_tree: bool
    class_tags: list[ClassTag] = field(default_factory=list)
    manifests: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "in_sync_tree": self.in_sync_tree,
            "class_tags": [t.to_dict() for t in self.class_tags],
            "manifests": sorted(self.manifests),
            "errors": self.errors,
        }


def _iter_workspaces(root: Path) -> Iterator[Path]:
    try:
        with os.scandir(root) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    yield Path(entry.path)
    except OSError:
        return


def _detect_manifests(workspace: Path) -> list[str]:
    found: list[str] = []
    try:
        with os.scandir(workspace) as it:
            for entry in it:
                if entry.name in MANIFEST_FILES and entry.is_file(follow_symlinks=False):
                    found.append(entry.name)
    except OSError:
        pass
    return sorted(found)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def classify_workspace(workspace: Path, synced_root: Path) -> WorkspaceClass:
    """Walk a workspace, prune at class boundaries, record tags + manifests."""
    result = WorkspaceClass(
        name=workspace.name,
        path=str(workspace),
        in_sync_tree=_is_under(workspace, synced_root),
        manifests=_detect_manifests(workspace),
    )

    walker_errors: list[str] = []

    def _onerror(exc: OSError) -> None:
        walker_errors.append(f"walk: {exc}")

    for dirpath, dirnames, _filenames in os.walk(workspace, followlinks=False, onerror=_onerror):
        # Find class dirs at this level, record them, prune them.
        keep: list[str] = []
        for d in dirnames:
            cls = classify_dirname(d)
            if cls is not None:
                rel = (Path(dirpath) / d).relative_to(workspace)
                result.class_tags.append(ClassTag(cls=cls, relative_path=str(rel)))
            else:
                keep.append(d)
        # Mutate in place so os.walk skips the class dirs.
        dirnames[:] = keep

    result.errors.extend(walker_errors)
    return result


def run_classify(root: Path, synced_root: Path) -> dict[str, Any]:
    if not root.exists():
        raise FileNotFoundError(f"Root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Root is not a directory: {root}")

    started = time.time()
    workspaces = [
        classify_workspace(ws, synced_root) for ws in sorted(_iter_workspaces(root), key=lambda p: p.name.lower())
    ]
    ended = time.time()

    total_tags = sum(len(w.class_tags) for w in workspaces)
    return {
        "schema": SCHEMA_VERSION,
        "scan": {
            "root": str(root),
            "synced_root": str(synced_root),
            "started_at": datetime.fromtimestamp(started, tz=UTC).isoformat(timespec="seconds"),
            "ended_at": datetime.fromtimestamp(ended, tz=UTC).isoformat(timespec="seconds"),
            "duration_seconds": round(ended - started, 3),
            "class_dirs_considered": sorted(ALL_CLASS_DIRS),
            "total_class_tags": total_tags,
        },
        "workspaces": [w.to_dict() for w in workspaces],
    }


def load_cached(root: Path) -> dict[str, Any] | None:
    return read_json(classify_cache_path(root))


def save_cache(root: Path, payload: dict[str, Any]) -> Path:
    path = classify_cache_path(root)
    write_json(path, payload)
    return path


def cache_is_fresh(payload: dict[str, Any]) -> bool:
    ended_at = payload.get("scan", {}).get("ended_at")
    if not isinstance(ended_at, str):
        return False
    try:
        dt = datetime.fromisoformat(ended_at)
    except ValueError:
        return False
    return (datetime.now(UTC) - dt).total_seconds() < CACHE_TTL_SECONDS


def log_run(root: Path, payload: dict[str, Any]) -> None:
    scan = payload.get("scan", {})
    workspaces = payload.get("workspaces", [])
    append_log(
        "classify",
        f"root={root} workspaces={len(workspaces)} "
        f"class_tags={scan.get('total_class_tags')} "
        f"duration_s={scan.get('duration_seconds')}",
    )


def get_or_run(
    root: Path, synced_root: Path, *, refresh: bool = False, use_cache: bool = True
) -> tuple[dict[str, Any], bool]:
    """Return (payload, cache_hit)."""
    if use_cache and not refresh:
        cached = load_cached(root)
        if cached is not None and cache_is_fresh(cached):
            return cached, True
    payload = run_classify(root, synced_root)
    if use_cache:
        save_cache(root, payload)
    log_run(root, payload)
    return payload, False
