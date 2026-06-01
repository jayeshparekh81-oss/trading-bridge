"""Sprint 3 — autonomous sweep runner.

Per-indicator pipeline:
    1. Resolve inputs (route by sig_kind + volume-aware → ^NSEI or RELIANCE.NS)
    2. Run TRADETRI impl with default params (signal-injected from inspect.signature)
    3. Attempt TA-Lib reference; if missing, mark NEEDS_HANDROLL
    4. Compute stats: max_delta, nan_ratio, sign_flips, threshold_flips_total
    5. Classify tier + severity

Hard-stop guards:
    - max 120 sec per indicator
    - max 50 CRITICAL classifications before STOP
    - graceful sweep abort on overall 8 hr clock
"""

from __future__ import annotations

import csv
import importlib
import math
import signal
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from .discover import discover_indicators
from .references import is_volume_aware, try_talib_reference


# ─── Data loaders ──────────────────────────────────────────────────


def _load_csv(path: Path) -> dict[str, Any]:
    closes, highs, lows, opens, volumes = [], [], [], [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            opens.append(float(row["open"]))
            volumes.append(float(row["volume"]))
    return {
        "open": np.asarray(opens, dtype=np.float64),
        "high": np.asarray(highs, dtype=np.float64),
        "low": np.asarray(lows, dtype=np.float64),
        "close": np.asarray(closes, dtype=np.float64),
        "volume": np.asarray(volumes, dtype=np.float64),
        "closes_list": closes,
        "highs_list": highs,
        "lows_list": lows,
        "opens_list": opens,
        "volumes_list": volumes,
    }


def load_test_data() -> dict[str, dict]:
    nifty = _load_csv(Path("/tmp/uu-venv/nifty_real_5m.csv"))
    reliance = _load_csv(Path("/tmp/uu-venv/reliance_real_5m.csv"))
    return {"nifty": nifty, "reliance": reliance}


# ─── Indicator runner ──────────────────────────────────────────────


def _build_args(sig_kind: str, params: list[str], defaults: dict[str, Any],
                data: dict, default_period: int = 14) -> tuple[list, dict]:
    """Build positional + keyword args for the indicator function."""
    pos = []
    kw = {}
    used = set()
    # Positional inputs by signature kind
    if sig_kind == "C":
        pos = [data["closes_list"]]
        used = {p for p in params[:1]}
    elif sig_kind == "HL":
        pos = [data["highs_list"], data["lows_list"]]
        used = set(params[:2])
    elif sig_kind == "HLC":
        pos = [data["highs_list"], data["lows_list"], data["closes_list"]]
        used = set(params[:3])
    elif sig_kind == "HLCV":
        pos = [data["highs_list"], data["lows_list"], data["closes_list"], data["volumes_list"]]
        used = set(params[:4])
    elif sig_kind == "CV":
        pos = [data["closes_list"], data["volumes_list"]]
        used = set(params[:2])
    elif sig_kind == "OHLC":
        pos = [data["opens_list"], data["highs_list"], data["lows_list"], data["closes_list"]]
        used = set(params[:4])
    elif sig_kind == "OHLCV":
        pos = [data["opens_list"], data["highs_list"], data["lows_list"], data["closes_list"], data["volumes_list"]]
        used = set(params[:5])
    # Remaining params: use defaults if available; supply default_period for periods
    for name in params:
        if name in used:
            continue
        if name in defaults:
            continue  # function will use the default
        if "period" in name.lower() or "length" in name.lower():
            kw[name] = default_period
    return pos, kw


def _to_np(out: Any) -> np.ndarray:
    """Coerce any indicator output to a 1-D ndarray of floats (NaN-padded).

    Handles: list[float|None], tuple-of-lists, dict[str, list], scalar.
    """
    if isinstance(out, tuple):
        out = out[0]  # primary series
    if isinstance(out, dict):
        # Take first value
        out = next(iter(out.values()), [])
    if isinstance(out, (int, float)):
        return np.asarray([out], dtype=np.float64)
    if isinstance(out, np.ndarray):
        return out.astype(np.float64, copy=False)
    if isinstance(out, list):
        return np.asarray(
            [np.nan if v is None else (float(v) if isinstance(v, (int, float)) else np.nan) for v in out],
            dtype=np.float64,
        )
    return np.asarray([], dtype=np.float64)


def _diff_stats(a: np.ndarray, b: np.ndarray) -> dict:
    m_len = min(len(a), len(b))
    a = a[:m_len]; b = b[:m_len]
    mask = np.isfinite(a) & np.isfinite(b)
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "max_abs": float("nan"), "mean_abs": float("nan"),
                "max_rel_pct": float("nan"), "sign_flips": 0}
    d = np.abs(a[mask] - b[mask])
    rel = d / np.maximum(np.abs(b[mask]), 1e-9)
    nz = mask & (a != 0) & (b != 0)
    flips = int(np.sum(np.sign(a[nz]) != np.sign(b[nz])))
    return {
        "n": n, "max_abs": float(d.max()), "mean_abs": float(d.mean()),
        "max_rel_pct": float(rel.max() * 100), "sign_flips": flips,
    }


