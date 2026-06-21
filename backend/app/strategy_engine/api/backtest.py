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
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.entitlements import plan_is_active
from app.core.config import get_settings
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
from app.strategy_engine.audit.loggers import log_backtest_run
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
from app.strategy_engine.data_provider import (
    DhanFetchError,
    HistoricalDataRequest,
    fetch_historical_candles,
)
from app.strategy_engine.data_provider.constants import (
    QUALITY_SCORE_WARN_THRESHOLD,
    TIMEFRAME_TO_INTERVAL_MINUTES,
)
from app.strategy_engine.data_quality import validate_candles
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
from app.strategy_engine.reliability.walk_forward import run_walk_forward
from app.strategy_engine.reliability.walk_forward_constants import (
    DEFAULT_NUM_WINDOWS,
    MIN_BARS_PER_WINDOW,
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
    a "deep analyse" button (Phase 5B Part 4). Kept for backwards
    compatibility — new callers should use ``sensitivity_enabled``
    below; the handler ORs the two flags."""

    # ─── Robustness Test Controls (Expert Builder) ─────────────────
    walk_forward_enabled: bool = True
    """Per-call gate for the walk-forward analysis. ANDed with
    ``include_reliability`` — both must be true for the WF report to
    be produced. Default True matches the prior behaviour where
    ``build_reliability_report`` always ran walk-forward when
    reliability was on."""

    walk_forward_windows: int = Field(default=5, ge=2, le=20)
    """Number of walk-forward windows to test. Default 5 matches
    :data:`DEFAULT_NUM_WINDOWS`; values in [2, 20] override per-call.
    The handler post-recomputes the WF report when this differs from
    the default — :func:`build_reliability_report` itself is not
    modified."""

    sensitivity_enabled: bool = False
    """New name for ``include_sensitivity``. Either flag set to true
    triggers the sensitivity run; defaults match the legacy field so
    a body that omits both behaves identically to today."""

    sensitivity_variation: float = Field(default=0.10, gt=0.0, le=0.5)
    """Variation factor for sensitivity (e.g. 0.10 = ±10 %). Currently
    accepted but **inert** at the run level — the underlying
    :data:`PARAMETER_SENSITIVITY_VARIATION` constant is module-level
    and modifying it would touch the reliability module, which Phase
    5B-locked rules forbid. The field is recorded in the request log
    so future plumbing has a deterministic per-call value to consume."""

    include_deviation_demo: bool = False
    """Synthesise a Phase 9 :class:`DeviationReport` by splitting the
    backtest's own trades 70/30 and treating the back 30% as the
    "actual" stream. Demo only — meaningful deviation analysis needs
    real paper-trading data, which lands when paper readiness is wired
    into this endpoint. Default off so the field stays ``None``."""
    candles_request: HistoricalDataRequest | None = None
    """When supplied, fetch real OHLCV from Dhan via the Phase B
    adapter and run the backtest on those candles. Falls back to the
    synthetic 120-bar series when omitted. Mutually exclusive with
    ``candles`` (raw injection) — when both are provided the explicit
    raw list wins for backwards compatibility."""


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

    ``candles_source`` records which source the candle stream came from:
    ``"dhan_historical"`` when the caller passed ``candles_request`` and
    the Phase B adapter served the data, ``"synthetic"`` for both the
    raw-injection path and the deterministic fallback. Always populated.

    ``data_quality_warnings`` is the list of short Phase 11 issue
    messages produced by the data-quality validator on the selected
    stream. Always populated (empty list when the stream is clean).
    """

    model_config = ConfigDict(extra="forbid")

    backtest: BacktestResult
    reliability: ReliabilityReport | None = None
    # Optional so B3.3 can null it for non-entitled users when the paywall is
    # enforced (premium section). Always populated by the endpoint otherwise.
    health_card: StrategyHealthCard | None = None
    truth: TruthReport | None = None
    regime: RegimeReport | None = None
    deviation: DeviationReport | None = None
    trade_quality: TradeQualityReport | None = None
    version_manifest: BacktestVersionManifest
    diagnosis: Diagnosis | None = None
    candles_source: Literal["dhan_historical", "synthetic"] = "synthetic"
    data_quality_warnings: list[str] = Field(default_factory=list)


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

    market_open = await _market_is_open()
    candles, candles_source, data_quality_warnings = _resolve_candles(
        body,
        market_open=market_open,
        allowed_symbols=strategy_row.allowed_symbols or [],
    )
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

    # ── Robustness Test Controls (Expert Builder) ───────────────────
    # Resolve the effective flags. ``include_sensitivity`` is the
    # legacy name; ``sensitivity_enabled`` is the new one — either set
    # to True triggers the run so old callers and new ones cohabit.
    sensitivity_on = body.include_sensitivity or body.sensitivity_enabled
    walk_forward_on = body.walk_forward_enabled

    reliability_report: ReliabilityReport | None = None
    if body.include_reliability:
        reliability_report = build_reliability_report(
            strategy=strategy,
            candles=candles,
            initial_capital=body.initial_capital,
            quantity=body.quantity,
            cost_settings=cost_settings,
            include_oos=True,
            include_walk_forward=walk_forward_on,
            include_sensitivity=sensitivity_on,
        )

        # When the caller asked for a non-default window count, recompute
        # the walk-forward report directly via :func:`run_walk_forward`
        # and patch the reliability report. ``build_reliability_report``
        # passes ``DEFAULT_NUM_WINDOWS`` hardcoded; touching that helper
        # to accept ``num_windows`` would modify the reliability module
        # (forbidden), so we substitute at the handler layer instead.
        if (
            walk_forward_on
            and reliability_report.walk_forward is not None
            and body.walk_forward_windows != DEFAULT_NUM_WINDOWS
        ):
            _wf_min_bars = body.walk_forward_windows * MIN_BARS_PER_WINDOW
            if len(candles) >= _wf_min_bars:
                custom_wf = run_walk_forward(
                    candles=candles,
                    strategy=strategy,
                    num_windows=body.walk_forward_windows,
                    cost_settings=cost_settings,
                    initial_capital=body.initial_capital,
                    quantity=body.quantity,
                )
                reliability_report = reliability_report.model_copy(
                    update={"walk_forward": custom_wf}
                )

    # ``sensitivity_variation`` is accepted but currently inert — the
    # underlying variation factor lives in
    # ``PARAMETER_SENSITIVITY_VARIATION`` (module constant) and the
    # rules forbid mutating reliability internals. Logged for now so
    # future plumbing has a per-call value to consume.
    logger.info(
        "strategy.backtest.robustness_controls",
        walk_forward_enabled=walk_forward_on,
        walk_forward_windows=body.walk_forward_windows,
        sensitivity_enabled=sensitivity_on,
        sensitivity_variation=body.sensitivity_variation,
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

    # Cache the latest Trust + Truth scores on the strategy row so the
    # live-orders SafetyChain (Phase 8B-2) can enforce the Trust >= 70
    # / Truth >= 55 gates without re-running the full pipeline. Both
    # reports must be present AND the run must be over real Dhan
    # candles — synthetic fallback (Dhan outage, market-hours gate,
    # raw-injection test path) produces a structurally valid report
    # computed on placeholder data; writing it onto the live row would
    # corrupt the SafetyChain gate. When the cache is left untouched,
    # last_scores_at retains its prior value so a previously-fresh
    # REAL score is not clobbered by a partial / synthetic run. The
    # write is a bulk UPDATE keyed by id; no ORM refresh, no extra SELECT.
    if (
        reliability_report is not None
        and truth_report is not None
        and candles_source == "dhan_historical"
    ):
        await db.execute(
            update(Strategy)
            .where(Strategy.id == strategy_id)
            .values(
                last_trust_score=float(reliability_report.trust_score.score),
                last_truth_score=float(truth_report.truth_score),
                last_scores_at=datetime.now(UTC),
            )
        )
        await db.commit()

    logger.info(
        "strategy.backtest.completed",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
        total_trades=backtest_result.total_trades,
        candles_source=candles_source,
        reliability_included=reliability_report is not None,
        truth_included=truth_report is not None,
        regime=regime_report.regime,
        deviation_demo=body.include_deviation_demo,
        trade_quality_grade=trade_quality_report.grade,
        data_quality_warnings=len(data_quality_warnings),
    )
    log_backtest_run(
        strategy_id=strategy_id,
        user_id=current_user.id,
        success=True,
        metadata={
            "total_trades": backtest_result.total_trades,
            "total_pnl": float(backtest_result.total_pnl),
            "candles_source": candles_source,
            "trust_score": (
                reliability_report.trust_score.score if reliability_report is not None else None
            ),
            "truth_score": (truth_report.truth_score if truth_report is not None else None),
        },
    )

    response = BacktestRunResponse(
        backtest=backtest_result,
        reliability=reliability_report,
        health_card=health_card,
        truth=truth_report,
        regime=regime_report,
        deviation=deviation_report,
        trade_quality=trade_quality_report,
        version_manifest=version_manifest,
        diagnosis=diagnosis,
        candles_source=candles_source,
        data_quality_warnings=data_quality_warnings,
    )

    # ── Phase 2 Billing B3.3 — premium-field gating ──────────────────────
    # Everything above is already computed; this ONLY nulls the premium
    # analytics sections for non-entitled users when the paywall is enforced.
    # The basic backtest result (incl. equity curve), version manifest,
    # candles source and data-quality warnings stay fully intact and free —
    # basic backtest is NEVER 402-gated. Flag OFF ⇒ unchanged for everyone.
    if get_settings().paywall_enforced and not plan_is_active(current_user):
        response.reliability = None
        response.health_card = None
        response.truth = None
        response.regime = None
        response.deviation = None
        response.trade_quality = None
        response.diagnosis = None
    return response


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


# Modest default window for the auto-fired real backtest when the market is
# CLOSED: enough bars for every Phase-4 sub-analysis to clear its minimum-bar
# gate, small enough to finish comfortably under the current ~60s host-nginx
# proxy_read_timeout. Widen only after that timeout is raised (tracked follow-up).
_DEFAULT_REAL_TIMEFRAME = "5m"
_DEFAULT_REAL_WINDOW_DAYS = 14


async def _market_is_open() -> bool:
    """Reuse the canonical market flag the kill-switch beat task caches in
    Redis ('market:status' = 'open'/'closed', refreshed every minute by
    ``check_market_status``). We READ the cached value rather than recompute
    hours, so the single source of truth for market hours stays in
    ``check_market_status`` (no duplicated cutoff here).

    Fail-safe: a missing/stale flag or any Redis error returns ``True``
    (assume OPEN), so a real Dhan fetch is NEVER attempted unless the market
    is positively confirmed closed — protecting the shared Dhan account's
    quota for live BSE/CDSL order placement.
    """
    try:
        from app.core import redis_client

        raw = await redis_client.get_redis().get("market:status")
    except Exception:
        return True
    if raw is None:
        return True
    value = raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
    return value.strip().lower() != "closed"


def _normalize_symbol(raw: str) -> str:
    """Map a stored ``allowed_symbols`` entry toward a data-provider handle:
    strip a leading ``EXCH:`` prefix and a trailing TradingView continuous-
    future ``1!`` marker (``"CDSL1!" -> "CDSL"``, ``"NSE:ANGELONE" ->
    "ANGELONE"``). The adapter's KNOWN_SYMBOLS/alias map does the real
    resolution; anything it can't resolve falls back to synthetic."""
    sym = raw.strip().upper()
    if ":" in sym:
        sym = sym.split(":", 1)[1]
    if sym.endswith("1!"):
        sym = sym[:-2]
    return sym.strip()


def _default_candles_request(
    allowed_symbols: list[Any],
) -> HistoricalDataRequest | None:
    """Build a modest real-candle request from the strategy's first allowed
    symbol. Returns ``None`` when there is no usable symbol (→ synthetic)."""
    if not allowed_symbols:
        return None
    first = allowed_symbols[0]
    if not isinstance(first, str) or not first.strip():
        return None
    symbol = _normalize_symbol(first)
    if not symbol:
        return None
    to_date = datetime.now(UTC)
    from_date = to_date - timedelta(days=_DEFAULT_REAL_WINDOW_DAYS)
    try:
        return HistoricalDataRequest(
            symbol=symbol,
            timeframe=_DEFAULT_REAL_TIMEFRAME,
            from_date=from_date,
            to_date=to_date,
        )
    except ValidationError:
        return None


def _resolve_candles(
    body: BacktestRunRequest,
    *,
    market_open: bool,
    allowed_symbols: list[Any],
) -> tuple[list[Candle], Literal["dhan_historical", "synthetic"], list[str]]:
    """Pick the candle stream this backtest runs on.

    Market-hours SAFETY GATE: real Dhan candles are fetched ONLY when the
    market is CLOSED, so a backtest can never contend with live BSE/CDSL
    order placement on the shared Dhan account. When closed, the stream is
    the explicit ``candles_request`` if supplied, else a modest default
    derived from the strategy's first allowed symbol. Any fetch failure
    (no token, Dhan error, low quality) GRACEFULLY falls back to synthetic
    with a 200 — never a 5xx.
    """
    # 1. Explicit raw injection (test suite) — unchanged, classified synthetic.
    if body.candles:
        candles = list(body.candles)
        return candles, "synthetic", _candle_warnings(candles, expected_minutes=5)

    # 2. SAFETY GATE — during market hours, never touch Dhan.
    if market_open:
        candles = _synthetic_candles()
        logger.info("backtest.candles.synthetic", reason="market_open")
        return candles, "synthetic", _candle_warnings(candles, expected_minutes=1)

    # 3. Market closed — explicit request, else a default from the strategy.
    request = body.candles_request or _default_candles_request(allowed_symbols)
    if request is None:
        candles = _synthetic_candles()
        logger.info("backtest.candles.synthetic", reason="no_symbol")
        return candles, "synthetic", _candle_warnings(candles, expected_minutes=1)

    # 4. Fetch real — GRACEFUL fallback to synthetic on any failure (never 5xx).
    try:
        return _fetch_dhan_candles(request)
    except Exception as exc:
        logger.warning(
            "backtest.candles.real_fallback",
            symbol=request.symbol,
            timeframe=request.timeframe,
            detail=str(getattr(exc, "detail", exc)),
        )
        candles = _synthetic_candles()
        warnings = [
            "Real market data unavailable — showing sample data.",
            *_candle_warnings(candles, expected_minutes=1),
        ]
        return candles, "synthetic", warnings


def _fetch_dhan_candles(
    request: HistoricalDataRequest,
) -> tuple[list[Candle], Literal["dhan_historical", "synthetic"], list[str]]:
    """Fetch via the Phase B adapter, gate on quality, return the
    resolved tuple. Token handling is here (not on the fetcher) so
    the Hinglish error message stays close to the user-facing
    boundary."""
    token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Dhan token configure nahi hai. Settings mein add karo (DHAN_ACCESS_TOKEN env var)."
            ),
        )

    try:
        response = fetch_historical_candles(request, access_token=token)
    except DhanFetchError as exc:
        # Surface the Dhan error message but never the access token.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Dhan historical fetch failed: {exc}",
        ) from exc

    expected_minutes = TIMEFRAME_TO_INTERVAL_MINUTES.get(
        request.timeframe,
        # Daily timeframe — pass a wide minute count so weekend gaps
        # don't trip the missing-candle gate.
        24 * 60,
    )
    quality_report = validate_candles(response.candles, expected_timeframe_minutes=expected_minutes)
    if quality_report.quality_score < QUALITY_SCORE_WARN_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": (
                    "Dhan candle quality is below the safety threshold for "
                    "backtesting; pick a different window or timeframe."
                ),
                "quality_score": quality_report.quality_score,
                "issues": [issue.message for issue in quality_report.issues],
            },
        )

    return list(response.candles), "dhan_historical", list(response.quality_warnings)


