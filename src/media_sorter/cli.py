"""Command-line entry point: scan, classify, reconcile, move, report."""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from .filename_parser import FilenameHints, parse_filename
from .ollama_client import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    ClassificationError,
    classify_file,
    make_client,
)
from .movelog import last_run, pop_last_run, record_run
from .organizer import (
    TitleRegistry,
    build_movie_dest,
    build_series_dest,
    find_subtitles,
    movie_label,
    prune_empty_dirs,
    prune_release_dirs,
    sanitize_name,
    scan_known_titles,
)

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts", ".vob",
}

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

_STOPWORDS = {"the", "a", "an", "of", "and"}

console = Console(highlight=False)


def tilde(path: Path) -> str:
    """Shorten a path for display: /Users/you/x -> ~/x."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


GB = 1024 ** 3


def gb(num_bytes: int) -> str:
    return f"{num_bytes / GB:.2f} GB"


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


# Marker files torrent clients keep next to (or instead of) unfinished
# downloads, and how recently a file must have been written to be suspect.
PARTIAL_SIBLING_SUFFIXES = (".part", ".!qB", ".crdownload")
RECENTLY_MODIFIED_SECONDS = 120


def active_download_reason(path: Path) -> Optional[str]:
    """Return a reason string if the file looks like it's still downloading."""
    for suffix in PARTIAL_SIBLING_SUFFIXES:
        if path.with_name(path.name + suffix).exists():
            return f"still downloading ({suffix} file present)"
    age = time.time() - path.stat().st_mtime
    if age < RECENTLY_MODIFIED_SECONDS:
        return f"modified {int(age)}s ago (may still be downloading)"
    return None


def undo_last_run(output_root: Path, dry_run: bool) -> None:
    """Reverse the most recent recorded run: move every file back."""
    run = last_run(output_root)
    if run is None:
        console.print("[yellow]No recorded runs to undo.[/]")
        return

    header = (
        f"Undoing run from [bold]{run['timestamp']}[/] — "
        f"[bold]{len(run['moves'])}[/] move(s)"
    )
    if dry_run:
        header += "\n[yellow italic]DRY RUN — nothing will be moved[/]"
    console.print(Panel.fit(header, title="undo", border_style="magenta"))

    restored = failed = 0
    for move in reversed(run["moves"]):
        current = Path(move["to"])
        original = Path(move["from"])
        if not current.exists():
            console.print(f"  [bold red]✗[/] no longer in library: {current.name}")
            failed += 1
            continue
        if original.exists():
            console.print(f"  [bold red]✗[/] original location occupied: {tilde(original)}")
            failed += 1
            continue
        console.print(f"  [green]↩[/] {current.name}  [dim]→ {tilde(original)}[/]")
        if not dry_run:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(current, original)
        restored += 1

    if not dry_run:
        if failed == 0:
            pop_last_run(output_root)
            prune_empty_dirs(output_root)  # drop folders the undo emptied
        else:
            console.print(
                "[yellow]Run kept in the log because some files could not "
                "be restored.[/]"
            )
    console.print(
        f"\nRestored [bold green]{restored}[/] file(s)"
        + (f", [bold red]{failed}[/] failed" if failed else "")
        + (" [yellow italic](dry run)[/]" if dry_run else "")
    )


def _title_tokens(text: str):
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS}


def title_plausible(model_title: str, guessed_title: Optional[str]) -> bool:
    """Sanity-check the model's title against the filename's own title text.

    Small models sometimes snap to an unrelated entry in the known-titles
    list. If the filename gave us usable title text and the model's answer
    shares not a single word with it, don't trust the classification.
    """
    if not guessed_title:
        return True
    guessed = _title_tokens(guessed_title)
    proposed = _title_tokens(model_title)
    if not guessed or not proposed:
        return True
    return bool(guessed & proposed)


def iter_video_files(source: Path):
    """Yield all video files under source, recursively, sorted for stable runs."""
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path


def reconcile(result: dict, hints: FilenameHints) -> dict:
    """Merge model output with regex hints; regex wins on numbers.

    An SxxEyy marker in the filename is close to certain, so a model that
    contradicts it is wrong about the numbers -- and if it thinks such a file
    is a movie, it is confused enough that we shouldn't move on its word.
    """
    if hints.season is not None:
        if result["type"] == "movie":
            logging.warning(
                "model said movie but filename has S%02dE%02d -> treating as ambiguous",
                hints.season, hints.episode or 0,
            )
            result["type"] = "ambiguous"
        elif result["type"] == "series":
            if result.get("season") != hints.season or (
                hints.episode is not None and result.get("episode") != hints.episode
            ):
                logging.debug(
                    "overriding model numbers S%sE%s with regex S%02dE%02d",
                    result.get("season"), result.get("episode"),
                    hints.season, hints.episode or 0,
                )
            result["season"] = hints.season
            result["episode"] = hints.episode

    if result["type"] == "series":
        result["episodes"] = (
            hints.episodes
            if hints.season is not None and hints.episodes
            else [result["episode"]] if result.get("episode") is not None
            else []
        )

    if not result.get("year") and hints.year and result["type"] == "movie":
        result["year"] = hints.year

    if (
        result["type"] in ("movie", "series")
        and result.get("title")
        and not title_plausible(result["title"], hints.guessed_title)
    ):
        logging.warning(
            "model title %r shares no words with filename title text %r "
            "-> treating as ambiguous",
            result["title"], hints.guessed_title,
        )
        result["type"] = "ambiguous"

    return result


