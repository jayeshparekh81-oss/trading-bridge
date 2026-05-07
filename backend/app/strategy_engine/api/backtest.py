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
from app.strategy_engine.advisor import (
    Diagnosis,
    TradeQualityReport,
    compute_trade_quality,
    diagnose_strategy,
)
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
from app.strategy_engine.deviation import (
    DeviationReport,
    LiveTradingStats,
    evaluate_deviation,
)
from app.strategy_engine.indicator_versioning import (
    BacktestVersionManifest,
    capture_manifest,
)
from app.strategy_engine.regime import (
    RegimeReport,
    detect_regime,
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
    include_deviation_demo: bool = False
    """Synthesise a Phase 9 :class:`DeviationReport` by splitting the
    backtest's own trades 70/30 and treating the back 30% as the
    "actual" stream. Demo only — meaningful deviation analysis needs
    real paper-trading data, which lands when paper readiness is wired
    into this endpoint. Default off so the field stays ``None``."""


class BacktestRunResponse(BaseModel):
    """Combined response — what the frontend page consumes.

    ``truth`` is the Phase 6 :class:`TruthReport` layered on top of the
    Phase 4 reliability output. It is ``None`` whenever ``reliability``
    is — the truth engine consumes the reliability report and cannot
    score a backtest without it.

    ``regime`` is the Phase 8 :class:`RegimeReport` — the deterministic
    market-regime detector run against the same candles the backtest
    consumed, with the strategy passed for an in-context suitability
    verdict. Always populated alongside a successful backtest.

    ``deviation`` is the Phase 9 :class:`DeviationReport`. ``None`` by
    default — only populated when the caller passes
    ``include_deviation_demo=True`` so the page can preview the panel
    without real paper-trading data wired in yet.

    ``trade_quality`` is the Phase 7 advisor :class:`TradeQualityReport`.
    Always populated alongside a successful backtest. The endpoint does
    not currently track gross (pre-cost) P&L, so the cost-survival
    component returns its documented unknown sentinel — the rest of the
    components score normally.

    ``version_manifest`` pins the indicator versions consumed by this
    run so the backtest can be replayed deterministically against the
    same calculation logic. Always populated.

    ``diagnosis`` is the Phase 7 :class:`Diagnosis` from the AI Doctor.
    Always populated alongside a successful backtest. Carries an
    ``improved_strategy_draft`` when ``can_auto_improve`` is true — the
    frontend feeds that draft back through ``POST /compare-fix`` to
    show a side-by-side comparison.
    """

    model_config = ConfigDict(extra="forbid")

    backtest: BacktestResult
    reliability: ReliabilityReport | None = None
    health_card: StrategyHealthCard
    truth: TruthReport | None = None
    regime: RegimeReport | None = None
    deviation: DeviationReport | None = None
    trade_quality: TradeQualityReport | None = None
    version_manifest: BacktestVersionManifest
    diagnosis: Diagnosis | None = None


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

    health_card = generate_health_card(backtest_result, reliability=reliability_report)

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

    # Phase 8 regime detection — runs on the same candle stream the
    # backtest consumed and is passed the strategy so the report
    # includes a strategy-suitability verdict.
    regime_report = detect_regime(candles=candles, strategy=strategy)

    # Phase 9 deviation monitor — opt-in demo. Real paper-trading data
    # will replace the synthetic split once the paper readiness signal
    # is plumbed through this endpoint.
    deviation_report = (
        _deviation_demo_report(backtest_result) if body.include_deviation_demo else None
    )

    # Phase 7 trade-quality scorer — pure function over the backtest
    # alone. ``gross_pnl`` is omitted because this endpoint does not
    # track the pre-cost figure separately; the cost-survival
    # component falls back to its unknown sentinel by design.
    trade_quality_report = compute_trade_quality(backtest_result)

    # Indicator-versioning manifest — pins the version of every
    # indicator the strategy referenced. Indicator IDs come from
    # ``IndicatorConfig.type`` (the registry id), not ``id`` (the
    # per-strategy instance handle). Duplicates are collapsed inside
    # ``capture_manifest``.
    version_manifest = capture_manifest(
        backtest_id=uuid.uuid4(),
        strategy_id=strategy_id,
        indicators_used=[ind.type for ind in strategy.indicators],
        schema_version=str(strategy.version),
    )

    # Phase 7 AI Doctor — pure rule-based diagnosis over the strategy
    # plus the upstream reports. The draft (when present) is fed
    # through ``POST /compare-fix`` so the user can preview the impact
    # of each auto-fix before applying it.
    diagnosis = diagnose_strategy(
        strategy=strategy,
        backtest=backtest_result,
        reliability=reliability_report,
        truth=truth_report,
    )

    logger.info(
        "strategy.backtest.completed",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
        total_trades=backtest_result.total_trades,
        synthetic_candles=body.candles is None,
        reliability_included=reliability_report is not None,
        truth_included=truth_report is not None,
        regime=regime_report.regime,
        deviation_demo=body.include_deviation_demo,
        trade_quality_grade=trade_quality_report.grade,
    )

    return BacktestRunResponse(
        backtest=backtest_result,
        reliability=reliability_report,
        health_card=health_card,
        truth=truth_report,
        regime=regime_report,
        deviation=deviation_report,
        trade_quality=trade_quality_report,
        version_manifest=version_manifest,
        diagnosis=diagnosis,
    )


# ─── Helpers ───────────────────────────────────────────────────────────


async def _load_owned_strategy(db: AsyncSession, user: User, strategy_id: uuid.UUID) -> Strategy:
    """Same auth-scoped pattern as the CRUD router. 404 covers both
    'not found' and 'not yours' so the endpoint isn't an enumerator."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )
    return strategy


def _deviation_demo_report(backtest: BacktestResult) -> DeviationReport:
    """Synthesise a :class:`DeviationReport` from the backtest itself.

    Splits the trade list 70/30 and treats the back 30% as the
    "actual" stream so the page can preview every Phase 9 surface
    (status badge, score, per-metric breakdown, decision flags)
    without real paper-trading data wired in. When the back portion
    has fewer than ``MIN_TRADES_FOR_EVAL`` trades the deviation
    monitor returns its own ``insufficient data`` placeholder report
    — which is exactly the empty-state we want the UI to render.

    The session count is set to ``max(1, days_spanned)`` so trade-
    frequency math has a sensible divisor; falling back to ``1`` is
    safe because the monitor degrades to "treat the whole window as
    one day" in that branch already.
    """
    trades = backtest.trades
    split_idx = int(len(trades) * 0.70)
    tail = trades[split_idx:]

    if not tail:
        actual = LiveTradingStats(
            total_trades=0,
            sessions=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            total_pnl=0.0,
        )
        return evaluate_deviation(backtest=backtest, actual=actual)

    pnls = [t.pnl for t in tail]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / len(tail)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float(min(10.0, gross_profit))
    sessions = max(1, _spanned_days(tail[0].entry_time, tail[-1].exit_time))

    actual = LiveTradingStats(
        total_trades=len(tail),
        sessions=sessions,
        win_rate=win_rate,
        # Demo uses the *full* backtest's drawdown as a proxy because
        # we do not have a per-segment drawdown curve here. The user
        # only sees this when they explicitly opt in to the demo.
        profit_factor=max(0.0, profit_factor),
        max_drawdown=backtest.max_drawdown,
        total_pnl=sum(pnls),
    )
    return evaluate_deviation(backtest=backtest, actual=actual)


def _spanned_days(start: datetime, end: datetime) -> int:
    """Count whole days between two timestamps, floor 1."""
    if end <= start:
        return 1
    return max(1, int((end - start).total_seconds() // 86_400) + 1)


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
