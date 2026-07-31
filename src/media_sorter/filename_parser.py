"""Regex heuristics for release filenames.

These run before the LLM. Season/episode numbers found here are treated as
ground truth (release names are extremely consistent about SxxEyy), while
the model is left to do what it is actually good at: producing a clean,
consistent title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SEASON_EPISODE_PATTERNS = [
    # S01E02, s1.e2, S01E01E02, S01E01-E03
    re.compile(
        r"[Ss](?P<season>\d{1,2})[ ._-]*[Ee](?P<episode>\d{1,3})"
        r"(?P<extra>(?:[ ._-]*[Ee-]+\d{1,3})*)"
    ),
    # 1x02, 12x103
    re.compile(r"(?<![\dA-Za-z])(?P<season>\d{1,2})x(?P<episode>\d{2,3})(?!\d)"),
    # Season 1 Episode 2
    re.compile(
        r"[Ss]eason[ ._-]*(?P<season>\d{1,2})[ ._-]*[Ee]pisode[ ._-]*(?P<episode>\d{1,3})"
    ),
]

# 19xx/20xx not followed by a digit or p/i (excludes 2160p-style resolutions)
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?![0-9pi])")

RELEASE_NOISE = re.compile(
    r"\b(?:"
    r"480p|720p|1080p|2160p|4k|uhd|hdr10?|dv|dolby|vision|atmos"
    r"|x26[45]|h[ .]?26[45]|hevc|avc|av1|xvid|divx"
    r"|web[ -]?dl|web[ -]?rip|blu[ -]?ray|b[dr]rip|dvdrip|hdtv|hdrip|remux|cam|ts"
    r"|aac(?:2[ .]0)?|ac3|eac3|ddp?[ .]?[257][ .]?[01]|dts(?:[ -]?hd)?|truehd|flac|[257][ .][01]ch?"
    r"|proper|repack|internal|limited|extended|unrated|remastered|complete"
    r"|multi|dual[ .]?audio|subbed|dubbed|amzn|nf|dsnp|hulu|hmax|atvp"
    r"|yify|yts(?:[ .]\w+)?|rarbg|ettv|eztv|galaxytv|sparks|fgt"
    r")\b",
    re.IGNORECASE,
)

SAMPLE_PATTERN = re.compile(r"\bsample\b", re.IGNORECASE)


@dataclass
class FilenameHints:
    season: Optional[int] = None
    episodes: List[int] = field(default_factory=list)
    year: Optional[str] = None
    guessed_title: Optional[str] = None
    is_sample: bool = False

    @property
    def episode(self) -> Optional[int]:
        return self.episodes[0] if self.episodes else None


def _spaces(text: str) -> str:
    return re.sub(r"[._]+", " ", text)


def parse_season_episode(text: str):
    """Return (season, [episodes], match_start) or (None, [], None)."""
    for pattern in SEASON_EPISODE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        season = int(m.group("season"))
        episodes = [int(m.group("episode"))]
        extra = m.groupdict().get("extra") or ""
        episodes += [int(n) for n in re.findall(r"\d{1,3}", extra)]
        return season, sorted(set(episodes)), m.start()
    return None, [], None


def extract_year(text: str) -> Optional[str]:
    matches = YEAR_PATTERN.findall(_spaces(text))
    return matches[-1] if matches else None


def clean_title(text: str) -> str:
    """Best-effort cleanup of the title portion of a release name.

    Only used as a hint for the model, so it errs on the side of leaving
    things in rather than mangling a real title.
    """
    text = _spaces(text)
    text = re.sub(r"[\[\(][^\]\)]*[\]\)]", " ", text)  # bracketed groups
    text = RELEASE_NOISE.sub(" ", text)
    text = YEAR_PATTERN.sub(" ", text)
    text = re.sub(r"[ \-]{2,}", " ", text)
    return text.strip(" -")


def parse_filename(path: Path) -> FilenameHints:
    """Extract whatever structure we can from a file path without the LLM."""
    stem = path.stem
    parent = path.parent.name

    is_sample = bool(
        SAMPLE_PATTERN.search(_spaces(stem))
        or parent.lower() in ("sample", "samples")
    )

    season, episodes, marker_pos = parse_season_episode(stem)
    source_text = stem
    if season is None:
        # e.g. file is "episode 3.mkv" inside "Show.Name.S02.1080p/"
        season, episodes, marker_pos = parse_season_episode(parent)
        source_text = parent

    year = extract_year(stem) or extract_year(parent)

    guessed_title = None
    if marker_pos is not None and marker_pos > 0:
        guessed_title = clean_title(source_text[:marker_pos]) or None
    elif season is None:
        guessed_title = clean_title(stem) or None

    return FilenameHints(
        season=season,
        episodes=episodes,
        year=year,
        guessed_title=guessed_title,
        is_sample=is_sample,
    )
