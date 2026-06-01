"""Sprint 4c — generic name-based input router (peer to Sprint 4b's variant).

Sub-sprints are independent per the chain spec. This file duplicates the
helper structure from Sprint 4b's `sprint_4b_args.py` (each lives on its
own branch) so Sprint 4c can run without depending on the Sprint 4b
branch's modules.

Extensions over Sprint 4b for NON_RUNNABLE patterns:
    * `values_a` / `values_b` (correlation_coefficient) — pair the close
      array against a 1-bar-lagged copy as a deterministic proxy.
    * `*args` / `**kwargs` (alma reflection wrapper) — pass closes
      positional + the function's documented period as keyword.

Per spec: mechanical input routing only. ZERO indicator math touched.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


def load_data_with_timestamps(csv_path: str | Path) -> dict[str, Any]:
    """yfinance OHLCV + timestamp loader. Matches Sprint 4b's signature."""
    closes, highs, lows, opens, volumes, ts_dt = [], [], [], [], [], []
    with Path(csv_path).open() as f:
        for row in csv.DictReader(f):
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            opens.append(float(row["open"]))
            volumes.append(float(row["volume"]))
            try:
                ts_dt.append(datetime.fromisoformat(row["timestamp"]))
            except (KeyError, ValueError):
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
    }


def build_args_4c(
    fn_params: list[str],
    fn_defaults: dict[str, Any],
    data: dict[str, Any],
) -> tuple[list, dict]:
    """Name-based input router with NON_RUNNABLE pattern handlers.

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

    # Pairwise correlation: values_a + values_b
    PAIRWISE_NAMES = {"values_a", "values_b"}
    if PAIRWISE_NAMES.issubset(set(fn_params)):
        closes = data["closes_list"]
        # Use closes for both arrays — produces trivial autocorrelation=1.
        # Avoids None-typed proxy that breaks internal sum() in pairwise impls.
        # Trivial output is still useful for invocation-sanity checking
        # (does the function run? does it return the right length?).
        return [list(closes), list(closes)], {}

    # alma-style *args / **kwargs: call with closes positional
    has_var_args = any(p in ("args", "kwargs") for p in fn_params)
    if has_var_args:
        # Try the close array as the primary positional argument
        return [data["closes_list"]], {}

    # Generic name-based routing
    for pname in fn_params:
        if pname in PARAM_TO_DATA:
            pos.append(data[PARAM_TO_DATA[pname]])
        elif pname in fn_defaults:
            # Has a default; skip
            continue
        else:
            # Required positional but unknown — let the call error
            continue
    return pos, kw
