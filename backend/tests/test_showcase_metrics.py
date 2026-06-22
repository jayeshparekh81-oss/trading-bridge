"""Tests for the honest showcase metrics engine (backend/scripts/showcase_metrics.py).

Focus: the NON-compounded, NON-normalised max-drawdown (the metric the previous
artifact got wrong), plus win-rate / avg / profit-factor / per-period reset, and
an integration check that the engine reproduces the independent reference values.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import showcase_metrics as sm  # noqa: E402

# Resolve the isolated SQLite by absolute path (cwd-independent under pytest).
_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backtest_signal_history.sqlite3"))


def rows(pnls, year="2020", direction="long"):
    """Build (exit_dt, net_pnl_pct, trade_number, direction) rows in order."""
    return [(f"{year}-01-{(i % 27) + 1:02d} 09:15", float(p), i + 1, direction) for i, p in enumerate(pnls)]


# ── max_drawdown: peak-to-trough of running SUM, percentage points, NOT normalised
def test_max_drawdown_empty_and_all_up():
    assert sm.max_drawdown([]) == 0.0
    assert sm.max_drawdown([1.0, 2.0, 3.0]) == 0.0


def test_max_drawdown_known_sequences():
    assert sm.max_drawdown([-1.0, -2.0]) == -3.0
    assert sm.max_drawdown([5.0, -3.0, -4.0, 2.0]) == -7.0
    assert sm.max_drawdown([2.0, -1.0, 3.0, -10.0, 4.0]) == -10.0


def test_max_drawdown_is_not_normalised_by_peak():
    # A peak of +100 then a -20 drop must read as -20 (points), NOT -20/120 (~16.7%).
    seq = [100.0, -20.0]
    assert sm.max_drawdown(seq) == -20.0


# ── metrics aggregate
def test_metrics_basic():
    m = sm.metrics(rows([2, -1, 3, -1]))
    assert m["trades"] == 4
    assert m["win_rate_pct"] == 50.0
    assert m["avg_net_pct_per_trade"] == 0.75
    assert m["profit_factor"] == 2.5  # (2+3) / |(-1-1)|
    assert m["max_drawdown_pct"] == -1.0


def test_metrics_no_losses_pf_none():
    m = sm.metrics(rows([1, 2, 3]))
    assert m["profit_factor"] is None  # infinite PF -> None
    assert m["win_rate_pct"] == 100.0
    assert m["max_drawdown_pct"] == 0.0


def test_longest_losing_streak():
    assert sm.longest_losing_streak(rows([1, -1, -1, 2, -1, -1, -1, 3])) == 3
    assert sm.longest_losing_streak(rows([1, 2, 3])) == 0


def test_aggregate_metrics_extras():
    a = sm.aggregate_metrics(rows([2, -1, 3, -1, 0]))
    assert a["wins"] == 2 and a["losses"] == 2 and a["flats"] == 1
    assert a["best_trade_pct"] == 3.0 and a["worst_trade_pct"] == -1.0


# ── per-period drawdown RESETS within each period (now split all/long/short)
def test_per_period_drawdown_resets():
    r = rows([5, -10], "2020") + rows([3, -2], "2021")
    by_year = sm.per_period(r, 4)
    assert by_year["2020"]["all"]["max_drawdown_pct"] == -10.0
    # 2021 within-year DD is -2, NOT the continuous -7 it would be without reset
    assert by_year["2021"]["all"]["max_drawdown_pct"] == -2.0


# ── per-direction split: {all, long, short} + slice flag on long/short only
def test_by_direction_split_and_slice_flag():
    r = rows([2, -1], direction="long") + rows([5, -3], "2020", direction="short")
    block = sm.by_direction(r, sm.metrics)
    assert set(block) == {"all", "long", "short"}
    assert block["all"]["trades"] == 4
    assert block["long"]["trades"] == 2 and block["short"]["trades"] == 2
    # long/short are flagged as slices; "all" is the full system (no flag)
    assert block["long"]["slice_of_full_system"] is True
    assert block["short"]["slice_of_full_system"] is True
    assert "slice_of_full_system" not in block["all"]


def test_direction_metrics_independent_of_other_side():
    # short slice metrics must use only short trades
    r = rows([10, 10], direction="long") + rows([-4, 1], "2020", direction="short")
    block = sm.by_direction(r, sm.metrics)
    assert block["short"]["max_drawdown_pct"] == -4.0  # only the short trades' running sum
    assert block["long"]["max_drawdown_pct"] == 0.0


# ── integration: engine reproduces the independent reference values
@pytest.mark.skipif(
    not os.path.isfile(_DB),
    reason="isolated backtest SQLite not present (local-only data file)",
)
def test_reference_values_reproduced():
    assert sm.verify(_DB) is True
