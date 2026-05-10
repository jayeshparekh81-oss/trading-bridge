"""Individual pre-trade checks composed by :mod:`guard`.

Each function takes the minimum slice of the engine's output it needs
and returns a :class:`GuardCheckResult` with a fixed severity. Pure,
deterministic, no I/O. Returning ``None`` means "this check could not
run because its required input is absent" — the orchestrator decides
whether that absence is a defensive block (for blocking checks) or a
silent skip (for warning / info checks).

Severity conventions:
    * ``blocking`` — a single ``passed=False`` here flips
      :attr:`GuardDecision.allowed` to ``False``.
    * ``warning`` — surfaces a concern but allows the trade.
    * ``info``    — purely advisory, never blocks.

Naming convention: ``check_<dimension>``. The string returned in
:attr:`GuardCheckResult.check_name` matches the function name minus the
``check_`` prefix so audit logs and tests can pin behaviour against a
stable identifier independent of the function symbol.
"""

from __future__ import annotations

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.broker_guard.constants import (
    HIGH_DRAWDOWN_WARNING,
    LOW_TRADE_COUNT_WARNING,
    MIN_TRUST_SCORE_FOR_LIVE,
    MIN_TRUTH_SCORE_FOR_LIVE,
    RECOMMENDED_PAPER_SESSIONS,
)
from app.strategy_engine.broker_guard.models import GuardCheckResult
from app.strategy_engine.paper_trading.models import PaperReadinessReport
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth import TruthReport

# ─── Blocking checks ───────────────────────────────────────────────────


def check_stop_loss_present(strategy: StrategyJSON) -> GuardCheckResult:
    """Block when the strategy declares neither a stop loss nor a trailing stop.

    Live execution without a programmatic exit is the single most
    common cause of unbounded losses in retail algo trading, so this
    is the first gate.
    """
    has_stop = strategy.exit.stop_loss_percent is not None
    has_trailing = strategy.exit.trailing_stop_percent is not None
    passed = has_stop or has_trailing
    if passed:
        message = "Strategy has a stop loss or trailing stop configured."
    else:
        message = "Strategy has no stop loss. Live trading blocked."
    return GuardCheckResult(
        check_name="stop_loss_present",
        passed=passed,
        severity="blocking",
        message=message,
    )


def check_broker_connected(broker_connected: bool) -> GuardCheckResult:
    """Block when the broker session is not connected.

    The flag is supplied by the caller — the guard intentionally does
    *not* import any broker adapter. Wiring the real connection state
    into this flag is the order-placement phase's responsibility.
    """
    return GuardCheckResult(
        check_name="broker_connected",
        passed=broker_connected,
        severity="blocking",
        message=(
            "Broker session is connected."
            if broker_connected
            else "Broker not connected. Connect Fyers/Dhan first."
        ),
    )


def check_kill_switch_inactive(auto_kill_switch_active: bool) -> GuardCheckResult:
    """Block when the Auto Kill Switch is currently active.

    The kill-switch state is supplied by the caller; the guard does
    not import any kill-switch module. When the switch is active, no
    new entries should be placed regardless of strategy quality.
    """
    return GuardCheckResult(
        check_name="kill_switch_inactive",
        passed=not auto_kill_switch_active,
        severity="blocking",
        message=(
            "Auto Kill Switch is inactive."
            if not auto_kill_switch_active
            else "Auto Kill Switch is active. Resolve before trading."
        ),
    )


def check_truth_score(truth: TruthReport | None) -> GuardCheckResult:
    """Block when the Phase 6 truth score is below
    :data:`MIN_TRUTH_SCORE_FOR_LIVE`, or when no truth report exists.

    Missing truth means we cannot verify the backtest is reliable, so
    the defensive default is to block — opt out by supplying a valid
    :class:`TruthReport`.
    """
    if truth is None:
        return GuardCheckResult(
            check_name="truth_score",
            passed=False,
            severity="blocking",
            message=(
                "Truth Score not available. Run backtest with reliability "
                "enabled before trading live."
            ),
        )
    passed = truth.truth_score >= MIN_TRUTH_SCORE_FOR_LIVE
    if passed:
        message = (
            f"Truth Score {truth.truth_score} meets the live threshold "
            f"({MIN_TRUTH_SCORE_FOR_LIVE})."
        )
    else:
        message = (
            f"Truth Score {truth.truth_score} too low (<"
            f"{MIN_TRUTH_SCORE_FOR_LIVE}). Strategy not reliable for live."
        )
    return GuardCheckResult(
        check_name="truth_score",
        passed=passed,
        severity="blocking",
        message=message,
    )


