"""Tests for ``app.tasks.historical_backfill_tasks``.

Coverage strategy:
    * Flag-OFF path (default) — runs without any DB/Dhan touch, so
      these tests run unmodified.
    * Flag-ON path — exercises ``_run_one`` directly with mocks for
      session, jobs_repo, repository, orchestrator. The whole
      ``backfill_one_job`` wrapper is also exercised via Celery's
      eager-mode (skipped if not configured) — but the async body is
      the meaningful target.

The Dhan credential factory `_dhan_client_factory_for_job` is
``# pragma: no cover`` in the source (Phase 3+ follow-up); we don't
target it here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.historical_backfill_tasks import (
    _backfill_enabled,
    _log_disabled,
    _run_one,
    backfill_one_job,
)


# ═══════════════════════════════════════════════════════════════════════
# _backfill_enabled
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("anything", False),
    ],
)
def test_backfill_enabled__truthy_table(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("BACKFILL_ENABLED", raw)
    assert _backfill_enabled() is expected


def test_backfill_enabled__defaults_off_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKFILL_ENABLED", raising=False)
    assert _backfill_enabled() is False


# ═══════════════════════════════════════════════════════════════════════
# _log_disabled
# ═══════════════════════════════════════════════════════════════════════


def test_log_disabled__returns_payload_with_job_id() -> None:
    payload = _log_disabled("abc-123")
    assert payload["status"] == "disabled"
    assert payload["job_id"] == "abc-123"
    assert "BACKFILL_ENABLED" in payload["reason"]


# ═══════════════════════════════════════════════════════════════════════
# backfill_one_job (Celery-wrapped, flag-OFF path)
# ═══════════════════════════════════════════════════════════════════════


def test_backfill_one_job__flag_off_returns_disabled_no_async(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKFILL_ENABLED", raising=False)
    # asyncio.run should NOT be invoked when flag is OFF.
    with patch(
        "app.tasks.historical_backfill_tasks.asyncio.run"
    ) as mock_run:
        result = backfill_one_job("00000000-0000-0000-0000-000000000001")
    assert result["status"] == "disabled"
    mock_run.assert_not_called()


def test_backfill_one_job__flag_on_invokes_async_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKFILL_ENABLED", "true")
    sentinel = {"status": "succeeded", "job_id": "test"}
    with patch(
        "app.tasks.historical_backfill_tasks.asyncio.run",
        return_value=sentinel,
    ) as mock_run:
        result = backfill_one_job("00000000-0000-0000-0000-000000000002")
    assert result == sentinel
    mock_run.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# _run_one (async body) — heavily mocked
# ═══════════════════════════════════════════════════════════════════════


def _job_stub(
    *, status: str = "PENDING", job_id: uuid.UUID | None = None
) -> MagicMock:
    """Stand-in for a HistoricalBackfillJob ORM row."""
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.symbol = "RELIANCE"
    job.exchange = "NSE_EQ"
    job.timeframe = "5m"
    job.dhan_security_id = "2885"
    job.from_ts = datetime(2026, 6, 1, tzinfo=UTC)
    job.to_ts = datetime(2026, 6, 2, tzinfo=UTC)
    job.requested_by_user_id = None
    job.status = status
    return job


def _patch_run_one_dependencies(
    *,
    job=None,
    mark_running_rows: int = 1,
    orchestrator_report=None,
    orchestrator_raises: Exception | None = None,
):
    """Helper context-manager bundle for patching every symbol _run_one
    pulls in. Returns a list of patcher objects so the caller can
    use ``contextlib.ExitStack``.

    The function returns started patches; caller is responsible for
    stopping them.
    """
    raise NotImplementedError  # we inline the patches inside each test


async def test_run_one__job_not_found_returns_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_maker = MagicMock(return_value=mock_session)

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)

    with (
        patch(
            "app.db.session.get_sessionmaker", return_value=mock_maker
        ),
        patch(
            "app.db.session.dispose_engine", new=AsyncMock()
        ),
        patch(
            "app.services.historical_candles.jobs_repository.HistoricalBackfillJobsRepository",
            return_value=mock_repo,
        ),
    ):
        result = await _run_one(str(uuid.uuid4()))

    assert result["status"] == "skipped"
    assert result["reason"] == "job_not_found"


async def test_run_one__concurrent_claim_lost_returns_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _job_stub()
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_maker = MagicMock(return_value=mock_session)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_id = AsyncMock(return_value=job)
    mock_jobs_repo.mark_running = AsyncMock(return_value=0)  # lost race

    with (
        patch(
            "app.db.session.get_sessionmaker", return_value=mock_maker
        ),
        patch(
            "app.db.session.dispose_engine", new=AsyncMock()
        ),
        patch(
            "app.services.historical_candles.jobs_repository.HistoricalBackfillJobsRepository",
            return_value=mock_jobs_repo,
        ),
    ):
        result = await _run_one(str(job.id))

    assert result["status"] == "skipped"
    assert result["reason"] == "concurrent_claim_lost"
    mock_jobs_repo.mark_running.assert_awaited_once()


async def test_run_one__happy_path_marks_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _job_stub()
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_maker = MagicMock(return_value=mock_session)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_id = AsyncMock(return_value=job)
    mock_jobs_repo.mark_running = AsyncMock(return_value=1)
    mock_jobs_repo.mark_succeeded = AsyncMock(return_value=1)
    mock_jobs_repo.mark_failed = AsyncMock(return_value=0)

    mock_orch = MagicMock()
    from app.services.historical_candles.orchestrator import OrchestratorReport

    mock_orch.fetch_and_persist = AsyncMock(
        return_value=OrchestratorReport(
            chunks_requested=1,
            bars_fetched=10,
            bars_inserted=10,
            quality_score_avg=Decimal("0.95"),
        )
    )

    with (
        patch(
            "app.db.session.get_sessionmaker", return_value=mock_maker
        ),
        patch(
            "app.db.session.dispose_engine", new=AsyncMock()
        ),
        patch(
            "app.services.historical_candles.jobs_repository.HistoricalBackfillJobsRepository",
            return_value=mock_jobs_repo,
        ),
        patch(
            "app.services.historical_candles.repository.HistoricalCandleRepository"
        ),
        patch(
            "app.services.historical_candles.orchestrator.HistoricalCandleOrchestrator",
            return_value=mock_orch,
        ),
    ):
        result = await _run_one(str(job.id))

    assert result["status"] == "succeeded"
    assert result["bars_inserted"] == 10
    assert result["bars_fetched"] == 10
    mock_jobs_repo.mark_succeeded.assert_awaited_once()
    mock_jobs_repo.mark_failed.assert_not_called()


async def test_run_one__orchestrator_raises_marks_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _job_stub()
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_maker = MagicMock(return_value=mock_session)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_id = AsyncMock(return_value=job)
    mock_jobs_repo.mark_running = AsyncMock(return_value=1)
    mock_jobs_repo.mark_succeeded = AsyncMock()
    mock_jobs_repo.mark_failed = AsyncMock(return_value=1)

    class _SimulatedError(RuntimeError):
        pass

    mock_orch = MagicMock()
    mock_orch.fetch_and_persist = AsyncMock(
        side_effect=_SimulatedError("Dhan 429")
    )

    with (
        patch(
            "app.db.session.get_sessionmaker", return_value=mock_maker
        ),
        patch(
            "app.db.session.dispose_engine", new=AsyncMock()
        ),
        patch(
            "app.services.historical_candles.jobs_repository.HistoricalBackfillJobsRepository",
            return_value=mock_jobs_repo,
        ),
        patch(
            "app.services.historical_candles.repository.HistoricalCandleRepository"
        ),
        patch(
            "app.services.historical_candles.orchestrator.HistoricalCandleOrchestrator",
            return_value=mock_orch,
        ),
    ):
        result = await _run_one(str(job.id))

    assert result["status"] == "failed"
    assert result["error_type"] == "_SimulatedError"
    mock_jobs_repo.mark_failed.assert_awaited_once()
    err_kwargs = mock_jobs_repo.mark_failed.call_args.kwargs
    assert err_kwargs["error"]["type"] == "_SimulatedError"
    assert "Dhan 429" in err_kwargs["error"]["message"]
