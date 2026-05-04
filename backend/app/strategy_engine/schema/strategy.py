"""Strategy JSON — the single source of truth for a user-built strategy.

The same JSON shape is consumed by:
    * the builder UI (Phase 5),
    * the entry/exit/risk engines (Phase 2),
    * the deterministic backtest engine (Phase 3),
    * the reliability / trust-score engine (Phase 4),
    * the AI advisor (Phase 6),
    * the Pine source-code importer (Phase 7),
    * the paper/live execution bridge (Phase 8).

Phase 1 ships only the schema. Downstream phases lean on Pydantic to
catch malformed strategies at the boundary so engine code never has to
guard against missing fields.

Conditions are a discriminated union on ``type`` so each variant carries
exactly the keys it needs and the validator surfaces clear error
messages when keys are missing or extra.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrategyMode(StrEnum):
    """User experience tier — drives builder UI affordances and AI tone."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class Side(StrEnum):
    """Direction of an entry."""

    BUY = "BUY"
    SELL = "SELL"


class ExecutionMode(StrEnum):
    """Which downstream runner the strategy targets.

    Phase 1 ships the literal; Phase 8 wires runners. The schema-level
    invariant is just that the user picked one; semantics live in the
    execution bridge.
    """

    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class OrderType(StrEnum):
    """Broker-agnostic order type vocabulary."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class ProductType(StrEnum):
    """Broker-agnostic product type vocabulary.

    Mirrors the existing ``app.schemas.broker.ProductType`` value set so
    Phase 8 can adapt without renaming. Kept as a separate enum here so
    the strategy schema does not pull in the broker schema package.
    """

    INTRADAY = "INTRADAY"
    MARGIN = "MARGIN"
    DELIVERY = "DELIVERY"
    BO = "BO"
    CO = "CO"


class IndicatorConfig(BaseModel):
    """One indicator instance configured for use inside a strategy.

    ``id`` is the user-facing instance handle (``"ema_20"``); ``type`` is
    the registry id (``"ema"``). ``params`` is validated against the
    registry's :class:`InputSpec` list at runtime by
    :func:`app.strategy_engine.indicators.registry.validate_indicator_params`,
    not here — the schema only enforces structural shape.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    type: str = Field(..., min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "type")
    @classmethod
    def _lower_snake(cls, value: str) -> str:
        if not value.replace("_", "").isalnum() or value != value.lower():
            raise ValueError(f"{value!r} must be lower-snake-case (a-z, 0-9, _).")
        return value


# ─── Conditions — discriminated union on ``type`` ───────────────────────


class IndicatorConditionOp(StrEnum):
    """Operators for indicator-on-indicator and indicator-on-value tests."""

    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    CROSSOVER = "crossover"
    CROSSUNDER = "crossunder"


class IndicatorCondition(BaseModel):
    """``left`` is the indicator id; ``right`` OR ``value`` is the RHS.

    Exactly one of ``right`` (another indicator id) and ``value`` (a
    constant) must be present. ``crossover``/``crossunder`` are only
    meaningful between two indicator series — using them with ``value``
    is rejected by the validator.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: Literal["indicator"]
    left: str = Field(..., min_length=1, max_length=64)
    op: IndicatorConditionOp
    right: str | None = Field(default=None, min_length=1, max_length=64)
    value: float | None = None

    @model_validator(mode="after")
    def _xor_right_and_value(self) -> IndicatorCondition:
        if (self.right is None) == (self.value is None):
            raise ValueError(
                "IndicatorCondition requires exactly one of 'right' (indicator id) "
                "or 'value' (constant)."
            )
        if (
            self.op in (IndicatorConditionOp.CROSSOVER, IndicatorConditionOp.CROSSUNDER)
            and self.right is None
        ):
            raise ValueError(
                f"op={self.op.value!r} requires 'right' (indicator id); "
                "crossover/crossunder are not defined against a constant."
            )
        return self


class CandlePattern(StrEnum):
    """Supported candle-pattern primitives. Phase 2 implements detection."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    ENGULFING = "engulfing"
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"


