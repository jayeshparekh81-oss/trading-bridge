"""Data Quality validator — public boundary.

Pure deterministic pipeline that consumes a candle stream and returns
a structured :class:`DataQualityReport`. No LLM calls, no network, no
clock reads — the same inputs always produce the same report.

The validator is read-only: candles are inspected, never mutated.
Consumers (UI, advisor, backtest gate) use :attr:`can_backtest` and
:attr:`is_valid` to decide whether to proceed.

Public surface::

    validate_candles / DataQualityReport / DataQualityIssue /
    IssueType / IssueSeverity
"""

from __future__ import annotations

from app.strategy_engine.data_quality.models import (
    DataQualityIssue,
    DataQualityReport,
    IssueSeverity,
    IssueType,
)
from app.strategy_engine.data_quality.validator import validate_candles

__all__ = [
    "DataQualityIssue",
    "DataQualityReport",
    "IssueSeverity",
    "IssueType",
    "validate_candles",
]
