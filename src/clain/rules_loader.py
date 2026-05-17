"""Load and validate the rule base from rules.toml.

Modules that need the rules consume them via `load_rules()`. Tests can pass an
explicit path to `load_rules()` for fixture-based overrides. The default path
points at the packaged `rules.toml` next to this module.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA = 1


class RulesLoadError(RuntimeError):
    """Raised when rules.toml is malformed or fails validation."""


@dataclass(frozen=True)
class ClassRule:
    name: str
    description: str
    default_action: str  # "delete" | "delete-and-recreate"
    directory_names: tuple[str, ...]


@dataclass(frozen=True)
class RecreateRule:
    manifest: str
    command: str
    ecosystem: str
    priority: int
    safe: bool
    unsafe_reason: str | None = None


@dataclass(frozen=True)
class Placement:
    ecosystem: str
    store_advice: str
    configure_via: str
    doc_url: str


@dataclass(frozen=True)
class Rules:
    schema: int
    classes: tuple[ClassRule, ...]
    manifests_to_detect: tuple[str, ...]
    recreate_rules: tuple[RecreateRule, ...]
    placements: tuple[Placement, ...]
    _class_of: dict[str, str] = field(default_factory=dict)
    _all_class_dirs: frozenset[str] = field(default_factory=frozenset)
    _recreate_by_manifest: dict[str, RecreateRule] = field(default_factory=dict)
    _placement_by_ecosystem: dict[str, Placement] = field(default_factory=dict)

    def class_of(self, dirname: str) -> str | None:
        return self._class_of.get(dirname)

    @property
    def all_class_dirs(self) -> frozenset[str]:
        return self._all_class_dirs

    def recreate_for(self, manifest: str) -> RecreateRule | None:
        return self._recreate_by_manifest.get(manifest)

    def placement_for(self, ecosystem: str) -> Placement | None:
        return self._placement_by_ecosystem.get(ecosystem)


DEFAULT_RULES_PATH = Path(__file__).parent / "rules.toml"


def _require(d: dict[str, Any], key: str, context: str) -> Any:
    if key not in d:
        raise RulesLoadError(f"missing required field {key!r} in {context}")
    return d[key]


def _parse_class(raw: dict[str, Any]) -> ClassRule:
    name = _require(raw, "name", "[[classes]]")
    description = _require(raw, "description", f"class {name!r}")
    action = _require(raw, "default_action", f"class {name!r}")
    if action not in ("delete", "delete-and-recreate"):
        raise RulesLoadError(
            f"class {name!r}: default_action must be 'delete' or 'delete-and-recreate', got {action!r}"
        )
    dirs = _require(raw, "directory_names", f"class {name!r}")
    if not isinstance(dirs, list) or not all(isinstance(d, str) for d in dirs):
        raise RulesLoadError(f"class {name!r}: directory_names must be a list of strings")
    return ClassRule(
        name=str(name),
        description=str(description),
        default_action=str(action),
        directory_names=tuple(dirs),
    )


def _parse_recreate(raw: dict[str, Any]) -> RecreateRule:
    manifest = _require(raw, "manifest", "[[recreate_rules]]")
    return RecreateRule(
        manifest=str(manifest),
        command=str(_require(raw, "command", f"recreate_rule for {manifest!r}")),
        ecosystem=str(_require(raw, "ecosystem", f"recreate_rule for {manifest!r}")),
        priority=int(_require(raw, "priority", f"recreate_rule for {manifest!r}")),
        safe=bool(_require(raw, "safe", f"recreate_rule for {manifest!r}")),
        unsafe_reason=(str(raw["unsafe_reason"]) if raw.get("unsafe_reason") is not None else None),
    )


def _parse_placement(raw: dict[str, Any]) -> Placement:
    return Placement(
        ecosystem=str(_require(raw, "ecosystem", "[[placements]]")),
        store_advice=str(_require(raw, "store_advice", "[[placements]]")),
        configure_via=str(_require(raw, "configure_via", "[[placements]]")),
        doc_url=str(_require(raw, "doc_url", "[[placements]]")),
    )


def _build_rules(data: dict[str, Any]) -> Rules:
    schema = data.get("schema")
    if schema != SUPPORTED_SCHEMA:
        raise RulesLoadError(f"unsupported schema version {schema!r}; this loader expects {SUPPORTED_SCHEMA}")

    classes_raw = data.get("classes", [])
    if not isinstance(classes_raw, list):
        raise RulesLoadError("[[classes]] must be a list of tables")
    classes = tuple(_parse_class(c) for c in classes_raw)

    # Reject duplicate directory names across classes.
    seen: dict[str, str] = {}
    for c in classes:
        for d in c.directory_names:
            if d in seen:
                raise RulesLoadError(f"directory name {d!r} appears in both classes {seen[d]!r} and {c.name!r}")
            seen[d] = c.name

    manifests_to_detect = tuple(str(m) for m in data.get("manifests", {}).get("detect", []))

    recreate_raw = data.get("recreate_rules", [])
    if not isinstance(recreate_raw, list):
        raise RulesLoadError("[[recreate_rules]] must be a list of tables")
    recreate_rules = tuple(
        sorted(
            (_parse_recreate(r) for r in recreate_raw),
            key=lambda r: r.priority,
        )
    )

    placements_raw = data.get("placements", [])
    if not isinstance(placements_raw, list):
        raise RulesLoadError("[[placements]] must be a list of tables")
    placements = tuple(_parse_placement(p) for p in placements_raw)

    class_of = {d: c.name for c in classes for d in c.directory_names}
    all_class_dirs = frozenset(class_of.keys())

    # First-match-wins lookup table, but iteration order is priority-sorted, so
    # callers can still walk `recreate_rules` for priority semantics.
    recreate_by_manifest: dict[str, RecreateRule] = {}
    for r in recreate_rules:
        recreate_by_manifest.setdefault(r.manifest, r)

    placement_by_ecosystem = {p.ecosystem: p for p in placements}

    return Rules(
        schema=schema,
        classes=classes,
        manifests_to_detect=manifests_to_detect,
        recreate_rules=recreate_rules,
        placements=placements,
        _class_of=class_of,
        _all_class_dirs=all_class_dirs,
        _recreate_by_manifest=recreate_by_manifest,
        _placement_by_ecosystem=placement_by_ecosystem,
    )


@lru_cache(maxsize=8)
def load_rules(path: Path = DEFAULT_RULES_PATH) -> Rules:
    """Load and validate the rule base.

    Raises RulesLoadError on schema or structural problems.
    """
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RulesLoadError(f"rules file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RulesLoadError(f"rules.toml is not valid TOML: {exc}") from exc
    return _build_rules(raw)
