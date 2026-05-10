"""Indicator metadata — the shape every entry in the registry must take.

The registry is the single source of truth for "what indicators does the
platform expose right now?". The UI builder, Pine importer, AI advisor,
and backtest engine all read from it. Metadata is intentionally
serialisable: the frontend can fetch a dump of the registry as JSON
(later phase) without any custom (de)serialisation code.

Status semantics:
    * ``active``       — calculation function implemented, usable in
                         strategies, shown to all difficulty levels per
                         the metadata's ``difficulty`` field.
    * ``coming_soon``  — metadata only; ``calculationFunction`` may be
                         ``None``. Hidden from beginner mode and
                         rejected by strategy execution paths.
    * ``experimental`` — implemented but unstable; visible only in
                         expert mode and surfaces a warning at use site.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InputType(StrEnum):
    """Allowed types for an indicator input parameter."""

    NUMBER = "number"  # int or float (range validation via min/max)
    SOURCE = "source"  # PriceSource enum value (e.g. "close")
    BOOLEAN = "boolean"
    STRING = "string"  # free-form (e.g. signal label)


class InputSpec(BaseModel):
    """Declares one parameter an indicator accepts.

    The ``default`` is whatever the registry's metadata claims; runtime
    callers (UI builder, backtest) read it when the user hasn't overridden
    the value. ``min``/``max`` apply only when ``type == NUMBER`` and are
    advisory — strict enforcement happens in
    :func:`app.strategy_engine.indicators.registry.validate_indicator_params`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    type: InputType
    default: Any = Field(...)
    min: float | None = None
    max: float | None = None
    description: str | None = Field(default=None, max_length=512)


class IndicatorChartType(StrEnum):
    """How the indicator is drawn relative to the price chart."""

    OVERLAY = "overlay"  # plotted on the price pane (e.g. EMA, Bollinger)
    SEPARATE = "separate"  # plotted in its own pane (e.g. RSI, MACD)


class IndicatorDifficulty(StrEnum):
    """User-difficulty-level filter; controls visibility in the builder."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class IndicatorStatus(StrEnum):
    """Lifecycle status — controls execution-time eligibility."""

    ACTIVE = "active"
    COMING_SOON = "coming_soon"
    EXPERIMENTAL = "experimental"


class IndicatorMetadata(BaseModel):
    """One entry in the indicator registry.

    The ``id`` is the canonical short name used everywhere else
    (``"ema"``, ``"rsi"``); strategy JSON references indicators by this
    id via :class:`IndicatorConfig.type`. ``calculationFunction`` is the
    string name of the pure-Python function in
    :mod:`app.strategy_engine.indicators.calculations` that computes the
    indicator. Coming-soon entries leave it as ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    category: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=1024)
    inputs: list[InputSpec] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    chart_type: IndicatorChartType = Field(..., alias="chartType")
    pine_aliases: list[str] = Field(default_factory=list, alias="pineAliases")
    difficulty: IndicatorDifficulty
    status: IndicatorStatus
    ai_explanation: str = Field(..., min_length=1, max_length=2048, alias="aiExplanation")
    tags: list[str] = Field(default_factory=list)
    calculation_function: str | None = Field(default=None, alias="calculationFunction")

    @field_validator("id")
    @classmethod
    def _id_must_be_lower_snake(cls, value: str) -> str:
        """Registry ids are lower_snake_case for predictability across UI/API/Pine."""
        if not value.replace("_", "").isalnum() or value != value.lower():
            raise ValueError(f"Indicator id {value!r} must be lower-snake-case (a-z, 0-9, _).")
        return value


__all__ = [
    "IndicatorChartType",
    "IndicatorDifficulty",
    "IndicatorMetadata",
    "IndicatorStatus",
    "InputSpec",
    "InputType",
]
