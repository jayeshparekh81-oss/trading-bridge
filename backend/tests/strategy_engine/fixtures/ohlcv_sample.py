"""Reusable OHLCV fixtures for indicator tests.

These are tiny hand-crafted bars; we never embed CSV in tests because
canonical vectors are short and a hard-coded list is the easiest thing
for a future contributor to reason about.
"""

from __future__ import annotations

#: Monotonic-up close series — every bar's close is one rupee higher
#: than the prior. RSI on a strict-up series saturates at 100 once the
#: smoothing seed is full of gains; useful for the "RSI = 100 when
#: avg_loss == 0" branch.
MONOTONIC_UP_CLOSES: list[float] = [
    100.0,
    101.0,
    102.0,
    103.0,
    104.0,
    105.0,
    106.0,
    107.0,
    108.0,
    109.0,
    110.0,
    111.0,
    112.0,
    113.0,
    114.0,
    115.0,
]

#: Wilder's original RSI worked example — 15 closing prices that the
#: 1978 book traces through. Reproduced exactly so the test asserts
#: against numbers Wilder himself published.
#:
#: Source: J. Welles Wilder Jr., "New Concepts in Technical Trading
#: Systems" (1978), Table III "RSI Calculation". The series below is
#: the close column. Period = 14 -> first defined RSI is at index 14.
WILDER_RSI_CLOSES: list[float] = [
    44.34,
    44.09,
    44.15,
    43.61,
    44.33,
    44.83,
    45.10,
    45.42,
    45.84,
    46.08,
    45.89,
    46.03,
    45.61,
    46.28,
    46.28,
    46.00,
    46.03,
    46.41,
    46.22,
    45.64,
]

#: A synthetic 5-bar OHLCV sequence covering both up and down candles.
#: Used by ATR, VWAP, OBV tests so each indicator gets the same input
#: and the cross-indicator behaviour stays auditable.
HIGHS: list[float] = [10.0, 11.0, 12.5, 12.0, 13.0]
LOWS: list[float] = [9.0, 9.5, 11.0, 10.5, 12.0]
CLOSES: list[float] = [9.5, 11.0, 12.0, 11.0, 12.5]
VOLUMES: list[float] = [1000.0, 1500.0, 2000.0, 1200.0, 1800.0]