def _candle_warnings(candles: list[Candle], *, expected_minutes: int) -> list[str]:
    """Run Phase 11 validation on a non-Dhan candle stream and return
    the warning messages. Synthetic / raw-injected paths still surface
    quality issues to the UI; the score-below-threshold gate only
    fires for Dhan-sourced data because synthetic windows are known-
    clean by construction."""
    if not candles:
        return ["Empty candle stream."]
    report = validate_candles(candles, expected_timeframe_minutes=expected_minutes)
    return [issue.message for issue in report.issues]


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


# ── Synthetic backtest data ─────────────────────────────────────────────
# Deterministic, structurally rich OHLCV used when no real candles are
# supplied. Replaces the old pure-sine placeholder, which by construction had
# zero divergence / trend / candle-pattern structure — so divergence and swing
# templates could never fire (see docs/QUEUE_RR_ZERO_TRADES_DIAGNOSIS.md and
# docs/QUEUE_SS_SYNTHETIC_DATA.md). Output contract is UNCHANGED: list[Candle].
#
# Layout: a SINGLE continuous 1-minute intraday session (09:15 IST anchor, one
# calendar day). The six structural regimes are packed into the in-window
# stretch (≤ 14:45 IST) so every template's intraday time-gate (09:30/09:15 →
# 15:00/15:15) is satisfied; the remaining bars are a neutral out-of-window
# continuation purely to reach the bar count. 1-minute spacing keeps the series
# gap-free (no data-quality "missing candle" warnings) AND fits all six regimes
# inside one intraday window — see docs/QUEUE_SS_SYNTHETIC_DATA.md for why
# 5-minute spacing could not satisfy both at once.

