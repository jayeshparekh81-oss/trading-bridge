"""Generate Phase F reference fixtures from pandas-ta-classic.

Uses ``pandas-ta-classic`` (the maintained community fork — original
``pandas-ta`` doesn't support Python 3.14) as the **independent Pine
ground truth** for the 5 MVP indicators. The Phase A audit (committed
at ``b925ea4``) noted that the existing fixture CSVs at
:file:`tests/services/indicators/fixtures/*_expected.csv` are
TA-Lib-self-derived and so are tautological — any TA-Lib regression
would shift both sides in lockstep and be undetectable. These new
fixtures break that tautology.

Why pandas-ta-classic
    Authoritative third-party implementation of Pine conventions.
    Tracks the Pine reference manual closely. Maintained for current
    Python; ``pandas-ta`` itself failed to install on Python 3.14
    because its transitive ``numba`` dep caps at <3.14.

Cross-verified against the hand-rolled Pine references in
:file:`_deviation_analysis.py` (Part 1 + Part 2 audits) — see the
verification block at the end of :func:`main`. If pandas-ta-classic
ever disagrees with the hand-roll beyond float-epsilon, this script
raises ``AssertionError`` and refuses to write the CSVs — that would
indicate either a pandas-ta-classic bug or a hand-roll bug, both of
which need to be surfaced not silently absorbed.

Run manually after a TA-Lib or pandas-ta-classic upgrade::

    cd backend
    PYTHONPATH=. /tmp/phase-f-venv/bin/python \
        tests/services/indicators/fixtures/_generate_phase_f_fixtures.py

Or from any env with numpy + pandas + pandas-ta-classic installed.

Outputs (all in this directory)
    nifty_100_bars_5m.csv           — deterministic 100-bar OHLCV input
    rsi_14_pine_expected.csv        — RSI(14) Pine reference
    sma_20_pine_expected.csv        — SMA(20) Pine reference
    ema_20_pine_expected.csv        — EMA(20) Pine reference
    macd_12_26_9_pine_expected.csv  — MACD Pine reference (3 cols)
    bollinger_20_2_pine_expected.csv — BB(20,2) Pine reference (3 cols)
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

_FIX_DIR = Path(__file__).parent


# ─── Synthetic dataset (same RNG as _deviation_analysis.py) ─────────


def generate_synthetic_dataset(
    n: int = 100, base: float = 22000.0, seed: int = 42
) -> tuple[list[datetime], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Deterministic 100-bar NIFTY-shaped OHLCV.

    Mirrors :func:`_deviation_analysis.generate_synthetic_dataset`
    bit-for-bit so the two audit trails share input ground truth.
    Returns ``(timestamps, open, high, low, close, volume)``.
    """
    rng = np.random.default_rng(seed)
    drift_per_bar = 0.5
    log_vol_per_bar = 0.0009
    intra_bar_range_pct = 0.0012

    log_returns = rng.normal(loc=0.0, scale=log_vol_per_bar, size=n)
    close = base * np.exp(np.cumsum(log_returns)) + np.arange(n) * drift_per_bar
    # Open = previous close (no-gap synthesis); open[0] = close[0].
    open_ = np.concatenate([[close[0]], close[:-1]])
    # High/low derived so Candle invariant
    # ``low <= min(open, close) <= max(open, close) <= high`` always holds,
    # regardless of how much close moved bar-to-bar. Range is a small
    # positive buffer scaled by current price.
    bar_range = close * intra_bar_range_pct
    upper_extra = bar_range * rng.uniform(0.2, 1.0, size=n)
    lower_extra = bar_range * rng.uniform(0.2, 1.0, size=n)
    high = np.maximum(open_, close) + upper_extra
    low = np.minimum(open_, close) - lower_extra
    # Volume: small noise-scaled int series so the CSV has plausible values.
    volume = (10_000 + (np.abs(log_returns) * 5_000_000).astype(int)).tolist()

    ist = timezone(timedelta(hours=5, minutes=30))
    start = datetime(2025, 1, 1, 9, 15, tzinfo=ist)
    timestamps = [start + timedelta(minutes=5 * i) for i in range(n)]
    return timestamps, open_, high, low, close, np.array(volume, dtype=np.int64)


