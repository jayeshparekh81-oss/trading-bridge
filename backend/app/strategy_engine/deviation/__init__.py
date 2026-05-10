"""Live-vs-Backtest Deviation Monitor — public boundary.

Pure deterministic module that compares actual paper / live trading
performance against backtest expectations and emits a structured
:class:`DeviationReport`. The report carries a read-only
``auto_kill_switch_signal`` boolean — wiring that signal into the
real safety system is a separate future phase by design.

Public surface::

    evaluate_deviation / DeviationReport / DeviationMetric /
    LiveTradingStats / Severity / ActualStats
"""

from __future__ import annotations

from app.strategy_engine.deviation.models import (
    DeviationMetric,
    DeviationReport,
    LiveTradingStats,
    Severity,
)
from app.strategy_engine.deviation.monitor import (
    ActualStats,
    evaluate_deviation,
)

__all__ = [
    "ActualStats",
    "DeviationMetric",
    "DeviationReport",
    "LiveTradingStats",
    "Severity",
    "evaluate_deviation",
]
