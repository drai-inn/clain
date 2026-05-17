# Specs

Every non-trivial change lands as a spec here before code. Specs are short, numbered, and traceable to a goal in [INTENT.md](../INTENT.md).

## Workflow

1. **Propose** — create `specs/NNNN-short-slug.md` using the template below. Status: `draft`.
2. **Agree** — user reviews. The goal-advisor agent (`.claude/agents/goal-advisor.md`) is the second pair of eyes that checks the spec against INTENT.
3. **Build** — status flips to `accepted`. Implementation may start. Commits should reference the spec number.
4. **Close** — when shipped, status flips to `shipped` with a one-line outcome. If abandoned, `dropped` with the reason.

Specs are not throwaway. They are the audit trail for *why* the code looks the way it does.

## Template

```markdown
---
id: NNNN
title: <short title>
status: draft   # draft | accepted | shipped | dropped
goal: <which INTENT goal this serves, e.g. "Goal 2: Deliberate cleanup">
---

## Problem
What is broken or missing today. One paragraph.

## Intent
What we want to be true after this lands. One paragraph. Must trace to INTENT.md.

## Spec
The concrete behaviour. Inputs, outputs, edge cases, failure modes. As terse as possible while still being unambiguous.

## Acceptance
Bulleted, checkable conditions. A reviewer (human or agent) can mark each ✅/❌.

## Out of scope
What this spec is deliberately *not* doing, to prevent scope creep during implementation.
```

## Numbering

Specs are numbered in creation order, zero-padded to 4 digits: `0001-…`, `0002-…`. Numbers are normally never reused, even if a spec is dropped.

**Exception (deliberately invoked once, 2026-05-18):** when an entire branch of the design is retracted in favour of a different model, the affected specs may be deleted outright and their numbers shuffled up rather than left as `dropped` placeholders. This happened with the original 0004 (Inventory of synced tree) → rewritten in place as *Classification scan*; the original 0005 (Duplication detection) was deleted entirely; the original 0006 (Recommendations) was superseded by the new 0005 (Executable plan model). The git history (after spec 0006 lands) is the durable record of what was retracted and why. Future invocations of this exception require an INTENT amendment and a goal-advisor verdict before the renumber happens.