_IST = ZoneInfo("Asia/Kolkata")
#: First bar of the synthetic session (a weekday, 09:15 IST open).
_SYNTH_ANCHOR = datetime(2026, 1, 5, 9, 15, tzinfo=_IST)
_SYNTH_BAR_MINUTES = 1
#: Bars reserved for structure: 09:15 → 14:45 IST at 1-min keeps entries inside
#: every template's gate (tightest is 09:30-15:00) with a square-off buffer.
_SYNTH_STRUCT_BARS = 330
#: Regime weights (fractions of the structural span). Each regime engineers the
#: structure one template family needs; every template scans the whole series
#: and fires in its matching regime. Order: divergence(rsi/macd) → obv-divergence
#: → band oscillation (supertrend/hull + macd/bb/orb sub-outputs) →
#: uptrend-pullbacks (triple-ema + trend baselines) → oversold dojis →
#: engulfing reversals. Divergence gets the largest slice (needs lookback=20 +
#: RSI/MACD warmup before it can emit a signal).
_SYNTH_REGIME_WEIGHTS = (0.26, 0.12, 0.16, 0.16, 0.15, 0.15)


def _synth_ohlc(n: int) -> list[tuple[float, float, float, float, float]]:
    """Build n ``(open, high, low, close, volume)`` rows across 6 regimes.

    Pure closed-form (sin / exp) → fully deterministic; reruns are
    byte-identical. The per-family motifs mirror the translator stack's own
    override-test harnesses (the proven structures that make each family fire).
    """
    counts = [round(w * n) for w in _SYNTH_REGIME_WEIGHTS]
    counts[-1] = n - sum(counts[:-1])  # absorb rounding into the last regime
    rows: list[tuple[float, float, float, float, float]] = []

    # R1 — decelerating decline → bullish rsi/macd divergence (close>open).
    for k in range(counts[0]):
        c = 25000.0 - 1500.0 * (1.0 - math.exp(-k / 60.0))
        o = c - 5.0
        rows.append((o, max(o, c) + 10.0, min(o, c) - 10.0, c, 1000.0))

    # R2 — down-drift with up-weighted volume → bullish OBV divergence.
    prev: float | None = None
    for k in range(counts[1]):
        c = 24800.0 - 2.0 * k + 100.0 * math.sin(k / 6.0)
        o = c - 5.0
        v = 2000.0 if (prev is not None and c > prev) else 500.0
        prev = c
        rows.append((o, max(o, c) + 10.0, min(o, c) - 10.0, c, v))

    # R3 — band-crossing oscillation → supertrend/hull + macd/bb/orb crossovers.
    for k in range(counts[2]):
        c = 25000.0 + 200.0 * math.sin(k / 10.0)
        o = c - 5.0
        rows.append((o, max(o, c) + 10.0, min(o, c) - 10.0, c, 1000.0))

    # R4 — strong uptrend with shallow pullbacks → triple-ema stack + trend
    #      baselines (ema-crossover etc.).
    for k in range(counts[3]):
        c = 24000.0 + 8.0 * k + 140.0 * math.sin(k / 8.0)
        o = c - 5.0
        rows.append((o, max(o, c) + 10.0, min(o, c) - 10.0, c, 1000.0))

    # R5a — steady oversold decline with a zero-body doji every 10th bar
    #       (close<ema, rsi<35) → doji-reversal + oversold baselines.
    for k in range(counts[4]):
        c = 25000.0 - 25.0 * k
        o = c if k % 10 == 0 else c + 15.0
        rows.append((o, max(o, c) + 20.0, min(o, c) - 20.0, c, 1000.0))

    # R5b — decline → pause → bullish bar engulfing the prior → engulfing-reversal.
    level = 25000.0
    cyc = 15
    for k in range(counts[5]):
        ph = k % cyc
        if ph == cyc - 3:  # small bearish setup (pause)
            o, c = level + 4.0, level - 4.0
        elif ph == cyc - 2:  # bullish engulfing of the setup
            o, c = level - 8.0, level + 8.0
        else:  # decline / hold
            o, c = level + 5.0, level - 5.0
            if ph != cyc - 1:
                level -= 15.0
        rows.append((o, max(o, c) + 5.0, min(o, c) - 5.0, c, 1000.0))

    return rows


