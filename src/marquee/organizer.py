"""Destination naming, known-title registry, and file moves."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
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


MOVE_RETRIES = 2  # extra attempts on a transient copy failure
MOVE_RETRY_DELAY = 2  # seconds, multiplied by attempt number

# Extra headroom required on top of the file's own size before starting a
# copy, so a nearly-full destination volume doesn't get topped off right to
# the edge.
FREE_SPACE_MARGIN = 1.02


def _free_bytes(path: Path) -> int:
    """Free space on the filesystem that would hold path.

    path (or its parent directories) may not exist yet, so walk up to the
    nearest ancestor that does.
    """
    probe = path
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free


def has_room_for(dest: Path, size: int) -> bool:
    """True if dest's filesystem has enough free space for a file this size."""
    return _free_bytes(dest) >= size * FREE_SPACE_MARGIN


def move_file(src: Path, dest: Path) -> None:
    """Move src to dest, never leaving a corrupt or half-written file behind.

    Tries an atomic rename first (instant and all-or-nothing whenever src and
    dest share a filesystem, which is the common case). When they don't,
    plain copy-then-delete (what shutil.move falls back to) can leave a
    truncated file at dest and the original untouched if the process dies
    mid-copy -- and a later run then sees dest already exists and treats the
    file as done, silently stranding a corrupt copy in the library forever.

    To avoid that, the fallback copies to a temp file beside dest, verifies
    its size matches the source, and only then atomically renames it into
    place and removes the source. A transient failure (flaky network/
    external drive) gets a couple of retries; if a prior attempt already
    completed the copy, later attempts skip straight to removing the source
    instead of copying again.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.rename(src, dest)
        return
    except OSError:
        pass  # different filesystem (or something else) -- fall back below

    tmp = dest.with_name(dest.name + ".msorter-tmp")
    last_error: Optional[OSError] = None
    for attempt in range(MOVE_RETRIES + 1):
        if attempt:
            delay = MOVE_RETRY_DELAY * attempt
            logging.warning(
                "Retrying move of %s in %ds (attempt %d/%d): %s",
                src.name, delay, attempt + 1, MOVE_RETRIES + 1, last_error,
            )
            time.sleep(delay)
        try:
            already_copied = dest.exists() and dest.stat().st_size == src.stat().st_size
            if not already_copied:
                shutil.copy2(src, tmp)
                if tmp.stat().st_size != src.stat().st_size:
                    raise OSError(f"copied size mismatch for {src.name}")
                os.replace(tmp, dest)
            os.remove(src)
            return
        except OSError as e:
            last_error = e
            tmp.unlink(missing_ok=True)

    raise last_error


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
