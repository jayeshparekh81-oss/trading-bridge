"""Queue EEE — smoke-test harness for 137 SKIPPED indicators.

Execution-quality testing only. No reference verification, no math fixes.
For each indicator we run the smoke battery (S1–S5) over 6 synthetic regimes
and classify SMOKE_PASS / SMOKE_WARN / SMOKE_FAIL.

Invocation:
    python -m backend.tests.queue_eee_smoketests.smoke_runner --batch 1
    python -m backend.tests.queue_eee_smoketests.smoke_runner --batch 1 --limit 5
"""

from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import math
import signal
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# Make backend importable when run as a script
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CALC_PKG = "app.strategy_engine.indicators.calculations"
SKIP_CSV = BACKEND_DIR / "tests" / "queue_xx_sprint_3" / "sprint_6b_needs_manual_review.csv"
RESULTS_CSV = Path(__file__).parent / "results.csv"
PER_RUN_TIMEOUT_SEC = 30

BATCH_SIZE = 25


# ─── Synthetic regimes ───────────────────────────────────────────────


def _lcg_series(n: int, seed: int, base: float, drift: float, noise_amp: float) -> dict:
    """Deterministic OHLCV via LCG; same scheme as services/_helpers.synthesise_candles."""
    state = seed & 0xFFFFFFFF
    opens, highs, lows, closes, vols = [], [], [], [], []
    for i in range(n):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        noise = (state / 0xFFFFFFFF - 0.5) * 2.0 * noise_amp
        cycle = math.sin(i / 7.0) * (noise_amp * 0.4)
        c = base + drift * i + noise + cycle
        o = c - noise * 0.3
        h = max(o, c) + abs(noise) * 0.5 + 0.01
        l = min(o, c) - abs(noise) * 0.5 - 0.01
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        vols.append(10_000 + (state % 50_000))
    return _pack(opens, highs, lows, closes, vols)


def _pack(opens, highs, lows, closes, vols) -> dict:
    return {
        "open": np.asarray(opens, dtype=np.float64),
        "high": np.asarray(highs, dtype=np.float64),
        "low": np.asarray(lows, dtype=np.float64),
        "close": np.asarray(closes, dtype=np.float64),
        "volume": np.asarray(vols, dtype=np.float64),
        "opens_list": list(opens),
        "highs_list": list(highs),
        "lows_list": list(lows),
        "closes_list": list(closes),
        "volumes_list": list(vols),
    }


def build_regimes() -> dict[str, dict]:
    """6 synthetic regimes spec'd in QUEUE_EEE_STATE.md."""
    r1 = _lcg_series(200, seed=11, base=22_500, drift=+1.2, noise_amp=10.0)
    r2 = _lcg_series(200, seed=22, base=22_500, drift=-1.2, noise_amp=10.0)
    r3 = _lcg_series(200, seed=33, base=22_500, drift=0.0, noise_amp=2.0)

    # R4 gappy: take r1 and inject ±2% gaps every 50 bars to closes/opens
    r4 = _lcg_series(200, seed=44, base=22_500, drift=+0.4, noise_amp=15.0)
    gap = 22_500 * 0.02
    direction = +1
    for k in range(50, 200, 50):
        shift = direction * gap
        r4["close"][k:] = r4["close"][k:] + shift
        r4["open"][k:] = r4["open"][k:] + shift
        r4["high"][k:] = r4["high"][k:] + shift
        r4["low"][k:] = r4["low"][k:] + shift
        for k2 in range(k, 200):
            r4["closes_list"][k2] += shift
            r4["opens_list"][k2] += shift
            r4["highs_list"][k2] += shift
            r4["lows_list"][k2] += shift
        direction *= -1

    r5 = _lcg_series(10, seed=55, base=22_500, drift=+0.5, noise_amp=8.0)

    r6 = _lcg_series(200, seed=66, base=22_500, drift=+0.3, noise_amp=12.0)
    r6["volume"] = np.zeros_like(r6["volume"])
    r6["volumes_list"] = [0.0] * 200

    return {
        "R1_uptrend": r1,
        "R2_downtrend": r2,
        "R3_flat": r3,
        "R4_gappy": r4,
        "R5_minimal_bars": r5,
        "R6_zero_volume": r6,
    }


