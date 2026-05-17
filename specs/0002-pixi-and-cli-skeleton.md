---
id: 0002
title: Pixi environment, Python package skeleton, and Rich-powered CLI entry point
status: shipped
goal: Goal 4 (Portability) — establishes the contract surface (CLI) defined by spec 0001
---

## Problem

Spec 0001 locked in a Python CLI named `clain`, managed by Pixi, as the project's contract surface. Nothing exists yet. Before any feature spec (0004 onward) can be implemented, the CLI has to be runnable end-to-end — `clain --version` must work from a fresh clone with a single Pixi command. Without this, every later spec re-litigates "how do I run anything?".

## Intent

A reproducible Pixi environment, a `src/`-layout Python package, and a CLI entry point that renders with Rich. The smallest possible thing that proves the contract surface is real and pleasant to use. Anyone cloning the repo should reach a working `clain` in two commands (`pixi install`, then run).

## Spec

**Python version.** Pin to Python 3.12 in `pixi.toml`. (3.13 is fine too; pick the higher one supported by Pixi's `conda-forge` channel at scaffolding time and write that version into the spec on implementation.)

**Pixi setup.** `pixi.toml` at the repo root defines:
- A default feature/environment with runtime deps: `python`, `typer`, `rich`.
- A `dev` feature adding: `pytest`, `ruff`, `mypy`.
- Tasks: `pixi run clain` (invokes the CLI), `pixi run test`, `pixi run lint`, `pixi run typecheck`.

No `requirements.txt`, no `setup.py`, no `poetry.lock`. Pixi is the single source of truth for the env.

**Package layout.**

```
clain-me/
├── pixi.toml
├── pyproject.toml          # PEP 621 metadata + entry point only
└── src/
    └── clain/
        ├── __init__.py     # __version__ = "0.0.1"
        ├── __main__.py     # enables `python -m clain`
        ├── cli.py          # Typer app, subcommand wiring
        └── console.py      # shared Rich Console instance
```

`pyproject.toml` declares the console script: `clain = "clain.cli:app"`.

**CLI framework.** [Typer](https://typer.tiangolo.com/) for command dispatch (it uses Rich for help text by default). [Rich](https://rich.readthedocs.io/) for all human-facing output — never bare `print()`. All output goes through the shared `Console` in `clain/console.py` so themes, redirection, and `--no-color` work uniformly.

**Subcommands in scope for this spec.**

- `clain --version` → prints `clain <version>` (the version from `clain.__version__`).
- `clain hello [NAME]` → renders a Rich `Panel` greeting. Exists purely to prove the Rich path end-to-end. May be removed once 0004 lands a real subcommand; if so, that removal is noted in 0004's "out of scope" / "supersedes" section.

**Output discipline (sets precedent for later specs).**

- Human output: Rich (tables, panels, progress, syntax-highlighted JSON).
- Machine output: `--json` flag on any command that produces structured data → emits a single JSON document to stdout, no Rich styling, suitable for piping. (Not required on `hello`; required from 0004 onward.)
- Errors: Rich-rendered to stderr; exit codes non-zero. JSON mode errors emit a JSON error object to stderr.

**Tooling baseline.**

- `ruff` for lint + format (configured in `pyproject.toml`).
- `mypy --strict` on `src/clain/`.
- `pytest` with one smoke test: `clain --version` exits 0 and prints a version string.

## Acceptance

- [ ] `pixi install` from a fresh clone produces a working env.
- [ ] `pixi run clain --version` prints `clain 0.0.1` (or whatever the package version is).
- [ ] `pixi run clain hello` renders a Rich Panel without errors.
- [ ] `pixi run test` passes the smoke test.
- [ ] `pixi run lint` and `pixi run typecheck` both pass on the skeleton.
- [ ] Nothing in the repo writes outside `clain-me/` at runtime — verified by running the CLI and checking no files appear in `$HOME` or elsewhere. (State-writing comes in 0004.)
- [ ] `.gitignore` excludes `.pixi/`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/`, `*.egg-info/`.

## Out of scope

- The Claude Code plugin (spec 0003).
- Any real feature behaviour (spec 0004+).
- Distribution beyond `pixi run` and editable install — no `pixi global install`, no PyPI, no PyInstaller. Picked up in a later spec.
- Logging framework choice. Rich's console is enough for now; a structured logger arrives when 0004 needs persisted audit trails.
- Config file format. No config yet; the `hello` command takes only a positional arg.
