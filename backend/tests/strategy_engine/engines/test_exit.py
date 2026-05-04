"""Exit engine tests — every primitive + the multi-trigger same-bar contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.strategy_engine.engines.exit import ExitType, evaluate_exit
from app.strategy_engine.engines.position import close_position, open_position
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import ExitRules, Side

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _bar(*, h: float, low: float, c: float, o: float | None = None, ts: datetime = T0) -> Candle:
    open_ = o if o is not None else (h + low) / 2
    return Candle(timestamp=ts, open=open_, high=h, low=low, close=c, volume=1000)


def _rules(**kwargs: Any) -> ExitRules:
    return ExitRules.model_validate(kwargs)


def _open(side: Side = Side.BUY, entry: float = 100.0) -> Any:
    return open_position(side=side, entry_price=entry, quantity=10, entry_time=T0)


# ─── Target ─────────────────────────────────────────────────────────────


def test_target_fires_for_buy_when_high_reaches_level() -> None:
    pos = _open()
    rules = _rules(targetPercent=2)  # target = 102
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=102, low=99, c=101),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert any(e.exit_type is ExitType.TARGET for e in events)
    target = next(e for e in events if e.exit_type is ExitType.TARGET)
    assert target.qty_percent == 100
    assert target.price == 102


def test_target_does_not_fire_when_high_below_level() -> None:
    pos = _open()
    rules = _rules(targetPercent=2)
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101.5, low=99, c=101),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert all(e.exit_type is not ExitType.TARGET for e in events)


def test_target_for_sell_uses_low_below_entry() -> None:
    pos = _open(side=Side.SELL, entry=100)
    rules = _rules(targetPercent=2)  # SELL target = 98
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=100, low=97.5, c=98),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert any(e.exit_type is ExitType.TARGET for e in events)


# ─── Stop-loss ──────────────────────────────────────────────────────────


def test_stop_loss_fires_for_buy_when_low_reaches_level() -> None:
    pos = _open()
    rules = _rules(stopLossPercent=1)  # SL = 99
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101, low=98.5, c=99),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert any(e.exit_type is ExitType.STOP_LOSS for e in events)


def test_same_bar_target_and_sl_both_fire() -> None:
    """The locked Phase 2 contract: report both, runner picks priority."""
    pos = _open()
    rules = _rules(targetPercent=2, stopLossPercent=1)  # T=102, SL=99
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=103, low=98, c=100),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    types = {e.exit_type for e in events}
    assert ExitType.TARGET in types
    assert ExitType.STOP_LOSS in types


# ─── Trailing stop ─────────────────────────────────────────────────────


def test_trailing_stop_fires_when_bar_crosses_position_trail() -> None:
    """Position carries trail=108.9; bar low 108 -> trail trigger fires."""
    from app.strategy_engine.engines.position import update_on_candle

    pos = _open()
    pos = update_on_candle(pos, _bar(h=110, low=99, c=108), trailing_stop_percent=1.0)
    rules = _rules(trailingStopPercent=1)
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=109, low=108, c=108.5),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert any(e.exit_type is ExitType.TRAILING_STOP for e in events)


def test_trailing_stop_silent_when_position_has_no_trail() -> None:
    pos = _open()  # trailing_stop_price is None until update_on_candle runs.
    rules = _rules(trailingStopPercent=1)
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101, low=98, c=99),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert all(e.exit_type is not ExitType.TRAILING_STOP for e in events)


# ─── Partial exits ─────────────────────────────────────────────────────


def test_partial_exit_fires_when_bar_crosses_target_level() -> None:
    pos = _open()
    rules = _rules(
        partialExits=[{"qtyPercent": 50, "targetPercent": 1}],
        stopLossPercent=2,  # required to satisfy at-least-one-exit rule
    )
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101.5, low=99, c=101),  # crosses 101
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    partials = [e for e in events if e.exit_type is ExitType.PARTIAL]
    assert len(partials) == 1
    assert partials[0].qty_percent == 50
    assert partials[0].price == 101


def test_multiple_partials_all_report_when_bar_crosses_all() -> None:
    pos = _open()
    rules = _rules(
        partialExits=[
            {"qtyPercent": 30, "targetPercent": 1},
            {"qtyPercent": 30, "targetPercent": 2},
            {"qtyPercent": 40, "targetPercent": 3},
        ],
        stopLossPercent=2,
    )
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=104, low=99, c=103),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    partials = [e for e in events if e.exit_type is ExitType.PARTIAL]
    assert len(partials) == 3


# ─── Indicator-driven exits ────────────────────────────────────────────


def test_indicator_exit_fires_when_condition_passes() -> None:
    pos = _open()
    rules = _rules(
        stopLossPercent=2,
        indicatorExits=[
            {"type": "indicator", "left": "rsi_14", "op": ">", "value": 80},
        ],
    )
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101, low=99, c=100),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={"rsi_14": 85},
    )
    assert any(e.exit_type is ExitType.INDICATOR for e in events)


# ─── Reverse-signal exit ───────────────────────────────────────────────


def test_reverse_signal_exit_only_fires_when_caller_says_so() -> None:
    pos = _open()
    rules = _rules(stopLossPercent=2, reverseSignalExit=True)
    no_event = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101, low=99, c=100),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
        reverse_signal_fired=False,
    )
    assert all(e.exit_type is not ExitType.REVERSE_SIGNAL for e in no_event)

    fired = evaluate_exit(
        position=pos,
        current_candle=_bar(h=101, low=99, c=100),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
        reverse_signal_fired=True,
    )
    assert any(e.exit_type is ExitType.REVERSE_SIGNAL for e in fired)


# ─── Square-off time ────────────────────────────────────────────────────


def test_square_off_fires_at_or_after_configured_time() -> None:
    pos = _open()
    rules = _rules(squareOffTime="15:20")
    at = datetime(2026, 5, 4, 15, 20, tzinfo=UTC)
    after = datetime(2026, 5, 4, 15, 21, tzinfo=UTC)
    before = datetime(2026, 5, 4, 15, 19, tzinfo=UTC)

    assert any(
        e.exit_type is ExitType.SQUARE_OFF
        for e in evaluate_exit(
            position=pos,
            current_candle=_bar(h=101, low=99, c=100, ts=at),
            prior_candle=None,
            exit_rules=rules,
            indicator_values={},
        )
    )
    assert any(
        e.exit_type is ExitType.SQUARE_OFF
        for e in evaluate_exit(
            position=pos,
            current_candle=_bar(h=101, low=99, c=100, ts=after),
            prior_candle=None,
            exit_rules=rules,
            indicator_values={},
        )
    )
    assert all(
        e.exit_type is not ExitType.SQUARE_OFF
        for e in evaluate_exit(
            position=pos,
            current_candle=_bar(h=101, low=99, c=100, ts=before),
            prior_candle=None,
            exit_rules=rules,
            indicator_values={},
        )
    )


# ─── No exits when closed ──────────────────────────────────────────────


def test_no_events_when_position_already_closed() -> None:
    pos = close_position(_open())
    rules = _rules(targetPercent=2, stopLossPercent=1)
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=200, low=50, c=150),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert events == []


# ─── ExitEvent model ───────────────────────────────────────────────────


def test_exit_event_is_frozen() -> None:
    pos = _open()
    rules = _rules(targetPercent=2)
    events = evaluate_exit(
        position=pos,
        current_candle=_bar(h=103, low=99, c=102),
        prior_candle=None,
        exit_rules=rules,
        indicator_values={},
    )
    assert events
    import pytest as _pytest

    with _pytest.raises((TypeError, ValueError)):
        events[0].qty_percent = 50  # type: ignore[misc]
