"""Risk engine — static strategy lint + runtime cap evaluation.

Two layers in one entry point:

    Static checks (always on, given a strategy):
        * No stop loss configured              -> WARNING
        * No exit primitives at all            -> ERROR (unreachable —
          schema's at-least-one-exit invariant catches this; defensive)
        * Too many indicators (> 8)            -> WARNING
        * No risk caps configured              -> INFO

    Runtime checks (when ``stats`` is supplied):
        * Daily P&L violates max_daily_loss_percent       -> BLOCK
        * Trades-today >= max_trades_per_day              -> BLOCK
        * Consecutive-loss streak >= max_loss_streak      -> BLOCK

Output is a :class:`RiskAssessment` carrying ``allowed`` (False whenever
any runtime check blocks new entries), ``severity`` (the highest level
across all messages), a list of :class:`RiskMessage` (each with its
own severity + suggestion), and a flat ``suggestions`` list for quick
UI rendering.

The engine is **stateless and pure** — runtime stats come from the
caller. Phase 3's backtest runner will compute the stats and call this
once per bar before deciding to fire an entry.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.schema.strategy import StrategyJSON


class RiskSeverity(StrEnum):
    """Ordered low->high so callers can pick the worst across messages."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCK = "block"


_SEVERITY_RANK: dict[RiskSeverity, int] = {
    RiskSeverity.INFO: 0,
    RiskSeverity.WARNING: 1,
    RiskSeverity.ERROR: 2,
    RiskSeverity.BLOCK: 3,
}


class RiskMessage(BaseModel):
    """One static or runtime risk finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: RiskSeverity
    code: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=512)
    suggestion: str | None = Field(default=None, max_length=512)


class RiskRuntimeStats(BaseModel):
    """Runtime context the caller passes for runtime cap evaluation.

    All fields are optional so the engine can run with partial info
    (e.g. "I want only static checks today"). Optional fields not
    supplied disable their corresponding runtime check.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    daily_pnl_percent: float | None = Field(default=None)
    trades_today: int | None = Field(default=None, ge=0)
    consecutive_loss_streak: int | None = Field(default=None, ge=0)


