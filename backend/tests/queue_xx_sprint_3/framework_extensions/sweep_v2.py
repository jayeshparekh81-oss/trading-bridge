"""Sprint 5d — Framework v2 consolidation.

Single module that supersedes the Sprint 3/4a/4b/4c/5b helpers for
future verification sweeps. Includes:

    * Data loading with timestamps (4b/4c)
    * Generic name-based input router (4b + 4c with pairwise + var-args)
    * Reference cascade — TA-Lib primary with param overrides + tuple
      column selection (Sprint 3 + 4a corrections)
    * Volume-aware data routing — whitelist-based, no regex false alarms
      (5c lesson #11)
    * Boolean-aware tier classifier (5b preview)
    * Indicator-level orchestrator: discover → invoke → compare → classify

Per spec: consolidation only. Math identical to prior sprints. Regression
sweep on the 81 prior-verified indicators must reproduce their tiers.
"""

from __future__ import annotations

import csv
import importlib
import inspect
import math
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


# ─── Data loading (4b/4c merged) ───────────────────────────────────


def load_csv_with_timestamps(csv_path: str | Path) -> dict[str, Any]:
    """yfinance CSV loader. Parses ISO 8601 timestamps."""
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


# ─── Volume-aware whitelist (5c lesson #11) ────────────────────────


VOLUME_AWARE_INDICATORS: set[str] = {
    # Sprint 1 / 3 confirmed volume-dependent
    "mfi", "obv", "cmf", "vwap", "accumulation_distribution",
    "ad_line", "chaikin_oscillator", "chaikin_money_flow",
    "money_flow_volume", "twiggs_money_flow", "volume_weighted_avg_close",
    # Sprint 4b / 5b extensions
    "ease_of_movement", "volume_breakout", "trin_proxy",
    "cumulative_volume_delta", "buying_pressure_ratio",
    "elder_force_index", "vwac",
    # Common volume customs (preemptive)
    "obv_divergence", "money_flow_index", "balance_of_power",
    "volume_oscillator", "rate_of_change_volume",
}


def is_volume_aware(module_name: str) -> bool:
    """Whitelist-based volume-aware check (replaces 4b's regex pattern
    matcher to avoid false alarms like 'trin'/'eom' not matching)."""
    return module_name in VOLUME_AWARE_INDICATORS


# ─── Generic input router (4b + 4c merged) ─────────────────────────


PARAM_TO_DATA_KEY = {
    "opens": "opens_list", "open": "opens_list",
    "highs": "highs_list", "high": "highs_list",
    "lows": "lows_list", "low": "lows_list",
    "closes": "closes_list", "close": "closes_list",
    "values": "closes_list", "source": "closes_list",
    "volumes": "volumes_list", "volume": "volumes_list",
    "timestamps": "timestamps_list", "timestamp": "timestamps_list",
}


def build_args_unified(
    fn_params: list[str],
    fn_defaults: dict[str, Any],
    data: dict[str, Any],
) -> tuple[list, dict]:
    """Unified name-based router covering 4b/4c patterns.

    Handles:
      * Conventional OHLCV params
      * Timestamp-aware params
      * Pairwise (values_a, values_b) → closes vs closes (trivial autocorr)
      * Reflection wrappers (*args, **kwargs) → closes positional
    """
    pos: list = []
    kw: dict = {}

    # Pairwise correlation special-case
    if {"values_a", "values_b"}.issubset(set(fn_params)):
        return [list(data["closes_list"]), list(data["closes_list"])], {}

    # *args/**kwargs reflection special-case
    if any(p in ("args", "kwargs") for p in fn_params):
        return [data["closes_list"]], {}

    # Generic per-param routing
    for pname in fn_params:
        if pname in PARAM_TO_DATA_KEY:
            pos.append(data[PARAM_TO_DATA_KEY[pname]])
        elif pname in fn_defaults:
            continue
        else:
            continue
    return pos, kw


# ─── TA-Lib reference cascade (Sprint 3 + 4a merged) ───────────────


