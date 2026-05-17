"""Anonymisation check: no personal information in examples/.

Spec 0007 § 8 mandates that no file under examples/ contain any of the personal-
info needles listed below. Mirrors the way spec 0003 made the boundary rule
grep-testable.
"""

from __future__ import annotations

from pathlib import Path

EXAMPLES_ROOT = Path(__file__).resolve().parent.parent / "examples"

# Personal-info needles forbidden in examples/.
#
# Note: `~/Library/pnpm/store`, `~/Library/Caches/pypoetry/...` and similar are
# canonical macOS placement advice — not personal info — so we do not forbid
# `~/Library/` outright. We forbid only patterns that identify a specific user
# or machine (GoogleDrive paths, real usernames, absolute /Users/<name>/ paths).
FORBIDDEN_SUBSTRINGS = (
    "GoogleDrive",
    "CloudStorage",
    "njon001",
    "clain-me",
    "nick@",
    "/Users/",
)


def _example_files() -> list[Path]:
    if not EXAMPLES_ROOT.is_dir():
        return []
    return sorted(p for p in EXAMPLES_ROOT.rglob("*") if p.is_file())


def test_examples_directory_exists() -> None:
    assert EXAMPLES_ROOT.is_dir(), f"examples/ directory missing at {EXAMPLES_ROOT}"


def test_examples_contain_no_personal_info() -> None:
    files = _example_files()
    assert files, "no files found under examples/"
    offending: list[tuple[Path, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                offending.append((path, needle))
    assert not offending, "Personal-info leak in examples/: " + ", ".join(
        f"{p.name} contains {n!r}" for p, n in offending
    )