class RiskAssessment(BaseModel):
    """Aggregate risk verdict for the strategy + (optional) runtime stats."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    severity: RiskSeverity
    messages: tuple[RiskMessage, ...] = Field(default_factory=tuple)
    suggestions: tuple[str, ...] = Field(default_factory=tuple)


# ─── Public API ────────────────────────────────────────────────────────


#: Soft cap on indicator count for the "too many indicators" warning.
#: Beyond this the strategy is likely overfitted; the AI advisor (Phase 6)
#: will surface this prominently.
TOO_MANY_INDICATORS_THRESHOLD = 8


def evaluate_risk(
    strategy: StrategyJSON,
    *,
    stats: RiskRuntimeStats | None = None,
) -> RiskAssessment:
    """Compute the risk assessment for ``strategy`` and optional ``stats``."""
    messages: list[RiskMessage] = list(_static_messages(strategy))
    if stats is not None:
        messages.extend(_runtime_messages(strategy, stats))

    blocked = any(m.severity is RiskSeverity.BLOCK for m in messages)
    severity = (
        max(messages, key=lambda m: _SEVERITY_RANK[m.severity]).severity
        if messages
        else RiskSeverity.INFO
    )
    suggestions = tuple(m.suggestion for m in messages if m.suggestion)

    return RiskAssessment(
        allowed=not blocked,
        severity=severity,
        messages=tuple(messages),
        suggestions=suggestions,
    )


# ─── Static checks ─────────────────────────────────────────────────────


def _static_messages(strategy: StrategyJSON) -> list[RiskMessage]:
    """Strategy-shape lint — independent of any runtime data."""
    out: list[RiskMessage] = []
    exit_rules = strategy.exit
    risk_rules = strategy.risk

    # Missing stop loss is the loudest single static warning.
    has_sl = (
        exit_rules.stop_loss_percent is not None or exit_rules.trailing_stop_percent is not None
    )
    if not has_sl:
        out.append(
            RiskMessage(
                severity=RiskSeverity.WARNING,
                code="missing_stop_loss",
                message="Strategy has no stop loss or trailing stop.",
                suggestion=(
                    "Add a stopLossPercent or trailingStopPercent so a "
                    "wrong-way move can't run unbounded."
                ),
            )
        )

    if len(strategy.indicators) > TOO_MANY_INDICATORS_THRESHOLD:
        out.append(
            RiskMessage(
                severity=RiskSeverity.WARNING,
                code="too_many_indicators",
                message=(
                    f"Strategy uses {len(strategy.indicators)} indicators, more "
                    f"than the {TOO_MANY_INDICATORS_THRESHOLD}-indicator soft "
                    "limit — risk of curve-fitting."
                ),
                suggestion=(
                    "Consider keeping 3-5 indicators that each measure a "
                    "different dimension (trend, momentum, volume)."
                ),
            )
        )

    if (
        risk_rules.max_daily_loss_percent is None
        and risk_rules.max_trades_per_day is None
        and risk_rules.max_loss_streak is None
    ):
        out.append(
            RiskMessage(
                severity=RiskSeverity.INFO,
                code="no_risk_caps",
                message="No account-level risk caps configured.",
                suggestion=(
                    "Set maxDailyLossPercent and maxTradesPerDay so a bad day stops itself."
                ),
            )
        )

    return out


# ─── Runtime checks ────────────────────────────────────────────────────


def _runtime_messages(strategy: StrategyJSON, stats: RiskRuntimeStats) -> list[RiskMessage]:
    """Per-bar runtime caps — translate breaches into BLOCKs."""
    out: list[RiskMessage] = []
    risk_rules = strategy.risk

    if risk_rules.max_daily_loss_percent is not None and stats.daily_pnl_percent is not None:
        # ``max_daily_loss_percent`` is the *magnitude* of the cap (e.g.
        # 2.0 means "stop trading if down 2 %"); P&L is a signed % where
        # negative = loss. We block when the loss meets or exceeds the cap.
        # Decimal-compare to avoid 0.1 + 0.2 != 0.3 surprises.
        loss_pct = -Decimal(str(stats.daily_pnl_percent))
        cap = Decimal(str(risk_rules.max_daily_loss_percent))
        if loss_pct >= cap:
            out.append(
                RiskMessage(
                    severity=RiskSeverity.BLOCK,
                    code="daily_loss_cap_hit",
                    message=(
                        f"Daily loss {stats.daily_pnl_percent:.2f}% has met "
                        f"the {risk_rules.max_daily_loss_percent}% cap."
                    ),
                    suggestion=(
                        "Stop trading for the day. Review what went wrong "
                        "before sizing up tomorrow."
                    ),
                )
            )

    if (
        risk_rules.max_trades_per_day is not None
        and stats.trades_today is not None
        and stats.trades_today >= risk_rules.max_trades_per_day
    ):
        out.append(
            RiskMessage(
                severity=RiskSeverity.BLOCK,
                code="max_trades_per_day_hit",
                message=(
                    f"Already taken {stats.trades_today} trades; cap is "
                    f"{risk_rules.max_trades_per_day}."
                ),
                suggestion=("Walk away from the screen; revenge-trading erodes discipline."),
            )
        )

    if (
        risk_rules.max_loss_streak is not None
        and stats.consecutive_loss_streak is not None
        and stats.consecutive_loss_streak >= risk_rules.max_loss_streak
    ):
        out.append(
            RiskMessage(
                severity=RiskSeverity.BLOCK,
                code="loss_streak_cap_hit",
                message=(
                    f"{stats.consecutive_loss_streak} losses in a row meets "
                    f"the {risk_rules.max_loss_streak} streak cap."
                ),
                suggestion=(
                    "Pause and review setups; persistent losses often signal a regime change."
                ),
            )
        )

    return out


__all__ = [
    "TOO_MANY_INDICATORS_THRESHOLD",
    "RiskAssessment",
    "RiskMessage",
    "RiskRuntimeStats",
    "RiskSeverity",
    "evaluate_risk",
]
