"""Day-6 supervised: real Dhan-fetch integration in the Celery task.

These tests pin the contract between
``app.backtest_extension.celery_tasks`` and
``app.strategy_engine.data_provider.fetch_historical_candles`` —
specifically the new ``_fetch_real_candles`` helper that replaces the
Day-1-3 synthetic stub.

Mocking policy:
    * ``fetch_historical_candles`` is patched at the import site
      (``app.backtest_extension.celery_tasks.fetch_historical_candles``)
      so no Dhan HTTP traffic ever fires.
    * ``_resolve_dhan_access_token`` is patched per-test EXCEPT in the
      no-broker-credential test (which exercises the real DB-backed
      path against the empty test ``broker_credentials`` table).
    * ``run_backtest`` is patched to a deterministic fake result on the
      happy path so engine internals stay untouched by these tests
      (engine has its own dedicated test suite).

Rate-limit retry behaviour is NOT covered here — per founder decision
on Day-6 audit Q1, the data provider's internal 3-attempt retry is the
single source of truth; ``test_dhan_fetch_error`` exercises the
exhaustion case via a raised :class:`DhanFetchError`.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest_extension import celery_tasks, persistence
from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
from app.strategy_engine.data_provider import (
    DhanFetchError,
    HistoricalDataRequest,
    HistoricalDataResponse,
)
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import Side
from tests.backtest_extension.conftest import make_request_payload


# ─── Helpers ───────────────────────────────────────────────────────────


def _build_fake_response(
    *,
    payload: dict,
    candle_count: int = 250,
    quality_warnings: list[str] | None = None,
) -> HistoricalDataResponse:
    """Wrap the existing deterministic synthetic series in a real
    :class:`HistoricalDataResponse` so we drive the new code path
    through realistic data without hitting Dhan."""
    candles = celery_tasks._build_synthetic_candles_payload(
        {"_synthetic_candle_count": candle_count}
    )
    request = HistoricalDataRequest(
        symbol=payload.get("symbol", "NIFTY"),
        timeframe=payload.get("timeframe", "5m"),
        from_date=datetime.fromisoformat(payload["start"]),
        to_date=datetime.fromisoformat(payload["end"]),
    )
    return HistoricalDataResponse(
        candles=candles,
        request=request,
        fetched_at=datetime.now(UTC),
        cache_hit=False,
        quality_warnings=list(quality_warnings or []),
    )


def _empty_response(payload: dict) -> HistoricalDataResponse:
    request = HistoricalDataRequest(
        symbol=payload.get("symbol", "NIFTY"),
        timeframe=payload.get("timeframe", "5m"),
        from_date=datetime.fromisoformat(payload["start"]),
        to_date=datetime.fromisoformat(payload["end"]),
    )
    return HistoricalDataResponse(
        candles=[],
        request=request,
        fetched_at=datetime.now(UTC),
        cache_hit=False,
        quality_warnings=["Empty candle stream returned by Dhan."],
    )


def _fake_result(*, total_trades: int = 2) -> BacktestResult:
    """Same shape as ``test_celery_tasks._fake_result`` — duplicated
    here so the Day-6 tests stay self-contained."""
    trades = [
        Trade(
            entry_time=datetime(2026, 5, 1, 9, 30, tzinfo=UTC),
            exit_time=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
            side=Side.BUY,
            entry_price=22000.0 + i,
            exit_price=22100.0 + i,
            quantity=1.0,
            pnl=100.0,
            exit_reason="target_hit",
            entry_reasons=("ema",),
        )
        for i in range(total_trades)
    ]
    equity = [
        EquityPoint(
            timestamp=datetime(2026, 5, 1, 9, 30, tzinfo=UTC)
            + timedelta(minutes=5 * i),
            equity=100_000.0 + i * 100.0,
        )
        for i in range(3)
    ]
    return BacktestResult(
        total_pnl=100.0 * total_trades,
        total_return_percent=0.1 * total_trades,
        win_rate=1.0,
        loss_rate=0.0,
        total_trades=total_trades,
        average_win=100.0,
        average_loss=0.0,
        largest_win=100.0,
        largest_loss=0.0,
        max_drawdown=0.0,
        profit_factor=math.inf,
        expectancy=100.0,
        equity_curve=equity,
        trades=trades,
        warnings=[],
    )


@pytest.fixture
def patched_sessionmaker(
    db_session_maker: async_sessionmaker[AsyncSession],
):
    with patch(
        "app.backtest_extension.celery_tasks.get_sessionmaker",
        return_value=db_session_maker,
    ):
        yield db_session_maker


# Note: ``patched_token_resolver`` lives in conftest.py as a shared fixture
# (Day-6: extracted so the pre-Day-6 engine + state-machine tests can opt
# into the same per-user-credential mock without duplicating boilerplate).


# ─── Test 1: Happy path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_real_fetch_succeeds(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    seed_user,
    seed_strategy,
) -> None:
    """Mock returns realistic 250-bar NIFTY response → run completes
    → metrics + trades persisted → status=SUCCEEDED."""
    payload = make_request_payload(symbol="NIFTY")
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6happy" + "a" * 57,
            engine_version="v1",
        )
        await session.commit()

    fake_response = _build_fake_response(payload=payload, candle_count=250)

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
        return_value=fake_response,
    ) as mock_fetch, patch(
        "app.backtest_extension.celery_tasks.run_backtest",
        return_value=_fake_result(total_trades=3),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "SUCCEEDED"
    assert mock_fetch.call_count == 1
    # Captured request shape — pins the BacktestInput → fetch mapping.
    captured_req = mock_fetch.call_args.args[0]
    assert isinstance(captured_req, HistoricalDataRequest)
    assert captured_req.symbol == "NIFTY"
    assert captured_req.timeframe == "5m"
    # Token threaded through as kwarg.
    assert mock_fetch.call_args.kwargs.get("access_token") == "fake-encrypted-dhan-token"

    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(
            session, run_id=run.id, with_metrics=True
        )
        assert final is not None
        assert final.status == "SUCCEEDED"
        assert final.error_json is None
        assert final.metrics is not None
        assert final.metrics.total_trades == 3


# ─── Test 2: Empty response → no_data_available ─────────────────────────


@pytest.mark.asyncio
async def test_empty_response_lands_failed_no_data(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    seed_user,
    seed_strategy,
) -> None:
    """Provider returns candles=[] (empty stream warning) →
    FAILED with error_json.message starting with 'no_data_available'."""
    payload = make_request_payload()
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6empt" + "b" * 58,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
        return_value=_empty_response(payload),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json is not None
        assert final.error_json["type"] == "NoDataError"
        assert final.error_json["message"].startswith("no_data_available")
        # Engine never ran → no metrics row
        assert final.metrics is None


# ─── Test 3: DhanFetchError (provider's retries exhausted) ──────────────


@pytest.mark.asyncio
async def test_dhan_fetch_error_lands_failed_fetch_failed(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    seed_user,
    seed_strategy,
) -> None:
    """Provider raises DhanFetchError(status_code=502) — represents the
    *post-retry* exhaustion case → FAILED with 'fetch_failed:' prefix.

    Per Day-6 audit Q1: provider already retries 3 times internally on
    429/5xx; we do not add a second retry layer. This test covers the
    case where those internal retries are exhausted."""
    payload = make_request_payload()
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6fech" + "c" * 58,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
        side_effect=DhanFetchError(
            "Dhan historical fetch exhausted retries (last status 502).",
            status_code=502,
        ),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json is not None
        # The wrapping RuntimeError carries the prefix; type is RuntimeError.
        assert final.error_json["type"] == "RuntimeError"
        msg = final.error_json["message"]
        assert msg.startswith("fetch_failed:")
        assert "status=502" in msg


# ─── Test 4: Invalid symbol → ValueError from _resolve_symbol ───────────


@pytest.mark.asyncio
async def test_invalid_symbol_lands_failed_invalid_symbol(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    seed_user,
    seed_strategy,
) -> None:
    """Provider raises ValueError (symbol not in KNOWN_SYMBOLS) →
    FAILED with 'invalid_symbol:' prefix."""
    payload = make_request_payload(symbol="ZZUNKNOWN")
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6inv0" + "d" * 58,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
        side_effect=ValueError(
            "Symbol 'ZZUNKNOWN' (normalised to 'ZZUNKNOWN') is not in "
            "the bundled KNOWN_SYMBOLS map. Pass security_id, "
            "exchange_segment, and instrument explicitly to bypass."
        ),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json is not None
        assert final.error_json["type"] == "RuntimeError"
        assert final.error_json["message"].startswith("invalid_symbol:")
        assert "ZZUNKNOWN" in final.error_json["message"]


# ─── Test 5: No broker credential → real DB lookup raises ──────────────


@pytest.mark.asyncio
async def test_no_broker_credential_lands_failed(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    seed_user,
    seed_strategy,
) -> None:
    """User has no active Dhan BrokerCredential row → token resolver
    raises NoBrokerCredentialError → FAILED with 'no_broker_credential'
    prefix. fetch_historical_candles should never be called.

    Intentionally does NOT use ``patched_token_resolver`` — exercises
    the real DB-backed credential lookup against the empty test
    ``broker_credentials`` table."""
    payload = make_request_payload()
    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6nocr" + "e" * 58,
            engine_version="v1",
        )
        await session.commit()

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
    ) as mock_fetch:
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "FAILED"
    assert mock_fetch.call_count == 0  # never reached the fetch step
    async with db_session_maker() as session:
        final = await persistence.get_run_by_id(session, run_id=run.id)
        assert final is not None
        assert final.status == "FAILED"
        assert final.error_json is not None
        assert final.error_json["type"] == "NoBrokerCredentialError"
        assert final.error_json["message"].startswith("no_broker_credential")


# ─── Test 6 (bonus): start/end defaulting when absent ──────────────────


@pytest.mark.asyncio
async def test_window_defaulting_when_start_end_absent(
    db_session_maker: async_sessionmaker[AsyncSession],
    patched_sessionmaker,
    patched_token_resolver,
    seed_user,
    seed_strategy,
) -> None:
    """Payload without start/end → fetcher receives a sane default
    window (~60 days ending now). Pins the defaulting contract
    introduced in Day-6 per BacktestEnqueueRequest schema."""
    # Strip start/end the way ``exclude_none=True`` would when the
    # API receives a request with no window override.
    payload = make_request_payload()
    payload.pop("start", None)
    payload.pop("end", None)

    async with db_session_maker() as session:
        run = await persistence.save_run(
            session,
            user_id=seed_user.id,
            strategy_id=seed_strategy.id,
            request_payload=payload,
            request_hash="d6dflt" + "f" * 58,
            engine_version="v1",
        )
        await session.commit()

    captured_request: dict = {}

    def _capture(request, *_args, **_kwargs):
        captured_request["req"] = request
        # Return a realistic response so the task continues to SUCCEEDED.
        return HistoricalDataResponse(
            candles=celery_tasks._build_synthetic_candles_payload(
                {"_synthetic_candle_count": 100}
            ),
            request=request,
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            quality_warnings=[],
        )

    with patch(
        "app.backtest_extension.celery_tasks.fetch_historical_candles",
        side_effect=_capture,
    ), patch(
        "app.backtest_extension.celery_tasks.run_backtest",
        return_value=_fake_result(total_trades=1),
    ):
        result = await celery_tasks._run_backtest_async(run.id)

    assert result == "SUCCEEDED"
    req = captured_request["req"]
    assert isinstance(req, HistoricalDataRequest)
    # Window spans roughly the default 60 days; tolerate a few seconds
    # of wall-clock drift between _parse_window's now() and the assertion.
    span = req.to_date - req.from_date
    assert timedelta(days=59, hours=23) <= span <= timedelta(days=60, minutes=1)
    # to_date is ~now (within 30 seconds)
    assert abs((datetime.now(UTC) - req.to_date).total_seconds()) < 30
