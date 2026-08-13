"""Glass-box signals output schema (Module R6). One row per evaluated candidate."""

from __future__ import annotations

import pyarrow as pa

SIGNALS_SCHEMA = pa.schema([
    pa.field("ts_ns", pa.int64()),
    pa.field("index", pa.string()),
    pa.field("instrument", pa.string()),
    pa.field("side", pa.string()),          # long | short
    pa.field("price", pa.float64()),
    pa.field("score", pa.float64()),
    pa.field("threshold", pa.float64()),    # adjusted (post asymmetric gate)
    pa.field("base_threshold", pa.float64()),
    pa.field("fired", pa.bool_()),
    pa.field("gate_reason", pa.string()),   # "" if entry allowed
    pa.field("regime_direction", pa.string()),
    pa.field("regime_vol_band", pa.string()),
    pa.field("breakdown", pa.string()),     # JSON of per-component contributions
    # exit plan + simulated outcome (fired only; outcome filled at close)
    pa.field("entry", pa.float64()),
    pa.field("stop", pa.float64()),
    pa.field("target", pa.float64()),
    pa.field("r_value", pa.float64()),
    pa.field("exit_reason", pa.string()),
    pa.field("realized_r", pa.float64()),        # GROSS R (always reported)
    pa.field("cost_r", pa.float64()),            # round-trip cost in R (see signals/costs.py)
    pa.field("realized_r_net", pa.float64()),    # realized_r - cost_r (net; never replaces gross)
    pa.field("lots", pa.int64()),                # R8 sized lots (None unless r8.enabled)
    pa.field("risk_inr", pa.float64()),          # R8 ₹ risked = 1R in rupees
])
SIGNALS_COLUMNS = [f.name for f in SIGNALS_SCHEMA]


def normalize_signal_row(row: dict) -> dict:
    return {c: row.get(c) for c in SIGNALS_COLUMNS}
