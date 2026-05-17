"""Order-router safety-guard tests.

Focused on the ``_evaluate_broker_guard_subset`` function — the
fail-closed gate that blocks live orders when the strategy has no
DSL or a malformed DSL.

Catches the regression class: any change that lets a strategy with
``strategy_json=None`` (cloned-from-template, legacy) reach the
broker would be a P0 customer-money-loss bug.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# bcrypt is a transitive import of order_router via app.core.security.
# The package is in pyproject.toml but may not be installed in every
# dev env. Skip-module gracefully if absent — CI with full deps
# runs these tests; local dev without bcrypt skips cleanly.
pytest.importorskip("bcrypt")

from app.strategy_engine.live_orders.order_router import (  # noqa: E402
    _evaluate_broker_guard_subset,
)


def _mock_strategy(strategy_json: dict | None) -> MagicMock:
    """Minimal Strategy stand-in carrying just the strategy_json field."""
    s = MagicMock()
    s.strategy_json = strategy_json
    return s


# ─── Null DSL — fail closed ───────────────────────────────────────────


def test_null_strategy_json_blocks_with_descriptive_message() -> None:
    """Cloned-from-template Strategy with strategy_json=None: live trading
    MUST be blocked (no SL to verify)."""
    strategy = _mock_strategy(None)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    assert result.passed is False
    assert result.severity == "blocking"
    assert "no DSL" in result.message or "DSL nahi" in result.message or "stop loss verify nahi" in result.message
    assert result.check_name == "stop_loss_present"


def test_empty_dict_strategy_json_blocks() -> None:
    """A {} (empty dict) strategy_json should also be blocked — Pydantic
    validation will fail on missing required fields."""
    strategy = _mock_strategy({})
    result = _evaluate_broker_guard_subset(strategy=strategy)
    assert result.passed is False
    assert result.severity == "blocking"


# ─── Malformed DSL — fail closed ─────────────────────────────────────


def test_malformed_strategy_json_blocks_with_recreate_message() -> None:
    """A strategy_json that fails Pydantic validation must produce a
    block result, NOT a crash."""
    bad = {
        "id": "bad",
        "name": "Malformed",
        # missing required mode + entry + exit + execution fields
    }
    strategy = _mock_strategy(bad)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    assert result.passed is False
    assert result.severity == "blocking"
    assert "invalid" in result.message.lower() or "recreate" in result.message.lower()


def test_strategy_json_missing_exit_block_blocks() -> None:
    """Strategy with no exit primitives — Pydantic rejects on _at_least_one_exit."""
    bad = {
        "id": "no_exit",
        "name": "No Exit",
        "mode": "expert",
        "indicators": [{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}
            ],
        },
        "exit": {},  # rejected by _at_least_one_exit validator
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    strategy = _mock_strategy(bad)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    assert result.passed is False
    assert result.severity == "blocking"


# ─── Valid DSL — delegates to check_stop_loss_present ─────────────────


def test_valid_strategy_with_stop_loss_passes_guard() -> None:
    valid = {
        "id": "good_strategy",
        "name": "Good with SL",
        "mode": "expert",
        "indicators": [{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}
            ],
        },
        "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    strategy = _mock_strategy(valid)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    # Result depends on check_stop_loss_present; valid stop loss → passes
    assert result.passed is True


def test_valid_strategy_without_stop_loss_fails_guard() -> None:
    """Valid DSL but only target%, no SL — guard catches the missing SL."""
    no_sl = {
        "id": "no_sl",
        "name": "No SL",
        "mode": "expert",
        "indicators": [{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}
            ],
        },
        # Only targetPercent — no stopLossPercent
        "exit": {"targetPercent": 2.0},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    strategy = _mock_strategy(no_sl)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    # The check_stop_loss_present function should flag this
    # NOTE: if check_stop_loss_present has a bug and lets this through,
    # this test catches it — that's a P0 (live trading without SL).
    assert result.passed is False
    assert result.severity == "blocking"


# ─── Trailing stop is also a valid stop ───────────────────────────────


def test_strategy_with_trailing_stop_only_passes() -> None:
    """trailingStopPercent alone counts as a stop loss (per check_stop_loss_present)."""
    valid = {
        "id": "trail_only",
        "name": "Trailing Stop Only",
        "mode": "expert",
        "indicators": [{"id": "ema_20", "type": "ema", "params": {"period": 20}}],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}
            ],
        },
        "exit": {"trailingStopPercent": 1.5, "targetPercent": 3.0},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    strategy = _mock_strategy(valid)
    result = _evaluate_broker_guard_subset(strategy=strategy)
    # Trailing stop counts; this should pass
    assert result.passed is True


# ─── Pydantic-error path stays informative ────────────────────────────


def test_guard_doesnt_crash_on_unusual_payload_shapes() -> None:
    """Any non-dict / weird payload shape should produce a structured
    block result, never an exception."""
    # Various malformations that shouldn't crash the guard
    weird_payloads = [
        {"not_a_strategy": True},
        {"id": "x"},  # too sparse
        {"id": "x", "name": "y", "mode": "invalid_mode"},
    ]
    for p in weird_payloads:
        strategy = _mock_strategy(p)
        # Must NOT raise — must return a structured failure
        result = _evaluate_broker_guard_subset(strategy=strategy)
        assert result.passed is False
        assert result.severity == "blocking"