def check_trust_score(reliability: ReliabilityReport | None) -> GuardCheckResult:
    """Block when the Phase 4 trust score is below
    :data:`MIN_TRUST_SCORE_FOR_LIVE`, or when no reliability report exists.
    """
    if reliability is None:
        return GuardCheckResult(
            check_name="trust_score",
            passed=False,
            severity="blocking",
            message=(
                "Trust Score not available. Reliability checks have not been run for this strategy."
            ),
        )
    score = reliability.trust_score.score
    passed = score >= MIN_TRUST_SCORE_FOR_LIVE
    if passed:
        message = f"Trust Score {score} meets the live threshold ({MIN_TRUST_SCORE_FOR_LIVE})."
    else:
        message = (
            f"Trust Score {score} too low (<{MIN_TRUST_SCORE_FOR_LIVE}). Reliability checks failed."
        )
    return GuardCheckResult(
        check_name="trust_score",
        passed=passed,
        severity="blocking",
        message=message,
    )


def check_paper_readiness(
    paper_readiness: PaperReadinessReport | None,
    user_override_paper: bool,
) -> GuardCheckResult:
    """Block when paper trading is not complete and the user has not
    explicitly overridden the gate.

    Override semantics: setting ``user_override_paper=True`` lets the
    decision ``allowed`` move through this check, but the override
    itself is surfaced as a separate warning by
    :func:`check_paper_override_used` so the bypass is auditable.
    """
    if user_override_paper:
        return GuardCheckResult(
            check_name="paper_readiness",
            passed=True,
            severity="blocking",
            message=("User override engaged — paper-readiness gate bypassed."),
        )
    if paper_readiness is None:
        return GuardCheckResult(
            check_name="paper_readiness",
            passed=False,
            severity="blocking",
            message=("Paper trading not complete. Reasons: paper-readiness report not generated."),
        )
    if paper_readiness.live_ready:
        return GuardCheckResult(
            check_name="paper_readiness",
            passed=True,
            severity="blocking",
            message="Paper trading readiness gates cleared.",
        )
    reasons = (
        ", ".join(paper_readiness.blocked_reasons)
        if paper_readiness.blocked_reasons
        else "no specific reason supplied"
    )
    return GuardCheckResult(
        check_name="paper_readiness",
        passed=False,
        severity="blocking",
        message=f"Paper trading not complete. Reasons: {reasons}",
    )


# ─── Warning checks ────────────────────────────────────────────────────


def check_truth_risk_level(truth: TruthReport | None) -> GuardCheckResult | None:
    """Warn when the truth engine flagged ``high`` or ``extreme`` risk.

    Returns ``None`` when ``truth`` is missing — a missing input does
    not justify a synthetic warning, and the absence is already
    surfaced as a blocking failure by :func:`check_truth_score`.
    """
    if truth is None:
        return None
    elevated = truth.risk_level in ("high", "extreme")
    if not elevated:
        return GuardCheckResult(
            check_name="truth_risk_level",
            passed=True,
            severity="warning",
            message=f"Truth risk level is {truth.risk_level}.",
        )
    return GuardCheckResult(
        check_name="truth_risk_level",
        passed=False,
        severity="warning",
        message=(
            f"High risk level ({truth.risk_level}) — reduce position size "
            "and watch the strategy closely on the first sessions."
        ),
    )


