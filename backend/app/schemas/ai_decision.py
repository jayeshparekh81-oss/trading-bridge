"""AI-decision dataclass — returned by :mod:`app.services.ai_validator`.

Lightweight Pydantic model so the validator can be stubbed in tests
without pulling in any LLM SDK. Carries the validator's recommended
lot count so the executor can honour the AI's tier rather than always
firing strategy.entry_lots.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AIDecisionStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class AIDecision(BaseModel):
    """Result of a validator pass over an inbound signal.

    ``recommended_lots`` mirrors the AWS bot's tier system (faithful port):
        * LONG  ≥ 85% score  → 4 lots
        * LONG  ≥ 51% score  → 2 lots
        * SHORT ≥ 55% score  → 2 lots
        * else               → 0 (REJECTED)

    The value is post-VIX modulation and post-ENTRY_QTY_MAX cap, so the
    executor can take it verbatim (then cap by strategy.entry_lots).

    ``confidence`` is the bot's 0-100 score scaled to 0-1 for cross-system
    comparability. Use ``recommended_lots`` (not confidence) for sizing.
    """

    model_config = ConfigDict(frozen=True)

    decision: AIDecisionStatus
    reasoning: str = Field(..., max_length=2048)
    confidence: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    recommended_lots: int = Field(
        default=0,
        ge=0,
        le=10,
        description=(
            "Lot count the AI recommends (post-VIX, post-cap). 0 when "
            "REJECTED. Executor caps further by strategy.entry_lots."
        ),
    )


__all__ = ["AIDecision", "AIDecisionStatus"]
