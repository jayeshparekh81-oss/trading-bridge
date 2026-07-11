"""Parquet schemas for levels-engine outputs (Module R4)."""

from __future__ import annotations

import pyarrow as pa

LEVELS_SCHEMA = pa.schema([
    pa.field("security_id", pa.int32()),
    pa.field("symbol", pa.string()),
    pa.field("date", pa.string()),
    pa.field("level_type", pa.string()),
    pa.field("price", pa.float64()),
    pa.field("metadata", pa.string()),      # json string (may be "")
])
LEVELS_COLUMNS = [f.name for f in LEVELS_SCHEMA]

# VWAP snapshots: bands are derivable as vwap +/- k*std, so only the primitives
# are stored (band-multiplier-agnostic).
VWAP_SNAPSHOT_SCHEMA = pa.schema([
    pa.field("security_id", pa.int32()),
    pa.field("symbol", pa.string()),
    pa.field("seq", pa.int32()),            # snapshot index within the session
    pa.field("cum_volume", pa.int64()),
    pa.field("vwap", pa.float64()),
    pa.field("std", pa.float64()),
])
VWAP_SNAPSHOT_COLUMNS = [f.name for f in VWAP_SNAPSHOT_SCHEMA]


def normalize_levels_row(row: dict) -> dict:
    return {c: row.get(c) for c in LEVELS_COLUMNS}


def normalize_vwap_row(row: dict) -> dict:
    return {c: row.get(c) for c in VWAP_SNAPSHOT_COLUMNS}
