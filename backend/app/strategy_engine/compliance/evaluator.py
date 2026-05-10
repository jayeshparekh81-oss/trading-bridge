"""Per-strategy compliance evaluator.

Maps the indicator registry's :class:`IndicatorStatus` lifecycle
states to a user-facing risk taxonomy + a 0-100 compliance score.

Risk taxonomy (kept separate from the registry's lifecycle so we
can evolve user-facing messaging without touching the source of
truth):

    * ``safe``     — registry status ``ACTIVE``. Usable in live
                     execution paths.
    * ``warning``  — registry status ``COMING_SOON`` or
                     ``EXPERIMENTAL``. Usable in backtest / paper;
                     blocked from live by the existing SafetyChain.
    * ``blocked``  — referenced indicator id is **not in the
                     registry at all**. This is the catch-all for
                     stale strategies referencing indicators that
                     have been removed, typo'd ids, or — rarely —
                     custom test fixtures. Blocked indicators
                     trigger the largest score deduction because
                     the strategy can't actually execute the
                     condition.

Scoring (start at 100, clamp at 0):

    * ``COMING_SOON`` instance:    -10
    * ``EXPERIMENTAL`` instance:   -25
    * Unknown / blocked instance:  -50

The deductions are per-instance, not per-distinct-id, so a
strategy that uses two different EXPERIMENTAL indicators loses
50 points (2 x 25). This rewards strategies that consolidate on a
small surface of well-understood indicators.

Helpers in this module are pure functions — no DB, no IO. The
:mod:`app.strategy_engine.api.compliance` layer feeds them the
strategy JSON it already has loaded.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY,
    get_indicator_by_id,
)
from app.strategy_engine.schema.indicator import IndicatorStatus

RiskLevel = Literal["safe", "warning", "blocked"]

#: Risk-level string literals. Kept as bare strings (not an enum)
#: because they cross the API boundary and Pydantic Literals are
#: friendlier for OpenAPI consumers than custom enums. Typed as
#: ``RiskLevel`` so mypy accepts them as constructor args.
SAFE_RISK: RiskLevel = "safe"
WARNING_RISK: RiskLevel = "warning"
BLOCKED_RISK: RiskLevel = "blocked"

#: Per-instance score deductions. Tuned so a single COMING_SOON
#: indicator drops the score to 90 (still "green" in the UI), an
#: EXPERIMENTAL drops to 75 (yellow), and an unknown id drops to
#: 50 (red).
_DEDUCTION_BY_STATUS: dict[IndicatorStatus, int] = {
    IndicatorStatus.COMING_SOON: 10,
    IndicatorStatus.EXPERIMENTAL: 25,
}
_DEDUCTION_BLOCKED = 50


class IndicatorComplianceInfo(BaseModel):
    """Per-indicator compliance metadata for the user-facing report."""

    model_config = ConfigDict(from_attributes=False)

    indicator_id: str = Field(
        ...,
        description=(
            "Registry id (e.g. ``ema``) — NOT the strategy-side "
            "instance handle (e.g. ``ema_20``)."
        ),
    )
    instance_id: str = Field(
        ...,
        description="The strategy-side instance handle.",
    )
    name: str
    status: str = Field(
        ..., description="Registry lifecycle status (or ``unknown``)."
    )
    risk_level: RiskLevel
    user_facing_message_hinglish: str
    can_use_live: bool = Field(
        ..., description="Permitted in live trading paths."
    )
    can_use_paper: bool = Field(
        ..., description="Permitted in paper trading paths."
    )
    can_use_backtest: bool = Field(
        ..., description="Permitted in backtest paths."
    )


class StrategyComplianceReport(BaseModel):
    """Full compliance report for one strategy."""

    model_config = ConfigDict(from_attributes=False)

    strategy_id: uuid.UUID
    strategy_name: str
    compliance_score: int = Field(..., ge=0, le=100)
    indicators_used: list[IndicatorComplianceInfo]
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class StrategyComplianceSummary(BaseModel):
    """Compact per-strategy summary for the list view (no per-indicator detail).

    Used by ``GET /api/compliance/strategies/me`` so the list page
    can render N rows without the wire payload ballooning per
    strategy that uses 5+ indicators.
    """

    model_config = ConfigDict(from_attributes=False)

    strategy_id: uuid.UUID
    strategy_name: str
    compliance_score: int = Field(..., ge=0, le=100)
    indicator_count: int
    blocking_issue_count: int
    warning_count: int


# ─── Pure helpers ─────────────────────────────────────────────────────


def _hinglish_message_for(
    name: str, status: IndicatorStatus | None
) -> str:
    """Hinglish line shown to the user in the per-indicator chip."""
    if status is IndicatorStatus.ACTIVE:
        return f"{name} active hai — live trading mein use kar sakte ho."
    if status is IndicatorStatus.COMING_SOON:
        return (
            f"{name} abhi coming_soon hai — backtest aur paper mein chalega, "
            "live trading SafetyChain block karega."
        )
    if status is IndicatorStatus.EXPERIMENTAL:
        return (
            f"{name} experimental hai — sirf expert mode mein use karo, "
            "live trading abhi recommended nahi hai."
        )
    return (
        f"{name} registry mein nahi mila — ya purana naam hai ya typo. "
        "Strategy edit karke valid indicator pick karo."
    )


def evaluate_indicator(
    *, indicator_id: str, instance_id: str
) -> IndicatorComplianceInfo:
    """Look up ``indicator_id`` in the registry and compute its
    compliance info. ``instance_id`` is the strategy-side handle so
    the report can point the user at the exact instance to fix
    (a strategy may use the same indicator twice with different
    params)."""
    meta = get_indicator_by_id(indicator_id)
    if meta is None:
        return IndicatorComplianceInfo(
            indicator_id=indicator_id,
            instance_id=instance_id,
            name=indicator_id,
            status="unknown",
            risk_level=BLOCKED_RISK,
            user_facing_message_hinglish=_hinglish_message_for(
                indicator_id, None
            ),
            can_use_live=False,
            can_use_paper=False,
            can_use_backtest=False,
        )

    if meta.status is IndicatorStatus.ACTIVE:
        risk: RiskLevel = SAFE_RISK
        live = True
        paper = True
    elif meta.status is IndicatorStatus.COMING_SOON:
        risk = WARNING_RISK
        live = False
        paper = True
    else:  # EXPERIMENTAL
        risk = WARNING_RISK
        live = False
        paper = True

    return IndicatorComplianceInfo(
        indicator_id=indicator_id,
        instance_id=instance_id,
        name=meta.name,
        status=meta.status.value,
        risk_level=risk,
        user_facing_message_hinglish=_hinglish_message_for(
            meta.name, meta.status
        ),
        can_use_live=live,
        can_use_paper=paper,
        # Backtest accepts everything the registry knows about,
        # active or not — the engine hot-paths gate live, not
        # backtest.
        can_use_backtest=True,
    )


def _compute_score(infos: Sequence[IndicatorComplianceInfo]) -> int:
    """Apply the deduction table and clamp to [0, 100]."""
    total = 100
    for info in infos:
        if info.risk_level == BLOCKED_RISK:
            total -= _DEDUCTION_BLOCKED
        elif info.status == IndicatorStatus.COMING_SOON.value:
            total -= _DEDUCTION_BY_STATUS[IndicatorStatus.COMING_SOON]
        elif info.status == IndicatorStatus.EXPERIMENTAL.value:
            total -= _DEDUCTION_BY_STATUS[IndicatorStatus.EXPERIMENTAL]
    return max(total, 0)


def _extract_indicator_pairs(
    strategy_json: dict[str, Any],
) -> list[tuple[str, str]]:
    """Pull ``(registry_type, instance_id)`` tuples from the JSON.

    Defensive: malformed entries (missing ``type``, non-string
    values) are silently skipped rather than raising — the
    compliance dashboard should never fail to render because of a
    weird strategy row. The strategy editor's own validation
    surfaces structural issues elsewhere.
    """
    out: list[tuple[str, str]] = []
    raw = strategy_json.get("indicators")
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        registry_type = entry.get("type")
        instance_id = entry.get("id") or registry_type
        if not isinstance(registry_type, str) or not isinstance(
            instance_id, str
        ):
            continue
        out.append((registry_type, instance_id))
    return out


def evaluate_strategy_compliance(
    *,
    strategy_id: uuid.UUID,
    strategy_name: str,
    strategy_json: dict[str, Any],
) -> StrategyComplianceReport:
    """Build a full compliance report for one strategy.

    Caller already has the strategy row loaded — we don't hit the
    DB here so this is cheap to call in tight loops (admin
    aggregation, list views).
    """
    pairs = _extract_indicator_pairs(strategy_json)
    infos = [
        evaluate_indicator(indicator_id=t, instance_id=i) for t, i in pairs
    ]
    score = _compute_score(infos)

    blocking_issues: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    for info in infos:
        if info.risk_level == BLOCKED_RISK:
            blocking_issues.append(
                f"'{info.indicator_id}' registry mein nahi mila "
                f"(instance: {info.instance_id})."
            )
            recommendations.append(
                f"'{info.indicator_id}' ko valid registry indicator se "
                "replace karo (Strategies → edit → Indicators panel)."
            )
        elif info.status == IndicatorStatus.COMING_SOON.value:
            warnings.append(
                f"{info.name} (instance: {info.instance_id}) abhi "
                "coming_soon hai — live trading mein nahi chalega."
            )
        elif info.status == IndicatorStatus.EXPERIMENTAL.value:
            warnings.append(
                f"{info.name} (instance: {info.instance_id}) experimental "
                "hai — production mein use karne se pehle paper trading "
                "mein 7+ sessions zaroor karo."
            )

    return StrategyComplianceReport(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        compliance_score=score,
        indicators_used=infos,
        blocking_issues=blocking_issues,
        warnings=warnings,
        recommendations=recommendations,
    )


def summarise_strategy(
    report: StrategyComplianceReport,
) -> StrategyComplianceSummary:
    """Trim a full report down to the list-view summary shape."""
    return StrategyComplianceSummary(
        strategy_id=report.strategy_id,
        strategy_name=report.strategy_name,
        compliance_score=report.compliance_score,
        indicator_count=len(report.indicators_used),
        blocking_issue_count=len(report.blocking_issues),
        warning_count=len(report.warnings),
    )


def known_registry_ids() -> Iterable[str]:
    """Helper used by aggregate.py — stable iteration order."""
    return sorted(INDICATOR_REGISTRY.keys())


__all__ = [
    "BLOCKED_RISK",
    "SAFE_RISK",
    "WARNING_RISK",
    "IndicatorComplianceInfo",
    "StrategyComplianceReport",
    "StrategyComplianceSummary",
    "evaluate_indicator",
    "evaluate_strategy_compliance",
    "known_registry_ids",
    "summarise_strategy",
]
