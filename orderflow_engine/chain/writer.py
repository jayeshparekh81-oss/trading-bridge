"""Chain-analytics output writer (Module R5). analysis/{date}/ (gitignored, S3-excluded)."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa

from recorder.writer import _atomic_write_table
from tape.writer import analysis_dir
from chain.schema import CHAIN_SNAPSHOT_SCHEMA, normalize_snapshot_row

__all__ = ["analysis_dir", "write_snapshots", "write_summary"]


def write_snapshots(out_dir: Path, index: str, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_snapshot_row(r) for r in rows],
                               schema=CHAIN_SNAPSHOT_SCHEMA)
    dest = out_dir / f"chain_{index}.parquet"
    _atomic_write_table(tbl, dest)
    return dest


def write_summary(out_dir: Path, summary: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "chain_summary.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, default=str))
    tmp.replace(dest)
    return dest
