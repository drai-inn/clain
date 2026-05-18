# Security policy

This document covers the threat model and reporting process for `clain`. Read this before reporting; it sets expectations about what is and isn't a security concern in this project.

## Supported versions

`clain` is pre-1.0. Only the latest commit on `main` is supported. There are no backported fixes for older commits.

## What `clain` does and doesn't do (relevant to security)

- **Read-only against the scanned root by design.** `clain classify` and `clain plan` perform no filesystem mutation against any path under the developer's `CLAIN_DEV_ROOT`. The full mutation-vector ban list is enforced by tests (`test_classify_module_does_not_modify_root` and the import-graph test on `clain.executor`).
- **No network I/O.** `clain` makes no HTTP requests, opens no sockets, and contacts no external services. There is no telemetry.
- **No process spawning while the phase gate is closed.** `clain.executor` imports no `subprocess`/`shutil`/`socket`/`urllib`/clipboard modules, and a static import-graph test asserts this.
- **Plans contain shell commands intended for the developer to execute.** A plan's `commands` array may include `rm -rf <path>`, `rsync …`, `pnpm install`, etc. The developer is responsible for inspecting plan contents before copy-pasting commands or, in the future, before enabling execution. Plans are deliberately preview-only today.
- **Writes stay inside `$XDG_STATE_HOME/clain/`.** Caches, plan JSON, and logs land there. Nothing is written under the project working tree or under the scanned root.

## The phase gate is a design property, not a security control

`EXECUTE_ENABLED = False` in [src/clain/executor.py](src/clain/executor.py) blocks real execution while the project is in its development phase. **This is a design property of the project's pre-execution phase, not a hardening control.** It exists so that the executable plan format can be exercised end-to-end before any commit is made to run things. Lifting the gate is the explicit job of a future named spec — *00NN — Lift the dry-run gate* — which must specify rollback, audit, and additional safety mechanisms.

Please do not report "the phase gate could be bypassed by editing one constant" as a security issue. It is not a security boundary. The contributor process is the boundary; the constant is the implementation.

## How to report a security issue

Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on this repository:

→ https://github.com/drai-inn/clain/security/advisories/new

If that's unavailable, open a minimal public issue saying only "Please contact me about a security topic via private channel" and we'll arrange a private channel.

## What is *not* a security issue

To set expectations and conserve attention, the following are not security issues:

- **The phase gate raising errors.** That is its intended behaviour.
- **Plans containing destructive-looking commands.** `rm -rf <node_modules>` is the correct delete action; the safety story is the dry-run preview and the developer's review, not the absence of such commands.
- **Dependencies declared in `pyproject.toml`.** Versions are pinned by `pixi.lock`. Report supply-chain concerns about specific packages upstream; if you believe `clain` itself selects an unsafe version, that's worth raising via a normal feature-request issue and a follow-up spec.
- **`rules.toml` allowing additions.** The rule base is intentionally extensible — by hand or by an agent. The loader's duplicate-directory check is the structural guardrail, not access control.
- **Personal information being absent from `examples/`, README, SECURITY.md, or CHANGELOG.md.** That's a project discipline, not a vulnerability; the test suite enforces it.
