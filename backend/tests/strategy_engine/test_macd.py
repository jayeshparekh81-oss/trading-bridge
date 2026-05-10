"""MACD calculation tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators.calculations.macd import macd


def test_macd_constant_series_is_zero_line() -> None:
    """For a constant series, fast and slow EMAs both equal the constant,
    so MACD line is identically zero (and so are signal + histogram).
    """
    values = [42.0] * 60
    macd_line, signal, hist = macd(values, fast_period=12, slow_period=26, signal_period=9)
    assert len(macd_line) == len(values) == len(signal) == len(hist)

    defined_macd = [v for v in macd_line if v is not None]
    defined_sig = [v for v in signal if v is not None]
    defined_hist = [v for v in hist if v is not None]
    assert defined_macd and defined_sig and defined_hist
    assert all(v == pytest.approx(0.0, abs=1e-12) for v in defined_macd)
    assert all(v == pytest.approx(0.0, abs=1e-12) for v in defined_sig)
    assert all(v == pytest.approx(0.0, abs=1e-12) for v in defined_hist)


def test_macd_histogram_equals_macd_minus_signal() -> None:
    values = [float(i) + (i % 4) * 0.5 for i in range(80)]
    macd_line, signal, hist = macd(values)
    for m, s, h in zip(macd_line, signal, hist, strict=True):
        if m is None or s is None or h is None:
            continue
        assert h == pytest.approx(m - s)


def test_macd_warmup_positions_match_slow_ema_warmup() -> None:
    """First defined MACD index equals slow_period - 1."""
    values = [float(i) for i in range(40)]
    slow_period = 10
    macd_line, _, _ = macd(values, fast_period=4, slow_period=slow_period, signal_period=3)
    first_defined = next(i for i, v in enumerate(macd_line) if v is not None)
    assert first_defined == slow_period - 1


def test_macd_empty_input() -> None:
    assert macd([]) == ([], [], [])


def test_macd_too_short_returns_empty() -> None:
    """Slow EMA cannot warm up -> all three outputs empty."""
    assert macd([1, 2, 3], fast_period=2, slow_period=4, signal_period=2) == (
        [],
        [],
        [],
    )


def test_macd_rejects_fast_ge_slow() -> None:
    with pytest.raises(ValueError):
        macd([1.0] * 30, fast_period=10, slow_period=10)
    with pytest.raises(ValueError):
        macd([1.0] * 30, fast_period=12, slow_period=10)


def test_macd_rejects_non_positive_periods() -> None:
    with pytest.raises(ValueError):
        macd([1.0] * 30, fast_period=0, slow_period=10)
