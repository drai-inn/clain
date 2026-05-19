"""Categorical classification scan (spec 0004).

Walks each workspace only down to the first directory matching a known class,
then prunes. Records (class, relative_path) tuples plus the manifests present
at the workspace root. Never stats individual files; never recurses into
class-tagged subtrees.

Class and manifest definitions come from the rule base (`rules.toml`) loaded
via `clain.rules_loader.load_rules`. Pass an explicit `Rules` to `run_classify`
for fixture-based testing; otherwise the packaged default is used.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clain.config import CACHE_TTL_SECONDS
from clain.rules_loader import Rules, load_rules
from clain.state import (
    append_log,
    classify_cache_path,
    prune_stale_classify_caches,
    read_json,
    write_json,
)
from clain.sync_detect import detect_synced_storage

# Bumped to 2 in spec 0014. The 0013 sync_placement block was technically
# additive, but bumping forces a clean cache invalidation across the user
# base — old caches lack sync_placement and would render as "unknown" under
# the new code.
SCHEMA_VERSION = 2


@dataclass
class ClassTag:
    cls: str
    relative_path: str

    def to_dict(self) -> dict[str, str]:
        return {"class": self.cls, "relative_path": self.relative_path}


@dataclass
class SyncPlacement:
    """Per-workspace sync-placement record (spec 0013).

    `state` aligns with the legacy `in_sync_tree` boolean:
        synced  ⇒ in_sync_tree == True
        local   ⇒ in_sync_tree == False
        unknown ⇒ in_sync_tree is None

    `source` tells the reader how the answer was determined:
        autodetect — pattern matched on macOS; provider names which one
        unset      — non-macOS platform; sync placement is not autodetected
    """

    state: str  # "synced" | "local" | "unknown"
    provider: str | None
    source: str  # "autodetect" | "unset"
    synced_root: str | None  # the matched-root prefix when state == "synced"; null otherwise

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "provider": self.provider,
            "source": self.source,
            "synced_root": self.synced_root,
        }


def _resolve_sync_placement(workspace: Path) -> SyncPlacement:
    """Resolve sync placement via macOS autodetection (spec 0013).

    `CLAIN_SYNCED_ROOT` was removed in spec 0013. The CLI hard-errors at
    startup if the developer still has it set; by the time we reach this
    function, autodetect is the only source.
    """
    state, provider, matched_root = detect_synced_storage(workspace)
    return SyncPlacement(
        state=state,
        provider=provider,
        source="autodetect" if state != "unknown" else "unset",
        synced_root=matched_root,
    )


@dataclass
class WorkspaceClass:
    name: str
    path: str
    in_sync_tree: bool | None
    sync_placement: SyncPlacement
    class_tags: list[ClassTag] = field(default_factory=list)
    manifests: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "in_sync_tree": self.in_sync_tree,
            "sync_placement": self.sync_placement.to_dict(),
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


def _detect_manifests(workspace: Path, rules: Rules) -> list[str]:
    detect = set(rules.manifests_to_detect)
    found: list[str] = []
    try:
        with os.scandir(workspace) as it:
            for entry in it:
                if entry.name in detect and entry.is_file(follow_symlinks=False):
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


def classify_workspace(workspace: Path, rules: Rules) -> WorkspaceClass:
    """Walk a workspace, prune at class boundaries, record tags + manifests.

    Sync placement is resolved per spec 0013 via macOS autodetect; off-macOS
    the state is "unknown". `CLAIN_SYNCED_ROOT` was removed in spec 0013.
    """
    sync_placement = _resolve_sync_placement(workspace)
    in_sync: bool | None = (
        True if sync_placement.state == "synced" else False if sync_placement.state == "local" else None
    )
    result = WorkspaceClass(
        name=workspace.name,
        path=str(workspace),
        in_sync_tree=in_sync,
        sync_placement=sync_placement,
        manifests=_detect_manifests(workspace, rules),
    )

    walker_errors: list[str] = []

    def _onerror(exc: OSError) -> None:
        walker_errors.append(f"walk: {exc}")

    for dirpath, dirnames, _filenames in os.walk(workspace, followlinks=False, onerror=_onerror):
        keep: list[str] = []
        for d in dirnames:
            if d in rules.prune_names:
                # Pruned: do not recurse, do not record.
                continue
            cls = rules.class_of(d)
            if cls is not None:
                rel = (Path(dirpath) / d).relative_to(workspace)
                result.class_tags.append(ClassTag(cls=cls, relative_path=str(rel)))
            else:
                keep.append(d)
        dirnames[:] = keep

    result.errors.extend(walker_errors)
    return result


def run_classify(
    root: Path,
    rules: Rules | None = None,
    *,
    single: bool = False,
) -> dict[str, Any]:
    """Classify a tree of workspaces or, with `single=True`, a single workspace.

    Per spec 0010, `single=True` treats ROOT itself as one workspace rather than
    enumerating depth-1 children. The JSON shape is unchanged (`workspaces` is a
    list with exactly one entry in single mode); only `scan.mode` differs.

    Spec 0013 removed the `synced_root` parameter — sync placement is now
    resolved per workspace via macOS autodetection (see `_resolve_sync_placement`).
    """
    if not root.exists():
        raise FileNotFoundError(f"Root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Root is not a directory: {root}")

    rules = rules or load_rules()

    started = time.time()
    if single:
        workspaces = [classify_workspace(root, rules)]
    else:
        workspaces = [
            classify_workspace(ws, rules) for ws in sorted(_iter_workspaces(root), key=lambda p: p.name.lower())
        ]
    ended = time.time()

    total_tags = sum(len(w.class_tags) for w in workspaces)
    return {
        "schema": SCHEMA_VERSION,
        "scan": {
            "root": str(root),
            "mode": "single" if single else "tree",
            "started_at": datetime.fromtimestamp(started, tz=UTC).isoformat(timespec="seconds"),
            "ended_at": datetime.fromtimestamp(ended, tz=UTC).isoformat(timespec="seconds"),
            "duration_seconds": round(ended - started, 3),
            "class_dirs_considered": sorted(rules.all_class_dirs),
            "prune_names": sorted(rules.prune_names),
            "rules_schema": rules.schema,
            "total_class_tags": total_tags,
        },
        "workspaces": [w.to_dict() for w in workspaces],
    }


def load_cached(root: Path) -> dict[str, Any] | None:
    return read_json(classify_cache_path(root, SCHEMA_VERSION))


def save_cache(root: Path, payload: dict[str, Any]) -> Path:
    path = classify_cache_path(root, SCHEMA_VERSION)
    write_json(path, payload)
    # Sweep any stale-schema cache files for this root so the disk doesn't
    # accumulate dead caches across upgrades (spec 0014).
    prune_stale_classify_caches(root, SCHEMA_VERSION)
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
    root: Path,
    *,
    refresh: bool = False,
    use_cache: bool = True,
    rules: Rules | None = None,
    single: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Return (payload, cache_hit)."""
    if use_cache and not refresh:
        cached = load_cached(root)
        if cached is not None and cache_is_fresh(cached):
            # Use cached only if the mode matches; absent mode = "tree" per spec 0010.
            cached_mode = cached.get("scan", {}).get("mode", "tree")
            wanted_mode = "single" if single else "tree"
            if cached_mode == wanted_mode:
                return cached, True
    payload = run_classify(root, rules, single=single)
    if use_cache:
        save_cache(root, payload)
    log_run(root, payload)
    return payload, False
