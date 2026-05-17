from __future__ import annotations

from pathlib import Path

import pytest

from clain.rules_loader import (
    DEFAULT_RULES_PATH,
    RulesLoadError,
    load_rules,
)


@pytest.fixture(autouse=True)
def _clear_loader_cache() -> None:
    """Rules loader is lru_cache'd; clear between tests so fixture paths work."""
    load_rules.cache_clear()


def test_default_rules_load_and_validate() -> None:
    rules = load_rules()
    assert rules.schema == 1
    assert len(rules.classes) >= 3
    assert "node_modules" in rules.all_class_dirs
    assert rules.class_of("node_modules") == "cache-managed"
    assert rules.class_of("dist") == "ephemeral"
    assert rules.class_of("__pycache__") == "bytecode"
    assert rules.class_of("not-a-class") is None


def test_default_rules_priority_ordering() -> None:
    rules = load_rules()
    # pixi.toml (priority 10) should win over pyproject.toml (priority 90).
    manifests_in_order = [r.manifest for r in rules.recreate_rules]
    assert manifests_in_order.index("pixi.toml") < manifests_in_order.index("pyproject.toml")
    assert manifests_in_order.index("pnpm-lock.yaml") < manifests_in_order.index("package.json")


def test_default_rules_unsafe_recreate_carries_reason() -> None:
    rules = load_rules()
    bare_pyproject = rules.recreate_for("pyproject.toml")
    assert bare_pyproject is not None
    assert bare_pyproject.safe is False
    assert bare_pyproject.unsafe_reason is not None
    assert "ambiguous" in bare_pyproject.unsafe_reason.lower()


def test_default_rules_placements_per_ecosystem() -> None:
    rules = load_rules()
    pnpm = rules.placement_for("pnpm")
    assert pnpm is not None
    assert "pnpm" in pnpm.store_advice.lower()
    assert pnpm.doc_url.startswith("https://")


def test_rules_path_default() -> None:
    assert DEFAULT_RULES_PATH.name == "rules.toml"
    assert DEFAULT_RULES_PATH.exists()


def test_duplicate_directory_names_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
        schema = 1

        [[classes]]
        name = "a"
        description = "x"
        default_action = "delete"
        directory_names = ["shared"]

        [[classes]]
        name = "b"
        description = "x"
        default_action = "delete"
        directory_names = ["shared"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(RulesLoadError, match="shared"):
        load_rules(bad)


def test_invalid_default_action_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
        schema = 1

        [[classes]]
        name = "a"
        description = "x"
        default_action = "rm-and-pray"
        directory_names = ["foo"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(RulesLoadError, match="default_action"):
        load_rules(bad)


def test_unsupported_schema_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("schema = 99\n", encoding="utf-8")
    with pytest.raises(RulesLoadError, match="schema"):
        load_rules(bad)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(RulesLoadError, match="not found"):
        load_rules(tmp_path / "does-not-exist.toml")
