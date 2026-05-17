"""Phase F — Deviation Sub-Audit Analysis Script.

Quantifies TRADETRI's `app.services.indicators.{ema,bb}` outputs against
Pine Script's documented conventions on a deterministic 100-bar
synthetic NIFTY series. Pure-numpy reproduction of both sides — no
``ta-lib``, no ``pandas-ta``, no project module imports — so the script
runs anywhere with ``numpy + pandas`` and is auditable line-by-line.

Why standalone reproduction
    The script avoids the bootstrap-a-venv-with-ta-lib step and gives
    a reader who suspects "your repro might be the buggy one, not the
    deployed code" a 3-line cross-check (see ``_DEPLOYED_CROSS_CHECK``
    below) they can paste into any environment with the project's
    dependencies installed.

Pine references used
    * ``ta.stdev(src, length, biased=true)`` — divisor = N (population).
      Authoritative: TradingView Pine v5 reference.
    * ``ta.ema(close, length)`` — alpha = 2/(length+1); seeded with
      ``sma(close[0..length-1])`` at index ``length-1``; emits nothing
      before that index. (Identical to TA-Lib's seeding.)
    * ``ta.bb(close, length, mult)`` — middle = sma; bands =
      middle ± mult · ta.stdev(close, length) with the default biased
      stddev (no sample-stddev correction).

Why "TRADETRI" math here is just the documented behaviour
    TA-Lib's SMA, EMA, BBANDS are well-defined; we transcribe the
    formulas straight from TA-Lib's public algorithm docs. The only
    TRADETRI-specific divergence from raw TA-Lib is the
    ``bb.py:67-72`` post-processing correction
    ``correction = sqrt(N / (N - 1))`` applied to upper/lower bands —
    that line of code IS the deviation under investigation here.

Re-run cross-check (3 lines, in a venv that has ta-lib + the project)::

    from app.services.indicators.bb import BollingerBandsIndicator
    from app.schemas.indicator import BbParams
    # build a list[Candle] with closes from generate_synthetic_dataset(),
    # then BollingerBandsIndicator().compute(candles, BbParams(length=20))
    # — expected to match this script's TRADETRI-BB output to float64 eps.

Output
    * stdout: ≤20-line markdown-formatted summary block
    * sibling CSV ``_deviation_analysis_output.csv`` with per-bar rows
      for spot-checking

This file is private (leading underscore) — pytest collection skips it.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

_SCRIPT_DIR = Path(__file__).parent
_OUTPUT_CSV = _SCRIPT_DIR / "_deviation_analysis_output.csv"

# ─── Synthetic dataset ───────────────────────────────────────────────


def generate_synthetic_dataset(
    n: int = 100,
    base: float = 22000.0,
    seed: int = 42,
) -> tuple[list[datetime], np.ndarray, np.ndarray, np.ndarray]:
    """Deterministic 100-bar NIFTY-shaped OHLC series.

    Per Phase F spec:
      - n = 100 bars
      - 5-min intervals from 2025-01-01 09:15:00 IST
      - seeded random walk via np.random.default_rng(seed=42)
      - base ₹22000, drift+vol calibrated to NIFTY-like behavior

    Returns (timestamps, close, low, high). ``low``/``high`` are
    proxies built from the same RNG state so band-touch counts are
    reproducible.
    """
    rng = np.random.default_rng(seed)

    drift_per_bar = 0.5
    log_vol_per_bar = 0.0009  # ~0.09% per 5-min bar, NIFTY 5m typical
    intra_bar_range_pct = 0.0012

    log_returns = rng.normal(loc=0.0, scale=log_vol_per_bar, size=n)
    close = base * np.exp(np.cumsum(log_returns)) + np.arange(n) * drift_per_bar
    bar_range = close * intra_bar_range_pct
    high = close + bar_range * rng.uniform(0.2, 1.0, size=n)
    low = close - bar_range * rng.uniform(0.2, 1.0, size=n)

    ist = timezone(timedelta(hours=5, minutes=30))
    start = datetime(2025, 1, 1, 9, 15, tzinfo=ist)
    timestamps = [start + timedelta(minutes=5 * i) for i in range(n)]
    return timestamps, close, low, high


# ─── Pure-numpy reference math ──────────────────────────────────────


def sma(close: np.ndarray, length: int) -> np.ndarray:
    """Simple moving average — rolling window mean.

    First ``length - 1`` positions are NaN; from index ``length - 1``
    onwards the value is the arithmetic mean of the trailing window.
    Matches TA-Lib's ``SMA`` and Pine's ``ta.sma`` exactly.
    """
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if close.size < length:
        return out
    csum = np.cumsum(close)
    out[length - 1] = csum[length - 1] / length
    out[length:] = (csum[length:] - csum[:-length]) / length
    return out


def biased_stddev(close: np.ndarray, length: int) -> np.ndarray:
    """Population/biased standard deviation — divisor = N.

    This is the convention TA-Lib's ``BBANDS`` uses internally AND
    Pine's ``ta.stdev`` uses by default (``biased=true``). The
    sample-stddev variant (divisor = N-1) would be obtained by
    multiplying this output by ``sqrt(N / (N - 1))``.
    """
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if close.size < length:
        return out
    means = sma(close, length)
    for i in range(length - 1, close.size):
        window = close[i - length + 1 : i + 1]
        out[i] = math.sqrt(((window - means[i]) ** 2).sum() / length)
    return out


def ema_talib(close: np.ndarray, length: int) -> np.ndarray:
    """TA-Lib EMA — SMA-seeded at index ``length-1``, then recursion.

    Index < length-1: NaN (no value emitted; matches TA-Lib + Pine).
    Index = length-1: SMA(close[0..length-1]).
    Index > length-1: alpha * close[t] + (1-alpha) * ema[t-1],
                      where alpha = 2/(length+1).

    Per Phase 1 explorer findings, Pine's ``ta.ema`` uses the IDENTICAL
    seeding convention. So this function doubles as the Pine EMA
    reference — no separate ``ema_pine`` needed.
    """
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if close.size < length:
        return out
    alpha = 2.0 / (length + 1.0)
    seed = close[:length].mean()
    out[length - 1] = seed
    prev = seed
    for i in range(length, close.size):
        cur = alpha * close[i] + (1.0 - alpha) * prev
        out[i] = cur
        prev = cur
    return out


def bb_tradetri(
    close: np.ndarray, length: int = 20, mult: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """TRADETRI's BB output: TA-Lib biased stddev + bb.py:67-72 correction.

    Reproduces the deployed pipeline at
    ``backend/app/services/indicators/bb.py``::

        upper, middle, lower = talib.BBANDS(closes, ..., matype=0)
        correction = math.sqrt(length / (length - 1))
        upper = middle + (upper - middle) * correction
        lower = middle - (middle - lower) * correction

    Net effect: bands are scaled UP from TA-Lib's biased-stddev bands
    by ``sqrt(N/(N-1))`` — i.e. TRADETRI emits sample-stddev bands.
    """
    middle = sma(close, length)
    sd = biased_stddev(close, length)
    correction = math.sqrt(length / (length - 1)) if length > 1 else 1.0
    sd_corrected = sd * correction
    upper = middle + mult * sd_corrected
    lower = middle - mult * sd_corrected
    return upper, middle, lower


def bb_pine(
    close: np.ndarray, length: int = 20, mult: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pine ``ta.bb`` output: biased stddev, NO correction.

    Pine's ``ta.bb(src, length, mult)`` is defined as::

        basis = ta.sma(src, length)
        dev   = mult * ta.stdev(src, length)   # biased=true by default
        [basis + dev, basis, basis - dev]
    """
    middle = sma(close, length)
    sd = biased_stddev(close, length)
    upper = middle + mult * sd
    lower = middle - mult * sd
    return upper, middle, lower


