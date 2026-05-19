"""Per-command identity: meter level, emoji, name, plain-English intent line.

Spec 0016 § Part A. Every primary render opens with an anchor row of the form

    ▰▰▱▱▱  clain  🏷  classify --here

followed by a plain-English intent line describing what the command is *for*,
not what was typed. The mapping from a "command key" (a short stable string
like `classify_here` or `plan_recreate_dry`) to the four parts (level, emoji,
display name, intent) lives here so future commands add a single dataclass
entry rather than a new render branch.

The meter level is a 1..5 reading of where in the conceptual workflow the
command sits:

    1  install / setup        (no rendered commands here)
    2  classify               — what's there
    3  plan (dry)             — what would happen
    4  review (plan explain)  — examine one action
    5  execute                — currently gate-blocked

The five meter blocks are coloured with `theme.brand_step1..5` (cyan → red).
Outline blocks render in `theme.dim`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandIdentity:
    level: int  # 1..5
    emoji: str
    name: str  # display string, e.g. "classify --here"
    intent: str  # one plain-English sentence


# Command-key → identity. Keys are stable; tests pin them.
COMMAND_IDENTITIES: dict[str, CommandIdentity] = {
    "classify_tree": CommandIdentity(
        level=2,
        emoji="🏷",
        name="classify",
        intent=("Categorical scan across every workspace under the root — class tags, manifests, sync placement."),
    ),
    "classify_here": CommandIdentity(
        level=2,
        emoji="🏷",
        name="classify --here",
        intent=(
            "Categorical scan of this workspace — what's regenerable, what isn't, "
            "and the recreate command derived from your manifest."
        ),
    ),
    "plan_recreate_dry": CommandIdentity(
        level=3,
        emoji="♻️",
        name="plan recreate --dry",
        intent=(
            "Preview the delete-and-recreate plan. Nothing executes; this is the review step before the real thing."
        ),
    ),
    "plan_recreate_exec": CommandIdentity(
        level=5,
        emoji="♻️",
        name="plan recreate",
        intent=(
            "Delete + recreate cache-managed subtrees. Execution is currently "
            "gate-blocked; the plan is rendered for review."
        ),
    ),
    "plan_move_dry": CommandIdentity(
        level=3,
        emoji="📦",
        name="plan move --dry",
        intent=(
            "Preview the move-and-triage plan for workspaces in synced storage. Nothing moves; this is the review step."
        ),
    ),
    "plan_move_exec": CommandIdentity(
        level=5,
        emoji="📦",
        name="plan move",
        intent=(
            "Move workspace sources out of synced storage. Execution is currently "
            "gate-blocked; the plan is rendered for review."
        ),
    ),
    "plan_explain": CommandIdentity(
        level=4,
        emoji="💬",
        name="plan explain",
        intent="Full record for one action — preconditions, command, safety reasoning.",
    ),
}


def identity_for(key: str) -> CommandIdentity:
    """Look up identity; raises KeyError if the caller passed an unregistered key.

    Failing loudly is the right behaviour — a typoed key shouldn't render a
    blank anchor row. Adding a new command means adding its identity here.
    """
    return COMMAND_IDENTITIES[key]
