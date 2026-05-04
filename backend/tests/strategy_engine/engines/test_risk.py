"""Risk engine tests — static + runtime."""

from __future__ import annotations

from typing import Any

from app.strategy_engine.engines.risk import (
    RiskRuntimeStats,
    RiskSeverity,
    evaluate_risk,
)
from app.strategy_engine.schema.strategy import StrategyJSON


def _strategy(
    *,
    indicator_count: int = 1,
    stop_loss: float | None = 1.0,
    trail: float | None = None,
    risk: dict[str, Any] | None = None,
) -> StrategyJSON:
    indicators = [
        {"id": f"ema_{i}", "type": "ema", "params": {"period": 10 + i}}
        for i in range(indicator_count)
    ]
    exit_block: dict[str, Any] = {}
    if stop_loss is not None:
        exit_block["stopLossPercent"] = stop_loss
    if trail is not None:
        exit_block["trailingStopPercent"] = trail
    if not exit_block:
        # The schema requires at least one exit primitive. For "no SL"
        # tests we put a target instead so we can isolate the SL warning.
        exit_block["targetPercent"] = 2

    payload: dict[str, Any] = {
        "id": "s",
        "name": "test",
        "mode": "expert",
        "indicators": indicators,
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [{"type": "price", "op": ">", "value": 100}],
        },
        "exit": exit_block,
        "risk": risk or {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    return StrategyJSON.model_validate(payload)


# ─── Static checks ─────────────────────────────────────────────────────


def test_missing_stop_loss_warning() -> None:
    strat = _strategy(stop_loss=None, trail=None)
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "missing_stop_loss" in codes
    assert any(m.severity is RiskSeverity.WARNING for m in assessment.messages)


def test_trailing_stop_satisfies_stop_loss_check() -> None:
    """Either a fixed SL or a trailing SL counts as 'has stop loss'."""
    strat = _strategy(stop_loss=None, trail=1.0)
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "missing_stop_loss" not in codes


def test_too_many_indicators_warning_above_threshold() -> None:
    strat = _strategy(indicator_count=9, stop_loss=1.0)
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "too_many_indicators" in codes


def test_eight_indicators_does_not_trip_warning() -> None:
    strat = _strategy(indicator_count=8, stop_loss=1.0)
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "too_many_indicators" not in codes


def test_no_risk_caps_emits_info_message() -> None:
    strat = _strategy(stop_loss=1.0, risk={})
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "no_risk_caps" in codes
    no_cap_msg = next(m for m in assessment.messages if m.code == "no_risk_caps")
    assert no_cap_msg.severity is RiskSeverity.INFO


def test_having_one_risk_cap_silences_no_caps_message() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxTradesPerDay": 5})
    assessment = evaluate_risk(strat)
    codes = {m.code for m in assessment.messages}
    assert "no_risk_caps" not in codes


def test_static_assessment_allowed_true_when_no_block() -> None:
    """No runtime stats supplied -> nothing can BLOCK -> allowed=True."""
    strat = _strategy(stop_loss=None)  # warning, not block
    assessment = evaluate_risk(strat)
    assert assessment.allowed is True
    assert assessment.severity is RiskSeverity.WARNING


# ─── Runtime checks ────────────────────────────────────────────────────


def test_daily_loss_cap_blocks_when_exceeded() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxDailyLossPercent": 2})
    stats = RiskRuntimeStats(daily_pnl_percent=-2.5)  # 2.5% loss
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is False
    assert assessment.severity is RiskSeverity.BLOCK
    assert any(m.code == "daily_loss_cap_hit" for m in assessment.messages)


def test_daily_loss_cap_silent_when_under() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxDailyLossPercent": 2})
    stats = RiskRuntimeStats(daily_pnl_percent=-1.5)
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is True
    assert all(m.code != "daily_loss_cap_hit" for m in assessment.messages)


def test_daily_loss_cap_silent_when_pnl_positive() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxDailyLossPercent": 2})
    stats = RiskRuntimeStats(daily_pnl_percent=3.0)  # +3 % gain
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is True
    assert all(m.code != "daily_loss_cap_hit" for m in assessment.messages)


def test_max_trades_per_day_blocks() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxTradesPerDay": 5})
    stats = RiskRuntimeStats(trades_today=5)
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is False
    assert any(m.code == "max_trades_per_day_hit" for m in assessment.messages)


def test_max_trades_per_day_silent_under_cap() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxTradesPerDay": 5})
    stats = RiskRuntimeStats(trades_today=4)
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is True


def test_loss_streak_cap_blocks() -> None:
    strat = _strategy(stop_loss=1.0, risk={"maxLossStreak": 3})
    stats = RiskRuntimeStats(consecutive_loss_streak=3)
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is False
    assert any(m.code == "loss_streak_cap_hit" for m in assessment.messages)


def test_unsupplied_runtime_stat_disables_its_check() -> None:
    """A None field on RiskRuntimeStats means 'don't evaluate this cap'."""
    strat = _strategy(
        stop_loss=1.0,
        risk={"maxDailyLossPercent": 2, "maxTradesPerDay": 5},
    )
    # Supply only trades_today; daily_pnl_percent is None and skipped.
    stats = RiskRuntimeStats(trades_today=3)
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.allowed is True


def test_assessment_severity_is_max_across_messages() -> None:
    strat = _strategy(
        stop_loss=None,  # WARNING
        risk={"maxTradesPerDay": 3},
    )
    stats = RiskRuntimeStats(trades_today=3)  # BLOCK
    assessment = evaluate_risk(strat, stats=stats)
    assert assessment.severity is RiskSeverity.BLOCK


def test_assessment_suggestions_collected_from_messages() -> None:
    strat = _strategy(stop_loss=None)
    assessment = evaluate_risk(strat)
    # Each emitted message has a suggestion; assert at least one is present.
    assert len(assessment.suggestions) >= 1
    assert all(isinstance(s, str) and s for s in assessment.suggestions)


# ─── Schema invariants of risk dataclasses ─────────────────────────────


def test_risk_assessment_is_frozen() -> None:
    strat = _strategy(stop_loss=1.0)
    assessment = evaluate_risk(strat)

    import pytest as _pytest

    with _pytest.raises((TypeError, ValueError)):
        assessment.allowed = False  # type: ignore[misc]


def test_risk_runtime_stats_rejects_negative_counts() -> None:
    import pytest as _pytest
    from pydantic import ValidationError

    with _pytest.raises(ValidationError):
        RiskRuntimeStats(trades_today=-1)
    with _pytest.raises(ValidationError):
        RiskRuntimeStats(consecutive_loss_streak=-1)
