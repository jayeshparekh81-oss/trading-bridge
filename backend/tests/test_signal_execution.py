"""Bug #2 — unit tests for the signal-execution Celery task wrapper.

Lives at ``tests/test_signal_execution.py`` (NOT under ``tests/integration``)
so it doesn't depend on the integration suite's aiosqlite-backed
``Base.metadata.create_all`` fixture — these tests only exercise the
dispatch surface + task-wrapper guarantees, which need neither a DB
session nor a real Redis.

End-to-end coverage (webhook → dispatch → eager worker → DB) lives in
``tests/integration/test_strategy_webhook_async.py``.
"""

from __future__ import annotations

import uuid

import pytest

from app.tasks import signal_execution
from app.tasks.celery_app import celery_app


@pytest.fixture(autouse=True)
def _celery_eager() -> None:
    """Run tasks synchronously in-process. ``.apply()`` is unconditionally
    sync; this is belt-and-braces so ``.delay()`` would also work."""
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


# ═══════════════════════════════════════════════════════════════════════
# dispatch_signal — input validation
# ═══════════════════════════════════════════════════════════════════════


class TestDispatchSignalValidation:
    def test_rejects_unknown_action_kind(self) -> None:
        """Misrouted callers (wrong tag) should fail loudly, not enqueue a
        worker task that the worker then has to error-handle."""
        with pytest.raises(ValueError, match="action_kind must be one of"):
            signal_execution.dispatch_signal(str(uuid.uuid4()), "garbage")

    def test_accepts_all_four_canonical_action_kinds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The webhook is the only caller and only ever passes these four."""
        captured: list[tuple[str, str]] = []

        class _FakeTask:
            def delay(self, sid: str, kind: str) -> None:
                captured.append((sid, kind))

        monkeypatch.setattr(
            signal_execution, "execute_signal_async", _FakeTask()
        )

        sid = str(uuid.uuid4())
        for kind in (
            signal_execution.ACTION_ENTRY,
            signal_execution.ACTION_PARTIAL,
            signal_execution.ACTION_EXIT,
            signal_execution.ACTION_SL_HIT,
        ):
            signal_execution.dispatch_signal(sid, kind)

        assert captured == [
            (sid, signal_execution.ACTION_ENTRY),
            (sid, signal_execution.ACTION_PARTIAL),
            (sid, signal_execution.ACTION_EXIT),
            (sid, signal_execution.ACTION_SL_HIT),
        ]


# ═══════════════════════════════════════════════════════════════════════
# execute_signal_async — task wrapper behaviour
# ═══════════════════════════════════════════════════════════════════════


class TestExecuteSignalAsyncWrapper:
    def test_bad_action_kind_returns_error_dict_not_raise(self) -> None:
        """A bad action_kind is a permanent, structural failure — there's
        no recovery on retry. The task wrapper must return an error dict
        rather than raise (which would trigger Celery's retry loop and
        burn 3× the worker time before giving up)."""
        result = signal_execution.execute_signal_async.apply(
            args=(str(uuid.uuid4()), "not-a-real-kind")
        ).get()
        assert result["status"] == "error"
        assert "invalid action_kind" in result["reason"]

    def test_missing_signal_row_resolves_cleanly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the StrategySignal row was deleted between webhook ack and
        worker pickup (manual ops, GDPR purge, …), the worker should log
        and exit cleanly — NOT retry until max-retries is exhausted."""

        async def _noop() -> None:
            return None

        async def _process_entry_stub(signal_id: str) -> None:
            # Simulate the real ``_process_entry`` short-circuit: the
            # session.get(StrategySignal, ...) returns None and the
            # function logs + returns without raising.
            return None

        monkeypatch.setattr(
            signal_execution, "_process_entry", _process_entry_stub
        )

        result = signal_execution.execute_signal_async.apply(
            args=(str(uuid.uuid4()), signal_execution.ACTION_ENTRY)
        ).get()
        assert result["status"] == "ok"

    def test_permanent_python_errors_do_not_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ValueError / TypeError / KeyError are structural — retrying
        won't help. The wrapper should return an error dict instead of
        raising into Celery's retry machinery."""

        async def _raise_value_error(signal_id: str) -> None:
            raise ValueError("permanent — bad data")

        monkeypatch.setattr(
            signal_execution, "_process_entry", _raise_value_error
        )

        result = signal_execution.execute_signal_async.apply(
            args=(str(uuid.uuid4()), signal_execution.ACTION_ENTRY)
        ).get()
        assert result == {"status": "error", "reason": "permanent — bad data"}

    def test_action_kinds_route_to_correct_coroutine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENTRY goes to ``_process_entry``; PARTIAL / EXIT / SL_HIT all go
        to ``_process_direct_exit`` (which then branches internally on
        ``leg_role``). This test pins the dispatch table so a future
        refactor can't silently route an ENTRY through the direct-exit
        path (which would skip AI validation — a safety regression)."""

        entry_calls: list[str] = []
        direct_calls: list[tuple[str, str]] = []

        async def _entry_stub(signal_id: str) -> None:
            entry_calls.append(signal_id)

        async def _direct_stub(signal_id: str, action_kind: str) -> None:
            direct_calls.append((signal_id, action_kind))

        monkeypatch.setattr(signal_execution, "_process_entry", _entry_stub)
        monkeypatch.setattr(
            signal_execution, "_process_direct_exit", _direct_stub
        )

        sid_entry = str(uuid.uuid4())
        sid_partial = str(uuid.uuid4())
        sid_exit = str(uuid.uuid4())
        sid_sl = str(uuid.uuid4())

        signal_execution.execute_signal_async.apply(
            args=(sid_entry, signal_execution.ACTION_ENTRY)
        ).get()
        signal_execution.execute_signal_async.apply(
            args=(sid_partial, signal_execution.ACTION_PARTIAL)
        ).get()
        signal_execution.execute_signal_async.apply(
            args=(sid_exit, signal_execution.ACTION_EXIT)
        ).get()
        signal_execution.execute_signal_async.apply(
            args=(sid_sl, signal_execution.ACTION_SL_HIT)
        ).get()

        assert entry_calls == [sid_entry], (
            "ENTRY must route to _process_entry (AI validator path); "
            "any other route would skip AI validation"
        )
        assert direct_calls == [
            (sid_partial, signal_execution.ACTION_PARTIAL),
            (sid_exit, signal_execution.ACTION_EXIT),
            (sid_sl, signal_execution.ACTION_SL_HIT),
        ]


# ═══════════════════════════════════════════════════════════════════════
# Module surface — guard against silent removal of public names
# ═══════════════════════════════════════════════════════════════════════


class TestModuleSurface:
    def test_required_action_constants_exported(self) -> None:
        """The webhook imports these by name; renames must be explicit."""
        assert signal_execution.ACTION_ENTRY == "entry"
        assert signal_execution.ACTION_PARTIAL == "partial"
        assert signal_execution.ACTION_EXIT == "exit"
        assert signal_execution.ACTION_SL_HIT == "sl_hit"

    def test_celery_task_registered_under_canonical_name(self) -> None:
        """Workers across restarts need a stable task name — never rely on
        the function module path (a rename would silently break in-flight
        queue entries)."""
        assert (
            signal_execution.execute_signal_async.name
            == "app.tasks.signal_execution.execute_signal_async"
        )
