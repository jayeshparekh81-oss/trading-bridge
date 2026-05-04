"""Normalizer tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.strategy_engine.backtest.normalizer import (
    NormalizerError,
    normalize_candles,
)
from app.strategy_engine.schema.ohlcv import Candle


def _candle(*, ts: datetime, base: float = 100.0) -> Candle:
    return Candle(
        timestamp=ts,
        open=base,
        high=base + 1,
        low=base - 1,
        close=base,
        volume=1000,
    )


def test_normalizer_returns_sorted_copy() -> None:
    t0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    cs = [
        _candle(ts=t0 + timedelta(minutes=2)),
        _candle(ts=t0),
        _candle(ts=t0 + timedelta(minutes=1)),
    ]
    out = normalize_candles(cs)
    assert [c.timestamp for c in out] == [
        t0,
        t0 + timedelta(minutes=1),
        t0 + timedelta(minutes=2),
    ]


def test_normalizer_returns_new_list_not_alias() -> None:
    t0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    cs = [_candle(ts=t0), _candle(ts=t0 + timedelta(minutes=1))]
    out = normalize_candles(cs)
    assert out is not cs
    out.append(_candle(ts=t0 + timedelta(minutes=2)))
    assert len(cs) == 2  # input untouched


def test_normalizer_rejects_empty_list() -> None:
    with pytest.raises(NormalizerError, match="empty"):
        normalize_candles([])


def test_normalizer_rejects_single_candle() -> None:
    t0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    with pytest.raises(NormalizerError, match="at least"):
        normalize_candles([_candle(ts=t0)])


def test_normalizer_rejects_duplicate_timestamps() -> None:
    t0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    cs = [_candle(ts=t0), _candle(ts=t0)]
    with pytest.raises(NormalizerError, match="Duplicate"):
        normalize_candles(cs)


def test_normalizer_rejects_naive_timestamp() -> None:
    """The schema's Candle accepts naive datetimes; the normalizer doesn't."""
    naive = datetime(2026, 5, 4, 9, 30)
    aware = datetime(2026, 5, 4, 9, 31, tzinfo=UTC)
    naive_candle = Candle(timestamp=naive, open=100, high=101, low=99, close=100, volume=1000)
    aware_candle = _candle(ts=aware)
    with pytest.raises(NormalizerError, match="naive"):
        normalize_candles([naive_candle, aware_candle])


def test_normalizer_accepts_iterable_input() -> None:
    """Generators (one-shot iterables) work too."""
    t0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)

    from collections.abc import Iterator

    def gen() -> Iterator[Candle]:
        yield _candle(ts=t0)
        yield _candle(ts=t0 + timedelta(minutes=1))

    out = normalize_candles(gen())
    assert len(out) == 2
