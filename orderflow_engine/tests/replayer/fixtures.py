"""Synthetic recorded-day builders for replayer tests (pure pyarrow, no recorder
runtime). Writes real parquet with the recorder's TICK/EVENT schema."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.schema import (
    EVENT_SCHEMA, TICK_SCHEMA, normalize_event_row, normalize_tick_row,
)


def write_instrument(day_dir: Path, symbol: str, sid: int, rows: list[dict]) -> Path:
    """rows: dicts with ts_recv_ns (+ optional ltt/ltp/seq_local/volume...)."""
    day_dir.mkdir(parents=True, exist_ok=True)
    norm = []
    for i, r in enumerate(rows):
        base = {"security_id": sid, "packet_type": 8, "seq_local": r.get("seq_local", i)}
        norm.append(normalize_tick_row({**base, **r}))
    tbl = pa.Table.from_pylist(norm, schema=TICK_SCHEMA)
    out = day_dir / f"{symbol}_{sid}.parquet"
    pq.write_table(tbl, str(out))
    return out


def write_events(day_dir: Path, events: list[dict]) -> Path:
    day_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_event_row(e) for e in events], schema=EVENT_SCHEMA)
    out = day_dir / "events.parquet"
    pq.write_table(tbl, str(out))
    return out


def write_report(day_dir: Path, status: str, coverage_pct: float | None = None) -> Path:
    day_dir.mkdir(parents=True, exist_ok=True)
    out = day_dir / "report.json"
    out.write_text(json.dumps({"status": status,
                               "coverage": {"coverage_pct": coverage_pct}}))
    return out


def tick(ts_recv_ns: int, ltt: int | None = None, ltp: float | None = None,
         **extra) -> dict:
    d = {"ts_recv_ns": ts_recv_ns, "ltt": ltt, "ltp": ltp}
    d.update(extra)
    return d
