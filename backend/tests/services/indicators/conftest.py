"""Shared fixtures + helpers for indicator unit tests.

Provides:
    * ``synthetic_candles`` factory — deterministic NIFTY-shaped
      OHLC series, parametrisable by length + seed + drift + noise
      amplitude. Used as the input fixture across all 5 indicators
      so test inputs are reproducible without committing real
      market data.
    * ``fixtures_dir`` Path fixture — points at
      ``tests/services/indicators/fixtures/``.
    * ``load_fixture_csv`` helper — reads an input or expected-output
      CSV into the canonical shape (list of Candle for input, dict
      of name→list[float] for expected).
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.candle import Candle, Timeframe


_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return _FIXTURES_DIR


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

    Uses a sine + Linear-Congruential pseudo-random walk seeded by
    ``seed`` so the same call always produces the same series. The
    LCG is hand-rolled (not ``random.Random``) to keep the test data
    bit-identical across Python versions.
    """
    if start is None:
        start = datetime(2026, 1, 15, 3, 45, tzinfo=timezone.utc)  # 09:15 IST
    state = seed & 0xFFFFFFFF
    candles: list[Candle] = []
    for i in range(n):
        # LCG (Numerical Recipes): state = (1664525 * state + 1013904223) mod 2^32
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        noise = (state / 0xFFFFFFFF - 0.5) * 2.0 * noise_amplitude
        cycle = math.sin(i / 7.0) * (noise_amplitude * 0.4)
        close_val = base_price + drift_per_bar * i + noise + cycle
        # Build OHLC such that the schema's invariants are satisfied:
        # low <= min(open, close) <= max(open, close) <= high.
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


@pytest.fixture
def synthetic_candles() -> list[Candle]:
    """Default 200-candle 5m series."""
    return synthesise_candles()


def load_input_csv(path: Path) -> list[Candle]:
    """Read a fixture input CSV → list[Candle].

    Schema: ``timestamp,open,high,low,close,volume`` with the
    timestamp as ISO 8601 UTC.
    """
    candles: list[Candle] = []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            candles.append(
                Candle(
                    symbol="NIFTY",
                    timeframe=Timeframe.FIVE_MIN,
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=int(row["volume"]),
                )
            )
    return candles


def load_expected_csv(path: Path) -> dict[str, list[float | None]]:
    """Read a fixture expected CSV → dict of series-name → values.

    First column is the timestamp (ignored — alignment is positional).
    Each subsequent column is one output series. Cells equal to ``""``
    or ``"NaN"`` parse to ``None``.
    """
    out: dict[str, list[float | None]] = {}
    with path.open() as fh:
        reader = csv.DictReader(fh)
        names = [name for name in reader.fieldnames or [] if name != "timestamp"]
        for name in names:
            out[name] = []
        for row in reader:
            for name in names:
                cell = (row[name] or "").strip()
                if cell == "" or cell.lower() == "nan":
                    out[name].append(None)
                else:
                    out[name].append(float(cell))
    return out


def write_expected_csv(
    path: Path,
    timestamps: list[datetime],
    series: dict[str, list[float]],
) -> None:
    """Inverse of :func:`load_expected_csv` — used by fixture
    generators in test setup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp"] + list(series.keys())
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        n = len(timestamps)
        for i in range(n):
            row: dict[str, str] = {"timestamp": timestamps[i].isoformat()}
            for name, values in series.items():
                val = values[i]
                if val is None or math.isnan(val):
                    row[name] = ""
                else:
                    row[name] = f"{val:.10f}"
            writer.writerow(row)
