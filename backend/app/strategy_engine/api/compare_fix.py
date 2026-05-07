"""Apply Fix and Compare endpoint — Phase 7 AI Doctor workflow.

When the AI Doctor produces an ``improved_strategy_draft`` on a
``Diagnosis``, the user can preview the fix before saving it. This
endpoint runs the same backtest + reliability + truth + coach +
trade-quality pipeline on both the original and the proposed draft
and returns a side-by-side comparison plus a Hinglish verdict.

The endpoint is **purely additive** — it reuses the existing pipeline
helpers from :mod:`backtest` (synthetic candles, ``BacktestInput``
plumbing, etc.) and the existing auth + ownership guard.
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.advisor import (
    TradeQualityReport,
    compute_trade_quality,
)
from app.strategy_engine.api.backtest import _load_owned_strategy, _synthetic_candles
from app.strategy_engine.backtest import (
    BacktestInput,
    BacktestResult,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.coach import (
    StrategyHealthCard,
    generate_health_card,
)
from app.strategy_engine.reliability.reliability_report import (
    ReliabilityReport,
    build_reliability_report,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth import (
    TruthReport,
    evaluate_strategy_truth,
)

logger = get_logger("app.strategy_engine.api.compare_fix")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


# ─── Boundary models ───────────────────────────────────────────────────


class CompareFixRequest(BaseModel):
    """POST body — the proposed improved-strategy draft.

    The draft is validated against :class:`StrategyJSON` here so a
    malformed body produces a 422 *before* the (slow) double-pipeline
    work begins.
    """

    model_config = ConfigDict(extra="forbid")

    improved_strategy_draft: dict[str, Any] = Field(..., min_length=1)
    candles: list[Candle] | None = None
    initial_capital: float = Field(default=100_000.0, gt=0)
    quantity: float = Field(default=1.0, gt=0)
    cost_settings: CostSettings | None = None


class StrategySnapshot(BaseModel):
    """One side of the comparison — the same set of reports the
    backtest endpoint emits, minus regime + deviation + version
    (those don't move between original and improved)."""

    model_config = ConfigDict(extra="forbid")

    backtest: BacktestResult
    reliability: ReliabilityReport | None = None
    health_card: StrategyHealthCard
    truth: TruthReport | None = None
    trade_quality: TradeQualityReport | None = None


class ComparisonDeltas(BaseModel):
    """Per-metric deltas (improved - original).

    Drawdown is tracked with its raw delta — *negative* drawdown_delta
    means the improved version reduced drawdown, which is the
    desirable direction. The verdict logic accounts for this.
    """

    model_config = ConfigDict(extra="forbid")

    pnl_delta: float
    win_rate_delta: float
    drawdown_delta: float
    profit_factor_delta: float
    truth_score_delta: float
    trust_score_delta: float
    trade_quality_delta: float
    verdict_hinglish: str = Field(..., min_length=1, max_length=512)


class CompareFixResponse(BaseModel):
    """Top-level response — original snapshot, improved snapshot, deltas."""

    model_config = ConfigDict(extra="forbid")

    original: StrategySnapshot
    improved: StrategySnapshot
    comparison: ComparisonDeltas


# ─── Endpoint ──────────────────────────────────────────────────────────


@router.post("/{strategy_id}/compare-fix", response_model=CompareFixResponse)
async def compare_fix(
    strategy_id: uuid.UUID,
    body: CompareFixRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CompareFixResponse:
    """Run the full pipeline on the original strategy *and* the
    proposed draft, then return a side-by-side comparison.

    422 when the strategy has no DSL (legacy) or the draft fails
    StrategyJSON validation. 404 when the strategy id is unknown or
    not owned by the caller.
    """
    strategy_row = await _load_owned_strategy(db, current_user, strategy_id)

    if not strategy_row.strategy_json:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Strategy has no DSL configured (legacy row). Recreate "
                "it via the Phase 5 builder to make it backtest-ready."
            ),
        )

    try:
        original_strategy = StrategyJSON.model_validate(strategy_row.strategy_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Stored strategy_json is invalid: {exc.errors()[0]['msg']}",
        ) from exc

    try:
        improved_strategy = StrategyJSON.model_validate(body.improved_strategy_draft)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"improved_strategy_draft is invalid: {exc.errors()[0]['msg']}",
        ) from exc

    candles = list(body.candles) if body.candles else _synthetic_candles()
    cost_settings = body.cost_settings or CostSettings()

    original_snapshot = _run_pipeline(
        strategy=original_strategy,
        candles=candles,
        initial_capital=body.initial_capital,
        quantity=body.quantity,
        cost_settings=cost_settings,
    )
    improved_snapshot = _run_pipeline(
        strategy=improved_strategy,
        candles=candles,
        initial_capital=body.initial_capital,
        quantity=body.quantity,
        cost_settings=cost_settings,
    )
    deltas = _build_deltas(original_snapshot, improved_snapshot)

    logger.info(
        "strategy.compare_fix.completed",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
        improved_pnl_delta=deltas.pnl_delta,
        improved_truth_delta=deltas.truth_score_delta,
    )

    return CompareFixResponse(
        original=original_snapshot,
        improved=improved_snapshot,
        comparison=deltas,
    )


