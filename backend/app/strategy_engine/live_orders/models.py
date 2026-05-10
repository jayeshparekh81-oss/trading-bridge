"""Pydantic boundary models for live-orders SafetyChain.

The chain's whole external API is two frozen models —
:class:`SafetyCheckResult` for an individual check's verdict and
:class:`SafetyChainResult` for the aggregated outcome the live-orders
router consumes. Both are ``frozen=True`` and ``extra="forbid"`` so
nothing downstream (router, audit emitter, frontend) can mutate the
verdict between consumers.

Hinglish in ``reason_hinglish``: each check fills this field with the
user-facing message the frontend renders verbatim. ``details`` is a
free-form bag for engineer-facing debug context (raw counts, score
values, broker names) that the audit log captures but the UI does not
display.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SafetyCheckResult(BaseModel):
    """One check's verdict.

    ``passed`` answers the literal check question — ``True`` means the
    user/strategy/system cleared this gate. The chain's overall
    ``all_passed`` is the AND of every check's ``passed``; the first
    failing check is captured separately as ``blocking_check`` so the
    UI can surface a single primary reason.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_name: str = Field(..., min_length=1, max_length=64)
    passed: bool
    reason_hinglish: str = Field(..., min_length=1, max_length=512)
    details: dict[str, Any] = Field(default_factory=dict)


class SafetyChainResult(BaseModel):
    """Aggregate verdict returned by :func:`run_safety_chain`.

    ``all_passed`` is the single boolean the live-orders router
    consults. ``checks`` carries every check that *executed* — when
    fail-fast short-circuits the chain, later checks are absent from
    the list (not present-with-passed-true) so the audit trail shows
    the chain's actual execution shape.

    ``blocking_check`` is the first failing entry in ``checks``; when
    every check passed it is ``None``. Tracking it separately keeps
    the router from re-scanning the list to find the primary reason
    on every block.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    all_passed: bool
    checks: tuple[SafetyCheckResult, ...] = Field(default_factory=tuple)
    blocking_check: SafetyCheckResult | None = None
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    checked_at: datetime


#: Wire vocabulary kept narrow on purpose — only the two sides the
#: strategy executor handles today, and only the exchanges Phase 8B
#: actually targets (NSE/BSE equity + F&O). Add more when the broker
#: adapter is exercised against them.
OrderSideLiteral = Literal["BUY", "SELL"]
ExchangeLiteral = Literal["NSE", "BSE", "NFO", "BFO", "MCX", "CDS"]
ProductTypeLiteral = Literal["INTRADAY", "DELIVERY", "MARGIN"]


class LiveOrderRequest(BaseModel):
    """Validated body for ``POST /api/orders/live``.

    Defaults match :func:`strategy_executor._live_place_order`'s
    production path: ``exchange=NFO`` (NSE F&O — covers NIFTY /
    BANKNIFTY / BSE Ltd.), ``product_type=INTRADAY``. Override
    ``exchange="BFO"`` or ``product_type="MARGIN"`` for swing
    strategies.
    """

    model_config = ConfigDict(extra="forbid")

    strategy_id: uuid.UUID
    symbol: str = Field(..., min_length=1, max_length=64)
    side: OrderSideLiteral
    quantity: int = Field(..., gt=0)
    price: float | None = None
    """``None`` → market order. Non-null → limit order at the given price."""
    dry_run: bool = False
    """When true, runs SafetyChain + Broker Guard but skips the actual
    broker call. Returns ``order_id="DRY_RUN_SIMULATED"``."""
    exchange: ExchangeLiteral = "NFO"
    product_type: ProductTypeLiteral = "INTRADAY"


class LiveOrderResult(BaseModel):
    """Outcome of a :func:`place_live_order` call.

    ``success`` is the single boolean the frontend uses to choose
    between "order placed" and "rejected" UI. The richer surface
    (``safety_chain_result``, ``broker_guard_passed``,
    ``failure_reason_hinglish``) lets the modal render a precise
    explanation when ``success=False``.

    ``audit_log_id`` always references the PRE-order audit event —
    that event is emitted at the start of every call (success or
    block, dry-run or live). On a successful place we also emit a
    POST audit event, but the PRE id is what the result surfaces so
    the field type stays non-optional.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    order_id: str | None = None
    safety_chain_result: SafetyChainResult
    broker_guard_passed: bool
    broker_response: dict[str, Any] | None = None
    audit_log_id: uuid.UUID
    placed_at: datetime
    failure_reason_hinglish: str | None = None
    is_dry_run: bool


__all__ = [
    "ExchangeLiteral",
    "LiveOrderRequest",
    "LiveOrderResult",
    "OrderSideLiteral",
    "ProductTypeLiteral",
    "SafetyChainResult",
    "SafetyCheckResult",
]