# ─── Signature classification (Sprint 3 lessons; small but local) ────


def detect_sig_kind(params: list[str]) -> str:
    p = set(params)
    has = lambda *names: any(n in p for n in names)
    has_high = has("highs", "high")
    has_low = has("lows", "low")
    has_close = has("closes", "close", "values", "source")
    has_open = has("opens", "open")
    has_volume = has("volumes", "volume")
    if has_open and has_high and has_low and has_close and has_volume:
        return "OHLCV"
    if has_open and has_high and has_low and has_close:
        return "OHLC"
    if has_high and has_low and has_close and has_volume:
        return "HLCV"
    if has_high and has_low and has_close:
        return "HLC"
    if has_high and has_low:
        return "HL"
    if has_close and has_volume:
        return "CV"
    if has_close:
        return "C"
    return "SCALAR" if params else "UNKNOWN"


def build_call(fn, data: dict) -> tuple[list, dict]:
    """Route synthetic inputs into the indicator's positional args.

    Reuses Sprint 3 sweep._build_args logic: route by sig_kind, defaults left alone.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return [], {}
    params = list(sig.parameters.keys())
    defaults = {n: p.default for n, p in sig.parameters.items()
                if p.default is not inspect.Parameter.empty}
    kind = detect_sig_kind(params)

    pos = []
    used = set()
    if kind == "C":
        pos = [data["closes_list"]]; used = set(params[:1])
    elif kind == "HL":
        pos = [data["highs_list"], data["lows_list"]]; used = set(params[:2])
    elif kind == "HLC":
        pos = [data["highs_list"], data["lows_list"], data["closes_list"]]; used = set(params[:3])
    elif kind == "HLCV":
        pos = [data["highs_list"], data["lows_list"], data["closes_list"], data["volumes_list"]]
        used = set(params[:4])
    elif kind == "CV":
        pos = [data["closes_list"], data["volumes_list"]]; used = set(params[:2])
    elif kind == "OHLC":
        pos = [data["opens_list"], data["highs_list"], data["lows_list"], data["closes_list"]]
        used = set(params[:4])
    elif kind == "OHLCV":
        pos = [data["opens_list"], data["highs_list"], data["lows_list"],
               data["closes_list"], data["volumes_list"]]
        used = set(params[:5])

    kw = {}
    for name in params:
        if name in used or name in defaults:
            continue
        # Period-ish kwargs default to 14
        lname = name.lower()
        if "period" in lname or "length" in lname or "window" in lname:
            kw[name] = 14
    return pos, kw


def coerce(out) -> np.ndarray | None:
    """Coerce indicator output → 1-D float ndarray (None when uninterpretable)."""
    if out is None:
        return np.asarray([], dtype=np.float64)
    if isinstance(out, tuple):
        out = out[0] if out else None
        if out is None:
            return np.asarray([], dtype=np.float64)
    if isinstance(out, dict):
        out = next(iter(out.values()), [])
    if isinstance(out, (bool,)):
        return np.asarray([float(out)], dtype=np.float64)
    if isinstance(out, (int, float)):
        return np.asarray([float(out)], dtype=np.float64)
    if isinstance(out, np.ndarray):
        try:
            return out.astype(np.float64, copy=False).ravel()
        except (TypeError, ValueError):
            return None
    if isinstance(out, list):
        flat = []
        for v in out:
            if v is None:
                flat.append(np.nan)
            elif isinstance(v, bool):
                flat.append(float(v))
            elif isinstance(v, (int, float)):
                flat.append(float(v))
            else:
                flat.append(np.nan)
        return np.asarray(flat, dtype=np.float64)
    return None


# ─── Per-indicator timeout ───────────────────────────────────────────


class _Timeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _Timeout()


def _safe_call(fn, pos, kw, timeout=PER_RUN_TIMEOUT_SEC):
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        return fn(*pos, **kw), None
    except _Timeout:
        return None, "TIMEOUT"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ─── Smoke battery ───────────────────────────────────────────────────


def _post_warmup_finite(arr: np.ndarray) -> bool:
    """At least one finite value in the trailing 30% (or in whole array if too short)."""
    if arr is None or len(arr) == 0:
        return False
    if np.any(np.isinf(arr)):
        return False
    tail_start = max(0, int(len(arr) * 0.7))
    tail = arr[tail_start:]
    if len(tail) == 0:
        tail = arr
    return bool(np.any(np.isfinite(tail)))


def _nan_safe_equal(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    if a is None or b is None:
        return a is b
    if len(a) != len(b):
        return False
    mask_a = np.isfinite(a)
    mask_b = np.isfinite(b)
    if not np.array_equal(mask_a, mask_b):
        return False
    return bool(np.array_equal(a[mask_a], b[mask_b]))


def run_battery(module_name: str, fn, regimes: dict) -> dict:
    """S1–S5 per regime, then aggregate into a classification."""
    per_regime: dict[str, dict] = {}
    for rname, rdata in regimes.items():
        pos, kw = build_call(fn, rdata)
        out, err = _safe_call(fn, pos, kw)
        arr = coerce(out) if err is None else None

        ran = err is None
        has_inf = bool(arr is not None and len(arr) > 0 and np.any(np.isinf(arr)))
        tail_ok = _post_warmup_finite(arr) if ran else False

        # Length match — primary input length
        input_len = len(rdata["closes_list"])
        len_match = (arr is not None and (len(arr) == input_len or len(arr) == 1))

        per_regime[rname] = {
            "ran": ran,
            "err": err or "",
            "out_len": (len(arr) if arr is not None else -1),
            "input_len": input_len,
            "has_inf": has_inf,
            "tail_ok": tail_ok,
            "len_match": len_match,
            "_arr": arr,
        }

    # S1 — ran on normal regimes R1-R4
    normal = ("R1_uptrend", "R2_downtrend", "R3_flat", "R4_gappy")
    s1 = all(per_regime[r]["ran"] for r in normal)

    # S2 — output length matches input length (primary regime R1)
    s2 = per_regime["R1_uptrend"]["len_match"] if per_regime["R1_uptrend"]["ran"] else False

    # S3 — post-warmup has finite values on R1 + no inf anywhere across R1-R4
    s3_no_inf = not any(per_regime[r]["has_inf"] for r in normal if per_regime[r]["ran"])
    s3_tail = per_regime["R1_uptrend"]["tail_ok"] if per_regime["R1_uptrend"]["ran"] else False
    s3 = s3_no_inf and s3_tail

    # S4 — deterministic on R1: run once more, compare
    s4 = False
    if per_regime["R1_uptrend"]["ran"]:
        pos, kw = build_call(fn, regimes["R1_uptrend"])
        out2, err2 = _safe_call(fn, pos, kw)
        arr2 = coerce(out2) if err2 is None else None
        s4 = _nan_safe_equal(per_regime["R1_uptrend"]["_arr"], arr2)

    # S5 — minimal bars and zero volume did NOT crash (NaN OK)
    s5 = per_regime["R5_minimal_bars"]["ran"] and per_regime["R6_zero_volume"]["ran"]

    # Classification
    if s1 and s2 and s3 and s4 and s5:
        klass = "SMOKE_PASS"
    elif s1 and s2 and s4 and not (s3 and s5):
        klass = "SMOKE_WARN"
    else:
        klass = "SMOKE_FAIL"

    # Note
    notes = []
    if not s1:
        crashed = [r for r in normal if not per_regime[r]["ran"]]
        notes.append(f"crash_on={','.join(crashed)}")
        # Capture first error
        for r in normal:
            if per_regime[r]["err"]:
                notes.append(f"err={per_regime[r]['err'][:80]}"); break
    if not s2 and s1:
        notes.append(f"len_mismatch out={per_regime['R1_uptrend']['out_len']} in={per_regime['R1_uptrend']['input_len']}")
    if not s3:
        if not s3_no_inf:
            notes.append("contains_inf")
        if not s3_tail:
            notes.append("all_nan_tail")
    if not s4 and s1:
        notes.append("non_deterministic")
    if not s5:
        notes.append("crash_on_edge_regime")

    return {
        "S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5,
        "classification": klass,
        "note": "; ".join(notes) if notes else "clean",
    }


# ─── Driver ──────────────────────────────────────────────────────────


def load_skip_list() -> list[dict]:
    with SKIP_CSV.open() as f:
        return list(csv.DictReader(f))


def select_batch(rows: list[dict], batch_num: int) -> list[dict]:
    start = (batch_num - 1) * BATCH_SIZE
    return rows[start:start + BATCH_SIZE]


def resolve_fn(module_name: str):
    """Import + locate the primary callable. Returns (fn, err_str)."""
    try:
        mod = importlib.import_module(f"{CALC_PKG}.{module_name}")
    except Exception as e:
        return None, f"IMPORT_FAIL: {type(e).__name__}: {str(e)[:120]}"
    fn = getattr(mod, module_name, None)
    if fn is None or not callable(fn):
        all_names = getattr(mod, "__all__", [])
        for n in all_names:
            cand = getattr(mod, n, None)
            if callable(cand):
                fn = cand
                break
    if fn is None or not callable(fn):
        return None, "NO_PUBLIC_FN"
    return fn, None


def append_result_row(row: dict):
    fieldnames = ["batch", "indicator", "skip_category_note",
                  "S1", "S2", "S3", "S4", "S5",
                  "classification", "note", "runtime_sec"]
    new_file = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        w.writerow(row)


def run_batch(batch_num: int, limit: int | None = None) -> dict:
    rows = load_skip_list()
    batch = select_batch(rows, batch_num)
    if limit:
        batch = batch[:limit]
    regimes = build_regimes()
    summary = {"pass": 0, "warn": 0, "fail": 0, "total": len(batch)}
    print(f"\n=== Batch {batch_num}: {len(batch)} indicators ===\n")
    for entry in batch:
        ind = entry["name"]
        skip_note = entry["severity"]
        t0 = time.time()
        fn, err = resolve_fn(ind)
        if fn is None:
            result = {
                "S1": False, "S2": False, "S3": False, "S4": False, "S5": False,
                "classification": "SMOKE_FAIL",
                "note": err or "module_resolution_failed",
            }
        else:
            try:
                result = run_battery(ind, fn, regimes)
            except Exception as e:
                tb = traceback.format_exc(limit=2).replace("\n", " | ")[:200]
                result = {
                    "S1": False, "S2": False, "S3": False, "S4": False, "S5": False,
                    "classification": "SMOKE_FAIL",
                    "note": f"battery_crash: {type(e).__name__}: {str(e)[:80]} | {tb}",
                }
        dt = time.time() - t0
        summary[result["classification"].split("_")[1].lower()] += 1
        print(f"  [{result['classification']:11s}] {ind:38s} ({dt:5.2f}s)  {result['note'][:80]}")
        append_result_row({
            "batch": batch_num,
            "indicator": ind,
            "skip_category_note": skip_note,
            **{k: ("Y" if result[k] else "N") for k in ("S1", "S2", "S3", "S4", "S5")},
            "classification": result["classification"],
            "note": result["note"],
            "runtime_sec": f"{dt:.3f}",
        })
    print(f"\nBatch {batch_num} summary: pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}\n")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True, help="Batch number 1..6")
    ap.add_argument("--limit", type=int, default=None, help="Run only first N of batch (debug)")
    args = ap.parse_args()
    run_batch(args.batch, args.limit)


if __name__ == "__main__":
    main()
