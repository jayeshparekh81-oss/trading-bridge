"""VWAP calculation tests.

Two regimes:
    * Legacy anchored-at-start (no ``timestamps`` arg, backward-compat).
    * Session-anchored (``timestamps`` arg supplied) — resets accumulators
      on each new IST trading day, skips NaN-volume bars without poisoning.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.indicators.calculations.vwap import vwap
from tests.strategy_engine.fixtures.ohlcv_sample import CLOSES, HIGHS, LOWS, VOLUMES

_IST = ZoneInfo("Asia/Kolkata")


# ─── Legacy anchored-at-start tests (backward-compat) ──────────────────


def test_vwap_first_bar_equals_typical_price() -> None:
    out = vwap(HIGHS, LOWS, CLOSES, VOLUMES)
    expected_first = (HIGHS[0] + LOWS[0] + CLOSES[0]) / 3
    assert out[0] == pytest.approx(expected_first)


def test_vwap_constant_typical_price_is_constant() -> None:
    n = 6
    h = [10.0] * n
    lo = [9.0] * n
    c = [9.0] * n
    v = [100.0, 200.0, 300.0, 0.0, 50.0, 25.0]
    out = vwap(h, lo, c, v)
    expected = (10.0 + 9.0 + 9.0) / 3
    for value in out:
        assert value == pytest.approx(expected)


def test_vwap_zero_volume_warmup_returns_none() -> None:
    out = vwap([10, 11], [9, 10], [9.5, 10.5], [0, 0])
    assert out == [None, None]


def test_vwap_zero_then_volume_starts_defined() -> None:
    out = vwap([10, 11, 12], [9, 10, 11], [9.5, 10.5, 11.5], [0, 100, 50])
    assert out[0] is None
    assert out[1] is not None
    assert out[2] is not None


def test_vwap_empty_input() -> None:
    assert vwap([], [], [], []) == []


def test_vwap_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        vwap([1, 2], [1], [1, 2], [10, 20])


def test_vwap_output_length_matches_input_length() -> None:
    out = vwap(HIGHS, LOWS, CLOSES, VOLUMES)
    assert len(out) == len(HIGHS)


# ─── Session-anchored tests (timestamps arg supplied) ──────────────────


def _ist_bars(start: datetime, count: int, step_minutes: int = 5) -> list[datetime]:
    return [start + timedelta(minutes=step_minutes * i) for i in range(count)]


def test_vwap_session_anchored_single_session_matches_unanchored() -> None:
    """Within one IST date, session-anchored output equals legacy output."""
    n = 10
    h = [100.0 + i for i in range(n)]
    lo = [99.0 + i for i in range(n)]
    c = [99.5 + i for i in range(n)]
    v = [1000.0 + 10 * i for i in range(n)]
    ts = _ist_bars(datetime(2026, 6, 2, 9, 15, tzinfo=_IST), n)

    legacy = vwap(h, lo, c, v)
    session = vwap(h, lo, c, v, ts)
    assert legacy == session


def test_vwap_session_anchored_resets_on_new_day() -> None:
    """First bar of a new IST day resets accumulators."""
    h = [100.0, 101.0, 200.0, 201.0]
    lo = [99.0, 100.0, 199.0, 200.0]
    c = [99.5, 100.5, 199.5, 200.5]
    v = [1000.0, 1000.0, 1000.0, 1000.0]
    ts = [
        datetime(2026, 6, 2, 15, 25, tzinfo=_IST),
        datetime(2026, 6, 2, 15, 30, tzinfo=_IST),
        datetime(2026, 6, 3, 9, 15, tzinfo=_IST),
        datetime(2026, 6, 3, 9, 20, tzinfo=_IST),
    ]
    out = vwap(h, lo, c, v, ts)

    expected_bar2_typical = (200.0 + 199.0 + 199.5) / 3
    assert out[2] == pytest.approx(expected_bar2_typical)

    expected_bar3 = ((200.0 + 199.0 + 199.5) / 3 * 1000.0 + (201.0 + 200.0 + 200.5) / 3 * 1000.0) / 2000.0
    assert out[3] == pytest.approx(expected_bar3)


def test_vwap_skips_nan_volume_without_poisoning() -> None:
    """NaN-volume bar must not poison cum_vol; output continues sanely."""
    h = [100.0, 101.0, 102.0, 103.0]
    lo = [99.0, 100.0, 101.0, 102.0]
    c = [99.5, 100.5, 101.5, 102.5]
    v = [1000.0, float("nan"), 1000.0, 1000.0]
    ts = _ist_bars(datetime(2026, 6, 2, 9, 15, tzinfo=_IST), 4)
    out = vwap(h, lo, c, v, ts)

    assert out[1] == pytest.approx(out[0])  # NaN bar inherits prior
    assert out[2] is not None and not math.isnan(out[2])
    assert out[3] is not None and not math.isnan(out[3])
    typical0 = (100.0 + 99.0 + 99.5) / 3
    typical2 = (102.0 + 101.0 + 101.5) / 3
    expected_bar2 = (typical0 * 1000.0 + typical2 * 1000.0) / 2000.0
    assert out[2] == pytest.approx(expected_bar2)


def test_vwap_session_anchored_empty_input_with_timestamps() -> None:
    assert vwap([], [], [], [], []) == []


def test_vwap_session_anchored_zero_volume_bar_returns_none() -> None:
    """A session whose only bars so far have zero volume produces None."""
    h = [100.0, 101.0]
    lo = [99.0, 100.0]
    c = [99.5, 100.5]
    v = [0.0, 0.0]
    ts = _ist_bars(datetime(2026, 6, 2, 9, 15, tzinfo=_IST), 2)
    out = vwap(h, lo, c, v, ts)
    assert out == [None, None]


def test_vwap_rejects_mismatched_timestamp_length() -> None:
    with pytest.raises(ValueError):
        vwap([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [10.0, 20.0], [datetime(2026, 1, 1)])


def test_vwap_naive_timestamp_treated_as_ist() -> None:
    """Naive datetime is assumed to already be in IST."""
    naive = [datetime(2026, 6, 2, 15, 25), datetime(2026, 6, 3, 9, 15)]
    h = [100.0, 200.0]
    lo = [99.0, 199.0]
    c = [99.5, 199.5]
    v = [1000.0, 1000.0]
    out = vwap(h, lo, c, v, naive)
    expected_bar1 = (200.0 + 199.0 + 199.5) / 3
    assert out[1] == pytest.approx(expected_bar1)


def test_vwap_utc_timestamp_converts_to_ist_session() -> None:
    """A UTC bar at 18:30 on 2026-06-02 = 00:00 IST 2026-06-03 (new session)."""
    h = [100.0, 200.0]
    lo = [99.0, 199.0]
    c = [99.5, 199.5]
    v = [1000.0, 1000.0]
    ts = [
        datetime(2026, 6, 2, 9, 45, tzinfo=timezone.utc),
        datetime(2026, 6, 2, 18, 30, tzinfo=timezone.utc),
    ]
    out = vwap(h, lo, c, v, ts)
    expected_bar1 = (200.0 + 199.0 + 199.5) / 3
    assert out[1] == pytest.approx(expected_bar1)
