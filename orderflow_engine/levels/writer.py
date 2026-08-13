"""Levels-engine output writer (Module R4).

Writes under analysis/{date}/ (sibling of data/, gitignored, S3-excluded — same
policy as R3): levels_{symbol}_{sid}.parquet, vwap_{symbol}_{sid}.parquet, and
levels_summary.json. Reuses R3's analysis_dir + the recorder atomic-write helper.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa

from recorder.writer import _atomic_write_table
from tape.writer import analysis_dir  # reuse the same analysis/{date}/ location
from levels.schema import (
    LEVELS_SCHEMA, VWAP_SNAPSHOT_SCHEMA, normalize_levels_row, normalize_vwap_row,
)

__all__ = ["analysis_dir", "write_levels", "write_vwap_snapshots", "write_summary"]


def write_levels(out_dir: Path, symbol: str, security_id: int, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_levels_row(r) for r in rows], schema=LEVELS_SCHEMA)
    dest = out_dir / f"levels_{symbol}_{security_id}.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_vwap_snapshots(out_dir: Path, symbol: str, security_id: int, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_vwap_row(r) for r in rows],
                               schema=VWAP_SNAPSHOT_SCHEMA)
    dest = out_dir / f"vwap_{symbol}_{security_id}.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_summary(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "levels_summary.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, default=str))
    tmp.replace(dest)
    return dest
