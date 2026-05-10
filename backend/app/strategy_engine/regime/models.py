"""Boundary models for the Market Regime detector.

All models are frozen + ``extra="forbid"`` so the regime report can
flow through the rest of the engine (UI, advisor, broker guard) as
an immutable snapshot. The detector returns a :class:`RegimeReport`
and consumers should never mutate it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RegimeName = Literal[
    "trending",
    "sideways",
    "high_volatility",
    "low_volatility",
    "gap_day",
    "choppy",
    "breakout",
    "abnormal",
]

SuitabilityRiskLevel = Literal["low", "medium", "high"]

StrategyType = Literal[
    "trend_following",
    "mean_reversion",
    "breakout",
    "volatility",
    "unknown",
]


class RegimeMetrics(BaseModel):
    """Deterministic metrics computed from the candle stream.

    Each field maps 1:1 to a numeric input the classifier consults.
    Optional fields are ``None`` when the candle history is too short
    or the underlying signal is undefined (e.g. gap_percent on the
    very first bar).

    JSON aliases match the camelCase wire convention used by
    :class:`BacktestResult` / :class:`TruthReport`; internal Python
    callers can keep using the snake_case attribute names thanks to
    ``populate_by_name=True``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    adx_value: float = Field(..., ge=0, le=100, alias="adxValue")
    atr_normalized: float = Field(
        ...,
        ge=0,
        alias="atrNormalized",
        description="Current ATR divided by current close — unitless volatility.",
    )
    ma_slope_percent: float = Field(
        ...,
        alias="maSlopePercent",
        description="Percent change of the 20-period SMA over the slope window.",
    )
    range_compression_ratio: float = Field(
        ...,
        ge=0,
        alias="rangeCompressionRatio",
        description="last_window_range / previous_window_range; <1 = compression.",
    )
    gap_percent: float | None = Field(
        default=None,
        alias="gapPercent",
        description="(open - prev_close) / prev_close — fraction; None for first bar.",
    )
    direction_changes_count: int = Field(..., ge=0, alias="directionChangesCount")
    volatility_percentile: float = Field(
        ...,
        ge=0,
        le=1,
        alias="volatilityPercentile",
        description="Percentile (0-1) of current ATR within the ATR series.",
    )


class StrategySuitability(BaseModel):
    """Verdict from matching a strategy against the detected regime.

    Populated only when the caller passes a strategy to ``detect_regime``;
    otherwise the detector returns :class:`RegimeReport` with
    ``strategy_suitability`` set to ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    suitable: bool
    reason: str = Field(..., min_length=1, max_length=512)
    risk_level: SuitabilityRiskLevel = Field(..., alias="riskLevel")
    strategy_type: StrategyType = Field(..., alias="strategyType")


class RegimeReport(BaseModel):
    """Top-level detector output.

    ``confidence`` is locked to 0-1; the classifier maps each rule's
    metric strength to a float so callers can apply their own
    thresholds (UI emphasis, advisor escalation, broker guard).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    regime: RegimeName
    confidence: float = Field(..., ge=0, le=1)
    metrics: RegimeMetrics
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    strategy_suitability: StrategySuitability | None = Field(
        default=None, alias="strategySuitability"
    )
    hinglish_summary: str = Field(..., min_length=1, max_length=512, alias="hinglishSummary")


__all__ = [
    "RegimeMetrics",
    "RegimeName",
    "RegimeReport",
    "StrategySuitability",
    "StrategyType",
    "SuitabilityRiskLevel",
]
