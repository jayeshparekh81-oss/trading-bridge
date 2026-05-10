"""Pine source-code importer endpoint — Phase 7 frontend wiring.

The actual conversion logic lives in
:mod:`app.strategy_engine.pine_import` (commit 72de0be); this module
is a thin FastAPI shell that:

    * accepts a JSON ``{ "pine_source": str }`` body,
    * delegates to :func:`convert_pine_to_strategy`,
    * returns the raw two-shape dict the converter produces.

The converter is purely textual / structural — no eval, no exec, no
network — so this endpoint is also side-effect-free and inherits that
guarantee. Authenticated like the rest of the strategy-engine surface
because Pine import is a premium-track feature; the auth dep can be
overridden in tests.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.user import User
from app.strategy_engine.audit.loggers import log_pine_import
from app.strategy_engine.pine_import import convert_pine_to_strategy

logger = get_logger("app.strategy_engine.api.pine_import")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


class PineImportRequest(BaseModel):
    """POST body for ``/api/strategies/pine-import``.

    ``min_length=1`` rejects empty / whitespace-only payloads at the
    Pydantic boundary so the converter never sees a degenerate input.
    """

    model_config = ConfigDict(extra="forbid")

    pine_source: str = Field(..., min_length=1, max_length=200_000)


@router.post("/pine-import")
async def import_pine_strategy(
    body: PineImportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, Any]:
    """Convert a Pine v5/v6 script to a Tradetri strategy.

    Returns the converter's native dict — one of two shapes:

        success → ``{"success": True, "strategy": {...},
                     "explanation": str, "license_status": str,
                     "notes": [...]}``

        failure / partial →
            ``{"success": False, "partial": bool, "converted": dict | None,
               "unsupported": [...], "message": str, "license_status": str}``

    The frontend reads ``success`` / ``partial`` to pick the right
    panel state and ``license_status`` to render the badge tone.
    """
    result = convert_pine_to_strategy(body.pine_source)
    success = bool(result.get("success"))
    license_status = str(result.get("license_status") or "unknown")
    logger.info(
        "strategy.pine_import.completed",
        user_id=str(current_user.id),
        success=success,
        partial=bool(result.get("partial", False)),
        license_status=license_status,
        unsupported_count=len(result.get("unsupported", [])),
    )
    log_pine_import(
        user_id=current_user.id,
        success=success,
        license_status=license_status,
        metadata={
            "partial": bool(result.get("partial", False)),
            "unsupported_count": len(result.get("unsupported", [])),
        },
    )
    return result


__all__ = ["PineImportRequest", "router"]
