"""AI-decision dataclass — returned by :mod:`app.services.ai_validator`.

Lightweight Pydantic model so the validator can be stubbed in tests
without pulling in the Anthropic SDK.
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
    """Result of a Claude validation pass over an inbound signal."""

    model_config = ConfigDict(frozen=True)

    decision: AIDecisionStatus
    reasoning: str = Field(..., max_length=2048)
    confidence: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))


__all__ = ["AIDecision", "AIDecisionStatus"]