def _synth_filler(count: int, last_close: float) -> list[tuple[float, float, float, float, float]]:
    """Neutral out-of-window continuation rows (no new signals).

    Gentle bounded oscillation around the final structural close so the bars
    are valid and continuous; these fall after 15:00 IST so the templates'
    intraday gate blocks any entries here. Purely to reach the bar count.
    """
    rows: list[tuple[float, float, float, float, float]] = []
    for k in range(count):
        c = last_close + 3.0 * math.sin(k / 9.0)
        o = c - 1.0
        rows.append((o, max(o, c) + 3.0, min(o, c) - 3.0, c, 1000.0))
    return rows


def _synthetic_candles(n: int = 720) -> list[Candle]:
    """Deterministic, structurally rich placeholder OHLCV series.

    A single continuous 1-minute intraday session (720 bars from the 09:15 IST
    anchor on one calendar day). The six structural regimes are packed into the
    first ``_SYNTH_STRUCT_BARS`` bars (the in-window stretch, ≤ 14:45 IST) so
    every newly-unlocked template's intraday time-gate is satisfied and it fires
    meaningfully; the remaining bars are a neutral out-of-window continuation to
    reach the bar count. 1-minute spacing is gap-free (no data-quality "missing
    candle" warnings). Fully deterministic (closed-form) → byte-identical
    reruns. Returns ``list[Candle]`` (the unchanged contract). Real candle-data
    integration lands in Phase 8B/9.
    """
    struct = min(n, _SYNTH_STRUCT_BARS)
    rows = _synth_ohlc(struct)
    if n > struct:
        rows += _synth_filler(n - struct, rows[-1][3])
    out: list[Candle] = []
    for idx, (o, h, lo, c, v) in enumerate(rows):
        ts = _SYNTH_ANCHOR + timedelta(minutes=_SYNTH_BAR_MINUTES * idx)
        out.append(Candle(timestamp=ts, open=o, high=h, low=lo, close=c, volume=v))
    return out


__all__ = ["BacktestRunRequest", "BacktestRunResponse", "router"]