class CandleCondition(BaseModel):
    """Match a single-candle pattern at the current bar."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: Literal["candle"]
    pattern: CandlePattern


class TimeConditionOp(StrEnum):
    """Time-of-day operators (IST wall-clock at runtime)."""

    AFTER = "after"
    BEFORE = "before"
    BETWEEN = "between"
    EXACT = "exact"


class TimeCondition(BaseModel):
    """Match the current bar's time against a wall-clock rule.

    ``value`` is an ``HH:MM`` string. ``end`` is required when
    ``op == BETWEEN`` and ignored otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: Literal["time"]
    op: TimeConditionOp
    value: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")

    @model_validator(mode="after")
    def _between_requires_end(self) -> TimeCondition:
        if self.op is TimeConditionOp.BETWEEN and self.end is None:
            raise ValueError("op='between' requires 'end' (HH:MM).")
        if self.op is not TimeConditionOp.BETWEEN and self.end is not None:
            raise ValueError(f"'end' is only valid when op='between'; got op={self.op.value!r}.")
        return self


class PriceConditionOp(StrEnum):
    """Price comparators and breakout primitives."""

    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    PREVIOUS_HIGH_BREAKOUT = "previous_high_breakout"
    PREVIOUS_LOW_BREAKDOWN = "previous_low_breakdown"


class PriceCondition(BaseModel):
    """Test the current price against a level or breakout primitive.

    ``value`` is required for the comparison operators (``>``/``<``/
    ``>=``/``<=``) and ignored for the breakout primitives.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: Literal["price"]
    op: PriceConditionOp
    value: float | None = None

    @model_validator(mode="after")
    def _value_required_for_comparators(self) -> PriceCondition:
        comparators = {
            PriceConditionOp.GT,
            PriceConditionOp.LT,
            PriceConditionOp.GTE,
            PriceConditionOp.LTE,
        }
        if self.op in comparators and self.value is None:
            raise ValueError(f"op={self.op.value!r} requires 'value' (price level).")
        if self.op not in comparators and self.value is not None:
            raise ValueError(f"op={self.op.value!r} does not use 'value'; remove it.")
        return self


Condition = Annotated[
    IndicatorCondition | CandleCondition | TimeCondition | PriceCondition,
    Field(discriminator="type"),
]


# ─── Top-level rule blocks ──────────────────────────────────────────────


class EntryRules(BaseModel):
    """Conditions that, when satisfied, fire an entry of ``side``."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    side: Side
    operator: Literal["AND", "OR"] = "AND"
    conditions: list[Condition] = Field(..., min_length=1)


class PartialExit(BaseModel):
    """Booking ``qtyPercent`` of the position when ``targetPercent`` is hit."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    qty_percent: float = Field(..., gt=0, le=100, alias="qtyPercent")
    target_percent: float = Field(..., gt=0, alias="targetPercent")


class ExitRules(BaseModel):
    """Exit primitives. All fields optional; at least one must be set so
    the engine never opens a position without a documented way out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    target_percent: float | None = Field(default=None, gt=0, alias="targetPercent")
    stop_loss_percent: float | None = Field(default=None, gt=0, alias="stopLossPercent")
    trailing_stop_percent: float | None = Field(default=None, gt=0, alias="trailingStopPercent")
    partial_exits: list[PartialExit] = Field(default_factory=list, alias="partialExits")
    square_off_time: str | None = Field(
        default=None, pattern=r"^\d{2}:\d{2}$", alias="squareOffTime"
    )
    indicator_exits: list[Condition] = Field(default_factory=list, alias="indicatorExits")
    reverse_signal_exit: bool = Field(default=False, alias="reverseSignalExit")

    @model_validator(mode="after")
    def _at_least_one_exit(self) -> ExitRules:
        has_exit = any(
            (
                self.target_percent is not None,
                self.stop_loss_percent is not None,
                self.trailing_stop_percent is not None,
                bool(self.partial_exits),
                self.square_off_time is not None,
                bool(self.indicator_exits),
                self.reverse_signal_exit,
            )
        )
        if not has_exit:
            raise ValueError(
                "ExitRules must define at least one exit primitive (target, "
                "stopLoss, trailingStop, partialExits, squareOffTime, "
                "indicatorExits, or reverseSignalExit)."
            )
        return self