def _threshold_flips(a: np.ndarray, b: np.ndarray, thresholds: list[float]) -> int:
    if not thresholds:
        return 0
    m_len = min(len(a), len(b))
    a = a[:m_len]; b = b[:m_len]
    mask = np.isfinite(a) & np.isfinite(b)
    total = 0
    for t in thresholds:
        total += int(np.sum((a[mask] > t) != (b[mask] > t)))
    return total


def _infer_thresholds(out: np.ndarray) -> list[float]:
    """Pick canonical thresholds based on output range."""
    finite = out[np.isfinite(out)]
    if len(finite) == 0:
        return []
    lo, hi = float(finite.min()), float(finite.max())
    # Oscillators 0-100
    if 0 <= lo and hi <= 105:
        return [20.0, 50.0, 80.0]
    # Oscillators -100 to +100 (CCI-like)
    if -200 <= lo and hi <= 200 and lo < 0:
        return [-100.0, 0.0, 100.0]
    # Centered at zero
    if lo < 0 < hi:
        return [0.0]
    return []


def _nan_ratio(out: np.ndarray) -> float:
    n = len(out)
    if n == 0:
        return 1.0
    return float(np.sum(~np.isfinite(out))) / n


def _classify(stats: dict, thresh_flips: int, nan_ratio: float, ref_kind: str) -> tuple[str, str]:
    """Sprint 3 tier: A/B/C/D + severity tag."""
    if ref_kind == "NEEDS_HANDROLL" or ref_kind == "FAILED":
        return ("NEEDS_MANUAL_REVIEW", "NEEDS_REF")
    if nan_ratio > 0.95:
        return ("D", "CRITICAL_ALL_NAN")
    if stats["sign_flips"] > 0:
        return ("D", "CRITICAL_SIGN_FLIPS")
    max_abs = stats["max_abs"]
    max_rel = stats["max_rel_pct"]
    if max_abs < 1e-10 and thresh_flips == 0:
        return ("A", "PASS")
    if thresh_flips == 0 and max_rel < 5.0:
        return ("B", "MINOR")
    if max_rel > 5.0 and thresh_flips > 0:
        return ("D", "CRITICAL_STRUCTURAL")
    if thresh_flips > 0 and 0.1 < max_rel <= 5.0:
        return ("C", "MEDIUM")
    if max_rel > 5.0:
        return ("D", "CRITICAL_DIVERGENCE")
    return ("B", "MINOR")


# ─── Per-indicator runner with timeout ─────────────────────────────


class IndicatorTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise IndicatorTimeout()