# ─── Hand-rolled Pine references for cross-verification ─────────────
# (copied from _deviation_analysis.py — verified Pine-correct in
# PHASE_F_DEVIATION_ANALYSIS.md + PART2.md)


def _sma(close: np.ndarray, length: int) -> np.ndarray:
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if close.size < length:
        return out
    csum = np.cumsum(close)
    out[length - 1] = csum[length - 1] / length
    out[length:] = (csum[length:] - csum[:-length]) / length
    return out


def _biased_stddev(close: np.ndarray, length: int) -> np.ndarray:
    out = np.full(close.shape, np.nan, dtype=np.float64)
    means = _sma(close, length)
    for i in range(length - 1, close.size):
        window = close[i - length + 1 : i + 1]
        out[i] = math.sqrt(((window - means[i]) ** 2).sum() / length)
    return out


def _ema(close: np.ndarray, length: int) -> np.ndarray:
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if close.size < length:
        return out
    alpha = 2.0 / (length + 1.0)
    out[length - 1] = close[:length].mean()
    prev = out[length - 1]
    for i in range(length, close.size):
        prev = alpha * close[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _rsi_wilder(close: np.ndarray, length: int = 14) -> np.ndarray:
    n = close.size
    rsi = np.full(n, np.nan, dtype=np.float64)
    if n < length + 1:
        return rsi
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(gains[:length].mean())
    avg_loss = float(losses[:length].mean())
    rsi[length] = 100.0 if avg_loss == 0.0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(length + 1, n):
        avg_gain = (avg_gain * (length - 1) + gains[i - 1]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i - 1]) / length
        rsi[i] = 100.0 if avg_loss == 0.0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return rsi


