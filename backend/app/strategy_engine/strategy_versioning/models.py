"""Boundary models for strategy versioning.

All three models are frozen + ``extra="forbid"`` so a version record,
once created, flows through the rest of the system (manager, future
DB persister, frontend) as an immutable snapshot. Equality is
structural — two records with the same fields compare equal.

The ``strategy_json`` payload is intentionally typed as a plain
``dict`` rather than the live :class:`StrategyJSON` model so the
version store keeps working unchanged when the schema evolves. The
manager re-validates against the current schema only on read paths
that need it (e.g. rollback).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChangeType = Literal["added", "modified", "removed"]


class StrategyVersion(BaseModel):
    """One immutable snapshot of a strategy at a point in time.

    The version store keeps an append-only history per ``strategy_id``.
    ``parent_version_id`` links to the previous version (``None`` for
    the very first version), so the history forms a single linear
    chain — branching is intentionally out of scope for Phase 1.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version_id: UUID
    strategy_id: UUID
    version_number: int = Field(..., ge=1)
    strategy_json: dict[str, Any]
    change_summary: str = Field(default="", max_length=2048)
    created_by: UUID
    created_at: datetime
    parent_version_id: UUID | None = None


class StrategyVersionDiff(BaseModel):
    """One field-level difference between two strategy snapshots.

    ``field_path`` uses bracket-and-dot notation:
    ``"indicators[2].period"`` means *index 2 of the* ``indicators``
    *list, then the* ``period`` *key*. ``old_value`` and ``new_value``
    are JSON-serialisable values copied straight from the source dicts;
    one of them is ``None`` when ``change_type`` is ``"added"`` or
    ``"removed"``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_path: str = Field(..., min_length=1)
    old_value: Any = None
    new_value: Any = None
    change_type: ChangeType


class StrategyVersionComparison(BaseModel):
    """Result of comparing two versions of a strategy.

    ``summary_hinglish`` is an auto-generated, beginner-friendly
    sentence (or two) describing the diff in mixed Hindi-English —
    consistent with the Strategy Coach voice elsewhere in the engine.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_version: int = Field(..., ge=1)
    to_version: int = Field(..., ge=1)
    diffs: list[StrategyVersionDiff] = Field(default_factory=list)
    summary_hinglish: str = Field(..., min_length=1)


__all__ = [
    "ChangeType",
    "StrategyVersion",
    "StrategyVersionComparison",
    "StrategyVersionDiff",
]
