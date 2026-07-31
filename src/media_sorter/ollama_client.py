"""Classification via the official `ollama` Python package."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable, Optional

import ollama

from .filename_parser import FilenameHints

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"

MAX_KNOWN_TITLES_IN_PROMPT = 300
RETRIES = 2  # extra attempts on transient failures

# Ollama >= 0.3.0 accepts a JSON schema as `format`, constraining decoding so
# the model can basically only emit valid, on-schema JSON. Pass
# json_mode_only=True for older versions.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["movie", "series", "ambiguous"]},
        "title": {"type": ["string", "null"]},
        "year": {"type": ["string", "null"]},
        "season": {"type": ["integer", "null"]},
        "episode": {"type": ["integer", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["type", "title", "year", "season", "episode", "confidence"],
}

PROMPT_TEMPLATE = """You are a media file classifier. Given a video filename \
(and its parent folder name for extra context), decide whether it is a MOVIE \
or a single TV SERIES episode.

IMPORTANT: many release filenames contain BOTH a series name and an episode's \
own title, e.g. "Daredevil - Born Again - S02E05 - The Grand Design.mkv". The \
series name is "Daredevil - Born Again" -- it is the part that comes right \
before the season/episode number (S02E05). "The Grand Design" is the EPISODE's \
own title, not the show. NEVER put an episode title in the "title" field for \
a series; always use the show's name.

You are already tracking these titles from earlier files in this run (folder \
names on disk). If this file clearly belongs to one of them -- even if this \
filename's punctuation, spacing, or capitalization differs -- you MUST reuse \
the EXACT existing name from this list instead of inventing a new one:

Known series: {known_series}
Known movies: {known_movies}

A regex pass already extracted these hints from the filename (they may be \
partial, but any season/episode numbers shown here are reliable):
{hints}

Respond with ONLY a JSON object matching this schema, nothing else:
{{
  "type": "movie" | "series" | "ambiguous",
  "title": string or null,    // series/show name, or movie title. Title
                               // case, no dots/underscores, no
                               // resolution/codec/release-group noise
                               // (e.g. strip 1080p, x264, WEB-DL, YIFY,
                               // bracketed release groups). Match an
                               // existing known title above if applicable.
  "year": string or null,     // release year if present, else null
  "season": integer or null,  // season number, required if type is "series"
  "episode": integer or null, // episode number, required if type is "series"
  "confidence": "high" | "medium" | "low"
}}

Rules:
- If type is "series", season and episode MUST both be integers, and title
  MUST be the show's name -- never an individual episode's title. If you
  cannot confidently determine the show name and both numbers, use
  "ambiguous" instead.
- If type is "movie", title MUST be a clean, non-empty string. If the title
  is too garbled or generic to trust, use "ambiguous" instead.
- If your confidence is "low", set type to "ambiguous" regardless of your
  best guess.
- Do not include any text before or after the JSON object.

Parent folder: {parent}
Filename: {filename}
"""


class ClassificationError(Exception):
    pass


def _format_known_list(names: Iterable[str]) -> str:
    names = sorted(names)[:MAX_KNOWN_TITLES_IN_PROMPT]
    return json.dumps(names) if names else "(none yet)"


def _format_hints(hints: FilenameHints) -> str:
    parts = []
    if hints.season is not None:
        parts.append(f"season={hints.season}")
    if hints.episodes:
        parts.append(f"episode(s)={hints.episodes}")
    if hints.year:
        parts.append(f"year={hints.year}")
    if hints.guessed_title:
        parts.append(f"probable title text: {hints.guessed_title!r}")
    return "; ".join(parts) if parts else "(none)"


def _generate_with_retries(
    client: ollama.Client, model: str, prompt: str, fmt, host: str
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(RETRIES + 1):
        if attempt:
            delay = 2 * attempt
            logging.warning(
                "Retrying Ollama request in %ds (attempt %d/%d): %s",
                delay, attempt + 1, RETRIES + 1, last_error,
            )
            time.sleep(delay)
        try:
            response = client.generate(
                model=model,
                prompt=prompt,
                format=fmt,
                options={"temperature": 0},
            )
            return response.response
        except ollama.ResponseError as e:
            if e.status_code and e.status_code >= 500:
                last_error = ClassificationError(
                    f"Ollama HTTP {e.status_code}: {e.error}"
                )
                continue
            raise ClassificationError(
                f"Ollama returned HTTP {e.status_code} for model '{model}': "
                f"{e.error}. Run `ollama list` to see available models and "
                f"pass the exact name via --model."
            ) from e
        except ConnectionError as e:
            raise ClassificationError(
                f"Could not reach Ollama at {host} ({e}). Is `ollama serve` running?"
            ) from e
        except Exception as e:  # httpx transport/timeout errors
            last_error = ClassificationError(
                f"Request to Ollama at {host} failed ({type(e).__name__}: {e}). "
                f"Is `ollama serve` running?"
            )
    raise last_error  # type: ignore[misc]


def _coerce_int(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _validate_result(result) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("type") not in ("movie", "series", "ambiguous"):
        return False
    if result.get("confidence") not in ("high", "medium", "low"):
        return False
    return True


def make_client(host: str = DEFAULT_HOST, timeout: int = 120) -> ollama.Client:
    return ollama.Client(host=host, timeout=timeout)


def classify_file(
    client: ollama.Client,
    path: Path,
    hints: FilenameHints,
    known_series: Iterable[str],
    known_movies: Iterable[str],
    model: str = DEFAULT_MODEL,
    json_mode_only: bool = False,
    host: str = DEFAULT_HOST,
) -> dict:
    """Ask Ollama to classify a single file. Returns a validated result dict."""
    prompt = PROMPT_TEMPLATE.format(
        parent=path.parent.name,
        filename=path.name,
        known_series=_format_known_list(known_series),
        known_movies=_format_known_list(known_movies),
        hints=_format_hints(hints),
    )
    fmt = "json" if json_mode_only else RESPONSE_SCHEMA

    raw = _generate_with_retries(client, model, prompt, fmt, host).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ClassificationError(f"Model did not return valid JSON: {raw!r}") from e

    if not _validate_result(result):
        raise ClassificationError(f"Model JSON missing/invalid fields: {result!r}")

    result["season"] = _coerce_int(result.get("season"))
    result["episode"] = _coerce_int(result.get("episode"))
    if isinstance(result.get("title"), str):
        result["title"] = result["title"].strip() or None
    return result
