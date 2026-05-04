"""Walk-forward: consistency-score aggregation."""

from __future__ import annotations

import pytest

from app.strategy_engine.reliability.walk_forward import (
    WalkForwardWindow,
    _summarise,
)


def test_all_windows_pass_yields_consistency_score_of_one() -> None:
    windows = [WalkForwardWindow(index=i, train_pnl=10, test_pnl=5, passed=True) for i in range(5)]
    summary = _summarise(windows)
    assert summary.consistency_score == 1.0
    assert summary.passed_windows == 5
    assert summary.failed_windows == 0


def test_no_windows_pass_yields_consistency_score_of_zero() -> None:
    windows = [
        WalkForwardWindow(index=i, train_pnl=-1, test_pnl=-2, passed=False) for i in range(5)
    ]
    summary = _summarise(windows)
    assert summary.consistency_score == 0.0
    assert summary.passed_windows == 0
    assert summary.failed_windows == 5


def test_three_of_five_pass_yields_60_percent() -> None:
    windows = [
        WalkForwardWindow(index=0, train_pnl=10, test_pnl=5, passed=True),
        WalkForwardWindow(index=1, train_pnl=10, test_pnl=-3, passed=False),
        WalkForwardWindow(index=2, train_pnl=10, test_pnl=2, passed=True),
        WalkForwardWindow(index=3, train_pnl=10, test_pnl=-1, passed=False),
        WalkForwardWindow(index=4, train_pnl=10, test_pnl=4, passed=True),
    ]
    summary = _summarise(windows)
    assert summary.passed_windows == 3
    assert summary.failed_windows == 2
    assert summary.consistency_score == pytest.approx(0.6)


def test_passed_count_matches_passed_field_not_pnl_sign() -> None:
    """If ``passed`` and ``test_pnl > 0`` ever disagreed (caller bug),
    the summary trusts the explicit ``passed`` field. Documents
    contract-strictness.
    """
    windows = [
        WalkForwardWindow(index=0, train_pnl=10, test_pnl=5, passed=False),
    ]
    summary = _summarise(windows)
    assert summary.passed_windows == 0
