"""Boundary models for indicator versioning.

Both models are frozen + ``extra="forbid"`` so a manifest, once
captured, flows through the rest of the engine (audit, future DB
persister, frontend) as an immutable record. Equality is structural —
two manifests with the same fields compare equal regardless of when
they were built.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndicatorVersionRecord(BaseModel):
    """One version of one indicator.

    The version registry stores a list of these per indicator id, with
    the most recent version at index 0. ``formula_version`` is a
    coarser tag than ``version``: a non-breaking metadata edit can bump
    ``version`` without touching ``formula_version``, but a numerical
    change to the calculation must bump both.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator_id: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., min_length=1, max_length=32)
    formula_version: str = Field(..., min_length=1, max_length=16)
    changelog: str = Field(..., min_length=1, max_length=512)
    created_at: datetime
    deprecated: bool = False


class BacktestVersionManifest(BaseModel):
    """The version pin for one backtest run.

    A manifest captures *which* version of each indicator the backtest
    consumed at the moment it ran. Replaying the same strategy later,
    against the same engine + schema versions, with the same seeded
    candles, must produce the same result — that's the contract this
    record protects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backtest_id: UUID
    strategy_id: UUID
    indicators_used: dict[str, IndicatorVersionRecord] = Field(default_factory=dict)
    schema_version: str = Field(..., min_length=1, max_length=32)
    engine_version: str = Field(..., min_length=1, max_length=32)
    captured_at: datetime


__all__ = [
    "BacktestVersionManifest",
    "IndicatorVersionRecord",
]
