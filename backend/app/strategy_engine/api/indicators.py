"""Indicator registry read-only endpoint — Phase 5B Part 2 backend.

The frontend Indicator Library calls ``GET /api/strategies/indicators``
to render the catalogue: 100+ entries with metadata (id, name,
category, description, inputs, outputs, difficulty, status, AI
explanation, tags). Coming-soon stubs ride along so the UI can grey
them out without a separate request.

This endpoint is **read-only** and **does not** invoke any
calculation function — it surfaces metadata only. Phase 1's
:func:`get_calculation_function` already raises on coming-soon ids;
this endpoint stays even further away from execution by never
resolving the function at all.

Mounted under the ``/api/strategies`` prefix alongside the CRUD
router. Registration order in :mod:`app.main` puts this router
*before* the CRUD router so the literal ``/indicators`` path wins
over the CRUD router's ``/{strategy_id}`` path-parameter route.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.strategy_engine.indicators.registry import INDICATOR_REGISTRY
from app.strategy_engine.schema.indicator import IndicatorMetadata

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get("/indicators", response_model=list[IndicatorMetadata])
async def list_indicators(
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[IndicatorMetadata]:
    """Return every indicator in the registry — active and coming-soon.

    Order is the registry's insertion order so the UI can render in a
    stable sequence. The handler iterates ``INDICATOR_REGISTRY.values()``
    directly; no Phase 1 helper is mutated, no calculation is invoked.
    """
    return list(INDICATOR_REGISTRY.values())


__all__ = ["router"]
