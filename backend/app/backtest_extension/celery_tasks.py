"""Celery task that wraps :func:`app.strategy_engine.backtest.run_backtest`.

One ``@shared_task`` ``run_backtest_task`` drives the state machine on
``backtest_runs``: PENDING → RUNNING → SUCCEEDED|FAILED. The task is
**idempotent on dispatch** — a second call for the same ``run_id``
while ``status != PENDING`` is a no-op (logged + returned).

**Day-1-3 sprint contract:**
    * Shared default worker queue (decision D6); ``BACKTEST_QUEUE``
      constant is exported for future Day-5 dedicated-worker wiring
      but NOT bound to the task yet.
    * Read-only import of the engine (hard guardrail #1); no
      decorators, no monkey-patches, no internal access.
    * Retries are NOT enabled (max_retries=0) — a failed engine
      invocation lands the run in FAILED state with a populated
      ``error_json``; the user submits a fresh request to retry.

State machine (driven through :mod:`persistence`):

    1. Load BacktestRun by id. If ``status != PENDING``, log a
       duplicate-dispatch warning and return (benign race, not a bug).
    2. ``update_status → RUNNING``
    3. Resolve the StrategyJSON payload from the Strategy row
       (`strategy_id` is set per Day-1-3 contract — see D8 in
       DECISIONS).
    4. Build the BacktestInput and call ``run_backtest()``.
    5. ``save_trades + save_metrics + update_status → SUCCEEDED``.

Exception path:
    Any uncaught exception during 3-5 → ``update_status → FAILED``
    with ``error_json = {type, message, traceback_first_line}``.
"""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest_extension import persistence
from app.backtest_extension.schemas import BacktestRunStatus
from app.core.logging import get_logger
from app.core.security import decrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.session import get_sessionmaker
from app.schemas.broker import BrokerName
from app.strategy_engine.backtest import (
    AmbiguityMode,
    BacktestInput,
    CostSettings,
    run_backtest,
)
from app.backtest_extension.trade_markers import persist_backtest_trade_markers
from app.strategy_engine.data_provider import (
    DhanFetchError,
    HistoricalDataRequest,
    Timeframe,
    fetch_historical_candles,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

_logger = get_logger("app.backtest_extension.celery_tasks")


# ─── Constants ──────────────────────────────────────────────────────────


#: Dedicated queue name reserved for Day-5 worker-isolation work.
#: NOT bound to the task on this branch (decision D6 + spec
#: "DEFAULT to shared worker pool"). Founder-approved Day-5 PR
#: will add `queue=BACKTEST_QUEUE` to the @shared_task decorator
#: and start a dedicated worker container.
BACKTEST_QUEUE = "backtest"


# ─── Error capture ──────────────────────────────────────────────────────


def _build_error_payload(exc: BaseException) -> dict[str, Any]:
    """Capture an exception as a small dict suitable for the ``error_json`` column.

    Three string-bounded fields:
        - type: ``exc.__class__.__name__``
        - message: ``str(exc)`` truncated to 1024 chars
        - traceback_first_line: top frame of the traceback for triage
    """
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    first_frame = ""
    for line in tb_lines:
        stripped = line.strip()
        if stripped.startswith("File "):
            first_frame = stripped
            break
    return {
        "type": exc.__class__.__name__,
        "message": str(exc)[:1024],
        "traceback_first_line": first_frame[:512],
    }


# ─── Strategy payload resolution ────────────────────────────────────────


class StrategyPayloadResolutionError(RuntimeError):
    """Raised when the run's strategy_id can't be resolved to a
    StrategyJSON. Lands the run in FAILED state with the cause in
    ``error_json``."""


async def _load_strategy_json(
    session: AsyncSession, *, strategy_id: uuid.UUID, user_id: uuid.UUID
) -> StrategyJSON:
    """Owner-scoped load of the Strategy.strategy_json column."""
    stmt = (
        select(Strategy)
        .where(Strategy.id == strategy_id)
        .where(Strategy.user_id == user_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise StrategyPayloadResolutionError(
            f"Strategy {strategy_id} not found or not owned by user {user_id}."
        )
    if not row.strategy_json:
        raise StrategyPayloadResolutionError(
            f"Strategy {strategy_id} has no DSL configured (legacy or "
            f"cloned-from-template row with null strategy_json)."
        )
    return StrategyJSON.model_validate(row.strategy_json)


# ─── Broker-credential resolution ───────────────────────────────────────


class NoBrokerCredentialError(RuntimeError):
    """Raised when the run's user has no active Dhan ``BrokerCredential``
    or the stored token has been wiped. Lands the run in FAILED state
    with ``error_json.message`` starting with ``no_broker_credential``."""


async def _resolve_dhan_access_token(
    session: AsyncSession, *, user_id: uuid.UUID
) -> str:
    """Return the user's decrypted Dhan access token.

    Mirrors :func:`app.api.chart._resolve_dhan_credentials` (and
    :func:`app.services.order_service._build_broker_credentials`) so
    encrypted-column handling stays consistent across chart + order +
    backtest flows. Trimmed to the one field
    :func:`fetch_historical_candles` needs.
    """
    stmt = select(BrokerCredential).where(
        BrokerCredential.user_id == user_id,
        BrokerCredential.broker_name == BrokerName.DHAN,
        BrokerCredential.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or not row.access_token_enc:
        raise NoBrokerCredentialError(
            "no_broker_credential: Dhan link missing or token wiped — "
            "user must reconnect Dhan account."
        )
    return decrypt_credential(row.access_token_enc)


# ─── Candle materialisation ─────────────────────────────────────────────


class NoDataError(RuntimeError):
    """Raised when the data provider returns zero candles for the
    requested window. Lands the run in FAILED state with
    ``error_json.message`` starting with ``no_data_available``."""


#: Default fallback window when the request payload omits ``start`` /
#: ``end`` (per :class:`BacktestEnqueueRequest` contract — final
#: defaulting was deferred from Phase 1 schemas to Day 6).
_DEFAULT_WINDOW_DAYS = 60


def _parse_window(
    payload: dict[str, Any], *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Extract ``(from_date, to_date)`` from the persisted request payload.

    Payload is the result of ``BacktestEnqueueRequest.model_dump(
    mode="json", exclude_none=True)`` so ``start``/``end`` are ISO
    strings when present, absent when the request omitted them.
    """
    now_utc = now or datetime.now(UTC)
    raw_end = payload.get("end")
    to_date = (
        datetime.fromisoformat(raw_end) if isinstance(raw_end, str) else now_utc
    )
    raw_start = payload.get("start")
    from_date = (
        datetime.fromisoformat(raw_start)
        if isinstance(raw_start, str)
        else to_date - timedelta(days=_DEFAULT_WINDOW_DAYS)
    )
    return from_date, to_date


def _fetch_real_candles(
    payload: dict[str, Any], *, access_token: str
) -> list[Candle]:
    """Fetch candles for the run from Dhan via the data-provider adapter.

    Translates provider-layer errors into application-layer messages
    with stable prefixes so :data:`error_json.message` is easy to
    grep (``fetch_failed:`` / ``invalid_symbol:`` / ``no_data_available``).

    Raises:
        NoDataError: provider returned zero candles.
        RuntimeError: ``DhanFetchError`` or symbol-resolution ``ValueError``
            wrapped with a stable prefix.
        pydantic.ValidationError: bad timeframe / inverted date range /
            intraday span > 90 days (bubbles unchanged — message is
            already informative).
    """
    from_date, to_date = _parse_window(payload)
    request = HistoricalDataRequest(
        symbol=cast(str, payload.get("symbol", "NIFTY")),
        timeframe=cast(Timeframe, payload.get("timeframe", "5m")),
        from_date=from_date,
        to_date=to_date,
    )

    try:
        response = fetch_historical_candles(request, access_token=access_token)
    except DhanFetchError as exc:
        status = exc.status_code if exc.status_code is not None else "unknown"
        raise RuntimeError(
            f"fetch_failed: status={status} message={str(exc)[:512]}"
        ) from exc
    except ValueError as exc:
        # ValueError is raised by data_provider._resolve_symbol when the
        # symbol isn't in KNOWN_SYMBOLS and no overrides were supplied.
        raise RuntimeError(f"invalid_symbol: {str(exc)[:512]}") from exc

    if response.quality_warnings:
        _logger.warning(
            "backtest.run.data_quality_warnings",
            warning_count=len(response.quality_warnings),
            sample_warnings=response.quality_warnings[:3],
            symbol=request.symbol,
            timeframe=request.timeframe,
        )

    if not response.candles:
        raise NoDataError("no_data_available")

    return list(response.candles)


def _build_synthetic_candles_payload(payload: dict[str, Any]) -> list[Any]:
    """**DEPRECATED — test-only.** Synthetic deterministic candle series.

    TODO(day-7-or-later): remove once Day-4 engine-integration tests
    have migrated to mocked :func:`fetch_historical_candles` fixtures.
    Day-6 production path now goes through :func:`_fetch_real_candles`;
    this helper is retained only because
    ``tests/backtest_extension/test_engine_integration.py`` still
    depends on it for end-to-end engine smoke runs.
    """
    import math

    from app.strategy_engine.schema.ohlcv import Candle

    n = int(payload.get("_synthetic_candle_count", 500))
    start_ts = datetime(2026, 5, 17, 9, 15, tzinfo=UTC)
    base = 22000.0
    # Period-tunable trend wave that triggers crossover-style logic
    long_period = 80.0
    short_period = 12.0
    # Volatility ramp keeps SL/TP reachable
    candles: list[Candle] = []
    for i in range(n):
        ts = start_ts + timedelta(minutes=5 * i)
        # Long-wave drift (peak-to-peak ~3%) + short wave (peak-to-peak ~0.5%)
        long_wave = math.sin(2 * math.pi * i / long_period) * 300.0
        short_wave = math.sin(2 * math.pi * i / short_period) * 50.0
        # Occasional volatility shock every ~50 bars
        shock = 30.0 if i % 50 == 0 and i > 0 else 0.0
        c = base + long_wave + short_wave + shock
        # Symmetric wick — engine's OHLC invariant must hold
        # (low <= min(open, close) <= max(open, close) <= high)
        prev_close = candles[-1].close if candles else c
        o = prev_close
        h = max(o, c) + abs(short_wave) * 0.1 + 5.0
        l = min(o, c) - abs(short_wave) * 0.1 - 5.0
        candles.append(
            Candle(
                timestamp=ts,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000.0 + (i % 100) * 10,
            )
        )
    return candles


# ─── Core async worker logic ────────────────────────────────────────────


async def _run_backtest_async(run_id: uuid.UUID) -> str:
    """Async worker body. Returns the terminal status string.

    Self-contained — opens its own session via ``get_sessionmaker``
    so the Celery task can call this with ``asyncio.run(...)``.
    """
    sessionmaker = get_sessionmaker()

    # Step 1 — duplicate-dispatch guard
    async with sessionmaker() as session:
        run = await persistence.get_run_by_id(
            session, run_id=run_id, with_metrics=False
        )
        if run is None:
            _logger.warning(
                "backtest.run.dispatch_unknown_id",
                run_id=str(run_id),
            )
            return "UNKNOWN"
        if run.status != BacktestRunStatus.PENDING.value:
            _logger.warning(
                "backtest.run.duplicate_dispatch",
                run_id=str(run_id),
                current_status=run.status,
            )
            return run.status

    # Step 2 — transition PENDING → RUNNING
    async with sessionmaker() as session:
        await persistence.update_status(
            session, run_id=run_id, status=BacktestRunStatus.RUNNING
        )
        await session.commit()
        # Re-fetch a hydrated copy so we have user_id + strategy_id + payload
        run = await persistence.get_run_by_id(
            session, run_id=run_id, with_metrics=False
        )
        assert run is not None  # we just updated it
        user_id = run.user_id
        strategy_id = run.strategy_id
        payload = dict(run.request_payload)

    try:
        # Step 3 — resolve strategy DSL
        async with sessionmaker() as session:
            if strategy_id is None:
                raise StrategyPayloadResolutionError(
                    "Anonymous-config preview not supported in Day 1-3 "
                    "(decision D8). strategy_id is required."
                )
            strategy_json = await _load_strategy_json(
                session, strategy_id=strategy_id, user_id=user_id
            )

        # Step 3.5 — resolve the user's Dhan access token (per-user
        # BrokerCredential pattern; mirrors chart history + live orders).
        async with sessionmaker() as session:
            access_token = await _resolve_dhan_access_token(
                session, user_id=user_id
            )

        # Step 4 — fetch real candles via data_provider, then call the
        # engine. Provider's internal 3-attempt retry handles 429/5xx
        # transient failures; we do NOT add a Celery-level retry layer.
        candles = _fetch_real_candles(payload, access_token=access_token)
        cost_settings = CostSettings.model_validate(
            payload.get("cost_settings", {})
        )
        ambiguity_mode = AmbiguityMode(
            payload.get("ambiguity_mode", AmbiguityMode.CONSERVATIVE.value)
        )
        bt_input = BacktestInput(
            candles=candles,
            strategy=strategy_json,
            initial_capital=payload.get("initial_capital", 100_000.0),
            quantity=payload.get("quantity", 1.0),
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )
        result = run_backtest(bt_input)

        # Step 5 — persist + transition RUNNING → SUCCEEDED
        async with sessionmaker() as session:
            await persistence.save_trades(
                session, run_id=run_id, trades=list(result.trades)
            )
            await persistence.save_metrics(
                session, run_id=run_id, result=result
            )
            await persistence.update_status(
                session,
                run_id=run_id,
                status=BacktestRunStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )
            await session.commit()

        # Step 5.5 — write chart-marker rows (Queue DD). Best-effort:
        # marker persistence is read-only enrichment for the chart
        # overlay; failure must NOT fail the backtest task. The Celery
        # worker has already transitioned RUNNING → SUCCEEDED above.
        try:
            assert strategy_id is not None  # narrowed above for step 3
            async with sessionmaker() as session:
                marker_count = await persist_backtest_trade_markers(
                    session,
                    backtest_run_id=run_id,
                    strategy_id=strategy_id,
                    user_id=user_id,
                    symbol=str(payload.get("symbol", "NIFTY")),
                    exchange=str(payload.get("exchange", "NSE")),
                    trades=list(result.trades),
                )
                await session.commit()
            _logger.info(
                "backtest.markers.persist_completed",
                run_id=str(run_id),
                strategy_id=str(strategy_id),
                marker_count=marker_count,
            )
        except Exception as marker_exc:  # noqa: BLE001
            _logger.error(
                "backtest.markers.persist_failed",
                run_id=str(run_id),
                strategy_id=str(strategy_id) if strategy_id else None,
                error_class=type(marker_exc).__name__,
                error_message=str(marker_exc)[:300],
            )

        _logger.info(
            "backtest.run.completed",
            run_id=str(run_id),
            user_id=str(user_id),
            total_trades=result.total_trades,
        )
        # Day 5: release the concurrent slot acquired by the API
        # rate-limit dep. Best-effort — failures don't block return.
        await _release_rate_limit_slot(user_id)
        return BacktestRunStatus.SUCCEEDED.value

    except Exception as exc:  # noqa: BLE001 — terminal-state capture
        error_payload = _build_error_payload(exc)
        async with sessionmaker() as session:
            try:
                await persistence.update_status(
                    session,
                    run_id=run_id,
                    status=BacktestRunStatus.FAILED,
                    completed_at=datetime.now(UTC),
                    error=error_payload,
                )
                await session.commit()
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "backtest.run.persist_failure_after_engine_error",
                    run_id=str(run_id),
                )
                # The original error is the diagnostic one to surface.

        _logger.error(
            "backtest.run.failed",
            run_id=str(run_id),
            user_id=str(user_id),
            error_type=error_payload["type"],
            error_message=error_payload["message"],
        )
        # Day 5: release on terminal failure too
        await _release_rate_limit_slot(user_id)
        return BacktestRunStatus.FAILED.value


async def _release_rate_limit_slot(user_id: uuid.UUID) -> None:
    """Best-effort release of the per-user concurrent slot. Failures
    are logged and swallowed — a leaked slot self-recovers via the
    1-hour TTL set by ``acquire_concurrent_slot``."""
    try:
        # Lazy import — avoids dragging Redis into modules that just
        # want to run the engine without rate-limit infra (e.g. tests).
        from app.backtest_extension.rate_limit import release_concurrent_slot

        await release_concurrent_slot(user_id)
    except Exception:  # noqa: BLE001
        _logger.warning(
            "backtest.run.rate_limit_release_failed",
            user_id=str(user_id),
        )


# ─── Celery entry point ─────────────────────────────────────────────────


@shared_task(
    name="app.backtest_extension.run_backtest_task",
    bind=False,
    max_retries=0,
    acks_late=True,
)
def run_backtest_task(run_id: str) -> str:
    """Celery entry point. Returns the terminal status as a string
    (``"SUCCEEDED" | "FAILED" | "UNKNOWN" | "PENDING"`` etc) so worker
    logs / monitoring can ingest the result without joining DB.

    Idempotent on dispatch: a second call for the same run_id while
    ``status != PENDING`` is a no-op.
    """
    return asyncio.run(_run_backtest_async(uuid.UUID(run_id)))


__all__ = [
    "BACKTEST_QUEUE",
    "NoBrokerCredentialError",
    "NoDataError",
    "StrategyPayloadResolutionError",
    "run_backtest_task",
]
