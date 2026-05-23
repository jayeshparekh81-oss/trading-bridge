"""Pine Script v4.8.1 alert payload schemas (raw, pre-mapping) + the
strategy-side options config.

Phase 2B adds options support:

  * :class:`PineAlertPayload` — the raw alert body. It gains two optional
    fields, ``spot_price`` (underlying price, used for strike resolution)
    and ``signal_direction`` (normalised entry/exit direction). Both are
    optional, so existing **futures** alerts — which omit them — keep
    validating unchanged.

  * :class:`OptionsConfig` — the options block stored on
    ``Strategy.strategy_json`` (under the ``"options"`` key). It encodes
    the **NRML carry-forward mandate**: ``product_type`` must be NRML and
    ``carry_forward`` must be true. MIS/INTRADAY are rejected at the
    schema boundary because their auto-square-off would silently
    liquidate a multi-day options position.

None of this touches the normalised :class:`StrategyWebhookPayload` shape,
so the live BSE LTD futures path is unaffected.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ───────────────────────────────────────────────────────────────────────
# Raw Pine alert
# ───────────────────────────────────────────────────────────────────────


class PineSignalDirection(StrEnum):
    """Normalised entry/exit direction a Pine alert may carry explicitly.

    Optional — the mapper also derives direction from the legacy ``type``
    field (``LONG_ENTRY`` / ``SHORT_ENTRY`` / …) when this is absent.
    """

    LONG_ENTRY = "LONG_ENTRY"
    SHORT_ENTRY = "SHORT_ENTRY"
    EXIT = "EXIT"


class PineAlertPayload(BaseModel):
    """Raw Pine v4.8.1 alert body.

    ``extra="allow"`` keeps the ~17 indicator keys and any TradingView
    template noise; we only pin the fields the mapper reads plus the two
    Phase 2B options additions.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    type: str | None = None
    action: str | None = None
    symbol: str | None = None
    qty: int | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0"))

    # ─── Phase 2B options additions (optional → futures stays valid) ────
    spot_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description=(
            "Underlying spot price at signal time. Used for ATM/OTM strike "
            "resolution. Optional; falls back to ``price`` when absent."
        ),
    )
    signal_direction: PineSignalDirection | None = Field(
        default=None,
        description=(
            "Normalised LONG_ENTRY/SHORT_ENTRY/EXIT. Optional — the mapper "
            "derives direction from ``type`` when this is omitted."
        ),
    )


# ───────────────────────────────────────────────────────────────────────
# Strategy-side options config (lives on Strategy.strategy_json["options"])
# ───────────────────────────────────────────────────────────────────────

#: Product types whose semantics are NRML carry-forward (overnight F&O).
_NRML_ALIASES: frozenset[str] = frozenset({"NRML", "MARGIN"})

#: Forbidden for options — both auto-square-off intraday.
_FORBIDDEN_PRODUCTS: frozenset[str] = frozenset({"MIS", "INTRADAY"})


class StrikeSelection(BaseModel):
    """How to pick the strike relative to spot.

    * ``ATM`` — nearest strike-step multiple to spot (``offset`` ignored).
    * ``OTM_OFFSET`` — ``offset`` strikes out-of-the-money from ATM.
    * ``ITM_OFFSET`` — ``offset`` strikes in-the-money from ATM.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["ATM", "OTM_OFFSET", "ITM_OFFSET"] = "ATM"
    offset: int = Field(default=0, ge=0, le=50)


class OptionsConfig(BaseModel):
    """Options config block on ``Strategy.strategy_json["options"]``.

    NRML carry-forward is mandatory (see module docstring). The Pydantic
    validators raise :class:`ValueError` for any other product type; the
    mapper's ``parse_options_config`` translates that into a
    ``PineMapperError`` so the webhook layer sees a single error type.
    """

    model_config = ConfigDict(extra="ignore")

    option_type: Literal["auto", "CE_only", "PE_only"] = "auto"
    strike_selection: StrikeSelection = Field(default_factory=StrikeSelection)
    expiry: Literal["current_week", "next_week", "current_month"] = "current_week"
    premium_budget_per_lot: Decimal | None = Field(default=None, gt=Decimal("0"))
    product_type: str = "NRML"
    carry_forward: bool = True
    expiry_day_force_close: bool = True
    no_intraday_squareoff: bool = True
    #: Optional override for the underlying's strike step. None → the
    #: mapper applies its instrument default (BSE LTD = 100, see notes).
    strike_step: Decimal | None = Field(default=None, gt=Decimal("0"))

    @field_validator("product_type", mode="after")
    @classmethod
    def _must_be_nrml(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper in _FORBIDDEN_PRODUCTS:
            raise ValueError(
                f"options are NRML carry-forward only; product_type={v!r} "
                "(MIS/INTRADAY) is forbidden — intraday auto-square-off "
                "breaks multi-day positions"
            )
        if upper not in _NRML_ALIASES:
            raise ValueError(
                f"unsupported options product_type {v!r}; must be 'NRML'"
            )
        return "NRML"

    @field_validator("carry_forward", mode="after")
    @classmethod
    def _must_carry_forward(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "options require carry_forward=true (NRML carry-forward only)"
            )
        return v


__all__ = [
    "_FORBIDDEN_PRODUCTS",
    "_NRML_ALIASES",
    "OptionsConfig",
    "PineAlertPayload",
    "PineSignalDirection",
    "StrikeSelection",
]