TALIB_MAP: dict[str, str] = {
    # Trend / MAs
    "wma": "WMA", "trima": "TRIMA", "kama": "KAMA",
    "dema": "DEMA", "tema": "T3", "tema_3": "TEMA",
    # Oscillators
    "willr": "WILLR", "williams_pct_r": "WILLR", "williams_r": "WILLR",
    "ad_line": "AD", "adosc": "ADOSC", "chaikin_oscillator": "ADOSC",
    "obv": "OBV", "natr": "NATR", "true_range": "TRANGE",
    "ultimate_oscillator": "ULTOSC", "trix": "TRIX",
    "ppo": "PPO", "apo": "APO",
    "linear_reg": "LINEARREG", "linear_reg_slope": "LINEARREG_SLOPE",
    "linear_reg_intercept": "LINEARREG_INTERCEPT", "linear_reg_angle": "LINEARREG_ANGLE",
    "stddev": "STDDEV", "variance": "VAR",
    "midpoint": "MIDPOINT", "midprice": "MIDPRICE",
    "sar": "SAR", "parabolic_sar": "SAR",
    "bop": "BOP", "mom": "MOM", "momentum": "MOM",
    "minus_di": "MINUS_DI", "plus_di": "PLUS_DI",
    "minus_dm": "MINUS_DM", "plus_dm": "PLUS_DM",
    "dx": "DX", "adxr": "ADXR",
    "aroon": "AROON", "aroon_up": "AROON", "aroon_down": "AROON",
    "aroon_oscillator": "AROONOSC",
    "ht_trendline": "HT_TRENDLINE",
    "cmo": "CMO", "chande_momentum": "CMO",
}


TALIB_PARAM_OVERRIDES: dict[str, dict[str, int]] = {
    "aroon":              {"timeperiod": 25},
    "aroon_up":           {"timeperiod": 14},
    "aroon_down":         {"timeperiod": 14},
    "aroon_oscillator":   {"timeperiod": 14},
    "chaikin_oscillator": {"fastperiod": 3, "slowperiod": 10},
    "chande_momentum":    {"timeperiod": 9},
    "trix":               {"timeperiod": 15},
    "ultimate_oscillator": {"timeperiod1": 7, "timeperiod2": 14, "timeperiod3": 28},
    "variance":           {"timeperiod": 20, "nbdev": 1},
}


TALIB_TUPLE_COLUMN: dict[str, int] = {
    "aroon": 1, "aroon_up": 1, "aroon_down": 0,  # talib.AROON = (down, up)
}


# ─── Boolean-aware tier classifier (5b preview, formalized) ────────


def _to_np(out: Any) -> np.ndarray:
    """Coerce indicator output to 1-D float ndarray with NaN padding."""
    if isinstance(out, tuple):
        out = out[0]
    if isinstance(out, dict):
        out = next(iter(out.values()), [])
    if isinstance(out, (int, float)):
        return np.asarray([float(out)], dtype=np.float64)
    if isinstance(out, np.ndarray):
        return out.astype(np.float64, copy=False)
    if isinstance(out, list):
        return np.asarray(
            [
                np.nan if v is None
                else (float(v) if isinstance(v, (int, float, bool)) else np.nan)
                for v in out
            ],
            dtype=np.float64,
        )
    return np.asarray([], dtype=np.float64)


def _is_boolean_like(arr: np.ndarray) -> bool:
    """Detect if the finite values are a small discrete set (boolean-ish)."""
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return False
    unique = np.unique(finite)
    return len(unique) <= 3 and set(unique.tolist()).issubset({-1.0, 0.0, 1.0})


def classify(
    tt_arr: np.ndarray,
    ref_arr: np.ndarray,
    canonical_thresholds: list[float] | None = None,
) -> tuple[str, str]:
    """Return (tier, severity_reason) for a TRADETRI vs reference comparison.

    Boolean-aware: if the reference output is in {-1, 0, 1}, use
    agreement-percentage as the load-bearing classifier metric.
    Continuous: use Sprint 1/4 max-rel + threshold-flips logic.
    """
    n = min(len(tt_arr), len(ref_arr))
    if n == 0:
        return ("NEEDS_MANUAL_REVIEW", "EMPTY_OVERLAP")
    a = tt_arr[:n]
    b = ref_arr[:n]
    mask = np.isfinite(a) & np.isfinite(b)
    nfin = int(mask.sum())
    if nfin == 0:
        return ("NEEDS_MANUAL_REVIEW", "NO_FINITE_OVERLAP")

    # Boolean-aware path
    if _is_boolean_like(b):
        agree = int((a[mask] == b[mask]).sum())
        pct = 100 * agree / nfin
        if pct >= 99: return ("A", f"PASS boolean {pct:.1f}%")
        if pct >= 90: return ("B", f"MINOR boolean {pct:.1f}%")
        if pct >= 70: return ("C", f"MEDIUM boolean {pct:.1f}%")
        return ("D", f"CRITICAL boolean {pct:.1f}%")

    # Continuous path
    d = np.abs(a[mask] - b[mask])
    max_abs = float(d.max())
    rel = d / np.maximum(np.abs(b[mask]), 1e-9)
    max_rel = float(rel.max() * 100)
    nz = mask & (a != 0) & (b != 0)
    sign_flips = int(np.sum(np.sign(a[nz]) != np.sign(b[nz])))

    # Threshold-flip count
    tf = 0
    if canonical_thresholds:
        for t in canonical_thresholds:
            tf += int(np.sum((a[mask] > t) != (b[mask] > t)))

    if sign_flips > 0:
        return ("D", f"CRITICAL_SIGN_FLIPS {sign_flips}")
    if max_abs < 1e-10 and tf == 0:
        return ("A", "PASS bit-exact")
    if tf == 0 and max_rel < 5.0:
        return ("B", f"MINOR {max_rel:.4f}% rel, 0 thresh-flips")
    if tf > 0 and 0.1 < max_rel <= 5.0:
        return ("C", f"MEDIUM {max_rel:.2f}% rel + {tf} flips")
    if max_rel > 5.0:
        return ("D", f"CRITICAL {max_rel:.2f}% rel")
    return ("B", f"minor {max_rel:.4f}%")


