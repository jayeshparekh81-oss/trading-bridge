"""Strategy-webhook Pydantic schemas.

Distinct from :class:`app.schemas.webhook.WebhookPayload` (which serves
the legacy single-order ``/api/webhook/{token}`` endpoint). The strategy
endpoint at ``/api/webhook/strategy/{token}`` accepts Pine-Script-driven
direct-exit actions:

    ENTRY    — open a new position (or add to existing — see "concurrent
               positions" note in the webhook handler)
    PARTIAL  — close ``closePct`` % of the current open quantity
    EXIT     — close all remaining quantity (Pine-decided exit)
    SL_HIT   — close all remaining quantity (Pine-decided stop loss).
               Semantically same as EXIT but recorded with
               ``leg_role='direct_sl'`` and a 🛑 Telegram emoji so the
               audit trail can distinguish the two reasons.
    BUY/SELL — legacy aliases for ENTRY. Webhook handler maps to
               ``ENTRY`` + ``side`` and logs an INFO message so callers
               know they're using deprecated names.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrategyAction(StrEnum):
    """Action vocabulary accepted by the strategy webhook.

    Internal vocabulary is ``ENTRY``/``PARTIAL``/``EXIT``/``SL_HIT`` plus
    the legacy ``BUY``/``SELL`` aliases. The Pine mapper emits the
    canonical names; the webhook handler aliases BUY/SELL → ENTRY.
    """

    ENTRY = "ENTRY"
    PARTIAL = "PARTIAL"
    EXIT = "EXIT"
    SL_HIT = "SL_HIT"
    # Legacy aliases — handler treats as ENTRY with INFO log on use.
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(StrEnum):
    """Direction of the open exposure. Carried separately from the
    action so PARTIAL/EXIT/SL_HIT can target the right position."""

    LONG = "long"
    SHORT = "short"


class StrategyWebhookPayload(BaseModel):
    """Normalized strategy-webhook payload (post-Pine-mapping).

    Fed by either:
      * Native callers sending the canonical shape directly.
      * The Pine mapper which translates v4.8.1 alerts into this shape.

    Validation rules:
      * ``ENTRY`` (and BUY/SELL aliases) require a positive ``quantity``.
      * ``PARTIAL`` requires ``close_pct`` in (0, 99]. ``quantity`` is
        ignored — close size is derived from the open position.
      * ``EXIT`` / ``SL_HIT`` ignore ``quantity`` and ``close_pct`` —
        always close the full remaining position.

    Extra fields are dropped (TradingView injects timestamp / description /
    template noise we don't care about).
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        use_enum_values=False,
        populate_by_name=True,
    )

    action: StrategyAction
    symbol: str = Field(..., min_length=1, max_length=64)
    side: PositionSide | None = Field(
        default=None,
        description=(
            "long|short — required for PARTIAL/EXIT/SL_HIT and for ENTRY "
            "when the legacy BUY/SELL alias is not used."
        ),
    )
    quantity: int | None = Field(
        default=None,
        gt=0,
        le=100_000,
        description="ENTRY only — total contracts to fill.",
    )
    close_pct: float | None = Field(
        default=None,
        gt=0,
        le=99,
        alias="closePct",
        description=(
            "PARTIAL only — % of the current open quantity to close. "
            "Range (0, 99]. Server logic mirrors server_final30mar.py: "
            "``close_qty = floor(open_qty * close_pct / 100)`` rounded "
            "down to the nearest lot multiple."
        ),
    )

    instrument_type: str | None = Field(default=None, max_length=32)
    product_type: str | None = Field(default=None, max_length=16)
    order_type: str | None = Field(default="market", max_length=16)
    price: Decimal | None = Field(default=None, ge=Decimal("0"))
    signal_id: str | None = Field(default=None, max_length=128)
    lot_size_hint: int | None = Field(default=None, gt=0)

    # Pine-mapped passthrough — opaque to the webhook handler but kept on
    # the row so the AI validator + audit log can introspect.
    indicators: dict[str, Any] | None = None
    score: float | None = None
    pine_type: str | None = None
    pine_action_raw: str | None = None

    @field_validator("symbol", mode="after")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        """Normalize symbol case at the schema boundary so position
        creation and PARTIAL/EXIT lookups never disagree on case.

        Dhan's scrip master keys symbols by `SEM_TRADING_SYMBOL.upper()`
        already (see :func:`app.brokers.dhan._ScripMaster._parse`), so
        uppering here matches the broker-side canonicalisation."""
        return v.upper()

    @model_validator(mode="after")
    def _per_action_required_fields(self) -> StrategyWebhookPayload:
        action = self.action
        # ENTRY family — quantity required, side derivable
        if action in (
            StrategyAction.ENTRY,
            StrategyAction.BUY,
            StrategyAction.SELL,
        ):
            if self.quantity is None or self.quantity <= 0:
                raise ValueError(
                    f"action={action.value} requires positive 'quantity'."
                )
            # BUY/SELL imply side; ENTRY needs explicit side
            if action == StrategyAction.ENTRY and self.side is None:
                raise ValueError(
                    "action=ENTRY requires 'side' (long|short). "
                    "Legacy BUY/SELL infer side automatically."
                )
        elif action == StrategyAction.PARTIAL:
            if self.close_pct is None:
                raise ValueError(
                    "action=PARTIAL requires 'closePct' in (0, 99]."
                )
            if self.side is None:
                raise ValueError("action=PARTIAL requires 'side' (long|short).")
        elif action in (StrategyAction.EXIT, StrategyAction.SL_HIT):
            if self.side is None:
                raise ValueError(
                    f"action={action.value} requires 'side' (long|short)."
                )
        return self

    def normalized_side(self) -> PositionSide:
        """Resolve side, honouring legacy BUY/SELL aliases.

        Raises ``ValueError`` if neither alias nor explicit side is
        present — the model_validator should have caught this already, so
        reaching here means a programming bug upstream.
        """
        if self.action == StrategyAction.BUY:
            return PositionSide.LONG
        if self.action == StrategyAction.SELL:
            return PositionSide.SHORT
        if self.side is None:
            raise ValueError(
                f"action={self.action.value} has no side and no legacy alias."
            )
        return self.side

    def is_entry(self) -> bool:
        return self.action in (
            StrategyAction.ENTRY,
            StrategyAction.BUY,
            StrategyAction.SELL,
        )


__all__ = [
    "PositionSide",
    "StrategyAction",
    "StrategyWebhookPayload",
]
