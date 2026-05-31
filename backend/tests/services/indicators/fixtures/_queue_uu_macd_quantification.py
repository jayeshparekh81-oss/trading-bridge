"""Queue UU — MACD aligned-vs-independent seeding quantification.

Discovery-only script. Reproduces RC1's synthetic 720-bar series and
computes MACD(12, 26, 9) under two conventions:

A. ALIGNED-SEEDING  — ``talib.MACD(close, 12, 26, 9)``
   (TA-Lib industry default; was reached through the dead
   ``MacdIndicator`` chain that Queue VV deleted).
   Internal fast EMA is seeded at index ``slow-1 = 25`` with the
   immediately-preceding ``fast`` closes ``SMA(close[14..25])``.

B. INDEPENDENT-SEEDING — Pine docs convention:
   ``macd_line   = talib.EMA(close, 12) - talib.EMA(close, 26)``
   ``signal_line = talib.EMA(macd_line, 9)``
   Each EMA seeds at its own ``length-1`` with its own SMA.

Reports per-series divergence, sign-flip count, sample bars, and
template-signal event counts for the two LIVE shipped templates:
    - ``macd-trend-signal``    (A2 synonym path)
    - ``macd-divergence``      (C2 override path)

NEW FILE — does not touch live trading paths or existing fixtures.
Run with:
    /tmp/uu-venv/bin/python \\
        backend/tests/services/indicators/fixtures/_queue_uu_macd_quantification.py
"""

from __future__ import annotations

import math
import sys

import numpy as np
import talib

# ─── Synthetic series — RC1 closed-form copy ────────────────────────

_SYNTH_STRUCT_BARS = 330
_SYNTH_REGIME_WEIGHTS = (0.26, 0.12, 0.16, 0.16, 0.15, 0.15)


def _synth_closes(n: int = 720) -> np.ndarray:
    """Byte-identical copy of ``_synth_ohlc`` close column + filler.

    Mirrors ``backend/app/strategy_engine/api/backtest.py:662``.
    """
    struct = min(n, _SYNTH_STRUCT_BARS)
    counts = [round(w * struct) for w in _SYNTH_REGIME_WEIGHTS]
    counts[-1] = struct - sum(counts[:-1])
    closes: list[float] = []

    for k in range(counts[0]):
        closes.append(25000.0 - 1500.0 * (1.0 - math.exp(-k / 60.0)))
    prev: float | None = None
    for k in range(counts[1]):
        c = 24800.0 - 2.0 * k + 100.0 * math.sin(k / 6.0)
        prev = c
        closes.append(c)
    for k in range(counts[2]):
        closes.append(25000.0 + 200.0 * math.sin(k / 10.0))
    for k in range(counts[3]):
        closes.append(24000.0 + 8.0 * k + 140.0 * math.sin(k / 8.0))
    for k in range(counts[4]):
        closes.append(25000.0 - 25.0 * k)
    level = 25000.0
    cyc = 15
    for k in range(counts[5]):
        ph = k % cyc
        if ph == cyc - 3:
            c = level - 4.0
        elif ph == cyc - 2:
            c = level + 8.0
        else:
            c = level - 5.0
            if ph != cyc - 1:
                level -= 15.0
        closes.append(c)

    last_close = closes[-1]
    for k in range(n - struct):
        closes.append(last_close + 3.0 * math.sin(k / 9.0))

    return np.asarray(closes, dtype=np.float64)


# ─── MACD: two conventions ──────────────────────────────────────────


