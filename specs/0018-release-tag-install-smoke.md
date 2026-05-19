---
id: 0018
title: Release-tag install smoke workflow
status: draft
goal: Goal 2 (Deliberate execution — the documented install path must actually work, not just be claimed to); Goal 8 (Reviewable evolution — a release cut should verify the user-facing contract automatically).
---

## Why

Spec 0015 documents `pipx install git+…` and `pixi global install --git …` as the supported end-user install paths and relies on `[project.scripts] clain = "clain.cli:app"` to produce a binary on PATH. The two install channels have failure modes (resolver behaviour, PATH-shimming, console-script entry-point packaging) that unit tests cannot reach. Spec 0015 originally listed these as "smoke-test by hand" acceptance items; manual checklist items with no forcing function rot the moment a PR merges.

The right enforcement is a CI job that fires on release-tag push and asserts both install paths produce a working `clain --version` matching `pyproject.toml`. This spec captures that workflow.

## Scope

One GitHub Actions workflow at `.github/workflows/release-install-smoke.yml`:

- **Trigger.** `push` on tags matching `v*` (and `workflow_dispatch` for manual reruns against an existing tag).
- **Job 1 — pipx channel.** Ubuntu runner; install pipx; run `pipx install "git+https://github.com/drai-inn/clain.git@${GITHUB_REF_NAME}"`; assert `clain --version` exit 0 and version string matches the `version =` field in `pyproject.toml` at the tagged commit.
- **Job 2 — pixi-global channel.** Ubuntu runner; install pixi via its official installer; run `pixi global install --git "https://github.com/drai-inn/clain.git" --branch "${GITHUB_REF_NAME}" clain` (or the pixi-global equivalent flag for tags as of pixi's current release); same `clain --version` assertion.
- **Failure semantics.** Either job failing blocks the release. The workflow's status is the gate; no auto-rollback of the tag (manual decision).

Both jobs run in parallel. Total wall-clock budget: under 5 minutes.

## Out of scope

- Running these on every PR. Too slow, too network-heavy, and the install path doesn't change PR-to-PR — only at release time. (A contributor who wants to verify pre-tag can run the commands locally; the workflow file itself documents them.)
- macOS / Windows runners. pipx + pixi-global both target Linux as the primary surface; cross-platform expansion is a future spec when there's demonstrated demand.
- Homebrew / Nix / Debian packaging recipes — already out of scope in 0015 and stay deferred.
- A self-update mechanism (`clain self update`). Defer.
- Publishing to PyPI. Separate concern; if/when we cut a PyPI release, that's its own spec.

## Files touched

- **`.github/workflows/release-install-smoke.yml`** — new file, the workflow itself.
- **`specs/0015-global-entry-and-error-sweep.md`** — already amended (this spec's prerequisite) to point its install-path acceptance item here.
- **`CHANGELOG.md`** — Unreleased entry when the workflow lands, noting the install-path verification gate.

No code change in `src/clain/`. No test change in `tests/`.

## Acceptance

- [ ] `.github/workflows/release-install-smoke.yml` exists.
- [ ] Workflow triggers on `v*` tag push and `workflow_dispatch`.
- [ ] pipx job installs from the tagged commit and asserts `clain --version` matches `pyproject.toml`.
- [ ] pixi-global job does the equivalent.
- [ ] At least one dry-run via `workflow_dispatch` against the most recent tag (or a temporary `v0.0.0-smoke` tag pushed and deleted) shows both jobs green.
- [ ] CHANGELOG entry added.
- [ ] PR follows the workflow template.
