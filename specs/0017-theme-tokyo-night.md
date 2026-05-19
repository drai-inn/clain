---
id: 0017
title: Tokyo Night theme (dark + light) with automated terminal-background detection
status: draft
goal: Goal 1 (Categorical visibility — colour should help the reader recognise classes, safety, and brand at a glance, not just be there for decoration); Goal 8 (Reviewable evolution — colours expressed as named tokens are reviewable; raw hex sprinkled through renderers is not)
---

## Problem

Today's palette is the Rich/ANSI defaults — `green`, `yellow`, `cyan`, `red`, `magenta`, `dim`. Three concrete issues:

1. **Bland and inconsistent.** Eight terminal-default colour names get reused across renderers with no design coherence. The same `yellow` carries "warning"-ish meaning in some places and "class label" meaning in others; the same `cyan` is brand-ish in one render and path-ish in another. Reuse without a token system means the colours don't *signal*.
2. **Terminal-theme-dependent.** The Rich defaults render however the terminal palette says. On a user's light terminal the dim-grey body text is barely legible; on a heavily-themed dark terminal the cyan brand is the same colour as the comment text. We have no control over what the user actually sees.
3. **No first-class light/dark distinction.** The few colour choices we made (mostly the spec-0013 `[green]✓[/]` / `[red]✗[/]`) work fine on both backgrounds, but they're the floor, not the design. Spec 0016 introduces a 5-block brand meter and per-command emoji; those need a coherent palette to anchor against.

## Intent

A small theme system that:

- Defines named tokens (`brand`, `safe`, `unsafe`, `warning`, `dim`, `class.cache_managed`, …) at module scope.
- Resolves each token to a 24-bit hex colour from the Tokyo Night palette — dark or light variant — based on the user's terminal background.
- **Detects the terminal background automatically** via `COLORFGBG`, with a graceful fallback to "dark" when unknown (the conservative choice; most CLI users on dark terminals).
- Allows manual override via `--theme dark|light|auto` and `CLAIN_THEME=…`, same precedence pattern as `--legend` (spec 0013) and `--banner` (spec 0016).
- Respects `NO_COLOR` (drops colour entirely; the existing Rich behaviour, codified).
- Replaces every `[green]`, `[yellow]`, etc. in `src/clain/ui/tables.py` with a token. No renderer ever names a colour directly.

No behaviour change. No JSON change. No new visible CLI semantics beyond `--theme`.

## Spec

### The token map

A new module `src/clain/ui/theme.py` defines a `Theme` dataclass and two named instances (`TOKYO_NIGHT_DARK`, `TOKYO_NIGHT_LIGHT`).

```python
@dataclass(frozen=True)
class Theme:
    # Brand identity (spec 0016 meter + name).
    brand: str
    brand_step1: str  # cyan-most
    brand_step2: str
    brand_step3: str  # core brand
    brand_step4: str
    brand_step5: str  # warmest, used for the highest-stakes (execute) step

    # Semantic status.
    safe: str         # ✓ marks; "this is safe to execute"
    unsafe: str       # ✗ marks; "this blocks safe execution"
    warning: str      # ⚠ in synced storage
    fix: str          # the literal-command-to-fix line in user_error (spec 0015)

    # Body and meta.
    fg: str           # default foreground
    dim: str          # dim-styled text (status asides, etc.)
    accent: str       # subtle accent (table headers, key column)

    # Per-class colours (class tags in classify; class column in plan).
    class_cache_managed: str
    class_bytecode: str
    class_ephemeral: str
    class_unknown: str   # for any future class not in the spec-0009 set
```

#### Tokyo Night Dark values

| Token | Hex | Tokyo Night source |
|---|---|---|
| `brand` | `#bb9af7` | purple (brand step 3) |
| `brand_step1` | `#7dcfff` | cyan |
| `brand_step2` | `#7aa2f7` | blue |
| `brand_step3` | `#bb9af7` | purple |
| `brand_step4` | `#ff9e64` | orange |
| `brand_step5` | `#f7768e` | red |
| `safe` | `#9ece6a` | green |
| `unsafe` | `#f7768e` | red |
| `warning` | `#e0af68` | yellow |
| `fix` | `#7dcfff` | cyan |
| `fg` | `#c0caf5` | foreground |
| `dim` | `#565f89` | dark5 |
| `accent` | `#bb9af7` | purple (matches brand) |
| `class_cache_managed` | `#e0af68` | yellow (cache = "valuable but rebuildable") |
| `class_bytecode` | `#7aa2f7` | blue (transient artefact) |
| `class_ephemeral` | `#bb9af7` | purple (build output) |
| `class_unknown` | `#9aa5ce` | foreground-grey |

#### Tokyo Night Light values

Official Tokyo Night Light hexes, not just darkened darks — the palette has different ratios for legibility on warm-off-white backgrounds.