# ─── Pipeline ──────────────────────────────────────────────────────────


def _run_pipeline(
    *,
    strategy: StrategyJSON,
    candles: list[Candle],
    initial_capital: float,
    quantity: float,
    cost_settings: CostSettings,
) -> StrategySnapshot:
    """Run the same Phase 3-7 pipeline the backtest endpoint runs.

    Smaller surface than the backtest endpoint: regime, deviation,
    audit + version manifest aren't part of the comparison, so we
    skip them. Reliability is always included because Truth Score
    consumes its sub-results.
    """
    backtest_result = run_backtest(
        BacktestInput(
            candles=candles,
            strategy=strategy,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
        )
    )
    reliability_report = build_reliability_report(
        strategy=strategy,
        candles=candles,
        initial_capital=initial_capital,
        quantity=quantity,
        cost_settings=cost_settings,
        include_oos=True,
        include_walk_forward=True,
        include_sensitivity=False,
    )
    truth_report: TruthReport | None = evaluate_strategy_truth(
        strategy=strategy,
        reliability=reliability_report,
        cost_settings=cost_settings,
        ambiguity_mode=AmbiguityMode.CONSERVATIVE,
    )
    health_card = generate_health_card(backtest_result, reliability=reliability_report)
    trade_quality_report = compute_trade_quality(backtest_result)

    return StrategySnapshot(
        backtest=backtest_result,
        reliability=reliability_report,
        health_card=health_card,
        truth=truth_report,
        trade_quality=trade_quality_report,
    )


# ─── Deltas + verdict ──────────────────────────────────────────────────


def _build_deltas(original: StrategySnapshot, improved: StrategySnapshot) -> ComparisonDeltas:
    """Compute the seven master deltas and assemble the Hinglish
    verdict from the count of metrics that moved in the desired
    direction."""
    o_bt = original.backtest
    i_bt = improved.backtest

    pnl_delta = i_bt.total_pnl - o_bt.total_pnl
    win_rate_delta = i_bt.win_rate - o_bt.win_rate
    drawdown_delta = i_bt.max_drawdown - o_bt.max_drawdown
    profit_factor_delta = _safe_finite_delta(i_bt.profit_factor, o_bt.profit_factor)

    truth_score_delta = _score_delta(
        original.truth.truth_score if original.truth else None,
        improved.truth.truth_score if improved.truth else None,
    )
    trust_score_delta = _score_delta(
        original.reliability.trust_score.score if original.reliability else None,
        improved.reliability.trust_score.score if improved.reliability else None,
    )
    trade_quality_delta = _score_delta(
        original.trade_quality.overall_score if original.trade_quality else None,
        improved.trade_quality.overall_score if improved.trade_quality else None,
    )

    # Count metrics where ``improved`` moved in the desirable direction.
    # Drawdown is the only metric where *lower* is better.
    improved_count = 0
    if pnl_delta > 0:
        improved_count += 1
    if win_rate_delta > 0:
        improved_count += 1
    if drawdown_delta < 0:
        improved_count += 1
    if profit_factor_delta > 0:
        improved_count += 1
    if truth_score_delta > 0:
        improved_count += 1
    if trust_score_delta > 0:
        improved_count += 1
    if trade_quality_delta > 0:
        improved_count += 1

    verdict = _verdict_for(improved_count)

    return ComparisonDeltas(
        pnl_delta=round(pnl_delta, 4),
        win_rate_delta=round(win_rate_delta, 6),
        drawdown_delta=round(drawdown_delta, 6),
        profit_factor_delta=round(profit_factor_delta, 4),
        truth_score_delta=round(truth_score_delta, 2),
        trust_score_delta=round(trust_score_delta, 2),
        trade_quality_delta=round(trade_quality_delta, 2),
        verdict_hinglish=verdict,
    )


def _score_delta(original: float | None, improved: float | None) -> float:
    """Return ``improved - original``; treat ``None`` as 0 so a missing
    snapshot is recorded as no movement (rather than blowing up)."""
    return (improved or 0.0) - (original or 0.0)


def _safe_finite_delta(improved: float, original: float) -> float:
    """Profit factor can be ``inf`` (no losses). Map both ``inf`` to a
    large finite value so the comparison stays JSON-serialisable and
    the delta retains its sign."""
    cap = 1e9
    a = improved if math.isfinite(improved) else cap
    b = original if math.isfinite(original) else cap
    return a - b


def _verdict_for(improved_count: int) -> str:
    """Map "metrics improved" count to the locked Hinglish verdict.

    7 metrics total. ``>= 5`` improved → big win;
    ``3-4`` → mixed; ``0-2`` → original was better.
    """
    if improved_count >= 5:
        return "Improved version better hai 🎉"
    if improved_count >= 3:
        return "Improved version mixed - kuch better, kuch worse"
    return "Original strategy better thi"


__all__ = [
    "CompareFixRequest",
    "CompareFixResponse",
    "ComparisonDeltas",
    "StrategySnapshot",
    "router",
]
