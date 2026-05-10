"""Boundary models for the feature-flag store.

All models are frozen + ``extra="forbid"`` so a flag snapshot, once
returned by the manager, flows through the rest of the engine (UI,
guards, advisor) as an immutable read-only object. The manager never
mutates a previously-returned :class:`FeatureFlag`; every state change
produces a new instance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FlagSource = Literal["default", "runtime_override", "env_override"]


class FeatureFlag(BaseModel):
    """One flag's resolved state at a point in time.

    ``enabled`` is the resolved value the caller should act on;
    ``source`` records *which* layer won (env > runtime > default) so
    UIs can show "overridden by env" indicators and tests can pin
    behavior unambiguously.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    flag_name: str = Field(..., min_length=1, max_length=128)
    enabled: bool
    description: str = Field(..., min_length=1, max_length=512)
    default: bool
    source: FlagSource
    last_updated: datetime


class FlagsSnapshot(BaseModel):
    """Frozen snapshot of every locked flag at a point in time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    flags: dict[str, FeatureFlag] = Field(default_factory=dict)
    snapshot_at: datetime


__all__ = [
    "FeatureFlag",
    "FlagSource",
    "FlagsSnapshot",
]
