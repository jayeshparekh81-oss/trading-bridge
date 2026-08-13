"""Parquet schema for 20-level market depth (Module R1).

One row per depth PACKET. Dhan's 20-depth feed sends the bid side and the ask
side as SEPARATE packets (feed code 41 = bid, 51 = ask), so each row carries a
single side's 20 price levels plus a ``side`` tag. This side-tagged shape is
deliberately columnar-friendly and is exactly what order-flow-imbalance (OFI)
computation consumes downstream — the recorder retains NO cross-packet state
(kdb+tick doctrine: capture stays dumb; the book is reconstructed by the
replayer/consumer, never by the writer).

Kept separate from the R0 tick schema (``recorder.schema``) so the two never
couple. Nullable everywhere below the header: a level absent from the book is
None rather than a spurious zero.
"""

from __future__ import annotations

import pyarrow as pa

DEPTH_LEVELS = 20

# side tag (normalized; the raw feed codes 41/51 map here)
SIDE_BID = 0
SIDE_ASK = 1

_LEVEL_FIELDS = []
for _i in range(1, DEPTH_LEVELS + 1):
    _LEVEL_FIELDS += [
        pa.field(f"price_{_i}", pa.float64()),
        pa.field(f"qty_{_i}", pa.int64()),
        pa.field(f"orders_{_i}", pa.int32()),
    ]

DEPTH_SCHEMA = pa.schema(
    [
        pa.field("ts_recv_ns", pa.int64()),      # epoch ns stamped at receipt
        pa.field("seq_local", pa.int64()),       # monotonic per instrument
        pa.field("security_id", pa.int32()),
        pa.field("exchange_segment", pa.int8()),
        pa.field("side", pa.int8()),             # 0 = bid, 1 = ask
        pa.field("msg_seq", pa.int64()),         # exchange message sequence (header)
    ]
    + _LEVEL_FIELDS
)

DEPTH_COLUMNS = [f.name for f in DEPTH_SCHEMA]


def normalize_depth_row(row: dict) -> dict:
    """Return a dict containing exactly DEPTH_COLUMNS (None for absent keys)."""
    return {col: row.get(col) for col in DEPTH_COLUMNS}
