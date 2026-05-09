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
from typing import Any

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


__all__ = [
    "SafetyChainResult",
    "SafetyCheckResult",
]
