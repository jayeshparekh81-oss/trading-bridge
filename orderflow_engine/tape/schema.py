"""Parquet schemas for tape-engine outputs (Module R3)."""

from __future__ import annotations

import pyarrow as pa

BARS_SCHEMA = pa.schema([
    pa.field("security_id", pa.int32()),
    pa.field("symbol", pa.string()),
    pa.field("bar_type", pa.string()),          # tick | volume
    pa.field("bar_index", pa.int32()),
    pa.field("start_ts_ns", pa.int64()),
    pa.field("end_ts_ns", pa.int64()),
    pa.field("duration_s", pa.float64()),
    pa.field("open", pa.float64()),
    pa.field("high", pa.float64()),
    pa.field("low", pa.float64()),
    pa.field("close", pa.float64()),
    pa.field("volume", pa.int64()),
    pa.field("buy_vol", pa.int64()),
    pa.field("sell_vol", pa.int64()),
    pa.field("delta", pa.int64()),
    pa.field("trade_count", pa.int32()),
    pa.field("cvd_running", pa.int64()),
    pa.field("cvd_slope", pa.float64()),
    pa.field("velocity_baseline_s", pa.float64()),   # nullable
    pa.field("velocity_ratio", pa.float64()),        # nullable
    pa.field("velocity_spike", pa.bool_()),
    pa.field("footprint", pa.string()),              # JSON: {price_bin: [buy_vol, sell_vol]}
])
BARS_COLUMNS = [f.name for f in BARS_SCHEMA]

TAPE_EVENTS_SCHEMA = pa.schema([
    pa.field("ts_ns", pa.int64()),
    pa.field("security_id", pa.int32()),
    pa.field("symbol", pa.string()),
    pa.field("kind", pa.string()),      # BIG_PRINT | BIG_PRINT_CLUSTER | VELOCITY_SPIKE
    pa.field("side", pa.int8()),        # nullable
    pa.field("notional", pa.float64()), # nullable
    pa.field("price", pa.float64()),    # nullable
    pa.field("size", pa.int64()),       # nullable
    pa.field("detail", pa.string()),
])
TAPE_EVENTS_COLUMNS = [f.name for f in TAPE_EVENTS_SCHEMA]


def normalize_bar_row(row: dict) -> dict:
    return {c: row.get(c) for c in BARS_COLUMNS}


def normalize_event_row(row: dict) -> dict:
    return {c: row.get(c) for c in TAPE_EVENTS_COLUMNS}