def macd_aligned(close: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Current TRADETRI path: ``talib.MACD`` (aligned-seeding)."""
    macd, signal, hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    return macd, signal, hist


def macd_independent(close: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pine-docs path: independent EMA seeding, composed externally."""
    ema_fast = talib.EMA(close, timeperiod=12)
    ema_slow = talib.EMA(close, timeperiod=26)
    macd = ema_fast - ema_slow
    # Signal is EMA(9) of the macd line, but macd[:25] is NaN. Trim,
    # compute, re-pad to align indices with the input series.
    valid_from = 25  # first non-NaN macd_line index
    signal_valid = talib.EMA(macd[valid_from:], timeperiod=9)
    signal = np.full_like(macd, np.nan)
    signal[valid_from:] = signal_valid
    hist = macd - signal
    return macd, signal, hist


# ─── Divergence metrics ─────────────────────────────────────────────


def _finite_mask(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.isfinite(a) & np.isfinite(b)


def diff_stats(name: str, a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """Per-series absolute + relative divergence stats."""
    mask = _finite_mask(a, b)
    n = int(mask.sum())
    if n == 0:
        return {"name": name, "n": 0}
    abs_diff = np.abs(a[mask] - b[mask])
    # Avoid div-by-zero on bars where independent macd ≈ 0
    rel_diff = abs_diff / np.maximum(np.abs(b[mask]), 1e-9)
    return {
        "name": name,
        "n_compared": n,
        "max_abs": float(abs_diff.max()),
        "mean_abs": float(abs_diff.mean()),
        "p95_abs": float(np.percentile(abs_diff, 95)),
        "max_rel_pct": float(rel_diff.max() * 100),
        "mean_rel_pct": float(rel_diff.mean() * 100),
    }


def sign_flip_count(a: np.ndarray, b: np.ndarray) -> int:
    """Bars where a and b have opposite signs (excluding NaN)."""
    mask = _finite_mask(a, b) & (a != 0) & (b != 0)
    return int(np.sum(np.sign(a[mask]) != np.sign(b[mask])))


# ─── Template-signal event counters ─────────────────────────────────


def _crossover(line: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Bool array: bar i is a crossover (line crosses ABOVE ref) if
    line[i-1] <= ref[i-1] and line[i] > ref[i]. NaN-safe."""
    above = line > ref
    prev_below = np.roll(line <= ref, 1)
    prev_below[0] = False
    finite = np.isfinite(line) & np.isfinite(ref)
    finite_prev = np.roll(finite, 1)
    finite_prev[0] = False
    return above & prev_below & finite & finite_prev


def _crossunder(line: np.ndarray, ref: np.ndarray) -> np.ndarray:
    return _crossover(ref, line)


def macd_trend_signal_events(
    macd: np.ndarray, signal: np.ndarray, hist: np.ndarray
) -> dict[str, int]:
    """Per the template:
       entry_long  = macd crosses above signal AND hist > 0
       entry_short = macd crosses below signal AND hist < 0
       exit_long   = macd crosses below signal
       exit_short  = macd crosses above signal
    """
    co = _crossover(macd, signal)
    cu = _crossunder(macd, signal)
    return {
        "entry_long": int(((co) & (hist > 0)).sum()),
        "entry_short": int(((cu) & (hist < 0)).sum()),
        "exit_long": int(cu.sum()),
        "exit_short": int(co.sum()),
    }


def macd_divergence_events(
    close: np.ndarray, macd: np.ndarray, signal: np.ndarray, hist: np.ndarray
) -> dict[str, int]:
    """Approximation of the template:
       entry_long = price lower-low in last 25 bars
                    AND macd hist higher-low (bullish divergence)
                    AND macd above its signal.

    Simplified detector: at bar i, look at i-25..i window. price_min
    at i is the rolling-25 min ending at i; histogram lower-low =
    hist[i] > hist[arg(price_min)] when price[i] is the window min.
    This is an APPROXIMATION of the real C2 override, but it's
    convention-comparable across the two MACD impls.
    """
    lookback = 25
    entries = 0
    exits = 0
    for i in range(lookback, len(close)):
        if not (np.isfinite(macd[i]) and np.isfinite(signal[i]) and np.isfinite(hist[i])):
            continue
        window_price = close[i - lookback : i + 1]
        window_hist = hist[i - lookback : i + 1]
        if not np.isfinite(window_hist).all():
            continue
        # Bullish divergence: this bar's price is the window min,
        # earlier window had a previous price min, current hist > hist
        # at that earlier price min.
        is_price_min = close[i] == window_price.min()
        if is_price_min:
            # find the second-lowest price idx (the "earlier low")
            sorted_idx = np.argsort(window_price)
            # skip current bar (last in window)
            earlier_min_local = next(
                (idx for idx in sorted_idx if idx != lookback), None
            )
            if earlier_min_local is None:
                continue
            earlier_min_global = i - lookback + earlier_min_local
            if (
                hist[i] > hist[earlier_min_global]
                and macd[i] > signal[i]
            ):
                entries += 1
        # exit: macd crosses below signal
        if (
            np.isfinite(macd[i - 1])
            and np.isfinite(signal[i - 1])
            and macd[i - 1] >= signal[i - 1]
            and macd[i] < signal[i]
        ):
            exits += 1
    return {"entry_long": entries, "exit_long": exits}


# ─── Main ───────────────────────────────────────────────────────────


def main() -> int:
    close = _synth_closes(n=720)
    print(f"Synthetic series: {close.size} bars, "
          f"min={close.min():.2f}, max={close.max():.2f}")
    print()

    A = macd_aligned(close)       # current TRADETRI
    B = macd_independent(close)   # Pine-docs

    # Per-series divergence
    print("=" * 72)
    print("PER-SERIES DIVERGENCE — aligned (current) vs independent (Pine)")
    print("=" * 72)
    for name, a, b in (
        ("macd_line", A[0], B[0]),
        ("signal_line", A[1], B[1]),
        ("histogram", A[2], B[2]),
    ):
        s = diff_stats(name, a, b)
        if s.get("n_compared", 0) == 0:
            print(f"  {name}: no overlapping finite bars")
            continue
        print(
            f"  {name:12s}  n={s['n_compared']:>3d}  "
            f"max|Δ|={s['max_abs']:>8.4f}  "
            f"mean|Δ|={s['mean_abs']:>8.4f}  "
            f"p95|Δ|={s['p95_abs']:>8.4f}  "
            f"max %|Δ|={s['max_rel_pct']:>7.4f}%"
        )

    # Sign flips on the macd line and histogram (signal-relevant)
    print()
    print("=" * 72)
    print("SIGN-FLIP COUNT (bars where one impl is +ve, other is -ve)")
    print("=" * 72)
    for name, a, b in (
        ("macd_line", A[0], B[0]),
        ("histogram", A[2], B[2]),
    ):
        n = sign_flip_count(a, b)
        finite = int(_finite_mask(a, b).sum())
        print(f"  {name:12s}  flips={n:>3d} / {finite} finite bars")

    # Crossover divergence (macd vs signal crosses) — the key event for
    # the macd-trend-signal template.
    print()
    print("=" * 72)
    print("CROSSOVER TIMING — macd vs signal (template-driving event)")
    print("=" * 72)
    co_A = _crossover(A[0], A[1])
    co_B = _crossover(B[0], B[1])
    cu_A = _crossunder(A[0], A[1])
    cu_B = _crossunder(B[0], B[1])
    print(f"  ALIGNED  (current): {int(co_A.sum())} cross-overs, "
          f"{int(cu_A.sum())} cross-unders")
    print(f"  INDEP   (Pine):     {int(co_B.sum())} cross-overs, "
          f"{int(cu_B.sum())} cross-unders")
    # Bars where one fires a crossover and the other doesn't
    co_xor = int((co_A ^ co_B).sum())
    cu_xor = int((cu_A ^ cu_B).sum())
    print(f"  crossover XOR (disagreement bars): {co_xor} cross-over, "
          f"{cu_xor} cross-under")

    # Sample 5 biggest macd_line divergences
    print()
    print("=" * 72)
    print("TOP-5 BIGGEST macd_line divergences (with bar context)")
    print("=" * 72)
    mask = _finite_mask(A[0], B[0])
    diff = np.where(mask, np.abs(A[0] - B[0]), -np.inf)
    top_idx = np.argsort(diff)[::-1][:5]
    print(
        f"  {'bar':>4s} {'close':>10s} {'A.macd':>10s} {'B.macd':>10s} "
        f"{'|Δ|':>8s} {'A.hist':>9s} {'B.hist':>9s}"
    )
    for i in top_idx:
        print(
            f"  {i:>4d} {close[i]:>10.2f} {A[0][i]:>10.4f} {B[0][i]:>10.4f} "
            f"{abs(A[0][i]-B[0][i]):>8.4f} {A[2][i]:>9.4f} {B[2][i]:>9.4f}"
        )

    # Template event counters
    print()
    print("=" * 72)
    print("LIVE TEMPLATE EVENT COUNTS — aligned vs independent")
    print("=" * 72)
    print("\n  macd-trend-signal (A2):")
    e_A = macd_trend_signal_events(*A)
    e_B = macd_trend_signal_events(*B)
    for k in e_A:
        print(f"    {k:14s}  ALIGNED={e_A[k]:>3d}  INDEP={e_B[k]:>3d}  "
              f"Δ={e_B[k]-e_A[k]:+d}")

    print("\n  macd-divergence (C2, approximated detector):")
    d_A = macd_divergence_events(close, *A)
    d_B = macd_divergence_events(close, *B)
    for k in d_A:
        print(f"    {k:14s}  ALIGNED={d_A[k]:>3d}  INDEP={d_B[k]:>3d}  "
              f"Δ={d_B[k]-d_A[k]:+d}")

    # Synthetic-data caveat
    print()
    print("=" * 72)
    print("CAVEAT")
    print("=" * 72)
    print(
        "  The 720-bar synthetic series has 330 structural bars + 390 neutral\n"
        "  filler bars. Most MACD signals fire in the in-window structural\n"
        "  region. The filler is near-flat so MACD lines converge → small abs\n"
        "  diffs there, magnitudes here represent the structural region."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
