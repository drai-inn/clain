"""Anonymisation check: no personal information in public-facing files.

Spec 0007 § 8 established the discipline for `examples/`. Spec 0008 extends it
to README.md, SECURITY.md, and CHANGELOG.md — the public docs that someone
landing on the GitHub repo reads first.

Mirrors the way spec 0003 made the boundary rule grep-testable.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_ROOT = REPO_ROOT / "examples"

# Personal-info needles forbidden in public-facing files.
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

PUBLIC_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "SECURITY.md",
    REPO_ROOT / "CHANGELOG.md",
)


def _example_files() -> list[Path]:
    if not EXAMPLES_ROOT.is_dir():
        return []
    return sorted(p for p in EXAMPLES_ROOT.rglob("*") if p.is_file())


def _check_files(files: list[Path]) -> list[tuple[Path, str]]:
    offending: list[tuple[Path, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                offending.append((path, needle))
    return offending


def test_examples_directory_exists() -> None:
    assert EXAMPLES_ROOT.is_dir(), f"examples/ directory missing at {EXAMPLES_ROOT}"


def test_examples_contain_no_personal_info() -> None:
    files = _example_files()
    assert files, "no files found under examples/"
    offending = _check_files(files)
    assert not offending, "Personal-info leak in examples/: " + ", ".join(
        f"{p.name} contains {n!r}" for p, n in offending
    )


def test_public_docs_contain_no_personal_info() -> None:
    """Spec 0008: README.md, SECURITY.md, CHANGELOG.md must follow the same discipline as examples/."""
    present = [p for p in PUBLIC_DOCS if p.is_file()]
    offending = _check_files(present)
    assert not offending, "Personal-info leak in public docs: " + ", ".join(
        f"{p.name} contains {n!r}" for p, n in offending
    )


def test_security_md_phase_gate_framing() -> None:
    """Spec 0008: SECURITY.md must describe the phase gate as a *design property*,
    not as a hardening / security control. This prevents a future edit from
    quietly reframing EXECUTE_ENABLED as a security knob that could be relaxed.

    Explicit *negations* of the forbidden framings are allowed (and encouraged) —
    the spec wants SECURITY.md to actively rule out the wrong reading. We strip
    those negations before checking that the bare framings don't sneak in.
    """
    security_md = REPO_ROOT / "SECURITY.md"
    if not security_md.is_file():
        return  # Test no-op until the file exists; acceptance bullet enforces presence.
    text = security_md.read_text(encoding="utf-8").lower()

    forbidden_framings = (
        "hardening",
        "defence in depth",
        "defense in depth",
        "security boundary",
        "security control",
    )
    # Phrases that explicitly rule out the forbidden framing — these are allowed
    # because they actively prevent the misreading the test exists to catch.
    allowed_negations = (
        "not a hardening control",
        "not a hardening",
        "not a security boundary",
        "not a security control",
        "not defence in depth",
        "not defense in depth",
    )

    cleaned = text
    for negation in allowed_negations:
        cleaned = cleaned.replace(negation, "")

    offending = [phrase for phrase in forbidden_framings if phrase in cleaned]
    assert not offending, (
        f"SECURITY.md frames the phase gate using forbidden hardening language: {offending}. "
        "The phase gate must be described as a design property, not a security control. "
        "Explicit negations like 'not a hardening control' are allowed."
    )
