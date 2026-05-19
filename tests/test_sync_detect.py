"""Tests for spec 0013 sync-placement autodetection.

Covers:
- Each pattern in SYNCED_STORAGE_PATTERNS detects its intended provider on macOS.
- A path outside all patterns returns ("local", None) on macOS.
- Non-macOS returns ("unknown", None) — the off-platform fallback.
- Hard-error on CLAIN_SYNCED_ROOT is tested in test_classify.py (CLI-level concern).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clain.sync_detect import SYNCED_STORAGE_PATTERNS, detect_synced_storage


def _expand(p: str) -> str:
    return p.replace("~", str(Path.home()), 1)


@pytest.mark.parametrize("prefix,expected_provider", list(SYNCED_STORAGE_PATTERNS))
def test_each_pattern_detects_its_provider(prefix: str, expected_provider: str) -> None:
    """Walking the canonical pattern list — each one must classify correctly."""
    fake_workspace = Path(_expand(prefix) + "/some/workspace")
    state, provider, matched_root = detect_synced_storage(fake_workspace, _platform="darwin")
    assert state == "synced"
    assert provider == expected_provider
    # matched_root is the expanded prefix that triggered detection — evidence.
    assert matched_root == _expand(prefix)


def test_sync_detect_returns_matched_root_on_synced() -> None:
    """Spec 0013: on a match, the third tuple element is the matched prefix path."""
    fake = Path(_expand("~/Library/CloudStorage/GoogleDrive-x@y/dev/foo"))
    state, provider, matched_root = detect_synced_storage(fake, _platform="darwin")
    assert state == "synced"
    assert provider == "Google Drive"
    assert matched_root == _expand("~/Library/CloudStorage/GoogleDrive-")


def test_local_path_returns_local_on_macos(tmp_path: Path) -> None:
    """A workspace under /tmp (or /private/var/folders) is not a synced pattern."""
    state, provider, matched_root = detect_synced_storage(tmp_path, _platform="darwin")
    assert state == "local"
    assert provider is None
    assert matched_root is None


def test_dev_directory_returns_local() -> None:
    """The user's local ~/dev/ tree (per INTENT) classifies as local."""
    ws = Path(_expand("~/dev/example-workspace"))
    state, provider, matched_root = detect_synced_storage(ws, _platform="darwin")
    assert state == "local"
    assert provider is None
    assert matched_root is None


def test_non_macos_returns_unknown(tmp_path: Path) -> None:
    """Off-macOS, we don't claim to know — sync placement is not autodetected."""
    state, provider, matched_root = detect_synced_storage(tmp_path, _platform="linux")
    assert state == "unknown"
    assert provider is None
    assert matched_root is None


def test_non_macos_returns_unknown_for_synced_lookalike_paths() -> None:
    """Even a path that looks like a macOS GDrive path doesn't trigger on Linux."""
    fake = Path(_expand("~/Library/CloudStorage/GoogleDrive-x@y/dev/foo"))
    state, provider, matched_root = detect_synced_storage(fake, _platform="linux")
    assert state == "unknown"
    assert provider is None
    assert matched_root is None
