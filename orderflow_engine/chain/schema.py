"""Parquet schema for chain snapshot output (Module R5).

One row per strike per snapshot. ΔOI windows are stored generically as w1/w2/w3
(mapped from chain.delta_oi_windows_s; the mapping is recorded in chain_summary).
"""

from __future__ import annotations

import pyarrow as pa

CHAIN_SNAPSHOT_SCHEMA = pa.schema([
    pa.field("snapshot_ts_ns", pa.int64()),
    pa.field("index", pa.string()),
    pa.field("trigger", pa.string()),        # grid | event
    pa.field("expiry", pa.string()),
    pa.field("right", pa.string()),          # CE | PE
    pa.field("strike", pa.int32()),
    pa.field("oi", pa.int64()),
    pa.field("doi_w1", pa.int64()),
    pa.field("doi_w2", pa.int64()),
    pa.field("doi_w3", pa.int64()),
    pa.field("volume", pa.int64()),
    pa.field("ltp", pa.float64()),
    pa.field("spot", pa.float64()),          # nullable
    pa.field("spot_stale", pa.bool_()),
    pa.field("iv", pa.float64()),            # nullable
    pa.field("iv_suspect", pa.bool_()),      # backed-out IV below iv_sanity_min (exclude)
    pa.field("delta", pa.float64()),         # nullable
    pa.field("gamma", pa.float64()),         # nullable
    pa.field("vega", pa.float64()),          # nullable
    pa.field("theta", pa.float64()),         # nullable
])
CHAIN_SNAPSHOT_COLUMNS = [f.name for f in CHAIN_SNAPSHOT_SCHEMA]


def normalize_snapshot_row(row: dict) -> dict:
    return {c: row.get(c) for c in CHAIN_SNAPSHOT_COLUMNS}
