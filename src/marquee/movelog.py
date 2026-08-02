"""Undo log: every run's moves are recorded so the last run can be reversed."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

LOG_NAME = ".marquee-undo.json"


def log_path(output_root: Path) -> Path:
    return output_root / LOG_NAME


def _load(path: Path) -> list:
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
    return []


def record_run(output_root: Path, moves: List[Tuple[Path, Path]]) -> None:
    path = log_path(output_root)
    runs = _load(path)
    runs.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "moves": [{"from": str(src), "to": str(dest)} for src, dest in moves],
    })
    path.write_text(json.dumps(runs, indent=2))


def last_run(output_root: Path) -> Optional[dict]:
    runs = _load(log_path(output_root))
    return runs[-1] if runs else None


def pop_last_run(output_root: Path) -> Optional[dict]:
    path = log_path(output_root)
    runs = _load(path)
    if not runs:
        return None
    run = runs.pop()
    if runs:
        path.write_text(json.dumps(runs, indent=2))
    else:
        path.unlink()
    return run
