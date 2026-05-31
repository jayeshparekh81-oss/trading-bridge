"""Shared test helpers for ``tests/services/*``.

Currently exposes ``synthesise_candles`` — a deterministic NIFTY-shaped
OHLC factory used by ``test_indicator_candles.py``. Extracted here
during Queue VV cleanup so the closed-candle infrastructure tests
keep working after ``tests/services/indicators/`` was deleted.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.schemas.candle import Candle, Timeframe


def synthesise_candles(
    *,
    n: int = 200,
    base_price: float = 22500.0,
    seed: int = 42,
    drift_per_bar: float = 0.5,
    noise_amplitude: float = 25.0,
    timeframe: Timeframe = Timeframe.FIVE_MIN,
    symbol: str = "NIFTY",
    start: datetime | None = None,
) -> list[Candle]:
    """Deterministic NIFTY-shaped synthetic candles.

    Sine + Linear-Congruential pseudo-random walk seeded by ``seed``
    so the same call always produces the same series. Hand-rolled LCG
    (not ``random.Random``) keeps the test data bit-identical across
    Python versions.
    """
    if start is None:
        start = datetime(2026, 1, 15, 3, 45, tzinfo=timezone.utc)  # 09:15 IST
    state = seed & 0xFFFFFFFF
    candles: list[Candle] = []
    for i in range(n):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        noise = (state / 0xFFFFFFFF - 0.5) * 2.0 * noise_amplitude
        cycle = math.sin(i / 7.0) * (noise_amplitude * 0.4)
        close_val = base_price + drift_per_bar * i + noise + cycle
        open_val = close_val - noise * 0.3
        high_val = max(open_val, close_val) + abs(noise) * 0.5 + 0.01
        low_val = min(open_val, close_val) - abs(noise) * 0.5 - 0.01
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start + timedelta(seconds=timeframe.seconds * i),
                open=Decimal(f"{open_val:.4f}"),
                high=Decimal(f"{high_val:.4f}"),
                low=Decimal(f"{low_val:.4f}"),
                close=Decimal(f"{close_val:.4f}"),
                volume=10_000 + (state % 50_000),
            )
        )
    return candles


__all__ = ["synthesise_candles"]
