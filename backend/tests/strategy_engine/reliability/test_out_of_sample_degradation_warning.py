"""OOS: degradation calculation + warning threshold."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
from app.strategy_engine.reliability.constants import (
    OOS_DEGRADATION_WARNING_THRESHOLD,
)
from app.strategy_engine.reliability.out_of_sample import (
    OOSResult,
    _build_warning,
    _compute_degradation,
)
from app.strategy_engine.schema.strategy import Side

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


# ─── _compute_degradation ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("train_ret", "test_ret", "expected"),
    [
        (10.0, 5.0, 0.5),  # 50 % drop
        (10.0, 10.0, 0.0),  # no degradation
        (10.0, 12.0, -0.2),  # improvement -> negative
        (-5.0, -5.0, 0.0),  # both negative, equal
        # train=-5, test=-10: ((-5) - (-10)) / abs(-5) = 5 / 5 = 1.0
        (-5.0, -10.0, 1.0),
    ],
)
def test_degradation_formula(train_ret: float, test_ret: float, expected: float) -> None:
    assert _compute_degradation(train_return=train_ret, test_return=test_ret) == expected


def test_degradation_zero_train_return_returns_zero() -> None:
    assert _compute_degradation(train_return=0.0, test_return=10.0) == 0


def test_degradation_zero_train_negative_test() -> None:
    assert _compute_degradation(train_return=0.0, test_return=-5.0) == 0


# ─── _build_warning ────────────────────────────────────────────────────


def test_warning_empty_when_no_degradation() -> None:
    assert _build_warning(0.10, train_return=10.0) == ""


def test_warning_fires_above_threshold() -> None:
    msg = _build_warning(OOS_DEGRADATION_WARNING_THRESHOLD + 0.01, train_return=10.0)
    assert "overfit risk" in msg.lower()


def test_warning_silent_at_exactly_threshold() -> None:
    """Strictly greater than — equality does NOT trigger."""
    assert _build_warning(OOS_DEGRADATION_WARNING_THRESHOLD, train_return=10.0) == ""


def test_warning_zero_train_returns_uninformative_message() -> None:
    msg = _build_warning(0.0, train_return=0.0)
    assert "uninformative" in msg.lower()


# ─── End-to-end OOSResult shape ────────────────────────────────────────


def _make_bt(total_return_percent: float) -> BacktestResult:
    """Minimal BacktestResult for plug-into-OOSResult tests."""
    return BacktestResult(
        total_pnl=total_return_percent * 1000,
        total_return_percent=total_return_percent,
        win_rate=0.5,
        loss_rate=0.5,
        total_trades=10,
        average_win=10.0,
        average_loss=8.0,
        largest_win=20.0,
        largest_loss=-15.0,
        max_drawdown=0.10,
        profit_factor=1.25,
        expectancy=1.0,
        equity_curve=[EquityPoint(timestamp=T0, equity=100_000)],
        trades=[
            Trade(
                entry_time=T0,
                exit_time=T0,
                side=Side.BUY,
                entry_price=100,
                exit_price=101,
                quantity=1,
                pnl=1.0,
                exit_reason="target",
            )
        ],
        warnings=[],
    )


def test_oos_result_round_trips_through_json() -> None:
    """Pydantic model_dump_json must round-trip the OOSResult cleanly."""
    result = OOSResult(
        training=_make_bt(10.0),
        testing=_make_bt(5.0),
        degradation_percent=0.5,
        warning="overfit risk",
    )
    blob = result.model_dump_json()
    rehydrated = OOSResult.model_validate_json(blob)
    assert rehydrated == result
