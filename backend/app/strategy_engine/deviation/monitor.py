"""Deviation Monitor — orchestrator.

Pure decision pipeline:

    backtest + actual stats ─► per-metric comparisons ─► aggregate ─►
    decision flags ─► report

The module emits an *advisory* :class:`DeviationReport` — including a
read-only ``auto_kill_switch_signal`` — but never invokes the actual
kill switch, broker, or any execution path. Wiring the boolean into
the safety system is a separate future phase by design; the AST
inspection test pins that isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeAlias

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.deviation.constants import MIN_TRADES_FOR_EVAL
from app.strategy_engine.deviation.messages import (
    insufficient_data_message,
    recommended_actions,
    status_summary,
)
from app.strategy_engine.deviation.metrics import (
    compare_drawdown,
    compare_profit_factor,
    compare_trade_frequency,
    compare_win_rate,
)
from app.strategy_engine.deviation.models import (
    DeviationMetric,
    DeviationReport,
    LiveTradingStats,
)
from app.strategy_engine.deviation.scorer import aggregate_score, decision_flags
from app.strategy_engine.paper_trading.models import PaperReadinessReport

ActualStats: TypeAlias = PaperReadinessReport | LiveTradingStats


def evaluate_deviation(
    backtest: BacktestResult,
    actual: ActualStats,
    min_trades_for_eval: int = MIN_TRADES_FOR_EVAL,
) -> DeviationReport:
    """Compare ``actual`` performance against ``backtest`` expectations.

    Args:
        backtest: Phase 3 backtest result. The expected baseline.
        actual: Either a :class:`LiveTradingStats` (full shape — all
            four metrics run) or a :class:`PaperReadinessReport`
            (degraded shape — only win-rate runs because PRR doesn't
            carry drawdown / profit-factor / total-trades).
        min_trades_for_eval: Below this trade count the analysis is
            statistically meaningless, so the monitor returns a
            ``normal`` report with an "insufficient data" summary
            instead of inventing a verdict.

    Returns:
        :class:`DeviationReport` carrying the deviation_score, status,
        per-metric breakdowns, recommended actions, decision flags,
        Hinglish summary, and the read-only kill-switch signal.
    """
    observed_trades = _observed_trade_count(actual)
    if observed_trades < min_trades_for_eval:
        return _insufficient_data_report(min_trades_for_eval, observed_trades)

    metrics = _build_metrics(backtest, actual)
    score, status = aggregate_score(metrics)
    pause, reduce_size, paper = decision_flags(status)

    return DeviationReport(
        deviation_score=round(score, 2),
        status=status,
        deviations=tuple(metrics),
        recommended_actions=recommended_actions(status),
        should_pause=pause,
        should_reduce_size=reduce_size,
        should_switch_to_paper=paper,
        hinglish_summary=status_summary(status),
        auto_kill_switch_signal=(status == "critical"),
    )


# ─── Helpers ───────────────────────────────────────────────────────────


def _observed_trade_count(actual: ActualStats) -> int:
    """Pick the trade-count field that exists on this input shape.

    ``LiveTradingStats.total_trades`` is the canonical signal;
    ``PaperReadinessReport.completed_sessions`` is the fallback (each
    paper session typically carries multiple trades, but the reading
    is still meaningful as a "have we collected enough data?" gate).
    """
    if isinstance(actual, LiveTradingStats):
        return actual.total_trades
    return actual.completed_sessions


def _build_metrics(
    backtest: BacktestResult,
    actual: ActualStats,
) -> list[DeviationMetric]:
    """Assemble the per-metric comparison list.

    Always runs win-rate. The richer metrics (drawdown, profit factor,
    trade frequency) require a :class:`LiveTradingStats` input —
    :class:`PaperReadinessReport` doesn't carry those fields, so we
    omit them rather than fabricate placeholder values.
    """
    metrics: list[DeviationMetric] = []
    metrics.append(
        compare_win_rate(
            expected=backtest.win_rate,
            actual=_actual_win_rate(actual),
        )
    )
    if isinstance(actual, LiveTradingStats):
        metrics.append(
            compare_drawdown(
                expected=backtest.max_drawdown,
                actual=actual.max_drawdown,
            )
        )
        metrics.append(
            compare_profit_factor(
                expected=backtest.profit_factor,
                actual=actual.profit_factor,
            )
        )
        expected_freq = _backtest_trades_per_day(backtest)
        actual_freq = _actual_trades_per_session(actual)
        metrics.append(
            compare_trade_frequency(
                expected=expected_freq,
                actual=actual_freq,
            )
        )
    return metrics


def _actual_win_rate(actual: ActualStats) -> float:
    if isinstance(actual, LiveTradingStats):
        return actual.win_rate
    return actual.paper_win_rate


def _actual_trades_per_session(stats: LiveTradingStats) -> float:
    if stats.sessions <= 0:
        return float(stats.total_trades)
    return stats.total_trades / stats.sessions


def _backtest_trades_per_day(backtest: BacktestResult) -> float:
    """Estimate trades-per-day from the backtest's equity curve.

    Tries timestamp span first; falls back to a 5-min-bar count
    heuristic (78 bars per trading day) and finally to "treat the
    whole backtest as one day" so the metric still has a finite
    denominator.
    """
    days = _backtest_period_days(backtest)
    return backtest.total_trades / days if days > 0 else float(backtest.total_trades)


def _backtest_period_days(backtest: BacktestResult) -> float:
    """Best-effort period estimation. Always returns ``>= 1.0``."""
    curve = backtest.equity_curve
    if len(curve) >= 2:
        first_ts = _ensure_aware(curve[0].timestamp)
        last_ts = _ensure_aware(curve[-1].timestamp)
        seconds = (last_ts - first_ts).total_seconds()
        if seconds > 0:
            return max(1.0, seconds / 86400.0)
    if curve:
        # Assume 5-minute bars — 78 per regular Indian trading day.
        return max(1.0, len(curve) / 78.0)
    return 1.0


def _ensure_aware(ts: datetime) -> datetime:
    """Pin a naive timestamp to UTC so subtractions don't raise."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _insufficient_data_report(threshold: int, observed: int) -> DeviationReport:
    """Build a ``normal``-status placeholder report when the actual
    sample is too small to evaluate."""
    summary = insufficient_data_message(threshold, observed)
    return DeviationReport(
        deviation_score=0.0,
        status="normal",
        deviations=(),
        recommended_actions=("Continue collecting data; no deviation analysis yet.",),
        should_pause=False,
        should_reduce_size=False,
        should_switch_to_paper=False,
        hinglish_summary=summary,
        auto_kill_switch_signal=False,
    )


__all__ = ["ActualStats", "evaluate_deviation"]