class RiskRules(BaseModel):
    """Account-level guardrails. All fields optional; defaults are 'no cap'.

    The risk engine (Phase 2) reads this and emits warnings/blocks when
    the strategy violates one of the configured caps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    max_daily_loss_percent: float | None = Field(default=None, gt=0, alias="maxDailyLossPercent")
    max_trades_per_day: int | None = Field(default=None, gt=0, alias="maxTradesPerDay")
    max_loss_streak: int | None = Field(default=None, gt=0, alias="maxLossStreak")
    max_capital_per_trade_percent: float | None = Field(
        default=None, gt=0, le=100, alias="maxCapitalPerTradePercent"
    )


class ExecutionConfig(BaseModel):
    """Routing + order shape. ``mode`` picks the runner (Phase 8)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    mode: ExecutionMode
    order_type: OrderType = Field(..., alias="orderType")
    product_type: ProductType = Field(..., alias="productType")


class StrategyJSON(BaseModel):
    """A user-built strategy in its canonical serialised form.

    Indicator references inside ``entry``/``exit`` conditions are
    validated structurally here (the indicator id used in a condition
    must appear in ``indicators[*].id``). Cross-checking against the
    runtime registry (does ``ema_20``'s registry ``type=ema`` exist and
    have valid params?) is the registry's job and runs at the next
    boundary up — the builder service or backtest entrypoint.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    mode: StrategyMode
    version: int = Field(default=1, ge=1)
    indicators: list[IndicatorConfig] = Field(default_factory=list)
    entry: EntryRules
    exit: ExitRules
    risk: RiskRules = Field(default_factory=RiskRules)
    execution: ExecutionConfig

    @model_validator(mode="after")
    def _indicator_ids_unique_and_referenced(self) -> StrategyJSON:
        ids = [ind.id for ind in self.indicators]
        if len(set(ids)) != len(ids):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"Duplicate indicator ids in 'indicators': {duplicates}.")
        known = set(ids)
        unknown = sorted(_collect_referenced_ids(self) - known)
        if unknown:
            raise ValueError(
                f"Conditions reference indicator ids not declared in 'indicators': {unknown}."
            )
        return self


def _collect_referenced_ids(strategy: StrategyJSON) -> set[str]:
    """Walk entry + exit conditions and return every indicator id referenced.

    Only :class:`IndicatorCondition` carries indicator ids; the others
    (candle/time/price) reference no registry instance. Both ``left`` and
    ``right`` (when set) are collected.
    """
    referenced: set[str] = set()
    for cond in strategy.entry.conditions:
        if isinstance(cond, IndicatorCondition):
            referenced.add(cond.left)
            if cond.right is not None:
                referenced.add(cond.right)
    for cond in strategy.exit.indicator_exits:
        if isinstance(cond, IndicatorCondition):
            referenced.add(cond.left)
            if cond.right is not None:
                referenced.add(cond.right)
    return referenced


__all__ = [
    "CandleCondition",
    "CandlePattern",
    "Condition",
    "EntryRules",
    "ExecutionConfig",
    "ExecutionMode",
    "ExitRules",
    "IndicatorCondition",
    "IndicatorConditionOp",
    "IndicatorConfig",
    "OrderType",
    "PartialExit",
    "PriceCondition",
    "PriceConditionOp",
    "ProductType",
    "RiskRules",
    "Side",
    "StrategyJSON",
    "StrategyMode",
    "TimeCondition",
    "TimeConditionOp",
]
