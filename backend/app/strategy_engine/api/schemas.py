"""Pydantic boundary models for the Phase 5 strategies CRUD endpoints.

Two responsibilities:

    * **Inbound** — :class:`StrategyCreateRequest` wraps the canonical
      :class:`StrategyJSON` DSL so FastAPI validates the full document
      (indicators, conditions, risk caps, exec config) at the request
      boundary; handlers never see malformed input.

    * **Outbound** — :class:`StrategyResponse` is built from the
      :class:`Strategy` ORM row. ``strategy_json`` is returned as the
      stored dict (no re-validation): any future schema change must
      keep older rows readable, and re-validating on read would force
      a migration whenever the DSL evolves.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.schema.strategy import StrategyJSON


class StrategyCreateRequest(BaseModel):
    """POST/PUT body — a validated :class:`StrategyJSON` payload.

    The ``name`` column on the row is denormalised from
    ``strategy_json.name`` so list endpoints can sort/filter by name
    without parsing JSON; the handler keeps the two in lockstep.
    """

    model_config = ConfigDict(extra="forbid")

    strategy_json: StrategyJSON = Field(
        ...,
        description="Canonical user-built strategy DSL (StrategyJSON).",
    )


class StrategyTemplateOriginInfo(BaseModel):
    """Provenance + config snapshot for a cloned-from-template strategy.

    Populated by ``GET /api/strategies/{id}`` when a matching row exists
    in ``strategy_template_origin``. ``None`` for hand-built strategies.

    The frontend uses this to (a) suppress the pre-Phase-5 legacy
    warning on the detail page, (b) render the template's indicators
    and risk envelope for preview, (c) gate the "Available with
    Strategy Builder" CTA. Live trading + backtesting remain blocked
    by the existing safety guards in
    ``app.strategy_engine.live_orders.order_router`` and
    ``app.strategy_engine.api.backtest``; this field is a UI signal,
    not a runtime-evaluation hook.
    """

    model_config = ConfigDict(extra="forbid")

    template_slug: str = Field(..., description="Stable template slug")
    template_name: str = Field(..., description="Human template name")
    template_category: str = Field(
        ..., description="e.g. 'Trend Following'"
    )
    template_complexity: str = Field(
        ..., description="beginner|intermediate|expert"
    )
    cloned_at: datetime = Field(..., description="When the clone happened")
    config_json: dict[str, Any] = Field(
        ...,
        description=(
            "Snapshot of the template's config_json at the time of "
            "cloning. Includes indicators, entry/exit conditions, "
            "SL/TP, position_sizing, trading_hours."
        ),
    )


class StrategyResponse(BaseModel):
    """Read shape — used by every GET / mutation response.

    ``current_version_number`` is populated by handlers that just wrote
    (POST/PUT/rollback) so the frontend gets the version number to
    pin the next backtest against without a follow-up call. List/get
    endpoints leave it ``None`` — clients can hit
    ``GET /api/strategies/{id}/versions`` for full history.

    ``template_origin`` is populated by ``GET /api/strategies/{id}``
    when the strategy was materialised via the template-clone flow.
    ``None`` for hand-built strategies and on list responses
    (list-endpoint perf budget excludes the join).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    is_paper: bool
    strategy_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    current_version_number: int | None = None
    template_origin: StrategyTemplateOriginInfo | None = None


class StrategyListResponse(BaseModel):
    """List wrapper — keeps room for paging metadata in later phases."""

    model_config = ConfigDict(extra="forbid")

    strategies: list[StrategyResponse] = Field(default_factory=list)
    count: int = Field(..., ge=0)


class StrategyActiveUpdateRequest(BaseModel):
    """PATCH body for toggling the ``is_active`` flag (Archive flow).

    Kept separate from :class:`StrategyCreateRequest` so the Archive
    button can flip the flag without sending the full DSL back.
    """

    model_config = ConfigDict(extra="forbid")

    is_active: bool = Field(
        ..., description="True = active, False = archived."
    )


__all__ = [
    "StrategyActiveUpdateRequest",
    "StrategyCreateRequest",
    "StrategyListResponse",
    "StrategyResponse",
    "StrategyTemplateOriginInfo",
]
