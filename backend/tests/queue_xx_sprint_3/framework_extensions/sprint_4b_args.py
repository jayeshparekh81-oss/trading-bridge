"""Sprint 4b — extended input routing for the 22 Sprint 3 EXEC_FAIL indicators.

Five patterns observed across the 22:

    A) opens + closes               (5 indicators) — Sprint 3 sig_kind=C
    B) opens + closes + volumes     (4 indicators) — Sprint 3 sig_kind=CV
    C) highs + lows + volumes       (1 indicator)  — Sprint 3 sig_kind=HL
    D) one of {high, low} + close   (2 indicators) — Sprint 3 sig_kind=C
    E) timestamp-aware               (10 indicators) — needs timestamps arr

Per spec: mechanical input routing only. ZERO indicator math touched.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


def load_data_with_timestamps(csv_path: str | Path) -> dict[str, Any]:
    """Like Sprint 3's load_test_data but also reads timestamps.

    yfinance CSVs carry ISO 8601 timestamps in the first column. Returned as
    a list of Python datetime objects (most indicators accept datetime-like
    iterables) and a parallel np.datetime64 ndarray for vector consumers.
    """
    closes, highs, lows, opens, volumes, ts_dt, ts_str = [], [], [], [], [], [], []
    with Path(csv_path).open() as f:
        for row in csv.DictReader(f):
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            opens.append(float(row["open"]))
            volumes.append(float(row["volume"]))
            ts = row["timestamp"]
            ts_str.append(ts)
            try:
                ts_dt.append(datetime.fromisoformat(ts))
            except ValueError:
                ts_dt.append(None)
    return {
        "open": np.asarray(opens, dtype=np.float64),
        "high": np.asarray(highs, dtype=np.float64),
        "low": np.asarray(lows, dtype=np.float64),
        "close": np.asarray(closes, dtype=np.float64),
        "volume": np.asarray(volumes, dtype=np.float64),
        "opens_list": opens,
        "highs_list": highs,
        "lows_list": lows,
        "closes_list": closes,
        "volumes_list": volumes,
        "timestamps_list": ts_dt,
        "timestamps_str_list": ts_str,
    }


def build_args_4b(
    fn_params: list[str],
    fn_defaults: dict[str, Any],
    data: dict[str, Any],
) -> tuple[list, dict]:
    """Generic per-parameter-name routing.

    Walks the function's parameters in order. For each, picks the matching
    array from ``data`` based on the parameter name. Numeric parameters
    (period, length, fast, slow, threshold_pct, etc.) get their function
    default; we don't override.

    Returns ``(positional_args, keyword_args)``.
    """
    pos = []
    kw = {}

    PARAM_TO_DATA = {
        "opens":      "opens_list",
        "open":       "opens_list",
        "highs":      "highs_list",
        "high":       "highs_list",
        "lows":       "lows_list",
        "low":        "lows_list",
        "closes":     "closes_list",
        "close":      "closes_list",
        "values":     "closes_list",
        "source":     "closes_list",
        "volumes":    "volumes_list",
        "volume":     "volumes_list",
        "timestamps": "timestamps_list",
        "timestamp":  "timestamps_list",
    }

    # Walk in declared order
    for pname in fn_params:
        if pname in PARAM_TO_DATA:
            pos.append(data[PARAM_TO_DATA[pname]])
        elif pname in fn_defaults:
            # Has a default — let the function use it
            continue
        else:
            # Required positional that we don't know how to fill — leave
            # to caller error handling
            continue
    return pos, kw
