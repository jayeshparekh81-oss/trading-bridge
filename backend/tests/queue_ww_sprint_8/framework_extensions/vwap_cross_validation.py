"""Cross-validate strategy_engine vwap() vs pandas-ta-classic on multi-day data.

Two checks:
    1. Convention agreement on clean multi-day 5m data (no NaN volumes).
       Expected: per-session output matches at machine-epsilon (anchor='D').
    2. NaN-volume convergence — pandas-ta-classic skips NaN via pandas'
       cumsum-with-skipna; the pre-fix `vwap.py` poisoned on NaN. The
       post-fix `vwap.py` (this sprint) skips NaN explicitly, so both
       implementations now converge. We assert that ours emits the same
       count of finite bars after a NaN-volume injection as pandas-ta.

Run:
    cd backend && python3 -m tests.queue_ww_sprint_8.framework_extensions.vwap_cross_validation
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_ta_classic as pta  # type: ignore[import-untyped]

from app.strategy_engine.indicators.calculations.vwap import vwap as ours

_IST = ZoneInfo("Asia/Kolkata")


def _synthetic_multi_day_5m(
    sessions: int = 3, bars_per_session: int = 75, seed: int = 42
) -> tuple[list[float], list[float], list[float], list[float], list[datetime]]:
    """Generate ``sessions`` NSE-shaped 5m sessions (09:15 → 15:30 IST)."""
    import random

    rng = random.Random(seed)
    h: list[float] = []
    lo: list[float] = []
    c: list[float] = []
    v: list[float] = []
    ts: list[datetime] = []
    price = 21500.0
    for s in range(sessions):
        day = datetime(2026, 6, 1 + s, 9, 15, tzinfo=_IST)
        for i in range(bars_per_session):
            bar_ts = day + timedelta(minutes=5 * i)
            close = price + rng.gauss(0, 8)
            high = max(price, close) + abs(rng.gauss(0, 4))
            low = min(price, close) - abs(rng.gauss(0, 4))
            volume = float(rng.randint(1000, 50000))
            h.append(high)
            lo.append(low)
            c.append(close)
            v.append(volume)
            ts.append(bar_ts)
            price = close
    return h, lo, c, v, ts


def check_clean_convention_agreement() -> tuple[float, float]:
    """Compare ours vs pta on clean multi-session data. Returns (max_abs, mean_abs)."""
    h, lo, c, v, ts = _synthetic_multi_day_5m(sessions=3, bars_per_session=75)

    our_out = ours(h, lo, c, v, ts)

    idx = pd.DatetimeIndex(ts)
    pta_out = pta.vwap(
        high=pd.Series(h, index=idx),
        low=pd.Series(lo, index=idx),
        close=pd.Series(c, index=idx),
        volume=pd.Series(v, index=idx),
        anchor="D",
    )

    diffs = []
    for i, (ours_i, theirs_i) in enumerate(zip(our_out, pta_out, strict=True)):
        if ours_i is None or pd.isna(theirs_i):
            continue
        diffs.append(abs(ours_i - float(theirs_i)))

    return (max(diffs), sum(diffs) / len(diffs)) if diffs else (math.nan, math.nan)


def check_nan_volume_divergence() -> dict[str, object]:
    """Ours skips NaN volume; pandas-ta poisons. Confirm expected behavior."""
    h, lo, c, v, ts = _synthetic_multi_day_5m(sessions=2, bars_per_session=75)
    v[30] = float("nan")
    v[31] = float("nan")

    our_out = ours(h, lo, c, v, ts)
    idx = pd.DatetimeIndex(ts)
    pta_out = pta.vwap(
        high=pd.Series(h, index=idx),
        low=pd.Series(lo, index=idx),
        close=pd.Series(c, index=idx),
        volume=pd.Series(v, index=idx),
        anchor="D",
    )

    our_finite_after = sum(1 for x in our_out[32:75] if x is not None and not (isinstance(x, float) and math.isnan(x)))
    pta_finite_after = int(pta_out[32:75].notna().sum())

    return {
        "our_finite_bars_after_nan_in_same_session": our_finite_after,
        "pta_finite_bars_after_nan_in_same_session": pta_finite_after,
        "both_skip_nan_correctly": our_finite_after == pta_finite_after == 43,
    }


def main() -> int:
    print("=== VWAP cross-validation: ours vs pandas-ta-classic ===\n")
    print("[1] Clean multi-session convention agreement (3 sessions × 75 bars)")
    max_diff, mean_diff = check_clean_convention_agreement()
    print(f"    max |diff| : {max_diff:.6e}")
    print(f"    mean |diff|: {mean_diff:.6e}")
    if max_diff < 1e-9:
        print("    VERDICT    : MATCH (sub-nanounit, machine-epsilon)")
        clean_ok = True
    elif max_diff < 1e-6:
        print("    VERDICT    : MATCH (numerical noise only)")
        clean_ok = True
    else:
        print(f"    VERDICT    : DIVERGENCE (max diff {max_diff:.6e})")
        clean_ok = False

    print("\n[2] NaN-volume convergence (both impls should skip)")
    nan_result = check_nan_volume_divergence()
    for k, val in nan_result.items():
        print(f"    {k:55s}: {val}")
    nan_fix_ok = bool(nan_result["both_skip_nan_correctly"])
    if nan_fix_ok:
        print("    VERDICT    : MATCH — ours now converges with pta (pre-fix poisoned)")
    else:
        print("    VERDICT    : DIVERGENCE — NaN-handling differs")

    print("\n=== Summary ===")
    print(f"  clean convention match : {'PASS' if clean_ok else 'FAIL'}")
    print(f"  NaN-skip bug fix       : {'PASS' if nan_fix_ok else 'FAIL'}")
    return 0 if (clean_ok and nan_fix_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
