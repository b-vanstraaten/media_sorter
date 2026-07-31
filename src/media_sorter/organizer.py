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


SUBTITLE_EXTENSIONS = {".srt", ".sub", ".ass", ".ssa", ".vtt", ".idx"}
SUBS_DIR_NAMES = {"subs", "subtitles", "sub"}

# Files torrents leave behind that should never block folder removal.
# Deliberately excludes executables and archives: those stay visible.
JUNK_EXTENSIONS = {
    ".nfo", ".sfv", ".srr", ".txt", ".md5", ".torrent",
    ".jpg", ".jpeg", ".png", ".gif",
    ".url", ".website", ".lnk",
}
JUNK_FILENAMES = {".ds_store", "thumbs.db"}


def _is_junk(path: Path) -> bool:
    return path.is_file() and (
        path.suffix.lower() in JUNK_EXTENSIONS
        or path.name.lower() in JUNK_FILENAMES
    )


def find_subtitles(video: Path, video_extensions) -> List[Tuple[Path, str]]:
    """Return (subtitle_path, name_tail) pairs belonging to a video file.

    name_tail is appended to the destination stem so language tags survive:
    "Movie.en.srt" next to "Movie.mkv" -> tail ".en.srt";
    "Subs/English.srt" -> tail ".English.srt". A Subs/ folder is only claimed
    when the video is the only one in its folder, otherwise ownership is
    ambiguous.
    """
    results = []
    stem_lower = video.stem.lower()
    for p in sorted(video.parent.iterdir()):
        if (
            p.is_file()
            and p.suffix.lower() in SUBTITLE_EXTENSIONS
            and p.name.lower().startswith(stem_lower)
        ):
            results.append((p, p.name[len(video.stem):]))

    sibling_videos = [
        p for p in video.parent.iterdir()
        if p.is_file() and p.suffix.lower() in video_extensions
    ]
    if len(sibling_videos) == 1:
        for d in video.parent.iterdir():
            if d.is_dir() and d.name.lower() in SUBS_DIR_NAMES:
                for p in sorted(d.iterdir()):
                    if p.is_file() and p.suffix.lower() in SUBTITLE_EXTENSIONS:
                        results.append((p, f".{p.name}"))
    return results


def prune_empty_dirs(root: Path) -> int:
    """Remove now-empty directories under root (never root itself)."""
    removed = 0
    # Deepest first so parents empty out as children are removed.
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed += 1
    return removed


def prune_release_dirs(root: Path) -> Tuple[int, int]:
    """Junk-aware prune: remove directories whose entire remaining content is
    release junk (.nfo, .txt, screenshots, ...), deleting that junk first.

    A directory containing anything that isn't junk (a video, an archive, an
    executable) is left untouched. Returns (dirs_removed, junk_files_removed).
    """
    removed_dirs = removed_junk = 0
    dirs = [p for p in root.rglob("*") if p.is_dir()]
    for path in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        entries = list(path.iterdir())
        if entries and all(_is_junk(e) for e in entries):
            for e in entries:
                e.unlink()
                removed_junk += 1
            entries = []
        if not entries:
            path.rmdir()
            removed_dirs += 1
    return removed_dirs, removed_junk
