"""Destination naming, known-title registry, and file moves."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_name(name: str) -> str:
    """Strip characters that are invalid in filenames on Windows/macOS/Linux."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip().rstrip(".")
    if not name or name.upper() in WINDOWS_RESERVED:
        return f"_{name}" if name else "Untitled"
    return name


def _normalize(name: str) -> str:
    """Key used to decide two spellings refer to the same title."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


class TitleRegistry:
    """Tracks folder names already in use so new files snap to them.

    The prompt asks the model to reuse known names, but models drift; this is
    the enforcement layer. Matching is exact on a normalized form (case,
    punctuation, spacing collapsed). Deliberately NOT fuzzy: similar-but-real
    distinct titles ("The Office (US)" vs "The Office (UK)") must never merge.
    """

    def __init__(self, names=()):
        self._canonical = {}
        for name in names:
            self._canonical.setdefault(_normalize(name), name)

    def __len__(self):
        return len(self._canonical)

    def names(self) -> List[str]:
        return sorted(self._canonical.values())

    def resolve(self, title: str) -> Tuple[str, bool]:
        """Return (canonical_title, was_existing) for a model-proposed title."""
        key = _normalize(title)
        if key in self._canonical:
            return self._canonical[key], True
        self._canonical[key] = title
        return title, False


def scan_known_titles(output_root: Path) -> Tuple[TitleRegistry, TitleRegistry]:
    """Seed registries from what's already in <output>/Series and /Movies."""
    def _folders(subdir: str):
        root = output_root / subdir
        if root.is_dir():
            return [p.name for p in root.iterdir() if p.is_dir()]
        return []

    return TitleRegistry(_folders("Series")), TitleRegistry(_folders("Movies"))


def movie_label(title: str, year: Optional[str]) -> str:
    label = f"{title} ({year})" if year else title
    return sanitize_name(label)


def build_movie_dest(output_root: Path, label: str, ext: str) -> Path:
    return output_root / "Movies" / label / f"{label}{ext}"


def episode_tag(season: int, episodes: List[int]) -> str:
    tag = f"S{season:02d}E{episodes[0]:02d}"
    if len(episodes) > 1:
        tag += f"-E{episodes[-1]:02d}"
    return tag


def build_series_dest(
    output_root: Path, series: str, season: int, episodes: List[int], ext: str
) -> Path:
    tag = episode_tag(season, episodes)
    return (
        output_root
        / "Series"
        / series
        / f"Season {season:02d}"
        / f"{series} - {tag}{ext}"
    )


def prune_empty_dirs(root: Path) -> int:
    """Remove now-empty directories under root (never root itself)."""
    removed = 0
    # Deepest first so parents empty out as children are removed.
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed += 1
    return removed
