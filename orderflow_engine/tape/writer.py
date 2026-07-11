"""Tape-engine output writer (Module R3).

Writes analysis under ``analysis/{date}/`` (a SIBLING of ``data/`` — never inside
a recorded day, so the recorder's S3 backup / retention never touch it; analysis
is derived + reproducible from raw via replay). Reuses the recorder's crash-safe
atomic write helper. Outputs are gitignored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa

from recorder.writer import _atomic_write_table
from tape.schema import (
    BARS_SCHEMA, TAPE_EVENTS_SCHEMA, normalize_bar_row, normalize_event_row,
)

HERE = Path(__file__).resolve().parent.parent  # orderflow_engine/


def analysis_dir(data_dir: Path, date: str) -> Path:
    """analysis/{date}/ as a sibling of the given data dir's parent."""
    return Path(data_dir).parent / "analysis" / date


def write_bars(out_dir: Path, symbol: str, security_id: int, bar_rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_bar_row(r) for r in bar_rows], schema=BARS_SCHEMA)
    dest = out_dir / f"{symbol}_{security_id}.bars.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_events(out_dir: Path, event_rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_event_row(r) for r in event_rows],
                               schema=TAPE_EVENTS_SCHEMA)
    dest = out_dir / "tape_events.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_summary(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "summary.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, default=str))
    tmp.replace(dest)
    return dest
