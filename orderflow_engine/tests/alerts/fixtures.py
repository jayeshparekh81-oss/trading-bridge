"""Fixtures for alert tests — real R6 signals.parquet schema (no invented fields)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from signals.schema import SIGNALS_SCHEMA, normalize_signal_row

IST = timezone(timedelta(hours=5, minutes=30))
TS = int(datetime(2026, 7, 13, 11, 0, tzinfo=IST).timestamp() * 1e9)


def sample_row(**kw) -> dict:
    breakdown = {
        "big_print": {"activation": 1.0, "weight": 20.0, "enabled": True, "contribution": 20.0},
        "cvd_confirm": {"activation": 1.0, "weight": 10.0, "enabled": True, "contribution": 10.0},
        "regime": {"activation": 1.0, "weight": 5.0, "enabled": True, "contribution": 5.0},
        "book_ofi": {"activation": 0.0, "weight": 25.0, "enabled": True, "contribution": 0.0},
    }
    r = {
        "ts_ns": TS, "index": "NIFTY", "instrument": "NIFTY_FUT", "side": "long",
        "price": 24000.0, "score": 35.0, "threshold": 30.0, "base_threshold": 30.0,
        "fired": True, "gate_reason": "", "regime_direction": "bull",
        "regime_vol_band": "normal", "breakdown": json.dumps(breakdown),
        "entry": 24000.0, "stop": 23950.0, "target": 24050.0, "r_value": 50.0,
        "exit_reason": None, "realized_r": None,
    }
    r.update(kw)
    return r


def write_signals_parquet(out_dir: Path, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_signal_row(r) for r in rows], schema=SIGNALS_SCHEMA)
    dest = out_dir / "signals.parquet"
    pq.write_table(tbl, str(dest))
    return dest