def sweep_one(row: dict, data_sources: dict, per_indicator_timeout: int = 120) -> dict:
    """Run a single indicator end-to-end."""
    started = time.time()
    module = row["module"]
    fn_name = row["function"]
    sig_kind = row["signature_kind"]
    params = row["params"]
    defaults = row["defaults"]

    result = {
        "name": module,
        "function": fn_name,
        "signature_kind": sig_kind,
        "params": "|".join(params),
        "reference_source": "",
        "max_delta": "",
        "mean_delta": "",
        "max_rel_pct": "",
        "nan_ratio": "",
        "sign_flips": "",
        "threshold_flips": "",
        "tier": "",
        "severity": "",
        "recommended_next_action": "",
        "runtime_sec": "",
        "error": "",
    }

    # Fast-path skip for non-runnable kinds
    if sig_kind in ("UNKNOWN", "IMPORT_FAIL", "NO_PUBLIC_FN", "SIG_FAIL", "SCALAR"):
        result["tier"] = "NEEDS_MANUAL_REVIEW"
        result["severity"] = "NON_RUNNABLE"
        result["recommended_next_action"] = "Manual signature classification"
        result["error"] = row.get("error", "non-runnable kind")
        result["runtime_sec"] = f"{time.time()-started:.3f}"
        return result

    data = data_sources["reliance"] if is_volume_aware(module) else data_sources["nifty"]
    result["reference_source"] = "talib_or_handroll"

    # Set SIGALRM timeout (Unix only)
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(per_indicator_timeout)
    try:
        mod = importlib.import_module(
            f"app.strategy_engine.indicators.calculations.{module}"
        )
        fn = getattr(mod, fn_name)
        pos, kw = _build_args(sig_kind, params, defaults, data)
        tt_out = fn(*pos, **kw)
        tt_arr = _to_np(tt_out)

        ref_arr, ref_name = try_talib_reference(
            module, sig_kind,
            {"open": data["open"], "high": data["high"], "low": data["low"],
             "close": data["close"], "volume": data["volume"]},
        )

        nan_r = _nan_ratio(tt_arr)
        if ref_arr is None:
            result["reference_source"] = "NEEDS_HANDROLL"
            result["nan_ratio"] = f"{nan_r:.4f}"
            tier, sev = _classify({"max_abs": 0, "max_rel_pct": 0, "sign_flips": 0},
                                  0, nan_r, "NEEDS_HANDROLL")
            result["tier"] = tier
            result["severity"] = sev
            result["recommended_next_action"] = "Hand-roll reference (Sprint 4)"
        else:
            stats = _diff_stats(tt_arr, ref_arr.astype(np.float64))
            thresholds = _infer_thresholds(ref_arr.astype(np.float64))
            tf = _threshold_flips(tt_arr, ref_arr.astype(np.float64), thresholds)
            tier, sev = _classify(stats, tf, nan_r, "OK")
            result["reference_source"] = ref_name
            result["max_delta"] = f"{stats['max_abs']:.6e}"
            result["mean_delta"] = f"{stats['mean_abs']:.6e}"
            result["max_rel_pct"] = f"{stats['max_rel_pct']:.4f}"
            result["nan_ratio"] = f"{nan_r:.4f}"
            result["sign_flips"] = str(stats["sign_flips"])
            result["threshold_flips"] = str(tf)
            result["tier"] = tier
            result["severity"] = sev
            if tier == "A":
                result["recommended_next_action"] = "Ship as-is"
            elif tier == "B":
                result["recommended_next_action"] = "Add convention note"
            elif tier == "C":
                result["recommended_next_action"] = "Founder decision (Sprint 4 deep)"
            else:
                result["recommended_next_action"] = "Fix or deactivate consuming templates"
    except IndicatorTimeout:
        result["tier"] = "NEEDS_MANUAL_REVIEW"
        result["severity"] = "TIMEOUT"
        result["recommended_next_action"] = "Investigate runtime; possible O(n^2)"
        result["error"] = f"timeout >{per_indicator_timeout}s"
    except Exception as e:
        result["tier"] = "NEEDS_MANUAL_REVIEW"
        result["severity"] = "EXEC_FAIL"
        result["recommended_next_action"] = "Investigate exception"
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    result["runtime_sec"] = f"{time.time()-started:.3f}"
    return result
