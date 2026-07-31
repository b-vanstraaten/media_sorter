# media-sorter

Sorts torrented movies and TV episodes from a downloads folder into an
organized media library, using a local [Ollama](https://ollama.com) model to
name things and plain regex to keep it honest.

```
<output>/Movies/<Title> (<year>)/<Title> (<year>).<ext>
<output>/Series/<Series Name>/Season <NN>/<Series Name> - S<NN>E<NN>.<ext>
```

Anything that can't be classified confidently is left in place and listed at
the end of the run — nothing gets moved on a guess.

## How it works

1. A regex pass extracts what release names encode reliably: `SxxEyy` /
   `1x02` markers (including multi-episode `S01E01-E02`), years, and the
   title text. Sample files are skipped outright.
2. The Ollama model classifies the file (movie / series / ambiguous) and
   produces a clean title, with the regex hints and the library's existing
   folder names in the prompt.
3. The two are reconciled with the regex as ground truth: season/episode
   numbers from the filename override the model's; a "movie" verdict on a
   file with an episode marker is demoted to ambiguous; a model title that
   shares no words with the filename's title text is rejected.
4. Titles are snapped to existing library folders (case, punctuation, and
   spacing insensitive) so "Daredevil.Born.Again" lands in an existing
   "Daredevil - Born Again" instead of creating a near-duplicate folder.
5. Matching subtitles (`.srt`/`.ass`/... with the same stem, or in the
   release's `Subs/` folder) move along with the video, renamed to match so
   Plex/Jellyfin picks them up. Language tags are preserved.
6. Files that look like they're still downloading (a `.part`/`.!qB`/
   `.crdownload` sibling, or modified in the last two minutes) are skipped.
7. Every run's moves are recorded in `<output>/.media-sorter-undo.json`;
   `--undo` reverses the most recent run.

## Requirements

- Python 3.9+
- Ollama running locally with a model pulled, e.g. `ollama pull llama3.2`

## Usage

```sh
uv sync

# Always preview first
uv run media-sorter --source ~/Downloads --output ~/Media --model llama3.2 --dry-run

# Real run, removing release folders left empty (or junk-only) by the move
uv run media-sorter --source ~/Downloads --output ~/Media --model llama3.2 --prune

# Changed your mind? Reverse the last run (preview with --dry-run first)
uv run media-sorter --output ~/Media --undo
```

Useful flags (see `--help` for all):

| Flag | Purpose |
| --- | --- |
| `--dry-run` | Show what would happen without moving anything |
| `--limit N` | Only process the first N files (trial runs) |
| `--min-confidence {low,medium,high}` | Threshold for moving a file (default: medium) |
| `--min-size-mb X` | Skip video files smaller than X MB |
| `--prune` | Remove source folders left empty or holding only junk (.nfo, .txt, screenshots) |
| `--undo` | Reverse the most recent run (moves files back where they came from) |
| `--host` | Ollama server URL (default: http://localhost:11434) |
| `--json-mode-only` | For Ollama versions without JSON-schema constrained output |

## Tests

```sh
uv run python -m unittest discover -s tests
```
