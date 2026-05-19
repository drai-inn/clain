"""Executable plan model — recreate and move actions, dry-run rendering only.

Per spec 0005 § Phase-gate invariant, this module is allowed to:
- Read the classify cache.
- Derive recreate commands from manifest evidence (via the rule base).
- Perform smoke-test reads of well-known integrity files at workspace depth 1.
- Emit plan JSON to `$XDG_STATE_HOME/clain/plans/`.

It is NOT allowed to spawn a process, mutate any path derived from ROOT, or
touch the destination of a move action. Those become available only when
spec 00NN lifts the dry-run gate.

Class membership, manifest → command mappings, and ecosystem placements all
come from the rule base (`rules.toml`) via `clain.rules_loader.load_rules`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clain.rules_loader import Placement, RecreateRule, Rules, load_rules
from clain.state import (
    plan_dir,
    prune_stale_plan_files,
    utc_now_filename_stamp,
    utc_now_iso,
    write_json,
)

# Spec 0016: bumped from 1 → 2 alongside the `type → action` field rename. Old
# plan files written with schema 1 are no longer loadable by plan explain; the
# user must regenerate via `clain plan recreate`.
SCHEMA_VERSION = 2


@dataclass
class Action:
    workspace: str
    action: str  # "delete" | "recreate" | "move" | "smoke-test"
    target: str
    cls: str
    rationale: str
    commands: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    safe_to_execute: bool = True
    unsafe_reason: str | None = None

    @property
    def id(self) -> str:
        h = hashlib.sha256(f"{self.workspace}|{self.action}|{self.target}".encode()).hexdigest()
        return h[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace": self.workspace,
            "action": self.action,
            "target": self.target,
            "class": self.cls,
            "rationale": self.rationale,
            "commands": list(self.commands),
            "preconditions": list(self.preconditions),
            "safe_to_execute": self.safe_to_execute,
            "unsafe_reason": self.unsafe_reason,
        }


def _select_recreate(manifests: set[str], rules: Rules) -> tuple[RecreateRule | None, Placement | None]:
    """Pick the highest-priority (lowest priority value) recreate rule whose manifest is present.

    The rule base's `recreate_rules` are pre-sorted by priority by the loader,
    so the first match wins.
    """
    for rule in rules.recreate_rules:
        if rule.manifest in manifests:
            placement = rules.placement_for(rule.ecosystem)
            return rule, placement
    return None, None


def _rationale(cls: str, manifest_hits: list[str], placement: Placement | None) -> str:
    base_by_cls = {
        "cache-managed": "Cache-managed dir — belongs in a single store per ecosystem, outside the synced tree.",
        "ephemeral": "Ephemeral build output — regenerable by the normal build step.",
        "bytecode": "Bytecode / tool cache — regenerated on the next run.",
    }
    base = base_by_cls.get(cls, "Subtree.")
    manifest_note = f" Evidence: {', '.join(manifest_hits)}." if manifest_hits else ""
    placement_note = f" Placement: {placement.store_advice}" if placement else ""
    return f"{base}{manifest_note}{placement_note}"


def build_recreate_plan(classify_payload: dict[str, Any], rules: Rules | None = None) -> dict[str, Any]:
    rules = rules or load_rules()
    recreate_manifests = {r.manifest for r in rules.recreate_rules}

    actions: list[Action] = []
    for ws in classify_payload.get("workspaces", []):
        manifests = set(ws.get("manifests", []))
        manifest_hits = sorted(manifests & recreate_manifests)
        rule, placement = _select_recreate(manifests, rules)

        if rule is None:
            commands: list[str] = []
            safe = False
            unsafe_reason: str | None = "no recognised manifest — investigate manually"
        else:
            commands = [rule.command]
            safe = rule.safe
            unsafe_reason = rule.unsafe_reason

        for tag in ws.get("class_tags", []):
            cls = tag.get("class")
            rel = tag.get("relative_path")
            target = str(Path(ws.get("path", "")) / rel)
            rationale = _rationale(cls, manifest_hits, placement)

            actions.append(
                Action(
                    workspace=ws["name"],
                    action="delete",
                    target=target,
                    cls=cls,
                    rationale=rationale,
                    commands=[f"rm -rf {target!r}"],
                    safe_to_execute=safe,
                    unsafe_reason=unsafe_reason,
                )
            )
            if cls == "cache-managed":
                actions.append(
                    Action(
                        workspace=ws["name"],
                        action="recreate",
                        target=str(ws.get("path", "")),
                        cls=cls,
                        rationale=rationale,
                        commands=commands,
                        preconditions=[f"delete action for {target!r} must complete first"],
                        safe_to_execute=safe,
                        unsafe_reason=unsafe_reason,
                    )
                )

    return _wrap_plan("recreate", classify_payload, actions, rules)


def build_move_plan(
    classify_payload: dict[str, Any],
    destination_root: Path,
    rules: Rules | None = None,
) -> dict[str, Any]:
    rules = rules or load_rules()
    actions: list[Action] = []

    exclude_args = " ".join(f"--exclude {d}" for d in sorted(rules.all_class_dirs))

    for ws in classify_payload.get("workspaces", []):
        if not ws.get("in_sync_tree"):
            continue
        manifests = set(ws.get("manifests", []))
        source = ws.get("path", "")
        destination = str(destination_root / ws["name"])

        preconditions: list[str] = []
        has_venv = any(t.get("relative_path", "").startswith((".venv", "venv")) for t in ws.get("class_tags", []))
        if has_venv:
            preconditions.append(
                "venv directories embed absolute paths in pyvenv.cfg and console "
                "scripts — delete-and-recreate via `clain plan recreate`, do not move."
            )
        if ".envrc" in manifests:
            preconditions.append(".envrc may contain absolute path references — review before move.")
        if "docker-compose.yml" in manifests or "docker-compose.yaml" in manifests:
            preconditions.append("docker-compose.* may reference absolute paths or bind-mounted volumes.")
        lockfile_manifests = {
            "uv.lock",
            "pixi.lock",
            "poetry.lock",
            "pnpm-lock.yaml",
            "package-lock.json",
            "yarn.lock",
        }
        has_lockfile = bool(manifests & lockfile_manifests)
        safe = has_lockfile or not any(t.get("class") == "cache-managed" for t in ws.get("class_tags", []))
        unsafe_reason = (
            None
            if safe
            else "cache-managed subtrees present but no lockfile — recreate after move would resolve fresh versions"
        )

        actions.append(
            Action(
                workspace=ws["name"],
                action="smoke-test",
                target=source,
                cls="workspace-source",
                rationale="Integrity scan over manifests + integrity files at workspace root.",
                commands=[],
                preconditions=preconditions,
                safe_to_execute=True,
            )
        )
        actions.append(
            Action(
                workspace=ws["name"],
                action="move",
                target=destination,
                cls="workspace-source",
                rationale=(
                    "Workspace is inside the synced tree. Move source out; "
                    "cache-managed subtrees (if any) must be excluded from the move and "
                    "regenerated via `clain plan recreate` against the new location."
                ),
                commands=[f"rsync -a --delete {exclude_args} {source!r}/ {destination!r}/"],
                preconditions=preconditions,
                safe_to_execute=safe,
                unsafe_reason=unsafe_reason,
            )
        )

    return _wrap_plan("move", classify_payload, actions, rules)


def _wrap_plan(
    kind: str,
    classify_payload: dict[str, Any],
    actions: list[Action],
    rules: Rules,
) -> dict[str, Any]:
    scan = classify_payload.get("scan", {})
    unsafe = sum(1 for a in actions if not a.safe_to_execute)
    workspaces = {a.workspace for a in actions}
    return {
        "schema": SCHEMA_VERSION,
        "kind": kind,
        "generated_at": utc_now_iso(),
        "root": scan.get("root"),
        "rules_schema": rules.schema,
        "classify_cache_id": f"{scan.get('root')}|{scan.get('ended_at')}",
        "actions": [a.to_dict() for a in actions],
        "summary": {
            "workspace_count": len(workspaces),
            "action_count": len(actions),
            "unsafe_count": unsafe,
        },
    }


def persist_plan(plan: dict[str, Any]) -> Path:
    """Write the plan to `$XDG_STATE_HOME/clain/plans/<kind>-<UTC>-v<schema>.json`.

    Spec 0016: filename includes the schema version (matching the spec-0014
    classify-cache pattern). Before writing, prune any stale-schema plan files
    older than the grace window so the disk doesn't accumulate dead plans.
    """
    kind = plan.get("kind", "plan")
    schema = int(plan.get("schema", SCHEMA_VERSION))
    stamp = utc_now_filename_stamp()
    out = plan_dir() / f"{kind}-{stamp}-v{schema}.json"
    prune_stale_plan_files(current_schema=SCHEMA_VERSION)
    write_json(out, plan)
    return out
