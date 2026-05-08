"""Phase 2 — read-only versioning endpoints + rollback.

Mounts under ``/api/strategies/{strategy_id}/versions`` and exposes:

    GET    /api/strategies/{id}/versions                  list history
    GET    /api/strategies/{id}/versions/compare          diff two versions
    GET    /api/strategies/{id}/versions/{n}              fetch one
    POST   /api/strategies/{id}/versions/{n}/rollback     create new version
                                                          mirroring v{n}

Every handler runs an ownership check first via
:func:`_load_owned_strategy_id` — the same 404-on-miss pattern the
strategies CRUD router uses, so cross-user probes can't enumerate
strategy ids that belong to other users.

Routing notes:

* ``compare`` is a literal segment registered before ``{n: int}`` so
  FastAPI matches it without trying to coerce ``"compare"`` into an
  ``int``. Even with the int coercion fallback this would 422, but
  declaring the literal first keeps the intent explicit.

* The router is mounted *before* the Phase 5 strategies CRUD router
  in :func:`app.main._register_routers`. The CRUD router's
  ``/{strategy_id}`` route would otherwise win for any path with one
  trailing segment, and while these paths have ≥2 segments and would
  not actually conflict, the conventional ordering keeps mental model
  simple: literal sub-paths > path-param sub-paths > the bare id.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.schemas import StrategyResponse
from app.strategy_engine.strategy_versioning import (
    StrategyVersion,
    StrategyVersionComparison,
    StrategyVersionNotFoundError,
    compare_versions,
    get_version,
    list_versions,
    rollback_to_version,
)

logger = get_logger("app.strategy_engine.api.strategy_versions")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get(
    "/{strategy_id}/versions/compare",
    response_model=StrategyVersionComparison,
)
async def compare_strategy_versions(
    strategy_id: uuid.UUID,
    from_version: Annotated[int, Query(ge=1, alias="from_version")],
    to_version: Annotated[int, Query(ge=1, alias="to_version")],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyVersionComparison:
    """Return a structured diff between two versions of a strategy.

    Both query parameters are required and must be ≥ 1. The diff is
    interpreted as ``from_version → to_version``; passing them in
    "wrong" order is allowed and just inverts the perspective in the
    Hinglish summary (added becomes removed, etc.).
    """
    await _load_owned_strategy_id(db, current_user, strategy_id)
    try:
        return compare_versions(strategy_id, from_version, to_version)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{strategy_id}/versions/{version_number}",
    response_model=StrategyVersion,
)
async def get_strategy_version(
    strategy_id: uuid.UUID,
    version_number: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyVersion:
    """Return one specific version of a strategy."""
    await _load_owned_strategy_id(db, current_user, strategy_id)
    try:
        return get_version(strategy_id, version_number)
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{strategy_id}/versions/{version_number}/rollback",
    response_model=StrategyResponse,
)
async def rollback_strategy_version(
    strategy_id: uuid.UUID,
    version_number: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyResponse:
    """Roll a strategy back to ``version_number``.

    Two side-effects:

    1. A *new* version is appended to history with the target's
       payload — history is never deleted, so the user can roll
       forward again by rolling back to the version they came from.
    2. The main ``strategies`` table is updated so subsequent reads
       see the rolled-back content immediately.
    """
    strategy = await _load_owned_strategy(db, current_user, strategy_id)
    try:
        new_version = rollback_to_version(
            strategy_id=strategy_id,
            target_version=version_number,
            user_id=current_user.id,
        )
    except StrategyVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    # Mirror the rolled-back payload onto the live row so the next GET
    # /api/strategies/{id} reflects the rollback without callers having
    # to know the versioning module exists.
    strategy.strategy_json = new_version.strategy_json
    rolled_name = new_version.strategy_json.get("name")
    if isinstance(rolled_name, str) and rolled_name:
        strategy.name = rolled_name
    await db.commit()
    await db.refresh(strategy)

    logger.info(
        "strategy.rolled_back",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
        target_version=version_number,
        new_version=new_version.version_number,
    )
    response = StrategyResponse.model_validate(strategy)
    return response.model_copy(
        update={"current_version_number": new_version.version_number}
    )


@router.get(
    "/{strategy_id}/versions",
    response_model=list[StrategyVersion],
)
async def list_strategy_versions(
    strategy_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[StrategyVersion]:
    """Return version history for a strategy, oldest first.

    ``limit`` caps the number of returned records (default 50, max
    500). The Phase 1 store keeps everything on disk but a
    high-velocity strategy could accumulate hundreds of versions; the
    cap keeps payloads bounded for the frontend without forcing a
    cursor-based API yet.
    """
    await _load_owned_strategy_id(db, current_user, strategy_id)
    history = list_versions(strategy_id)
    if limit < len(history):
        return history[-limit:]
    return history


async def _load_owned_strategy(
    db: AsyncSession, user: User, strategy_id: uuid.UUID
) -> Strategy:
    """Fetch the strategy ORM row scoped to ``user``; 404 covers both
    'not found' and 'not yours' so cross-user probes can't enumerate.
    Mirrors the helper in :mod:`strategies` deliberately — we don't
    import it cross-module to keep this router self-contained."""
    stmt = select(Strategy).where(
        Strategy.id == strategy_id, Strategy.user_id == user.id
    )
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )
    return strategy


async def _load_owned_strategy_id(
    db: AsyncSession, user: User, strategy_id: uuid.UUID
) -> None:
    """Lighter-weight variant — only confirms ownership; doesn't load
    the row. Used by read paths that don't need the ORM object."""
    await _load_owned_strategy(db, user, strategy_id)


__all__ = ["router"]
