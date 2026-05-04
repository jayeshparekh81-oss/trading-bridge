"""Pure-metric tests."""

from __future__ import annotations

import math

import pytest

from app.strategy_engine.backtest.metrics import (
    average_loss,
    average_win,
    expectancy,
    largest_loss,
    largest_win,
    loss_rate,
    max_drawdown,
    profit_factor,
    total_pnl,
    total_return_percent,
    win_rate,
)

# ─── total_pnl ──────────────────────────────────────────────────────────


def test_total_pnl_sums_signed_values() -> None:
    assert total_pnl([10, -5, 20, -3]) == 22


def test_total_pnl_empty_is_zero() -> None:
    assert total_pnl([]) == 0


# ─── win_rate / loss_rate ──────────────────────────────────────────────


def test_win_rate_basic() -> None:
    assert win_rate([10, 20, -5]) == pytest.approx(2 / 3)


def test_win_rate_excludes_zero_pnl_trades() -> None:
    """A zero-P&L trade is neither win nor loss for the *rate*."""
    assert win_rate([10, 0, -5]) == pytest.approx(1 / 3)
    assert loss_rate([10, 0, -5]) == pytest.approx(1 / 3)


def test_win_and_loss_rate_empty_is_zero() -> None:
    assert win_rate([]) == 0
    assert loss_rate([]) == 0


# ─── average_win / average_loss / largest_win / largest_loss ──────────


def test_average_win_only_counts_positive_pnls() -> None:
    assert average_win([10, -5, 20, 0]) == pytest.approx(15)


def test_average_loss_returns_magnitude() -> None:
    """avg_loss is documented as a positive number (magnitude)."""
    assert average_loss([10, -5, -15]) == pytest.approx(10)


def test_average_with_no_matching_trades_is_zero() -> None:
    assert average_win([-1, -2, -3]) == 0
    assert average_loss([1, 2, 3]) == 0


def test_largest_win_and_loss() -> None:
    assert largest_win([10, 20, -5, -100]) == 20
    assert largest_loss([10, 20, -5, -100]) == -100


def test_largest_with_no_matching_trades_is_zero() -> None:
    assert largest_win([-1, -2, -3]) == 0
    assert largest_loss([1, 2, 3]) == 0


# ─── profit_factor ─────────────────────────────────────────────────────


def test_profit_factor_basic() -> None:
    """gross_win = 10 + 20 = 30; gross_loss = 5 + 15 = 20; PF = 1.5."""
    assert profit_factor([10, -5, 20, -15]) == pytest.approx(1.5)


def test_profit_factor_no_losses_is_infinite() -> None:
    assert profit_factor([10, 20, 30]) == math.inf


def test_profit_factor_no_wins_is_zero() -> None:
    assert profit_factor([-10, -20, -30]) == 0


def test_profit_factor_empty_is_zero() -> None:
    assert profit_factor([]) == 0


def test_profit_factor_only_zero_pnls_is_zero() -> None:
    assert profit_factor([0, 0, 0]) == 0


def test_profit_factor_inf_compares_equal_to_itself() -> None:
    """math.inf == math.inf — important so determinism tests can compare."""
    pf1 = profit_factor([10, 20])
    pf2 = profit_factor([10, 20])
    assert pf1 == pf2 == math.inf


# ─── expectancy ────────────────────────────────────────────────────────


def test_expectancy_balanced_2to1_pnls() -> None:
    """50 % win rate, avg_win 20, avg_loss 10 -> 20*0.5 - 10*0.5 = 5."""
    assert expectancy([20, -10, 20, -10]) == pytest.approx(5)


def test_expectancy_all_winners() -> None:
    """100 % win rate, avg_win 15 -> 15 * 1 - 0 * 0 = 15."""
    assert expectancy([10, 20]) == pytest.approx(15)


def test_expectancy_all_losers_is_negative_avg_loss_magnitude() -> None:
    """0 % win rate, avg_loss 10 -> 0 - 10 = -10."""
    assert expectancy([-10, -10]) == pytest.approx(-10)


def test_expectancy_empty_is_zero() -> None:
    assert expectancy([]) == 0


# ─── max_drawdown ──────────────────────────────────────────────────────


def test_max_drawdown_monotonic_up_is_zero() -> None:
    assert max_drawdown([100, 110, 120, 130]) == 0


def test_max_drawdown_simple_dip() -> None:
    """100 -> 120 -> 60 -> 80; peak=120, trough=60 -> dd = 60/120 = 0.5."""
    assert max_drawdown([100, 120, 60, 80]) == pytest.approx(0.5)


def test_max_drawdown_takes_max_across_multiple_dips() -> None:
    """Worst dip in the middle, not the final one."""
    curve = [100, 120, 60, 110, 100, 70]
    # First peak 120, trough 60: dd = (120-60)/120 = 0.5
    # New peak 110, trough 70: dd = (110-70)/110 ~ 0.364
    # Max = 0.5
    assert max_drawdown(curve) == pytest.approx(0.5)


def test_max_drawdown_empty_curve_is_zero() -> None:
    assert max_drawdown([]) == 0


def test_max_drawdown_single_point_curve_is_zero() -> None:
    assert max_drawdown([100]) == 0


def test_max_drawdown_handles_zero_or_negative_peak_safely() -> None:
    """Curve that starts non-positive: function shouldn't divide by zero."""
    assert max_drawdown([0, -10, -5]) == 0
    # A subsequent positive peak does count for the rest of the curve.
    curve = [0, 10, 5, 8]  # peak=10, trough=5 -> dd=0.5
    assert max_drawdown(curve) == pytest.approx(0.5)


# ─── total_return_percent ─────────────────────────────────────────────


def test_total_return_percent_gains() -> None:
    assert total_return_percent(100_000, 110_000) == pytest.approx(10.0)


def test_total_return_percent_losses() -> None:
    assert total_return_percent(100_000, 95_000) == pytest.approx(-5.0)


def test_total_return_percent_zero_initial_safe() -> None:
    assert total_return_percent(0, 100) == 0