def decide_destination(
    path: Path,
    result: dict,
    output_root: Path,
    min_confidence: str,
    series_registry: TitleRegistry,
    movie_registry: TitleRegistry,
) -> Tuple[Optional[Path], str]:
    """Return (destination, reason). Destination is None if left in place."""
    kind = result.get("type")
    confidence = result.get("confidence")

    if kind == "ambiguous":
        return None, "model classified as ambiguous"
    if CONFIDENCE_RANK.get(confidence, 0) < CONFIDENCE_RANK[min_confidence]:
        return None, f"confidence '{confidence}' below --min-confidence"

    ext = path.suffix.lower()

    if kind == "movie" and result.get("title"):
        label = movie_label(sanitize_name(result["title"]), result.get("year"))
        label, existing = movie_registry.resolve(label)
        if existing:
            logging.debug("matched existing movie folder: %s", label)
        return build_movie_dest(output_root, label, ext), ""

    if (
        kind == "series"
        and result.get("title")
        and result.get("season") is not None
        and result.get("episodes")
    ):
        series, existing = series_registry.resolve(sanitize_name(result["title"]))
        if existing:
            logging.debug("matched existing series folder: %s", series)
        return (
            build_series_dest(
                output_root, series, result["season"], result["episodes"], ext
            ),
            "",
        )

    return None, f"classified as {kind} but required fields are missing"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media-sorter",
        description="Sort movie/series video files using a local Ollama model.",
    )
    parser.add_argument(
        "--source", default=str(Path.home() / "Downloads"),
        help="Folder to scan recursively (default: ~/Downloads)",
    )
    parser.add_argument(
        "--output", default=str(Path.home() / "Media"),
        help="Root folder to move sorted files into (default: ~/Media)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Ollama model to use for classification (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST,
        help=f"Ollama server URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--min-confidence", choices=["low", "medium", "high"], default="medium",
        help="Minimum model confidence required to move a file (default: medium)",
    )
    parser.add_argument(
        "--min-size-mb", type=float, default=0,
        help="Skip video files smaller than this many MB (default: 0, disabled)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process at most N files (useful for a trial run)",
    )
    parser.add_argument(
        "--json-mode-only", action="store_true",
        help='Use plain "format": "json" instead of a JSON schema '
             "(use this if your Ollama version predates schema-constrained output)",
    )
    parser.add_argument(
        "--timeout", type=int, default=120,
        help="Per-file timeout in seconds for the Ollama request (default: 120)",
    )
    parser.add_argument(
        "--prune", action="store_true",
        help="After moving, remove source folders left holding only release "
             "junk (.nfo, .txt, screenshots, ...) or nothing at all",
    )
    parser.add_argument(
        "--undo", action="store_true",
        help="Reverse the most recent run recorded in the library's undo log, "
             "then exit (combine with --dry-run to preview)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without moving/renaming anything",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show debug logging (raw model output, etc.)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            RichHandler(
                console=console, show_path=args.verbose, rich_tracebacks=True
            )
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    source = Path(args.source).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()

    if args.undo:
        undo_last_run(output_root, args.dry_run)
        return

    if not source.is_dir():
        console.print(f"[bold red]Source folder does not exist:[/] {source}")
        sys.exit(1)
    if output_root == source or output_root in source.parents:
        console.print(
            "[bold red]--output must not contain --source[/] "
            "(would rescan moved files)"
        )
        sys.exit(1)

    files = list(iter_video_files(source))
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        console.print(f"No video files found under [cyan]{source}[/]")
        return

    client = make_client(host=args.host, timeout=args.timeout)
    series_registry, movie_registry = scan_known_titles(output_root)

    header = (
        f"[bold]{len(files)}[/] video file(s) in [cyan]{tilde(source)}[/]\n"
        f"Library: [cyan]{tilde(output_root)}[/]  ·  Model: [magenta]{args.model}[/]"
    )
    if len(series_registry) or len(movie_registry):
        header += (
            f"\nKnown: [bold]{len(series_registry)}[/] series, "
            f"[bold]{len(movie_registry)}[/] movies already in the library"
        )
    if args.dry_run:
        header += "\n[yellow italic]DRY RUN — nothing will be moved[/]"
    console.print(Panel.fit(header, title="media-sorter", border_style="blue"))

    moved_movies = moved_series = 0
    leftovers: List[Tuple[Path, str]] = []  # (path, reason) for the final report
    # series name -> [folder path, bytes added this run] for the summary table
    touched_series = {}
    recorded_moves: List[Tuple[Path, Path]] = []  # for the undo log

    def note_skip(rel: Path, reason: str, style: str = "yellow") -> None:
        leftovers.append((rel, reason))
        console.print(f"  [{style}]○ skip[/]   {rel}  [dim]— {reason}[/]")

    for index, path in enumerate(files):
        if index:
            console.print()
        rel = path.relative_to(source)
        size = path.stat().st_size
        hints = parse_filename(path)

        if hints.is_sample:
            note_skip(rel, "sample file")
            continue

        active_reason = active_download_reason(path)
        if active_reason:
            note_skip(rel, active_reason)
            continue

        if args.min_size_mb and size < args.min_size_mb * 1024 * 1024:
            note_skip(rel, f"below size threshold ({size / (1024 * 1024):.1f} MB)")
            continue

        try:
            with console.status(f"Classifying [bold]{rel}[/] …", spinner="dots"):
                result = classify_file(
                    client, path, hints,
                    series_registry.names(), movie_registry.names(),
                    model=args.model, json_mode_only=args.json_mode_only,
                    host=args.host,
                )
        except ClassificationError as e:
            leftovers.append((rel, f"classification error: {e}"))
            console.print(f"  [bold red]✗ error[/]  {rel}  [red]{e}[/]")
            continue

        logging.debug("raw result: %s", result)
        result = reconcile(result, hints)

        dest, reason = decide_destination(
            path, result, output_root, args.min_confidence,
            series_registry, movie_registry,
        )

        if dest is None:
            note_skip(rel, reason)
            continue

        if dest.exists():
            note_skip(
                rel,
                f"already in library: {dest.relative_to(output_root)}",
                style="red",
            )
            continue

        # Find companions before the video moves: ownership of a Subs/ folder
        # depends on the video still being in its source folder.
        subtitles = find_subtitles(path, VIDEO_EXTENSIONS)

        if not args.dry_run:
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(path, dest)
            except OSError as e:
                leftovers.append((rel, f"move failed: {e}"))
                console.print(f"  [bold red]✗ error[/]  {rel}  [red]move failed: {e}[/]")
                continue
            recorded_moves.append((path, dest))

        if result["type"] == "movie":
            kind_markup = "[bold green]✓ movie[/]"
            moved_movies += 1
        else:
            kind_markup = "[bold cyan]✓ series[/]"
            moved_series += 1
        console.print(f"  {kind_markup}  {rel}  [bold]({gb(size)})[/]")
        console.print(f"           [dim]→ {dest.relative_to(output_root)}[/]")

        for sub_path, tail in subtitles:
            sub_dest = dest.with_name(dest.stem + tail)
            if sub_dest.exists():
                continue
            if not args.dry_run:
                try:
                    shutil.move(sub_path, sub_dest)
                except OSError as e:
                    console.print(f"           [red]subtitle move failed: {e}[/]")
                    continue
                recorded_moves.append((sub_path, sub_dest))
            console.print(f"           [dim]+ subtitle →[/] [green]{sub_dest.name}[/]")

        if result["type"] == "series":
            series_folder = dest.parent.parent
            entry = touched_series.setdefault(series_folder.name, [series_folder, 0])
            entry[1] += size

    if recorded_moves:
        record_run(output_root, recorded_moves)

    if args.prune and not args.dry_run:
        removed_dirs, removed_junk = prune_release_dirs(source)
        if removed_dirs or removed_junk:
            console.print(
                f"\n[dim]Pruned {removed_dirs} folder(s) and "
                f"{removed_junk} junk file(s)[/]"
            )

    verb = "Would move" if args.dry_run else "Moved"
    summary = (
        f"{verb} [bold green]{moved_movies}[/] movie(s) and "
        f"[bold cyan]{moved_series}[/] episode(s)  ·  "
        f"[yellow]{len(leftovers)}[/] left in place"
    )
    if args.dry_run:
        summary += "\n[yellow italic]dry run — nothing was actually moved[/]"
    console.print()
    console.print(
        Panel.fit(
            summary,
            title="done",
            border_style="yellow" if leftovers else "green",
        )
    )

    if touched_series:
        table = Table(
            title="Series folders", box=box.ROUNDED,
            border_style="cyan", title_style="bold cyan",
        )
        table.add_column("Series", style="bold cyan", overflow="fold")
        table.add_column("Added", justify="right", style="green")
        table.add_column("Total size", justify="right", style="bold magenta")
        for name in sorted(touched_series):
            folder, added = touched_series[name]
            total = dir_size(folder) if folder.exists() else 0
            if args.dry_run:
                total += added  # files weren't actually moved in
            table.add_row(name, gb(added), gb(total))
        console.print(table)

    if leftovers:
        table = Table(
            title="Left in place", box=box.ROUNDED,
            border_style="yellow", title_style="bold yellow",
        )
        table.add_column("File", overflow="fold")
        table.add_column("Reason", style="dim", overflow="fold")
        for rel, reason in leftovers:
            table.add_row(str(rel), reason)
        console.print(table)


if __name__ == "__main__":
    main()