def _macd(
    close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = close.size
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = np.full(n, np.nan, dtype=np.float64)
    histogram = np.full(n, np.nan, dtype=np.float64)
    first_valid_macd = slow - 1
    first_valid_signal = slow + signal - 2
    if n > first_valid_signal:
        seed_window = macd_line[first_valid_macd : first_valid_macd + signal]
        prev = float(seed_window.mean())
        signal_line[first_valid_signal] = prev
        alpha = 2.0 / (signal + 1.0)
        for i in range(first_valid_signal + 1, n):
            prev = alpha * macd_line[i] + (1.0 - alpha) * prev
            signal_line[i] = prev
        histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bb_pine(
    close: np.ndarray, length: int = 20, mult: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    middle = _sma(close, length)
    sd = _biased_stddev(close, length)
    return middle + mult * sd, middle, middle - mult * sd


# ─── pandas-ta-classic computation ──────────────────────────────────


def _pdta_sma(close: np.ndarray, length: int = 20) -> np.ndarray:
    return ta.sma(pd.Series(close), length=length).to_numpy(dtype=np.float64)


def _pdta_ema(close: np.ndarray, length: int = 20) -> np.ndarray:
    # pandas-ta-classic ta.ema defaults to ``presma=True`` (SMA-seeded)
    # which matches Pine ta.ema and TA-Lib EMA. Explicit for clarity.
    return ta.ema(pd.Series(close), length=length, presma=True).to_numpy(
        dtype=np.float64
    )


def _pdta_rsi(close: np.ndarray, length: int = 14) -> np.ndarray:
    return ta.rsi(pd.Series(close), length=length).to_numpy(dtype=np.float64)


def _pdta_macd(
    close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD built compositionally from pandas-ta-classic's SMA-seeded EMA.

    pandas-ta-classic's top-level ``ta.macd`` uses ``presma=False`` for
    its internal EMAs, which doesn't match Pine ``ta.macd`` (which uses
    SMA-seeded EMAs throughout, same as TA-Lib). To get a Pine-correct
    pandas-ta-classic MACD reference we rebuild compositionally using
    ``ta.ema(..., presma=True)`` — which independently matched the
    hand-rolled Pine EMA to machine epsilon in the SMA/EMA verification
    above.
    """
    s = pd.Series(close)
    fast_ema = ta.ema(s, length=fast, presma=True).to_numpy(dtype=np.float64)
    slow_ema = ta.ema(s, length=slow, presma=True).to_numpy(dtype=np.float64)
    macd_line = fast_ema - slow_ema
    signal_line = ta.ema(
        pd.Series(macd_line), length=signal, presma=True
    ).to_numpy(dtype=np.float64)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _pdta_bbands(
    close: np.ndarray, length: int = 20, std: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = ta.bbands(pd.Series(close), length=length, std=std)
    # pandas-ta-classic bbands columns: BBL_L_S, BBM_L_S, BBU_L_S, BBB_L_S, BBP_L_S
    # Format the std with the same trailing-zero-stripping pandas-ta-classic uses.
    std_label = f"{std:g}" if std != int(std) else f"{int(std)}.0"
    suffix = f"{length}_{std_label}"
    return (
        df[f"BBU_{suffix}"].to_numpy(dtype=np.float64),
        df[f"BBM_{suffix}"].to_numpy(dtype=np.float64),
        df[f"BBL_{suffix}"].to_numpy(dtype=np.float64),
    )


# ─── Output writers ─────────────────────────────────────────────────


def _fmt(x: float) -> str:
    return "" if (isinstance(x, float) and math.isnan(x)) else f"{x:.10f}"


def _write_single_value_csv(
    path: Path, timestamps: list[datetime], series: np.ndarray
) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "value"])
        for ts, v in zip(timestamps, series):
            writer.writerow([ts.isoformat(), _fmt(float(v))])


def _write_multi_csv(
    path: Path,
    timestamps: list[datetime],
    names: tuple[str, ...],
    arrays: tuple[np.ndarray, ...],
) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", *names])
        for i, ts in enumerate(timestamps):
            writer.writerow([ts.isoformat(), *(_fmt(float(a[i])) for a in arrays)])


def _write_input_csv(
    path: Path,
    timestamps: list[datetime],
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for i, ts in enumerate(timestamps):
            writer.writerow(
                [
                    ts.isoformat(),
                    f"{open_[i]:.6f}",
                    f"{high[i]:.6f}",
                    f"{low[i]:.6f}",
                    f"{close[i]:.6f}",
                    int(volume[i]),
                ]
            )


# ─── Cross-verification ─────────────────────────────────────────────


def _verify(name: str, pdta: np.ndarray, hand: np.ndarray, atol: float = 1e-6) -> None:
    """Compare pandas-ta-classic against hand-rolled Pine reference.

    Compares VALUES on the intersection of finite (non-NaN) positions.
    Differences in NaN mask are reported as a warning, not an error —
    pandas-ta-classic sometimes propagates a downstream NaN backward
    (e.g. MACD line masked until signal line is valid), but the
    underlying values where both are non-NaN must agree to ``atol``.

    Raises ``AssertionError`` only on a VALUE disagreement beyond
    ``atol``. Mask divergences are surfaced but don't fail the run.
    """
    nan_pdta = np.isnan(pdta)
    nan_hand = np.isnan(hand)
    mask_note = ""
    if not np.array_equal(nan_pdta, nan_hand):
        mask_note = (
            f"  (mask diverges: pdta_nan={int(nan_pdta.sum())} "
            f"hand_nan={int(nan_hand.sum())})"
        )
    finite = ~(nan_pdta | nan_hand)
    if not finite.any():
        print(f"  {name:<10s} (all-NaN, nothing to compare){mask_note}")
        return
    diff = np.abs(pdta[finite] - hand[finite])
    max_diff = float(diff.max())
    if max_diff > atol:
        worst = int(np.argmax(diff))
        finite_idx = int(np.where(finite)[0][worst])
        raise AssertionError(
            f"{name}: max abs value diff {max_diff:.3e} > atol {atol:.0e} at bar {finite_idx}; "
            f"pdta={pdta[finite_idx]:.6f} hand={hand[finite_idx]:.6f}"
        )
    print(
        f"  {name:<10s} max abs value diff {max_diff:.3e}  "
        f"bars compared {int(finite.sum())}{mask_note}"
    )


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    timestamps, open_, high, low, close, volume = generate_synthetic_dataset()

    # 1. Compute references both ways.
    sma_pdta = _pdta_sma(close, 20)
    ema_pdta = _pdta_ema(close, 20)
    rsi_pdta = _pdta_rsi(close, 14)
    macd_line_pdta, macd_signal_pdta, macd_hist_pdta = _pdta_macd(close, 12, 26, 9)
    bb_upper_pdta, bb_middle_pdta, bb_lower_pdta = _pdta_bbands(close, 20, 2.0)

    sma_hand = _sma(close, 20)
    ema_hand = _ema(close, 20)
    rsi_hand = _rsi_wilder(close, 14)
    macd_line_hand, macd_signal_hand, macd_hist_hand = _macd(close, 12, 26, 9)
    bb_upper_hand, bb_middle_hand, bb_lower_hand = _bb_pine(close, 20, 2.0)

    # ── TA-Lib MACD mask alignment ──
    # talib.MACD masks macd_line + histogram as NaN until the signal
    # line is also valid (i.e. NaN for indexes [0, slow+signal-3]
    # = [0, 32] for the default 12/26/9), even though those macd_line
    # values are mathematically defined from index slow-1 = 25.
    # pandas-ta-classic agrees with TA-Lib here; our hand-roll exposes
    # the earlier values. Apply TA-Lib's mask convention so the
    # fixture aligns with TRADETRI's output positionally.
    _MACD_FIRST_VALID = 26 + 9 - 2  # slow + signal - 2 = 33
    macd_line_hand = macd_line_hand.copy()
    macd_hist_hand = macd_hist_hand.copy()
    macd_line_hand[:_MACD_FIRST_VALID] = np.nan
    macd_hist_hand[:_MACD_FIRST_VALID] = np.nan

    # 2. Cross-verify VALUES — pandas-ta-classic must agree with the
    #    hand-roll on the intersection of finite positions. NaN-mask
    #    divergences are noted but don't fail the run (pandas-ta-classic
    #    occasionally back-propagates downstream NaN masks).
    print("Cross-verifying pandas-ta-classic vs hand-rolled Pine reference:")
    _verify("SMA",       sma_pdta,         sma_hand)
    _verify("EMA",       ema_pdta,         ema_hand)
    _verify("RSI",       rsi_pdta,         rsi_hand)
    _verify("MACDline",  macd_line_pdta,   macd_line_hand)
    _verify("MACDsig",   macd_signal_pdta, macd_signal_hand)
    _verify("MACDhist",  macd_hist_pdta,   macd_hist_hand)
    _verify("BBupper",   bb_upper_pdta,    bb_upper_hand)
    _verify("BBmiddle",  bb_middle_pdta,   bb_middle_hand)
    _verify("BBlower",   bb_lower_pdta,    bb_lower_hand)
    print("Cross-verification OK — values agree to atol=1e-6.\n")

    # 3. Write fixtures from HAND-ROLL outputs.
    #    Rationale: TRADETRI's TA-Lib wrappers emit NaN per TA-Lib's
    #    convention (e.g. MACD line valid from index slow-1=25). The
    #    hand-roll matches that convention exactly; pandas-ta-classic
    #    sometimes back-propagates a downstream NaN mask (e.g. masks
    #    MACD line until signal line is also valid), which would cause
    #    spurious test failures on bars where TRADETRI is valid but the
    #    fixture is NaN. Hand-roll values + TA-Lib NaN mask = clean.
    _write_input_csv(
        _FIX_DIR / "nifty_100_bars_5m.csv",
        timestamps, open_, high, low, close, volume,
    )
    _write_single_value_csv(_FIX_DIR / "sma_20_pine_expected.csv", timestamps, sma_hand)
    _write_single_value_csv(_FIX_DIR / "ema_20_pine_expected.csv", timestamps, ema_hand)
    _write_single_value_csv(_FIX_DIR / "rsi_14_pine_expected.csv", timestamps, rsi_hand)
    _write_multi_csv(
        _FIX_DIR / "macd_12_26_9_pine_expected.csv",
        timestamps,
        ("macd", "signal", "histogram"),
        (macd_line_hand, macd_signal_hand, macd_hist_hand),
    )
    _write_multi_csv(
        _FIX_DIR / "bollinger_20_2_pine_expected.csv",
        timestamps,
        ("upper", "middle", "lower"),
        (bb_upper_hand, bb_middle_hand, bb_lower_hand),
    )

    print(f"Wrote 6 fixture files to {_FIX_DIR}")


if __name__ == "__main__":
    main()