def check_low_trade_count(backtest: BacktestResult | None) -> GuardCheckResult | None:
    """Warn when the backtest's sample size is below
    :data:`LOW_TRADE_COUNT_WARNING`. Skipped when no backtest was run.
    """
    if backtest is None:
        return None
    passed = backtest.total_trades >= LOW_TRADE_COUNT_WARNING
    if passed:
        return GuardCheckResult(
            check_name="low_trade_count",
            passed=True,
            severity="warning",
            message=(f"Backtest covered {backtest.total_trades} trades — adequate sample size."),
        )
    return GuardCheckResult(
        check_name="low_trade_count",
        passed=False,
        severity="warning",
        message=(
            f"Low backtest sample size ({backtest.total_trades} trades < "
            f"{LOW_TRADE_COUNT_WARNING}); statistics may be noisy."
        ),
    )


def check_high_drawdown(backtest: BacktestResult | None) -> GuardCheckResult | None:
    """Warn when historical drawdown exceeded
    :data:`HIGH_DRAWDOWN_WARNING` (fraction). Skipped when no backtest exists.

    The ``BacktestResult.max_drawdown`` field stores a fraction (e.g.
    ``0.25`` ≡ "25 % peak-to-trough"); the constant is in the same
    units, so the comparison is direct.
    """
    if backtest is None:
        return None
    passed = backtest.max_drawdown <= HIGH_DRAWDOWN_WARNING
    if passed:
        return GuardCheckResult(
            check_name="high_drawdown",
            passed=True,
            severity="warning",
            message=(
                f"Max drawdown {backtest.max_drawdown * 100:.1f} % is within "
                f"the {HIGH_DRAWDOWN_WARNING * 100:.0f} % warning threshold."
            ),
        )
    return GuardCheckResult(
        check_name="high_drawdown",
        passed=False,
        severity="warning",
        message=(
            f"High historical drawdown {backtest.max_drawdown * 100:.1f} % "
            f"(>{HIGH_DRAWDOWN_WARNING * 100:.0f} %); position sizing should "
            "compensate."
        ),
    )


def check_paper_override_used(
    paper_readiness: PaperReadinessReport | None,
    user_override_paper: bool,
) -> GuardCheckResult | None:
    """Warn when the user override actually bypassed an unmet paper gate.

    Skipped when the override is not engaged or when paper readiness is
    actually satisfied — emitting a warning in those cases would be
    noise. We *do* warn when ``paper_readiness`` is missing entirely
    while override is engaged; that is also a meaningful bypass.
    """
    if not user_override_paper:
        return None
    if paper_readiness is not None and paper_readiness.live_ready:
        return None
    return GuardCheckResult(
        check_name="paper_override_used",
        passed=False,
        severity="warning",
        message=(
            "Paper-readiness gate bypassed via user override. The strategy "
            "did not clear the standard paper-trading verification."
        ),
    )


# ─── Info checks ───────────────────────────────────────────────────────


def check_paper_sessions_recommended(
    paper_readiness: PaperReadinessReport | None,
) -> GuardCheckResult | None:
    """Info-level nudge to keep paper-trading longer than the engine's
    minimum, up to :data:`RECOMMENDED_PAPER_SESSIONS`. Skipped when no
    paper-readiness report is available.
    """
    if paper_readiness is None:
        return None
    enough = paper_readiness.completed_sessions >= RECOMMENDED_PAPER_SESSIONS
    if enough:
        return GuardCheckResult(
            check_name="paper_sessions_recommended",
            passed=True,
            severity="info",
            message=(
                f"{paper_readiness.completed_sessions} paper sessions completed "
                f"(target {RECOMMENDED_PAPER_SESSIONS})."
            ),
        )
    return GuardCheckResult(
        check_name="paper_sessions_recommended",
        passed=False,
        severity="info",
        message=(
            f"More paper sessions recommended: {paper_readiness.completed_sessions} "
            f"completed, target {RECOMMENDED_PAPER_SESSIONS}."
        ),
    )


__all__ = [
    "check_broker_connected",
    "check_high_drawdown",
    "check_kill_switch_inactive",
    "check_low_trade_count",
    "check_paper_override_used",
    "check_paper_readiness",
    "check_paper_sessions_recommended",
    "check_stop_loss_present",
    "check_trust_score",
    "check_truth_risk_level",
    "check_truth_score",
]
