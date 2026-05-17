"""Per-ecosystem store-placement advice.

Curated data, not code logic. Updating this is a normal source change subject
to PR review. Each entry cites the canonical doc URL so reviewers can verify
the advice is still current at the time of update.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Placement:
    ecosystem: str
    store_advice: str
    configure_via: str
    doc_url: str


PLACEMENTS: Final[dict[str, Placement]] = {
    "pnpm": Placement(
        ecosystem="pnpm",
        store_advice="~/Library/pnpm/store on macOS — single content-addressable store shared across all projects.",
        configure_via="pnpm config set store-dir ~/Library/pnpm/store (or ~/.npmrc: store-dir=...)",
        doc_url="https://pnpm.io/configuring#store-dir",
    ),
    "npm": Placement(
        ecosystem="npm",
        store_advice="npm has no shared store; migrate to pnpm or yarn-berry PnP to get one.",
        configure_via="(no equivalent of pnpm's store-dir for classic npm)",
        doc_url="https://pnpm.io/motivation",
    ),
    "yarn": Placement(
        ecosystem="yarn",
        store_advice="Yarn Berry's PnP mode avoids per-project node_modules entirely; classic yarn does not.",
        configure_via="yarn set version berry && yarn config set nodeLinker pnp",
        doc_url="https://yarnpkg.com/features/pnp",
    ),
    "pixi": Placement(
        ecosystem="pixi",
        store_advice=(
            "Pixi keeps per-project envs under .pixi/envs/ but shares a package cache. "
            "Workspace-local .pixi/ must live outside the synced tree (i.e. the whole "
            "workspace must be in ~/dev/, not in GDrive)."
        ),
        configure_via="PIXI_CACHE_DIR env var (defaults to ~/.cache/rattler/cache on macOS)",
        doc_url="https://pixi.sh/latest/reference/cli/",
    ),
    "uv": Placement(
        ecosystem="uv",
        store_advice="~/.cache/uv — single cache, content-addressed, shared across all projects.",
        configure_via="UV_CACHE_DIR env var (default: ~/.cache/uv)",
        doc_url="https://docs.astral.sh/uv/reference/settings/#cache-dir",
    ),
    "poetry": Placement(
        ecosystem="poetry",
        store_advice=(
            "~/Library/Caches/pypoetry/virtualenvs on macOS. Poetry stores virtualenvs "
            "centrally rather than in-project by default."
        ),
        configure_via="poetry config virtualenvs.path",
        doc_url="https://python-poetry.org/docs/configuration/",
    ),
}


def for_manifest(manifest: str) -> Placement | None:
    """Map a manifest filename to its primary ecosystem's placement advice."""
    return {
        "pnpm-lock.yaml": PLACEMENTS["pnpm"],
        "package-lock.json": PLACEMENTS["npm"],
        "yarn.lock": PLACEMENTS["yarn"],
        "pixi.toml": PLACEMENTS["pixi"],
        "uv.lock": PLACEMENTS["uv"],
    }.get(manifest)