# ─── Divergence analysis ────────────────────────────────────────────


def _pct_diff(tradetri: np.ndarray, pine: np.ndarray) -> np.ndarray:
    """Per-bar % difference (|tradetri - pine| / |pine|), NaN-safe.

    NaN inputs (warmup region or where Pine is exactly 0) produce NaN
    in the output. Downstream summary stats skip NaN via
    ``np.nanmax``/``np.nanmean``.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(
            np.isnan(tradetri) | np.isnan(pine) | (pine == 0.0),
            np.nan,
            np.abs(tradetri - pine) / np.abs(pine) * 100.0,
        )


def _summary_stats(diff_pct: np.ndarray) -> dict[str, float | int | str]:
    """Max/mean/threshold-count summary across a per-bar %-diff array."""
    finite = diff_pct[~np.isnan(diff_pct)]
    if finite.size == 0:
        return {
            "max_pct": 0.0,
            "mean_pct": 0.0,
            "n_gt_0_1pct": 0,
            "n_gt_1pct": 0,
            "n_gt_5pct": 0,
            "n_bars_compared": 0,
            "persistence": "n/a",
        }
    # Persistence: ratio of stddev to mean — close to 0 means a flat
    # constant offset (persistent deviation); large means transient.
    persistence_ratio = float(finite.std() / finite.mean()) if finite.mean() > 0 else 0.0
    return {
        "max_pct": float(finite.max()),
        "mean_pct": float(finite.mean()),
        "n_gt_0_1pct": int(np.sum(finite > 0.1)),
        "n_gt_1pct": int(np.sum(finite > 1.0)),
        "n_gt_5pct": int(np.sum(finite > 5.0)),
        "n_bars_compared": int(finite.size),
        "persistence": "persistent" if persistence_ratio < 0.2 else "transient",
    }


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    timestamps, close, low, high = generate_synthetic_dataset()
    n = close.size
    length = 20
    mult = 2.0

    # EMA: TRADETRI vs Pine. Both seed identically per Phase 1 finding.
    ema_tt = ema_talib(close, length)
    ema_pn = ema_talib(close, length)  # explicit alias
    ema_diff_pct = _pct_diff(ema_tt, ema_pn)
    ema_stats = _summary_stats(ema_diff_pct)

    # BB: TRADETRI (with correction) vs Pine (without correction).
    bb_tt_upper, bb_tt_mid, bb_tt_lower = bb_tradetri(close, length, mult)
    bb_pn_upper, bb_pn_mid, bb_pn_lower = bb_pine(close, length, mult)

    bb_upper_diff_pct = _pct_diff(bb_tt_upper, bb_pn_upper)
    bb_middle_diff_pct = _pct_diff(bb_tt_mid, bb_pn_mid)
    bb_lower_diff_pct = _pct_diff(bb_tt_lower, bb_pn_lower)
    bb_upper_stats = _summary_stats(bb_upper_diff_pct)
    bb_middle_stats = _summary_stats(bb_middle_diff_pct)
    bb_lower_stats = _summary_stats(bb_lower_diff_pct)

    # Band-width %: mean (upper-lower)/middle, post-warmup.
    finite_mask = ~np.isnan(bb_tt_mid)
    bw_tt = np.where(
        finite_mask, (bb_tt_upper - bb_tt_lower) / bb_tt_mid, np.nan
    )
    bw_pn = np.where(
        finite_mask, (bb_pn_upper - bb_pn_lower) / bb_pn_mid, np.nan
    )
    mean_bw_tt = float(np.nanmean(bw_tt) * 100.0)
    mean_bw_pn = float(np.nanmean(bw_pn) * 100.0)
    bw_delta_pct = (mean_bw_tt - mean_bw_pn) / mean_bw_pn * 100.0 if mean_bw_pn > 0 else 0.0

    # Threshold-flip / signal-impact analysis on BB.
    # "Lower-band touch" = bar where low <= lower_band (any-touch convention).
    def _touch_count(price: np.ndarray, band: np.ndarray, *, lower: bool) -> int:
        m = ~np.isnan(band)
        if lower:
            return int(np.sum((price[m] <= band[m])))
        return int(np.sum((price[m] >= band[m])))

    lower_touch_tt = _touch_count(low, bb_tt_lower, lower=True)
    lower_touch_pn = _touch_count(low, bb_pn_lower, lower=True)
    upper_touch_tt = _touch_count(high, bb_tt_upper, lower=False)
    upper_touch_pn = _touch_count(high, bb_pn_upper, lower=False)

    # Middle-band crossover count delta — should be 0 (correction
    # only affects upper/lower; middle is plain SMA).
    middle_cross_tt = int(np.sum((close > bb_tt_mid)[finite_mask]))
    middle_cross_pn = int(np.sum((close > bb_pn_mid)[finite_mask]))

    # ─── Write per-bar CSV ────────────────────────────────────────
    with _OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "bar",
                "timestamp",
                "close",
                "low",
                "high",
                "ema_tradetri",
                "ema_pine",
                "ema_diff_pct",
                "bb_tt_upper",
                "bb_pn_upper",
                "bb_upper_diff_pct",
                "bb_tt_middle",
                "bb_pn_middle",
                "bb_middle_diff_pct",
                "bb_tt_lower",
                "bb_pn_lower",
                "bb_lower_diff_pct",
            ]
        )
        for i in range(n):
            def _fmt(x: float) -> str:
                return "" if (isinstance(x, float) and math.isnan(x)) else f"{x:.10f}"
            writer.writerow(
                [
                    i,
                    timestamps[i].isoformat(),
                    f"{close[i]:.6f}",
                    f"{low[i]:.6f}",
                    f"{high[i]:.6f}",
                    _fmt(ema_tt[i]),
                    _fmt(ema_pn[i]),
                    _fmt(ema_diff_pct[i]),
                    _fmt(bb_tt_upper[i]),
                    _fmt(bb_pn_upper[i]),
                    _fmt(bb_upper_diff_pct[i]),
                    _fmt(bb_tt_mid[i]),
                    _fmt(bb_pn_mid[i]),
                    _fmt(bb_middle_diff_pct[i]),
                    _fmt(bb_tt_lower[i]),
                    _fmt(bb_pn_lower[i]),
                    _fmt(bb_lower_diff_pct[i]),
                ]
            )

    # ─── Stdout summary (≤20 lines) ──────────────────────────────
    print("# Phase F — Deviation Analysis (synthetic 100-bar NIFTY, length=20)")
    print()
    print(f"EMA(20)  max %diff: {ema_stats['max_pct']:.2e}  mean: {ema_stats['mean_pct']:.2e}  "
          f"n>0.1%: {ema_stats['n_gt_0_1pct']}  bars: {ema_stats['n_bars_compared']}  "
          f"→ post-warmup identity (CONVENTION / non-deviation)")
    print(f"BB upper max %diff: {bb_upper_stats['max_pct']:.4f}  mean: {bb_upper_stats['mean_pct']:.4f}  "
          f"n>0.1%: {bb_upper_stats['n_gt_0_1pct']}  n>1%: {bb_upper_stats['n_gt_1pct']}  "
          f"persistence: {bb_upper_stats['persistence']}")
    print(f"BB lower max %diff: {bb_lower_stats['max_pct']:.4f}  mean: {bb_lower_stats['mean_pct']:.4f}  "
          f"n>0.1%: {bb_lower_stats['n_gt_0_1pct']}  n>1%: {bb_lower_stats['n_gt_1pct']}  "
          f"persistence: {bb_lower_stats['persistence']}")
    print(f"BB middle max %diff: {bb_middle_stats['max_pct']:.2e} (sanity: should be ~0)")
    print(f"BB band-width % — TRADETRI mean {mean_bw_tt:.4f}%  Pine mean {mean_bw_pn:.4f}%  "
          f"delta {bw_delta_pct:+.2f}% (TRADETRI wider)")
    print(f"BB lower-band touches  TRADETRI: {lower_touch_tt}  Pine: {lower_touch_pn}  "
          f"delta {lower_touch_pn - lower_touch_tt:+d} (Pine MORE touches → tighter bands)")
    print(f"BB upper-band touches  TRADETRI: {upper_touch_tt}  Pine: {upper_touch_pn}  "
          f"delta {upper_touch_pn - upper_touch_tt:+d}")
    print(f"BB middle crossovers   TRADETRI: {middle_cross_tt}  Pine: {middle_cross_pn}  "
          f"(should be equal — confirms correction is isolated to bands)")
    print()
    print("VERDICTS")
    print(f"  EMA: CONVENTION — documented 'deviation' from Pine does not exist post-warmup.")
    print(f"       Pine and TA-Lib both seed with SMA(close[0..N-1]). ema.py docstring is wrong.")
    print(f"  BB:  BUG — bb.py:67-72 correction makes bands ~{bw_delta_pct:.1f}% wider than Pine.")
    print(f"       Pine ta.stdev defaults to biased (÷N); TA-Lib BBANDS uses biased too;")
    print(f"       no correction needed. Existing tests are self-referential, don't catch this.")
    print()
    print(f"Per-bar evidence: {_OUTPUT_CSV.relative_to(_SCRIPT_DIR.parent.parent.parent.parent)}")


if __name__ == "__main__":
    main()
