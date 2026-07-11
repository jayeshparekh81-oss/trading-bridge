"""Signals output writer (Module R6). analysis/{date}/ (gitignored, S3-excluded)."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa

from recorder.writer import _atomic_write_table
from tape.writer import analysis_dir
from signals.schema import SIGNALS_SCHEMA, normalize_signal_row

__all__ = ["analysis_dir", "write_signals", "write_summary"]


def write_signals(out_dir: Path, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_signal_row(r) for r in rows], schema=SIGNALS_SCHEMA)
    dest = out_dir / "signals.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_summary(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "signals_summary.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, default=str))
    tmp.replace(dest)
    return dest
