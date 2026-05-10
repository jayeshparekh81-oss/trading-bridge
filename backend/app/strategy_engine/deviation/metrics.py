"""Per-metric comparison functions for the Deviation Monitor.

Each function maps an ``(expected, actual)`` pair to a single
:class:`DeviationMetric`. They never raise — degenerate inputs (zero
divisor, NaN, etc.) collapse to ``severity="normal"`` with a
deviation_percent of ``0.0`` so the aggregate scorer doesn't crash on
edge cases.

Pure functions: no I/O, no mutation, no module-level state.
"""

from __future__ import annotations

import math

from app.strategy_engine.deviation.constants import (
    DRAWDOWN_MULTIPLIERS,
    PROFIT_FACTOR_DROP_PCT,
    TRADE_FREQ_THRESHOLDS,
    WIN_RATE_THRESHOLDS,
)
from app.strategy_engine.deviation.messages import (
    drawdown_message,
    profit_factor_message,
    trade_frequency_message,
    win_rate_message,
)
from app.strategy_engine.deviation.models import DeviationMetric, Severity

# ─── Severity band lookup ──────────────────────────────────────────────


def _band(value: float, thresholds: tuple[float, float, float]) -> Severity:
    """Pick the severity band for ``value`` against ``thresholds``.

    ``thresholds`` is ``(watch_min, warning_min, critical_min)``: the
    smallest value that still escalates to that severity. A value
    *strictly less than* ``watch_min`` is ``normal``.
    """
    watch_min, warning_min, critical_min = thresholds
    if value < watch_min:
        return "normal"
    if value < warning_min:
        return "watch"
    if value < critical_min:
        return "warning"
    return "critical"


def _signed_deviation_percent(expected: float, actual: float) -> float:
    """Return ``(actual - expected) / abs(expected) * 100``.

    When ``expected`` is zero or non-finite, falls back to ``0.0`` so
    the metric stays renderable. Real backtest metrics are always
    well-defined; this just keeps the math safe in tests.
    """
    if not math.isfinite(expected) or expected == 0:
        return 0.0
    return (actual - expected) / abs(expected) * 100.0


# ─── Public per-metric comparisons ─────────────────────────────────────


def compare_win_rate(expected: float, actual: float) -> DeviationMetric:
    """Win-rate diff in *absolute percentage points*.

    Symmetric: a much-higher live win-rate (rare; usually means the
    backtest under-counts) lands in the same band as a much-lower one.
    The locked thresholds are 0.10 / 0.20 / 0.30 fraction.
    """
    diff = abs(expected - actual)
    severity = _band(diff, WIN_RATE_THRESHOLDS)
    return DeviationMetric(
        metric_name="win_rate",
        expected=expected,
        actual=actual,
        deviation_percent=_signed_deviation_percent(expected, actual),
        severity=severity,
        hinglish_message=win_rate_message(expected, actual),
    )


def compare_drawdown(expected: float, actual: float) -> DeviationMetric:
    """Drawdown comparison — *one-sided*.

    Only larger-than-expected drawdown is bad; a smaller live drawdown
    stays in ``normal``. Severity is the multiplier ``actual / expected``
    against the ``DRAWDOWN_MULTIPLIERS`` ladder.

    When the expected drawdown is zero (synthetic / never-loses case),
    we treat *any* nonzero actual drawdown as ``warning`` and a large
    one as ``critical`` — a divide-by-zero would otherwise mask a real
    deviation.
    """
    if expected <= 0:
        if actual <= 0:
            severity: Severity = "normal"
        elif actual >= 0.05:
            severity = "critical"
        else:
            severity = "warning"
        return DeviationMetric(
            metric_name="drawdown",
            expected=expected,
            actual=actual,
            deviation_percent=_signed_deviation_percent(expected, actual),
            severity=severity,
            hinglish_message=drawdown_message(expected, actual),
        )
    if actual <= expected:
        severity = "normal"
    else:
        ratio = actual / expected
        watch_min, warning_min, critical_min = DRAWDOWN_MULTIPLIERS
        if ratio <= watch_min:
            severity = "normal"
        elif ratio <= warning_min:
            severity = "watch"
        elif ratio <= critical_min:
            severity = "warning"
        else:
            severity = "critical"
    return DeviationMetric(
        metric_name="drawdown",
        expected=expected,
        actual=actual,
        deviation_percent=_signed_deviation_percent(expected, actual),
        severity=severity,
        hinglish_message=drawdown_message(expected, actual),
    )


def compare_profit_factor(expected: float, actual: float) -> DeviationMetric:
    """Profit-factor *relative drop* from expected.

    ``drop = (expected - actual) / expected`` (negative when actual
    beats expected → ``normal``). When expected is zero/non-finite we
    can't form a ratio; severity falls to ``normal`` with no false
    alarm.
    """
    if not math.isfinite(expected) or expected <= 0:
        return DeviationMetric(
            metric_name="profit_factor",
            expected=expected,
            actual=actual,
            deviation_percent=_signed_deviation_percent(expected, actual),
            severity="normal",
            hinglish_message=profit_factor_message(expected, actual),
        )
    drop = (expected - actual) / expected
    if drop <= 0:
        severity: Severity = "normal"
    else:
        severity = _band(drop, PROFIT_FACTOR_DROP_PCT)
    return DeviationMetric(
        metric_name="profit_factor",
        expected=expected,
        actual=actual,
        deviation_percent=_signed_deviation_percent(expected, actual),
        severity=severity,
        hinglish_message=profit_factor_message(expected, actual),
    )


def compare_trade_frequency(expected: float, actual: float) -> DeviationMetric:
    """Trade-frequency *relative diff*.

    Symmetric ``abs(expected - actual) / expected``. When the expected
    rate is zero or undefined the metric returns ``normal`` — no
    baseline to deviate from.
    """
    if not math.isfinite(expected) or expected <= 0:
        return DeviationMetric(
            metric_name="trade_frequency",
            expected=expected,
            actual=actual,
            deviation_percent=_signed_deviation_percent(expected, actual),
            severity="normal",
            hinglish_message=trade_frequency_message(expected, actual),
        )
    diff = abs(expected - actual) / expected
    severity = _band(diff, TRADE_FREQ_THRESHOLDS)
    return DeviationMetric(
        metric_name="trade_frequency",
        expected=expected,
        actual=actual,
        deviation_percent=_signed_deviation_percent(expected, actual),
        severity=severity,
        hinglish_message=trade_frequency_message(expected, actual),
    )


__all__ = [
    "compare_drawdown",
    "compare_profit_factor",
    "compare_trade_frequency",
    "compare_win_rate",
]
