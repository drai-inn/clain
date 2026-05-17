---
id: 0006
title: Git + GitHub workflow for the clain repo itself
status: shipped
goal: Goal 8 (Version-controlled, reviewable evolution)
---

## Problem

The `clain-me` working directory is not currently a git repository. INTENT now states that this project tracks its own changes via git on a defined remote with a pull-request practice (goal 8). Without an initial commit and a published remote, every spec landed so far has no review record beyond this conversation — and the goal-advisor + tests cannot serve as PR gates if there are no PRs.

## Intent

Initialise `~/dev/clain-me/` as a git repository, make a baseline commit of the current shipped state, create a public GitHub repository named `clain` under the developer's account, push the baseline, and adopt a feature-branch + pull-request practice going forward. Use the `gh` CLI for all GitHub-side operations. The workflow itself becomes the review gate for future spec/code changes.

## Spec

**Local repo setup.**

- `git init` at `~/dev/clain-me/`.
- Configure local user identity for this repo only (do not touch global git config) — name and email matching the developer's preferred public attribution.
- Existing `.gitignore` is reviewed and extended for the broader scope: caches, scratch state, OS artefacts, IDE configs, Pixi env dir.
- A small `LICENSE` file is added before publishing (public repo) — choice between MIT and Apache 2.0 is the developer's call at PR time, not specced here.
- Baseline commit message: `chore: initial commit — specs 0001–0006 + skeleton CLI` (or current equivalent). The commit message references the specs that were already shipped during the pre-git phase, so the audit trail starts honestly.

**Remote setup (GitHub).**

- Repo name: `clain`. Local directory name `clain-me` is left unchanged.
- Visibility: public.
- Created via `gh repo create clain --public --source=. --remote=origin --push`. No description/topics are baked into this spec; the developer can set those on the GitHub side.
- The repo's default branch is `main`.

**Going-forward workflow.**

- Every non-trivial change lands on a feature branch named after the spec being implemented or amended: `spec/0007-foo`, `fix/classify-edge-case`, `docs/readme`.
- The PR description references the spec(s) it implements, includes the goal-advisor verdict (paste from agent output), and confirms tests/lint/typecheck pass.
- PRs are reviewed (by the developer, by the goal-advisor agent, or by future collaborators); CI integration is a later spec.
- Direct pushes to `main` are reserved for trivia (typo fixes, dependency bumps); everything else goes through a PR.
- Spec status transitions (`draft` → `accepted` → `shipped`/`dropped`) happen in the same PR that lands the implementation, so the spec file's git history reflects when it was actually realised.

**Pre-publish review (public repo discipline).**

Before `gh repo create --push`, verify:

- No personal email addresses or absolute home-directory paths in source defaults. (Spec 0004 has already moved the `CLAIN_DEV_ROOT` default away from a hardcoded GDrive path; this spec confirms it landed before publication.)
- No secrets or `.env` files staged.
- `pyproject.toml` and `pixi.toml` author email reflect the developer's chosen public attribution.
- A short `README.md` (already present) gives a public-friendly overview without baking in machine-specific instructions.

**Out of bounds for this spec.**

- CI configuration (GitHub Actions). A later spec covers it.
- Branch protection rules, required reviewers, signing requirements.
- Release tagging / semver. The project is pre-1.0 throughout this spec set.
- Migrating any of the legacy synced-tree workspaces into git. That is independent work the developer does per workspace.

## Acceptance

- [ ] `~/dev/clain-me/.git` exists and the baseline commit is reachable as `HEAD`.
- [ ] `gh repo view clain` returns a public repo under the developer's account, with `main` as default branch and the baseline commit visible.
- [ ] `origin` remote in the local repo points at the GitHub repo.
- [ ] CLAUDE.md is updated to document the feature-branch + PR practice and the `gh` CLI dependency.
- [ ] Pre-publish review passes: no personal email or absolute paths in source defaults; no secrets staged; LICENSE present.
- [ ] First post-baseline PR follows the workflow (branch name, spec reference, advisor verdict in description) — exercised by whichever spec lands next.

## Out of scope

- GitHub Actions / CI. Separate spec when it bites.
- Signed commits or signed tags.
- Issue templates, PR templates beyond the conventions stated above.
- Mirror to GitLab or any second remote.
- Pre-commit hook framework. Useful, but not blocking this spec.
