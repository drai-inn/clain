# clain (Claude Code plugin)

Thin Claude Code wrapper over the `clain` CLI.

## Boundary rule (load-bearing)

Per [spec 0001](../specs/0001-architecture.md), this plugin **must not** contain business logic. Skills, agents, commands, and hooks here may orchestrate, prompt, summarise, and render. They may **not** decide what to delete, compute what is duplicated, touch the filesystem, or hold any logic that isn't also reachable from the `clain` CLI binary. Any contribution that violates this rule is rejected on first read.

If a skill needs behaviour the CLI doesn't expose, the fix is to add a CLI subcommand first (via a spec), then have the skill shell out to it.

## Layout

```
plugin/
├── .claude-plugin/plugin.json   # manifest
├── skills/                      # one directory per skill
│   └── clain-version/SKILL.md
└── README.md                    # this file
```

## Skills

- **`clain-version`** — reports the installed CLI version by invoking `clain --version`. Reference implementation of the boundary rule: prose + a single Bash invocation, nothing else.

## Installing locally during development

This plugin is not yet packaged for distribution. To exercise it, point a local Claude Code session at the `plugin/` directory (mechanism depends on the Claude Code version in use; see Claude Code's plugin documentation for the current install path).

A future spec covers packaging and distribution.

## Assumed environment

The plugin assumes the `clain` binary is already on `PATH`. Bootstrapping the CLI from inside the plugin is deliberately out of scope (see spec 0003 § Out of scope).
