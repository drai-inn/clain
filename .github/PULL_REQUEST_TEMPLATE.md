<!--
  The template below mirrors the one in CONTRIBUTING.md § PR template.
  See https://github.com/drai-inn/clain/blob/main/CONTRIBUTING.md for the full
  workflow including the goal-advisor pattern and quality gates.
-->

## Spec reference

Lands [specs/NNNN-slug.md](specs/NNNN-slug.md) as `shipped` (or amends it; or addresses fix XYZ).

## Goal-advisor verdict

<!--
Paste the goal-advisor's verdict block here, in this exact shape:

> Spec NNNN
> Verdict: aligned
> Goal(s) it serves: …
> Reasoning: …
> Recommended next step: proceed

If the verdict was `tighten`, apply the tightenings *before* opening the PR and note them under "Tightenings applied" below.
-->

## Acceptance bullets

<!--
Copy the acceptance bullets from the spec and mark each ✓ with evidence (a code
link, test name, or screenshot). Reviewers should be able to confirm every
acceptance bullet without leaving the diff.
-->

- [ ] (bullet 1 from the spec)
- [ ] (bullet 2 from the spec)
- [ ] PR follows the template in CONTRIBUTING.md.

## Checks

- `pixi run -e dev test` → N passed
- `pixi run -e dev lint` → clean
- `pixi run -e dev typecheck` → clean

## Notes (optional)

<!-- Anything reviewers should know that isn't covered above. -->
