"""Position state + transition tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.strategy_engine.engines.position import (
    PartialExitRecord,
    PositionState,
    apply_partial_exit,
    close_position,
    open_position,
    update_on_candle,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import Side

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _candle(
    *,
    high: float,
    low: float,
    close: float,
    open_: float | None = None,
    volume: float = 1000.0,
    ts: datetime = T0,
) -> Candle:
    """Helper — build a Candle with sensible OHLC defaults."""
    o = open_ if open_ is not None else (high + low) / 2
    c = close
    # Force OHLC invariant in case the caller picked endpoints inside [low, high].
    return Candle(timestamp=ts, open=o, high=high, low=low, close=c, volume=volume)


# ─── open_position ──────────────────────────────────────────────────────


def test_open_position_buy_seeds_watermarks_at_entry() -> None:
    pos = open_position(side=Side.BUY, entry_price=100.0, quantity=10, entry_time=T0)
    assert pos.is_open is True
    assert pos.side is Side.BUY
    assert pos.remaining_quantity == 10
    assert pos.highest_price_since_entry == 100.0
    assert pos.lowest_price_since_entry == 100.0
    assert pos.trailing_stop_price is None
    assert pos.partial_exits_done == ()


def test_open_position_rejects_zero_or_negative_price() -> None:
    with pytest.raises(ValueError):
        open_position(side=Side.BUY, entry_price=0, quantity=10, entry_time=T0)
    with pytest.raises(ValueError):
        open_position(side=Side.BUY, entry_price=-1, quantity=10, entry_time=T0)


def test_open_position_rejects_zero_or_negative_quantity() -> None:
    with pytest.raises(ValueError):
        open_position(side=Side.BUY, entry_price=100, quantity=0, entry_time=T0)
    with pytest.raises(ValueError):
        open_position(side=Side.BUY, entry_price=100, quantity=-5, entry_time=T0)


# ─── update_on_candle: watermarks ───────────────────────────────────────


def test_update_on_candle_extends_watermarks() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    after = update_on_candle(pos, _candle(high=105, low=99, close=104))
    assert after.highest_price_since_entry == 105
    assert after.lowest_price_since_entry == 99


def test_update_on_candle_does_not_lower_high_or_raise_low() -> None:
    """Watermarks ratchet — they only ever move outward."""
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos = update_on_candle(pos, _candle(high=110, low=95, close=105))
    after = update_on_candle(pos, _candle(high=108, low=98, close=102))
    assert after.highest_price_since_entry == 110  # not lowered
    assert after.lowest_price_since_entry == 95  # not raised


def test_update_on_candle_immutable_input() -> None:
    """Transitions return a new state; the input is untouched."""
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    after = update_on_candle(pos, _candle(high=105, low=99, close=104))
    assert pos.highest_price_since_entry == 100
    assert after is not pos


def test_update_on_candle_noop_when_closed() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos = close_position(pos)
    after = update_on_candle(pos, _candle(high=200, low=50, close=150))
    assert after is pos


# ─── update_on_candle: trailing stop ────────────────────────────────────


def test_trailing_stop_seeds_then_ratchets_up_for_buy() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    # First candle: high=110, trail = 110 * 0.99 = 108.9
    pos = update_on_candle(pos, _candle(high=110, low=99, close=108), trailing_stop_percent=1.0)
    assert pos.trailing_stop_price == pytest.approx(108.9)
    # Next candle: high lower than seen — trail must NOT decrease.
    pos = update_on_candle(pos, _candle(high=105, low=100, close=103), trailing_stop_percent=1.0)
    assert pos.trailing_stop_price == pytest.approx(108.9)
    # Next candle: new high 115 -> trail jumps to 115 * 0.99 = 113.85
    pos = update_on_candle(pos, _candle(high=115, low=109, close=114), trailing_stop_percent=1.0)
    assert pos.trailing_stop_price == pytest.approx(113.85)


def test_trailing_stop_seeds_then_ratchets_down_for_sell() -> None:
    pos = open_position(side=Side.SELL, entry_price=100, quantity=10, entry_time=T0)
    pos = update_on_candle(pos, _candle(high=101, low=90, close=92), trailing_stop_percent=1.0)
    # SELL: trail = low * 1.01 = 90.9
    assert pos.trailing_stop_price == pytest.approx(90.9)
    # Next: lows still 90 — trail unchanged
    pos = update_on_candle(pos, _candle(high=95, low=92, close=93), trailing_stop_percent=1.0)
    assert pos.trailing_stop_price == pytest.approx(90.9)
    # Next: low 85 -> trail = 85 * 1.01 = 85.85
    pos = update_on_candle(pos, _candle(high=88, low=85, close=86), trailing_stop_percent=1.0)
    assert pos.trailing_stop_price == pytest.approx(85.85)


def test_trailing_stop_remains_none_when_no_pct_supplied() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos = update_on_candle(pos, _candle(high=105, low=99, close=104))
    assert pos.trailing_stop_price is None


# ─── apply_partial_exit ─────────────────────────────────────────────────


def test_apply_partial_exit_records_and_reduces_remaining() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos, record = apply_partial_exit(
        pos,
        qty_percent=50,
        price=110,
        timestamp=T0 + timedelta(minutes=5),
        reason="target_1",
    )
    assert pos.remaining_quantity == 5
    assert pos.is_open is True
    assert len(pos.partial_exits_done) == 1
    assert isinstance(record, PartialExitRecord)
    assert record.qty_percent == 50


def test_apply_partial_exit_full_quantity_closes_position() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos, _ = apply_partial_exit(pos, qty_percent=100, price=110, timestamp=T0, reason="full")
    assert pos.remaining_quantity == 0
    assert pos.is_open is False


def test_apply_partial_exit_chained_partials_sum_to_full() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos, _ = apply_partial_exit(pos, qty_percent=30, price=105, timestamp=T0, reason="t1")
    pos, _ = apply_partial_exit(pos, qty_percent=30, price=108, timestamp=T0, reason="t2")
    pos, _ = apply_partial_exit(pos, qty_percent=40, price=112, timestamp=T0, reason="t3")
    assert pos.remaining_quantity == pytest.approx(0.0)
    assert pos.is_open is False
    assert len(pos.partial_exits_done) == 3


def test_apply_partial_exit_rejects_over_exit() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos, _ = apply_partial_exit(pos, qty_percent=80, price=105, timestamp=T0, reason="t1")
    with pytest.raises(ValueError):
        # Only 20 % left; this asks for 50 % of original (which is 5 contracts
        # vs remaining 2) — over-exit.
        apply_partial_exit(pos, qty_percent=50, price=108, timestamp=T0, reason="t2")


def test_apply_partial_exit_rejects_invalid_inputs() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    with pytest.raises(ValueError):
        apply_partial_exit(pos, qty_percent=0, price=105, timestamp=T0, reason="x")
    with pytest.raises(ValueError):
        apply_partial_exit(pos, qty_percent=101, price=105, timestamp=T0, reason="x")
    with pytest.raises(ValueError):
        apply_partial_exit(pos, qty_percent=50, price=0, timestamp=T0, reason="x")


def test_apply_partial_exit_rejects_closed_position() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    pos = close_position(pos)
    with pytest.raises(ValueError):
        apply_partial_exit(pos, qty_percent=10, price=105, timestamp=T0, reason="x")


# ─── close_position ─────────────────────────────────────────────────────


def test_close_position_marks_closed_and_zeros_remaining() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    closed = close_position(pos)
    assert closed.is_open is False
    assert closed.remaining_quantity == 0


def test_close_position_idempotent() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    once = close_position(pos)
    twice = close_position(once)
    assert twice is once  # short-circuit returns same instance


# ─── PositionState invariants ───────────────────────────────────────────


def test_position_state_rejects_remaining_above_quantity() -> None:
    with pytest.raises(ValidationError):
        PositionState(
            side=Side.BUY,
            entry_price=100,
            entry_time=T0,
            quantity=5,
            remaining_quantity=10,
            highest_price_since_entry=100,
            lowest_price_since_entry=100,
        )


def test_position_state_rejects_low_above_high() -> None:
    with pytest.raises(ValidationError):
        PositionState(
            side=Side.BUY,
            entry_price=100,
            entry_time=T0,
            quantity=10,
            remaining_quantity=10,
            highest_price_since_entry=100,
            lowest_price_since_entry=110,
        )


def test_position_state_is_frozen() -> None:
    pos = open_position(side=Side.BUY, entry_price=100, quantity=10, entry_time=T0)
    with pytest.raises((TypeError, ValueError)):
        pos.is_open = False  # type: ignore[misc]
