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
    """Read shape — used by every GET / mutation response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    strategy_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class StrategyListResponse(BaseModel):
    """List wrapper — keeps room for paging metadata in later phases."""

    model_config = ConfigDict(extra="forbid")

    strategies: list[StrategyResponse] = Field(default_factory=list)
    count: int = Field(..., ge=0)


__all__ = [
    "StrategyCreateRequest",
    "StrategyListResponse",
    "StrategyResponse",
]
