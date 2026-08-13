"""Parquet schema for recorded ticks (one row per persisted packet).

Kept separate so the writer and verify_session agree on the exact layout.
Nullable everywhere: a given packet type only fills the fields it carries.
"""

from __future__ import annotations

import pyarrow as pa

from recorder.parser import DEPTH_LEVELS

_DEPTH_FIELDS = []
for _i in range(1, DEPTH_LEVELS + 1):
    _DEPTH_FIELDS += [
        pa.field(f"bid_price_{_i}", pa.float64()),
        pa.field(f"bid_qty_{_i}", pa.int64()),
        pa.field(f"bid_orders_{_i}", pa.int32()),
        pa.field(f"ask_price_{_i}", pa.float64()),
        pa.field(f"ask_qty_{_i}", pa.int64()),
        pa.field(f"ask_orders_{_i}", pa.int32()),
    ]

TICK_SCHEMA = pa.schema(
    [
        pa.field("ts_recv_ns", pa.int64()),      # epoch ns at receipt (monotonic-ish, wall clock)
        pa.field("packet_type", pa.int8()),
        pa.field("seq_local", pa.int64()),       # monotonic per instrument
        pa.field("security_id", pa.int32()),
        pa.field("ltt", pa.int32()),             # exchange last-trade-time (epoch s)
        pa.field("ltp", pa.float64()),
        pa.field("ltq", pa.int32()),
        pa.field("atp", pa.float64()),
        pa.field("volume", pa.int64()),
        pa.field("total_buy_qty", pa.int64()),
        pa.field("total_sell_qty", pa.int64()),
        pa.field("oi", pa.int64()),
    ]
    + _DEPTH_FIELDS
)

# Field name order for building rows/tables.
TICK_COLUMNS = [f.name for f in TICK_SCHEMA]

# Events parquet: reconnects, gaps, subscribe acks, market-status, disconnects.
EVENT_SCHEMA = pa.schema(
    [
        pa.field("ts_ns", pa.int64()),
        pa.field("kind", pa.string()),           # RECONNECT|GAP|SUBSCRIBE|STATUS|DISCONNECT|SESSION|PREV_CLOSE
        pa.field("security_id", pa.int32()),     # nullable (connection-level events)
        pa.field("detail", pa.string()),         # free-form / json string
        pa.field("value_num", pa.float64()),     # optional numeric (downtime s, gap s, code)
    ]
)
EVENT_COLUMNS = [f.name for f in EVENT_SCHEMA]


def normalize_tick_row(row: dict) -> dict:
    """Return a dict containing exactly TICK_COLUMNS (None for absent keys)."""
    return {col: row.get(col) for col in TICK_COLUMNS}


def normalize_event_row(row: dict) -> dict:
    return {col: row.get(col) for col in EVENT_COLUMNS}
