"""Typography constants for clain's primary renders (spec 0014).

The values here are not magic — each is a deliberate choice grounded in
making the output rhythm readable across terminal widths:

- `BODY_INDENT` / `META_INDENT` (2 spaces) match the leading indent
  every renderer already uses for body content. Meta lines (cached /
  dry-mode asides) get the same indent so they sit *under* the body
  visually rather than out at col 0.
- `RULE_WIDTH` (72) is the standard comfortable line measure used by
  most prose linters and CLI tools. A full-width rule on a 200-col
  terminal reads as a horizontal scar; 72 chars reads as punctuation.
- `SECTION_GAP` / `META_GAP` (1) — one blank line between named sections
  and around `Rule()`s. Tested for, not assumed.

Renderers import the constants rather than hard-coding the values.
"""

from __future__ import annotations

# Blank lines between named sections in a render.
SECTION_GAP = 1

# Blank lines before status/meta lines (cached, dry-mode).
META_GAP = 1

# 2 spaces — the leading indent for body content.
BODY_INDENT = "  "

# Status/meta lines indent matches body, not col 0.
META_INDENT = "  "

# Fixed measure for Rule()s — punctuation, not architecture.
RULE_WIDTH = 72
