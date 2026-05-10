"""Hinglish copy templates for the Deviation Monitor.

Per-metric formatters and status-level summaries are kept here so the
calculation layer (``metrics``, ``scorer``) stays pure-math and the
copy can be tweaked without re-validating thresholds.

Templates are *exactly* the ones locked in
``prompts/master-plan-final.md``; the unit tests assert their keywords
to catch silent re-wording.
"""

from __future__ import annotations

from app.strategy_engine.deviation.models import Severity

# ─── Status-level summaries ────────────────────────────────────────────


_STATUS_SUMMARY: dict[Severity, str] = {
    "normal": ("Live performance backtest se match kar raha hai. Continue monitoring."),
    "watch": "Halki si deviation hai. Watch karte raho.",
    "warning": ("Deviation badh raha hai. Position size kam karo aur paper mode mein switch karo."),
    "critical": (
        "Strategy expectation se bahut alag chal raha hai. Pause karo, paper mein test karo."
    ),
}


def status_summary(status: Severity) -> str:
    """Return the locked Hinglish summary line for ``status``."""
    return _STATUS_SUMMARY[status]


# ─── Recommended-action lists (locked) ─────────────────────────────────


_RECOMMENDED_ACTIONS: dict[Severity, tuple[str, ...]] = {
    "normal": ("Continue monitoring.",),
    "watch": ("Live performance slightly differs from backtest. Continue but watch closely.",),
    "warning": (
        "Reduce position size to 50%.",
        "Switch to paper for next session.",
    ),
    "critical": (
        "Pause strategy immediately.",
        "Switch to paper trading.",
        "Re-run reliability test.",
    ),
}


def recommended_actions(status: Severity) -> tuple[str, ...]:
    """Return the locked action list for ``status``."""
    return _RECOMMENDED_ACTIONS[status]


# ─── Per-metric Hinglish formatters ────────────────────────────────────


def win_rate_message(expected: float, actual: float) -> str:
    """Backtest-vs-actual win-rate copy (expects fractions, prints %).

    Negative diffs (actual higher than expected) are rare but render
    cleanly: the ``Difference`` line shows the absolute % gap so the
    operator sees magnitude regardless of sign.
    """
    expected_pct = expected * 100
    actual_pct = actual * 100
    diff_pct = abs(expected_pct - actual_pct)
    return (
        f"Backtest mein {expected_pct:.1f}% win rate tha, abhi sirf "
        f"{actual_pct:.1f}% mil raha. Difference {diff_pct:.1f}%."
    )


def drawdown_message(expected: float, actual: float) -> str:
    """Drawdown copy — fractions are converted to % for display."""
    return (
        f"Backtest mein max {expected * 100:.1f}% drawdown tha, abhi "
        f"{actual * 100:.1f}% pahunch gaya. Sambhalo."
    )


def profit_factor_message(expected: float, actual: float) -> str:
    """Profit-factor copy — printed with 2 decimal places like the
    rest of the strategy-engine surface."""
    return (
        f"Profit factor expected {expected:.2f} tha, abhi sirf "
        f"{actual:.2f}. Charges aur slippage check karo."
    )


def trade_frequency_message(expected: float, actual: float) -> str:
    """Trade-frequency copy. ``expected`` and ``actual`` are
    trades-per-day / trades-per-session respectively."""
    return (
        f"Backtest mein {expected:.2f} trades/day expected the, abhi "
        f"{actual:.2f}. Market conditions badal gayi shayad."
    )


def insufficient_data_message(threshold: int, observed: int) -> str:
    """Returned when the actual sample is too small to evaluate.

    The monitor still emits a ``DeviationReport``; this string lands as
    the ``hinglish_summary`` and a single placeholder metric so the UI
    has something concrete to render.
    """
    return (
        f"Insufficient data for deviation analysis: {observed} trades observed, "
        f"need at least {threshold}."
    )


__all__ = [
    "drawdown_message",
    "insufficient_data_message",
    "profit_factor_message",
    "recommended_actions",
    "status_summary",
    "trade_frequency_message",
    "win_rate_message",
]
