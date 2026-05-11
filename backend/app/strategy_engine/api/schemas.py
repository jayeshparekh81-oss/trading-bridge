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


class StrategyResponse(BaseModel):
    """Read shape — used by every GET / mutation response.

    ``current_version_number`` is populated by handlers that just wrote
    (POST/PUT/rollback) so the frontend gets the version number to
    pin the next backtest against without a follow-up call. List/get
    endpoints leave it ``None`` — clients can hit
    ``GET /api/strategies/{id}/versions`` for full history.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    strategy_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    current_version_number: int | None = None


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
]
