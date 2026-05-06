"""Per-strategy backtest endpoint — Phase 5B Part 3 backend.

Loads a user-owned strategy, runs the deterministic Phase 3 backtest
on it, layers Phase 4 reliability analysis on top, then asks the
Phase X (Strategy Coach) generator for a Hinglish health card. The
combined response is what the new ``/strategies/[id]/backtest`` page
renders.

This module is **purely additive** — every Phase 1-9 helper called
here is consumed read-only. Real candle-data ingestion lives in
Phase 8B/9; until then a deterministic synthetic series stands in
when the caller does not supply candles in the request body.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
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

logger = get_logger("app.strategy_engine.api.backtest")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


# ─── Boundary models ───────────────────────────────────────────────────


class BacktestRunRequest(BaseModel):
    """POST body. Every field is optional; ``{}`` triggers all defaults.

    ``candles`` is the only field worth supplying right now — once
    Phase 8B wires real OHLCV ingestion, the frontend will pass actual
    market data here. Until then leaving it ``None`` falls back to a
    deterministic 120-bar synthetic series so the UI has *something*
    to render.
    """

    model_config = ConfigDict(extra="forbid")

    candles: list[Candle] | None = None
    initial_capital: float = Field(default=100_000.0, gt=0)
    quantity: float = Field(default=1.0, gt=0)
    cost_settings: CostSettings | None = None
    include_reliability: bool = True
    include_sensitivity: bool = False
    """Sensitivity adds ~21 extra backtests; opt-in until the UI gains
    a "deep analyse" button (Phase 5B Part 4)."""


class BacktestRunResponse(BaseModel):
    """Combined response — what the frontend page consumes.

    ``truth`` is the Phase 6 :class:`TruthReport` layered on top of the
    Phase 4 reliability output. It is ``None`` whenever ``reliability``
    is — the truth engine consumes the reliability report and cannot
    score a backtest without it.
    """

    model_config = ConfigDict(extra="forbid")

    backtest: BacktestResult
    reliability: ReliabilityReport | None = None
    health_card: StrategyHealthCard
    truth: TruthReport | None = None


# ─── Endpoint ──────────────────────────────────────────────────────────


@router.post(
    "/{strategy_id}/backtest",
    response_model=BacktestRunResponse,
    response_model_by_alias=True,
)
async def run_strategy_backtest(
    strategy_id: uuid.UUID,
    body: BacktestRunRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestRunResponse:
    """Run the full backtest + reliability + coach pipeline.

    422 when the strategy has no ``strategy_json`` (legacy rows).
    404 when the strategy id doesn't exist or doesn't belong to the
    caller — the same body for both prevents id-enumeration probes.
    """
    strategy_row = await _load_owned_strategy(db, current_user, strategy_id)

    if not strategy_row.strategy_json:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Strategy has no DSL configured (legacy row). Recreate it "
                "via the Phase 5 builder to make it backtest-ready."
            ),
        )

    try:
        strategy = StrategyJSON.model_validate(strategy_row.strategy_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Stored strategy_json is invalid: {exc.errors()[0]['msg']}",
        ) from exc

    candles = list(body.candles) if body.candles else _synthetic_candles()
    cost_settings = body.cost_settings or CostSettings()

    backtest_result = run_backtest(
        BacktestInput(
            candles=candles,
            strategy=strategy,
            initial_capital=body.initial_capital,
            quantity=body.quantity,
            cost_settings=cost_settings,
        )
    )

    reliability_report: ReliabilityReport | None = None
    if body.include_reliability:
        reliability_report = build_reliability_report(
            strategy=strategy,
            candles=candles,
            initial_capital=body.initial_capital,
            quantity=body.quantity,
            cost_settings=cost_settings,
            include_oos=True,
            include_walk_forward=True,
            include_sensitivity=body.include_sensitivity,
        )

    health_card = generate_health_card(
        backtest_result, reliability=reliability_report
    )

    # Phase 6 truth report rides on top of the reliability output. If
    # the caller opted out of reliability we cannot score truth either —
    # the engine consumes the ReliabilityReport directly. ``ambiguity_mode``
    # mirrors ``BacktestInput``'s default since this endpoint does not
    # expose it on the request body.
    truth_report: TruthReport | None = None
    if reliability_report is not None:
        truth_report = evaluate_strategy_truth(
            strategy=strategy,
            reliability=reliability_report,
            cost_settings=cost_settings,
            ambiguity_mode=AmbiguityMode.CONSERVATIVE,
        )

    logger.info(
        "strategy.backtest.completed",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
        total_trades=backtest_result.total_trades,
        synthetic_candles=body.candles is None,
        reliability_included=reliability_report is not None,
        truth_included=truth_report is not None,
    )

    return BacktestRunResponse(
        backtest=backtest_result,
        reliability=reliability_report,
        health_card=health_card,
        truth=truth_report,
    )


# ─── Helpers ───────────────────────────────────────────────────────────


async def _load_owned_strategy(
    db: AsyncSession, user: User, strategy_id: uuid.UUID
) -> Strategy:
    """Same auth-scoped pattern as the CRUD router. 404 covers both
    'not found' and 'not yours' so the endpoint isn't an enumerator."""
    stmt = select(Strategy).where(
        Strategy.id == strategy_id, Strategy.user_id == user.id
    )
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )
    return strategy


def _synthetic_candles(n: int = 120) -> list[Candle]:
    """Deterministic placeholder OHLCV series.

    Sinusoidal oscillation around 100 (amplitude 5) with a small
    intra-bar range. Reruns produce identical output so the endpoint
    is deterministic when no candles are supplied. Real candle-data
    integration lands in Phase 8B/9.
    """
    base = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)
    out: list[Candle] = []
    for i in range(n):
        mid = 100.0 + 5.0 * math.sin(i / 8.0)
        # Mild intra-bar range so target / stop levels can plausibly cross.
        out.append(
            Candle(
                timestamp=base + timedelta(minutes=i),
                open=mid,
                high=mid + 0.6,
                low=mid - 0.6,
                close=mid + 0.2 * math.sin(i / 4.0),
                volume=1_000.0 + 50.0 * math.sin(i / 6.0),
            )
        )
    return out


__all__ = ["BacktestRunRequest", "BacktestRunResponse", "router"]
