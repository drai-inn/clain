"""Validate that all skills under skills/ conform to the Agent Skills spec.

Reference: https://agentskills.io/specification
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
OPTIONAL_FRONTMATTER_FIELDS = (
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
)


def _read_frontmatter(skill_md: Path) -> dict[str, str]:
    """Tiny YAML-frontmatter reader. Only supports flat string fields, which is
    all the Agent Skills spec requires at this validation depth."""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{skill_md}: missing opening '---' frontmatter delimiter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise AssertionError(f"{skill_md}: missing closing '---' frontmatter delimiter")
    block = text[4:end]
    fields: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _skill_dirs() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return [p for p in SKILLS_ROOT.iterdir() if p.is_dir()]


def test_skills_directory_exists() -> None:
    assert SKILLS_ROOT.is_dir(), f"top-level skills/ directory missing at {SKILLS_ROOT}"


def test_each_skill_has_skill_md() -> None:
    skills = _skill_dirs()
    assert skills, "no skills found under skills/"
    for skill_dir in skills:
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file(), f"missing {skill_md}"


def test_each_skill_frontmatter_required_fields() -> None:
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        fields = _read_frontmatter(skill_md)
        for required in REQUIRED_FRONTMATTER_FIELDS:
            assert required in fields, f"{skill_md}: missing required field '{required}'"
            assert fields[required], f"{skill_md}: field '{required}' is empty"


def test_each_skill_name_matches_directory() -> None:
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        fields = _read_frontmatter(skill_md)
        name = fields.get("name", "")
        assert name == skill_dir.name, f"{skill_md}: name '{name}' must equal parent directory name '{skill_dir.name}'"


def test_each_skill_name_is_kebab_case_and_bounded() -> None:
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        fields = _read_frontmatter(skill_md)
        name = fields.get("name", "")
        assert 1 <= len(name) <= 64, f"{skill_md}: name length out of range (1..64): {len(name)}"
        assert NAME_RE.match(name), (
            f"{skill_md}: name '{name}' must be lowercase kebab-case "
            f"(letters, digits, single hyphens; no leading/trailing/consecutive hyphens)"
        )


def test_each_skill_description_bounded() -> None:
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        fields = _read_frontmatter(skill_md)
        desc = fields.get("description", "")
        assert 1 <= len(desc) <= 1024, f"{skill_md}: description length out of range (1..1024): {len(desc)}"


def test_each_skill_body_drives_the_cli_not_inline_logic() -> None:
    """Spec 0001 boundary rule: skill body must not contain business logic.

    Operationalised as: no Python source, no version literals, no imports.
    The skill body must mention shelling out to the `clain` CLI.
    """
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        body_start = text.find("\n---\n", 4) + len("\n---\n")
        body = text[body_start:]
        # Must reference the CLI.
        assert "clain" in body, f"{skill_md}: body must reference the `clain` CLI"
        # Must not contain Python source or imports.
        assert "import " not in body, f"{skill_md}: body contains Python `import` statement"
        # Must not hardcode a version literal like 0.0.1.
        assert not re.search(r"\b\d+\.\d+\.\d+\b", body), (
            f"{skill_md}: body contains a version literal (would duplicate CLI source-of-truth)"
        )
