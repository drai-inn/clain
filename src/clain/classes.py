"""The closed set of directory classes — single source of truth.

Per spec 0004: classes are identified by directory name only. Adding or
renaming requires a spec amendment.
"""

from __future__ import annotations

from typing import Final

CACHE_MANAGED: Final[frozenset[str]] = frozenset({"node_modules", ".venv", "venv", "site-packages"})

EPHEMERAL: Final[frozenset[str]] = frozenset({"dist", "build", ".next", ".cache"})

BYTECODE: Final[frozenset[str]] = frozenset({"__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

ALL_CLASS_DIRS: Final[frozenset[str]] = CACHE_MANAGED | EPHEMERAL | BYTECODE


CLASS_OF: Final[dict[str, str]] = {
    **{name: "cache-managed" for name in CACHE_MANAGED},
    **{name: "ephemeral" for name in EPHEMERAL},
    **{name: "bytecode" for name in BYTECODE},
}


WORKSPACE_SOURCE = "workspace-source"


MANIFEST_FILES: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "pixi.toml",
    "uv.lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "Pipfile",
    "Pipfile.lock",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".envrc",
)


def classify_dirname(name: str) -> str | None:
    """Return the class for a directory name, or None if it's workspace-source."""
    return CLASS_OF.get(name)
