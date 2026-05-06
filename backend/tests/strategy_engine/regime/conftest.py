"""Synthetic candle builders for the regime tests.

Each helper produces a deterministic OHLCV series tuned to make a
single regime classification pop. We pin behaviour at the boundaries
(adx 25, vol percentile 0.9, etc.) by parameterising the underlying
mathematics rather than scraping market data.

Conventions:

    * All timestamps are 5-minute spaced UTC bars starting 2026-01-01.
    * ``base_price`` defaults to 100 so percentage gaps and moves are
      easy to reason about (1.0 = 1% of 100).
    * Every series has at least 80 bars by default — enough for ADX
      (28-bar warm-up) and three non-overlapping 20-bar windows the
      breakout rule needs.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

_START = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)
_DELTA = timedelta(minutes=5)


def _bar(
    i: int, *, open_: float, high: float, low: float, close: float, volume: float = 1000.0
) -> Candle:
    return Candle(
        timestamp=_START + i * _DELTA,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


# ─── Regime-shaped candle factories ────────────────────────────────────


def make_strong_uptrend_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Monotone uptrend with small intra-bar wiggle.

    Each bar advances ``+0.4`` from the previous close; intra-bar
    range is ±0.15. ADX should rise well past 25 and the 20-period
    SMA slope clears the 0.5 % bar by a wide margin.
    """
    out: list[Candle] = []
    price = base
    for i in range(n):
        close = price + 0.4
        high = close + 0.15
        low = price - 0.05
        out.append(_bar(i, open_=price, high=high, low=low, close=close))
        price = close
    return out


def make_range_bound_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Smooth 12-bar sine wave with constant intra-bar range.

    The constant ±0.5 high/low envelope keeps TR uniform across all
    bars, so the volatility-percentile metric falls through the
    "constant series" guard and lands at the neutral 0.5. ADX stays
    low (no sustained direction); direction_changes ≈ 5 per 30-bar
    window at 12-bar wavelength. The classifier's "weak ADX" fallback
    parks the regime in ``sideways`` (or ``low_volatility`` when
    Wilder smoothing nudges the percentile below 0.20 — both are
    accepted by the parametrised hinglish test).
    """
    out: list[Candle] = []
    for i in range(n):
        close = base + 0.5 * math.sin(2 * math.pi * i / 12.0)
        # ``open == close`` (zero-body bars) keeps the open inside the
        # high-low envelope unconditionally — no gap-day false positives.
        open_ = close
        high = close + 0.5
        low = close - 0.5
        out.append(_bar(i, open_=open_, high=high, low=low, close=close))
    return out


def make_compressed_then_range_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Sine wave whose CLOSE amplitude shrinks in the last 25% — but
    intra-bar (high-low) stays constant.

    The constant intra-bar envelope keeps TR essentially uniform across
    all bars, so the volatility-percentile metric (post the constant-
    series guard) sits at 0.5 — neither high_vol nor low_vol fires.
    The shrinking close amplitude does compress the 20-bar high-low
    *range* enough that ``range_compression_ratio`` lands well below
    0.7, satisfying the sideways predicate.

    Concretely:

      * first 75 bars: close amplitude 1.0 → 20-bar range ≈ 3.0
      * last 25 bars: close amplitude 0.3 → 20-bar range ≈ 1.6
      * ratio ≈ 0.53 < 0.7 ✓
    """
    out: list[Candle] = []
    boundary = int(n * 0.75)
    for i in range(n):
        amplitude = 1.0 if i < boundary else 0.3
        close = base + amplitude * math.sin(2 * math.pi * i / 12.0)
        # Zero-body bars keep the boundary safe — see range-bound factory.
        open_ = close
        high = close + 0.5
        low = close - 0.5
        out.append(_bar(i, open_=open_, high=high, low=low, close=close))
    return out


def make_high_atr_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Wide-range bars at the very tail so the ATR percentile of the
    last bar lands above 0.90 within its own series."""
    out: list[Candle] = []
    price = base
    for i in range(n):
        # Quiet first 80 % of the window, explosive last 20 %.
        if i < int(n * 0.8):
            high = price + 0.1
            low = price - 0.1
            close = price + (0.05 if i % 2 == 0 else -0.05)
        else:
            high = price + 5.0
            low = price - 5.0
            close = price + (3.0 if i % 2 == 0 else -3.0)
        out.append(_bar(i, open_=price, high=high, low=low, close=close))
        price = close
    return out


def make_low_atr_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Wide-range bars at the start, tight bars at the end so the
    final ATR sits below the 20th percentile of its own history."""
    out: list[Candle] = []
    price = base
    for i in range(n):
        if i < int(n * 0.6):
            high = price + 1.5
            low = price - 1.5
            close = price + (0.5 if i % 2 == 0 else -0.5)
        else:
            high = price + 0.05
            low = price - 0.05
            close = price + (0.02 if i % 2 == 0 else -0.02)
        out.append(_bar(i, open_=price, high=high, low=low, close=close))
        price = close
    return out


