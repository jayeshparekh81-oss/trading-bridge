"""Boundary models for the Data Quality validator.

All models are frozen + ``extra="forbid"`` so a quality report can
flow through the rest of the engine (UI, advisor, broker guard) as
an immutable snapshot. The validator returns a
:class:`DataQualityReport` and consumers should never mutate it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IssueType = Literal[
    "missing_candle",
    "duplicate_candle",
    "invalid_ohlc",
    "zero_volume",
    "time_gap",
    "timezone_mismatch",
    "out_of_order",
]

IssueSeverity = Literal["info", "warning", "critical"]


class DataQualityIssue(BaseModel):
    """One detected anomaly in the candle stream.

    ``candle_index`` references the position of the offending bar in
    the input list. ``None`` means the issue is series-level rather
    than tied to a specific bar (e.g. a timezone mix observed across
    several bars and reported once).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_type: IssueType
    severity: IssueSeverity
    candle_index: int | None = Field(default=None, ge=0)
    message: str = Field(..., min_length=1, max_length=512)
    hinglish_message: str = Field(..., min_length=1, max_length=512)


class DataQualityReport(BaseModel):
    """Top-level validator output.

    ``is_valid`` is the lightweight gate (no critical issues at all);
    ``can_backtest`` is the stricter gate the backtest engine should
    consult before trusting the candle stream.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool
    total_candles: int = Field(..., ge=0)
    issues: tuple[DataQualityIssue, ...] = Field(default_factory=tuple)
    quality_score: float = Field(..., ge=0, le=100)
    summary_hinglish: str = Field(..., min_length=1, max_length=512)
    can_backtest: bool


__all__ = [
    "DataQualityIssue",
    "DataQualityReport",
    "IssueSeverity",
    "IssueType",
]