# ─── Regression-sweep helpers ──────────────────────────────────────


def run_indicator(
    module_name: str,
    data: dict[str, Any],
) -> tuple[np.ndarray, str]:
    """Discover + invoke an indicator via name-based routing.

    Returns (output_array, error_msg). error_msg is empty on success.
    """
    try:
        mod = importlib.import_module(
            f"app.strategy_engine.indicators.calculations.{module_name}"
        )
        fn = getattr(mod, module_name, None)
        if fn is None:
            all_names = getattr(mod, "__all__", [])
            cand = [n for n in all_names if callable(getattr(mod, n, None))]
            fn = getattr(mod, cand[0]) if cand else None
        if fn is None:
            return np.asarray([]), "NO_FN"
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        defaults = {
            n: p.default for n, p in sig.parameters.items()
            if p.default is not inspect.Parameter.empty
        }
        pos, kw = build_args_unified(params, defaults, data)
        out = fn(*pos, **kw)
        return _to_np(out), ""
    except Exception as e:
        return np.asarray([]), f"{type(e).__name__}: {str(e)[:120]}"


def call_talib_reference(
    module_name: str,
    data: dict[str, Any],
) -> tuple[np.ndarray | None, str]:
    """Invoke TA-Lib reference for ``module_name`` if available."""
    import talib
    talib_name = TALIB_MAP.get(module_name)
    if talib_name is None:
        return None, ""
    fn = getattr(talib, talib_name, None)
    if fn is None:
        return None, ""
    kwargs = TALIB_PARAM_OVERRIDES.get(module_name, {})
    high, low, close, volume, opn = (
        data["high"], data["low"], data["close"], data["volume"], data["open"],
    )
    try:
        # Heuristic: try common positional shapes by indicator
        if module_name in ("aroon", "aroon_up", "aroon_down", "aroon_oscillator"):
            out = fn(high, low, **kwargs)
        elif module_name == "chaikin_oscillator":
            out = fn(high, low, close, volume, **kwargs)
        elif module_name in ("variance", "trix", "chande_momentum", "willr",
                              "williams_pct_r", "williams_r", "linear_reg",
                              "linear_reg_slope", "linear_reg_intercept",
                              "linear_reg_angle", "stddev", "midpoint",
                              "ht_trendline", "cmo", "ppo", "apo", "mom",
                              "momentum", "kama", "dema", "tema", "tema_3",
                              "wma", "trima"):
            out = fn(close, **kwargs)
        elif module_name in ("midprice", "sar", "parabolic_sar"):
            out = fn(high, low, **kwargs)
        elif module_name in ("ultimate_oscillator", "natr", "true_range",
                              "minus_di", "plus_di", "minus_dm", "plus_dm",
                              "dx", "adxr", "bop"):
            out = fn(high, low, close, **kwargs)
        elif module_name in ("ad_line", "adosc"):
            out = fn(high, low, close, volume, **kwargs)
        elif module_name == "obv":
            out = fn(close, volume, **kwargs)
        else:
            return None, ""
        if isinstance(out, tuple):
            col = TALIB_TUPLE_COLUMN.get(module_name, 0)
            out = out[col]
        return out, f"talib.{talib_name}"
    except Exception as e:
        return None, f"talib.{talib_name} error: {type(e).__name__}"


__all__ = [
    "VOLUME_AWARE_INDICATORS",
    "PARAM_TO_DATA_KEY",
    "TALIB_MAP", "TALIB_PARAM_OVERRIDES", "TALIB_TUPLE_COLUMN",
    "build_args_unified",
    "call_talib_reference",
    "classify",
    "is_volume_aware",
    "load_csv_with_timestamps",
    "run_indicator",
]