| Token | Hex |
|---|---|
| `brand` | `#5a4a78` |
| `brand_step1` | `#007197` |
| `brand_step2` | `#34548a` |
| `brand_step3` | `#5a4a78` |
| `brand_step4` | `#b15c00` |
| `brand_step5` | `#8c4351` |
| `safe` | `#485e30` |
| `unsafe` | `#8c4351` |
| `warning` | `#8f5e15` |
| `fix` | `#007197` |
| `fg` | `#343b58` |
| `dim` | `#9699a3` |
| `accent` | `#5a4a78` |
| `class_cache_managed` | `#8f5e15` |
| `class_bytecode` | `#34548a` |
| `class_ephemeral` | `#5a4a78` |
| `class_unknown` | `#6c6e75` |

(Hex values lifted from the upstream Tokyo Night repo's `tokyonight_day.lua` and `tokyonight_night.lua` palette files.)

### Resolution: how `clain` picks dark vs light

A function `resolve_theme(flag: str | None, env: str | None, colorfgbg: str | None, no_color: bool) -> Theme | None`:

1. **`NO_COLOR` set** → return `None` (no colour applied; callers see plain text). This is the existing convention, codified.
2. **Explicit `--theme dark|light`** → return the matching theme.
3. **Explicit `--theme auto`** → fall through to detection (same as if the flag were absent).
4. **`CLAIN_THEME=dark|light`** → return the matching theme.
5. **`CLAIN_THEME=auto` or unset** → detect:
   - **`COLORFGBG` env var present.** Format is `fg;bg` (sometimes `fg;ig;bg` for older terminals). Parse the last segment as the background colour index. Values `0–7` are dark backgrounds; `8–15` and `default` typically light; some terminals report symbolic strings like `15;default`. Map: index ≤ 7 ⇒ dark; index ≥ 8 ⇒ light; unparseable ⇒ fall through.
   - **OSC 11 escape sequence query** (`\x1b]11;?\x07`). Send to stdout; read terminal response on stdin with a short timeout (50ms). If the terminal answers with `rgb:RRRR/GGGG/BBBB`, average the luminance; > 0.5 ⇒ light, else dark. Skipped when stdout isn't a TTY (no terminal to query) or when stdin isn't a TTY (no response channel). Times out cleanly.
   - **Fallback** when neither detector resolves: **dark**. The conservative default — clain's audience skews dark-terminal — and any user on a light terminal can set `CLAIN_THEME=light` once in their shell rc.
6. **Unknown explicit values** (e.g. `--theme=blue`, `CLAIN_THEME=midnight`) → CLI error naming the valid vocabulary (`dark`, `light`, `auto`). Silently falling through would mask typos, same reasoning as spec 0013's `CLAIN_LEGEND` handling.

The `--theme` flag and `CLAIN_THEME` env var are processed in `cli.py`'s `@app.callback()` once, the resolved theme is stashed on a module-level singleton (or threaded through render-function kwargs), and every renderer references `theme.brand` etc. by token name. No renderer hard-codes hex anywhere.

### Renderer migration

Every Rich markup colour name in `src/clain/ui/tables.py` (plus any spec-0016 additions) maps to a token:

| Today | After |
|---|---|
| `[bold cyan]` (orientation header) | `[{theme.brand} bold]` |
| `[green]` (✓ safe glyph) | `[{theme.safe}]` |
| `[red]` (✗ unsafe glyph, error count) | `[{theme.unsafe}]` |
| `[yellow]` (warning, class column) | `[{theme.warning}]` (warnings) or class-specific token (class column) |
| `[bold yellow]` (class header in classify-here) | `[{theme.class_cache_managed} bold]` etc. — per class |
| `[dim]` (status asides) | `[{theme.dim}]` |
| `[cyan]` (paths, fix-line in user_error) | `[{theme.accent}]` (paths) or `[{theme.fix}]` (literal commands) |
| `[magenta]` (manifests column in tree view) | `[{theme.accent}]` |

A grep test pins the migration: `test_no_raw_color_names_in_renderers` greps `src/clain/ui/*.py` for `[red]`, `[green]`, `[yellow]`, `[cyan]`, `[magenta]`, `[blue]` and asserts zero hits outside of `theme.py` itself. (Style modifiers like `bold` / `dim` / `italic` are not colour names and stay raw.)

### Where the theme is applied

- Every primary render (classify single + tree; plan default + table) uses theme tokens.
- The spec-0016 brand meter + per-step colours use `theme.brand_step1..5`.
- The spec-0016 first-run banner renders in a five-row gradient using the same per-step colours.
- The spec-0015 `user_error(what, why, fix)` template uses `theme.unsafe` for the error headline and `theme.fix` for the fix line.

### Tests

- `test_theme_token_set_complete` — every field on the `Theme` dataclass is set on both `TOKYO_NIGHT_DARK` and `TOKYO_NIGHT_LIGHT`.
- `test_no_color_returns_none` — `resolve_theme(flag=None, env=None, colorfgbg=None, no_color=True)` returns `None`.
- `test_explicit_flag_overrides_env_and_detection` — `flag="dark", env="light", colorfgbg="0;15"` returns dark.
- `test_env_overrides_detection_when_no_flag` — `flag=None, env="light", colorfgbg="0;0"` returns light.
- `test_colorfgbg_dark_detection` — `colorfgbg="15;0"` returns dark.
- `test_colorfgbg_light_detection` — `colorfgbg="0;15"` returns light.
- `test_colorfgbg_unparseable_falls_back_to_dark` — `colorfgbg="garbage"` returns dark.
- `test_default_when_nothing_set` — all `None` returns dark.
- `test_unknown_theme_value_raises` — `flag="blue"` errors; `env="midnight"` errors.
- `test_no_raw_color_names_in_renderers` — grep all renderer modules for raw Rich colour names; assert zero hits outside `theme.py`.
- `test_renderer_uses_theme_tokens_e2e` — capture a classify render with `TOKYO_NIGHT_DARK`; assert the literal hex `#bb9af7` (or equivalent) appears in the markup-resolved output.
- (Skipped on CI — needs a TTY) `test_osc11_query_with_real_terminal` — interactive smoke test invoking the OSC 11 detector; documented as manual-only via a `pytest.mark.skip` reason.

### Documentation updates

- **README.md** — single screenshot showing the dark theme; one-line note that `CLAIN_THEME=light` switches the palette.
- **docs/USAGE.md** — new "Theme" subsection: token model, `--theme`, `CLAIN_THEME`, `NO_COLOR`, detection precedence, fallback to dark.
- **CHANGELOG.md** — Unreleased entry for spec 0017.
- **examples/capture.py** — capture in dark mode by default; one extra capture (`capture-classify-here-light.txt`) generated with `CLAIN_THEME=light` so the diff between palettes is visible.

## Acceptance

- [ ] `src/clain/ui/theme.py` exists, exports `Theme`, `TOKYO_NIGHT_DARK`, `TOKYO_NIGHT_LIGHT`, and `resolve_theme(…)`.
- [ ] No raw Rich colour names appear in `src/clain/ui/tables.py` or any other renderer module. `test_no_raw_color_names_in_renderers` passes.
- [ ] `--theme dark|light|auto` flag works on every primary command; `CLAIN_THEME` env var works at second-precedence; `NO_COLOR` strips colour entirely.
- [ ] Auto detection uses `COLORFGBG` then OSC 11; falls back to dark when neither resolves.
- [ ] Unknown `--theme` / `CLAIN_THEME` values are CLI errors naming the valid vocabulary.
- [ ] Brand meter renders the five-step gradient in the theme's brand-step colours.
- [ ] The spec-0016 first-run banner renders in five rows using the brand-step gradient.
- [ ] `user_error` (spec 0015) headlines render in `theme.unsafe`; the fix line renders in `theme.fix`.
- [ ] All tests above pass; lint, typecheck, full test suite clean.
- [ ] Docs swept; light + dark captures regenerated.
- [ ] CHANGELOG entry added.
- [ ] PR follows the workflow template.

## Out of scope

- Other themes (Catppuccin, Gruvbox, Nord, Solarized). Spec 0017 ships Tokyo Night dark + light only; once the token system exists, adding another theme is a one-file PR and a non-spec change.
- User-defined themes via TOML. Same reasoning — the token system enables it; the implementation is a future spec when there's demonstrated demand.
- 256-colour / 8-colour fallback for terminals that don't support truecolour. Most modern terminals do; for ones that don't, the truecolour hex degrades reasonably via Rich's own colour-system detection. If a contributor on a 256-colour terminal hits issues, we revisit.
- Theming the unsafe-actions banner from spec 0005 distinctly. Its red comes from `theme.unsafe` already; that's enough.
- Animations / colour transitions. Out of scope.

## Notes

- Tokyo Night was chosen over Catppuccin Mocha because (a) the dark variant has a slightly less saturated palette which reads better in a terminal that may also have other tools' output above/below clain's, and (b) the official light variant is a real design, not a brightness-flip of the dark variant. Catppuccin's light variant (Latte) is good too; the choice between them is mostly taste, and the user has expressed a preference.
- The OSC 11 detector is best-effort. Some terminals don't respond; some respond but slowly; some get confused by the query and leave junk on stdin. The 50ms timeout + tty-only-on-both-streams gating make this safe in CI and in non-interactive contexts. If the detector misbehaves in practice, the workaround is always `CLAIN_THEME=dark|light` in the shell rc.
- Light/dark *terminal* detection is genuinely hard cross-platform — `COLORFGBG` is the de facto standard but not universal. We accept that detection is imperfect and provide an explicit override; this is the right trade-off for a CLI.
- The token names are intentionally specific (`safe`, `unsafe`, `class_cache_managed`) rather than generic (`color1`, `color2`). A future contributor reading `[{theme.unsafe}]` immediately understands its semantic role; `[{theme.color5}]` would not survive review.
- This spec is presentation-only. It pairs with spec 0016 (which introduces new visual elements that need the palette), but neither blocks the other. If 0017 ships first, 0016 lands using `theme.brand` for everything until per-step granularity is needed; if 0016 ships first, the meter renders in single `brand` cyan until 0017 lands.
