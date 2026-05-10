"""Boundary models for the Broker Execution Guard.

The guard's whole API surface is two frozen models: :class:`GuardCheckResult`
for an individual check's verdict, and :class:`GuardDecision` for the
overall pre-trade decision the orchestrator returns.

Both are frozen + ``extra="forbid"`` so the structure can't be mutated
between consumers (the upcoming order-placement wiring phase, the
frontend, future audit logging).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["info", "warning", "blocking"]


class GuardCheckResult(BaseModel):
    """One check's verdict.

    ``passed`` answers the literal check question — ``True`` means the
    strategy/state cleared this gate. A failed (``passed=False``)
    blocking check makes the overall decision ``allowed=False``;
    failed warning/info checks decorate the decision but do not block.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_name: str = Field(..., min_length=1, max_length=64)
    passed: bool
    severity: Severity
    message: str = Field(..., min_length=1, max_length=512)


class GuardDecision(BaseModel):
    """Pre-trade verdict returned by :func:`evaluate_broker_guard`.

    ``allowed`` is the single boolean the order-placement wiring (a
    future phase) should consult. The four lists below mirror the
    severity bands so callers can render warnings/info without re-
    scanning the check log.

    ``checks_run`` lists every check that *executed* (skipped checks —
    typically warning/info checks whose required input was missing —
    are *not* in this list). It exists so an audit trail can show
    "we evaluated these N gates" without inventing synthetic passes
    for missing inputs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    reason: str = Field(..., min_length=1, max_length=512)
    blocking_failures: tuple[GuardCheckResult, ...] = Field(default_factory=tuple)
    warnings: tuple[GuardCheckResult, ...] = Field(default_factory=tuple)
    info: tuple[GuardCheckResult, ...] = Field(default_factory=tuple)
    checks_run: tuple[str, ...] = Field(default_factory=tuple)


__all__ = [
    "GuardCheckResult",
    "GuardDecision",
    "Severity",
]