def make_gap_up_candles(
    n: int = 100, base: float = 100.0, gap_percent: float = 0.025
) -> list[Candle]:
    """Quiet sideways tape with a >1% gap on the final bar's open.

    The classifier requires ``|gap| > 1%`` of the prior close.
    """
    out = make_range_bound_candles(n, base)
    last = out[-1]
    prev_close = out[-2].close
    gapped_open = prev_close * (1 + gap_percent)
    gapped_close = gapped_open + 0.05
    out[-1] = _bar(
        n - 1,
        open_=gapped_open,
        high=gapped_close + 0.10,
        low=gapped_open - 0.05,
        close=gapped_close,
    )
    # Reference the original last bar for completeness so static
    # analysis doesn't flag the unused local.
    _ = last
    return out


def make_choppy_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Alternating up/down closes — direction-change count saturates
    well above the 12-flip threshold inside any 30-bar window."""
    out: list[Candle] = []
    for i in range(n):
        # Sin-flavoured alternation: every bar flips direction relative
        # to the prior bar's close.
        offset = 0.3 * math.sin(i * math.pi)
        close = base + (0.5 if i % 2 == 0 else -0.5) + offset
        open_ = base + (-0.5 if i % 2 == 0 else 0.5)
        high = base + 0.7
        low = base - 0.7
        out.append(_bar(i, open_=open_, high=high, low=low, close=close))
    return out


def make_breakout_candles(n: int = 100, base: float = 100.0) -> list[Candle]:
    """Three windows: normal, tight (compression), wide (expansion).

    The classifier walks the last 60 bars: ``oldest`` (-60..-40),
    ``middle`` (-40..-20), ``latest`` (-20..end). For breakout we
    need ``middle/oldest < 0.5`` and ``latest/middle > 1.5``. The
    factory makes ``middle`` very tight and ``latest`` very wide.
    """
    out: list[Candle] = []
    price = base
    for i in range(n):
        bars_from_end = n - 1 - i
        if bars_from_end >= 40:
            # Oldest window: wider band.
            high = price + 1.0
            low = price - 1.0
            close = price + (0.2 if i % 2 == 0 else -0.2)
        elif bars_from_end >= 20:
            # Middle window: extreme compression (tight band).
            high = price + 0.05
            low = price - 0.05
            close = price + (0.02 if i % 2 == 0 else -0.02)
        else:
            # Latest window: explosive expansion.
            high = price + 4.0
            low = price - 4.0
            close = price + (1.5 if i % 2 == 0 else -1.5)
        out.append(_bar(i, open_=price, high=high, low=low, close=close))
        price = close
    return out


# ─── Strategy factories ────────────────────────────────────────────────


def _strategy(payload_overrides: dict[str, Any]) -> StrategyJSON:
    base: dict[str, Any] = {
        "id": "regime_test_strategy",
        "name": "Regime Test Strategy",
        "mode": "expert",
        "indicators": [],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [],
        },
        "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    base.update(payload_overrides)
    return StrategyJSON.model_validate(base)


def make_trend_following_strategy() -> StrategyJSON:
    """Two-EMA crossover — canonical trend-following signature."""
    return _strategy(
        {
            "indicators": [
                {"id": "ema_9", "type": "ema", "params": {"period": 9}},
                {"id": "ema_21", "type": "ema", "params": {"period": 21}},
            ],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [
                    {"type": "indicator", "left": "ema_9", "op": ">", "right": "ema_21"},
                ],
            },
        }
    )


def make_mean_reversion_strategy() -> StrategyJSON:
    """RSI-oversold buy — canonical mean-reversion signature."""
    return _strategy(
        {
            "indicators": [
                {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
            ],
            "entry": {
                "side": "BUY",
                "operator": "AND",
                "conditions": [
                    {"type": "indicator", "left": "rsi_14", "op": "<", "value": 30.0},
                ],
            },
        }
    )
