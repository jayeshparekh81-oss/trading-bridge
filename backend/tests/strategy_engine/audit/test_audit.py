"""Audit log tests.

Pure-function coverage for the in-memory audit emitter. Each test
clears the buffer up front so order between tests is irrelevant; the
ring buffer test additionally rebuilds from empty so eviction
behavior is exercised in isolation.
"""

from __future__ import annotations

import ast
import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.strategy_engine.audit import (
    AuditEvent,
    clear_audit_log,
    emit_event,
    query_events,
)
from app.strategy_engine.audit.constants import MAX_EVENTS_IN_MEMORY
from app.strategy_engine.audit.loggers import (
    log_ai_suggestion,
    log_backtest_run,
    log_kill_switch_event,
    log_live_order_attempt,
    log_paper_trade,
    log_pine_import,
    log_risk_block,
    log_strategy_change,
)


@pytest.fixture(autouse=True)
def _isolated_audit_log() -> Generator[None, None, None]:
    """Reset the module-level buffer before *and* after every test so
    one test never leaks events into another."""
    clear_audit_log()
    yield
    clear_audit_log()


# ─── 1. emit_event creates a valid AuditEvent ─────────────────────────


def test_emit_event_creates_event_with_uuid_and_utc_timestamp() -> None:
    before = datetime.now(UTC)
    event = emit_event(
        event_type="strategy_created",
        actor="user",
        summary="Created strategy X",
        user_id=uuid4(),
        strategy_id=uuid4(),
    )
    after = datetime.now(UTC)

    assert isinstance(event, AuditEvent)
    assert isinstance(event.event_id, UUID)
    assert event.event_id.version == 4
    assert event.timestamp.tzinfo is not None
    assert event.timestamp.utcoffset() == timedelta(0)
    assert before <= event.timestamp <= after
    assert event.event_type == "strategy_created"
    assert event.actor == "user"
    assert event.severity == "info"
    assert event.summary == "Created strategy X"
    assert event.metadata == {}


# ─── 2. query_events with no filters returns everything ───────────────


def test_query_events_returns_all_when_no_filters() -> None:
    for i in range(5):
        emit_event(
            event_type="strategy_created",
            actor="user",
            summary=f"event-{i}",
        )
    result = query_events()
    assert result.total_count == 5
    assert result.filtered_count == 5
    assert len(result.events) == 5
    assert [e.summary for e in result.events] == [f"event-{i}" for i in range(5)]


# ─── 3. Filter by user_id ─────────────────────────────────────────────


def test_query_events_filters_by_user_id() -> None:
    user_a = uuid4()
    user_b = uuid4()
    emit_event(event_type="strategy_created", actor="user", summary="a1", user_id=user_a)
    emit_event(event_type="strategy_created", actor="user", summary="b1", user_id=user_b)
    emit_event(event_type="strategy_created", actor="user", summary="a2", user_id=user_a)

    result = query_events(user_id=user_a)
    assert result.total_count == 3
    assert result.filtered_count == 2
    assert {e.summary for e in result.events} == {"a1", "a2"}


# ─── 4. Filter by strategy_id ─────────────────────────────────────────


def test_query_events_filters_by_strategy_id() -> None:
    strat_a = uuid4()
    strat_b = uuid4()
    emit_event(event_type="backtest_run", actor="user", summary="ba", strategy_id=strat_a)
    emit_event(event_type="backtest_run", actor="user", summary="bb", strategy_id=strat_b)
    result = query_events(strategy_id=strat_a)
    assert result.filtered_count == 1
    assert result.events[0].summary == "ba"


# ─── 5. Filter by event_type ──────────────────────────────────────────


def test_query_events_filters_by_event_type() -> None:
    emit_event(event_type="strategy_created", actor="user", summary="c")
    emit_event(event_type="strategy_updated", actor="user", summary="u")
    emit_event(event_type="strategy_deleted", actor="user", summary="d")

    result = query_events(event_type="strategy_updated")
    assert result.filtered_count == 1
    assert result.events[0].event_type == "strategy_updated"


# ─── 6. Filter by severity (auto-promotion respected) ─────────────────


def test_query_events_filters_by_severity() -> None:
    emit_event(event_type="strategy_created", actor="user", summary="ok")
    # risk_block is auto-promoted to critical regardless of requested severity.
    emit_event(
        event_type="risk_block",
        actor="broker_guard",
        summary="blocked",
        severity="info",
    )
    emit_event(
        event_type="ai_suggestion_rejected",
        actor="user",
        summary="rejected",
        severity="info",
    )

    critical = query_events(severity="critical")
    assert critical.filtered_count == 1
    assert critical.events[0].event_type == "risk_block"

    warnings = query_events(severity="warning")
    assert warnings.filtered_count == 1
    assert warnings.events[0].event_type == "ai_suggestion_rejected"

    infos = query_events(severity="info")
    assert infos.filtered_count == 1
    assert infos.events[0].event_type == "strategy_created"


# ─── 7. Time-range filtering (since/until inclusive) ──────────────────


def test_query_events_time_range_filtering() -> None:
    e1 = emit_event(event_type="strategy_created", actor="user", summary="t1")
    # Tiny pause so timestamps differ — datetime.now is monotonic on
    # macOS/Linux at microsecond resolution but a sleep makes the
    # ordering robust to any kernel weirdness.
    e2 = emit_event(event_type="strategy_created", actor="user", summary="t2")
    emit_event(event_type="strategy_created", actor="user", summary="t3")

    # since == e2.timestamp → e2 and e3 only.
    after_e1 = query_events(since=e2.timestamp)
    assert {e.summary for e in after_e1.events} == {"t2", "t3"}

    # until == e2.timestamp → e1 and e2 only.
    upto_e2 = query_events(until=e2.timestamp)
    assert {e.summary for e in upto_e2.events} == {"t1", "t2"}

    # window strictly around e2.
    middle = query_events(since=e2.timestamp, until=e2.timestamp)
    assert {e.summary for e in middle.events} == {"t2"}

    # Sanity: hard before-e1 returns nothing.
    before_all = query_events(until=e1.timestamp - timedelta(seconds=1))
    assert before_all.filtered_count == 0
    assert before_all.total_count == 3


# ─── 8. Ring buffer caps and evicts oldest ────────────────────────────


def test_ring_buffer_caps_and_evicts_oldest() -> None:
    """Sanity-check eviction without paying for 10k events: append a
    couple past capacity and confirm the oldest two are dropped."""
    for i in range(MAX_EVENTS_IN_MEMORY + 2):
        emit_event(
            event_type="strategy_created",
            actor="user",
            summary=f"e-{i}",
        )
    result = query_events(limit=MAX_EVENTS_IN_MEMORY)
    assert result.total_count == MAX_EVENTS_IN_MEMORY
    assert result.filtered_count == MAX_EVENTS_IN_MEMORY
    summaries = [e.summary for e in result.events]
    # Oldest two ("e-0", "e-1") were evicted; newest two are present.
    assert "e-0" not in summaries
    assert "e-1" not in summaries
    assert summaries[-1] == f"e-{MAX_EVENTS_IN_MEMORY + 1}"


# ─── 9. Thread-safety: concurrent emits don't lose events ─────────────


def test_concurrent_emits_do_not_lose_events() -> None:
    n_threads = 20
    per_thread = 5  # 100 total emits.

    def worker(idx: int) -> None:
        for j in range(per_thread):
            emit_event(
                event_type="strategy_created",
                actor="user",
                summary=f"t{idx}-{j}",
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result = query_events(limit=n_threads * per_thread)
    assert result.total_count == n_threads * per_thread
    # Every (thread, index) pair must be present exactly once.
    expected = {f"t{i}-{j}" for i in range(n_threads) for j in range(per_thread)}
    assert {e.summary for e in result.events} == expected
    # Every emitted event must have a unique event_id.
    assert len({e.event_id for e in result.events}) == n_threads * per_thread


# ─── 10. log_risk_block sets severity=critical ────────────────────────


def test_log_risk_block_sets_severity_critical() -> None:
    event = log_risk_block(
        strategy_id=uuid4(),
        user_id=uuid4(),
        reason="position_limit_exceeded",
    )
    assert event.severity == "critical"
    assert event.event_type == "risk_block"
    assert event.actor == "broker_guard"
    assert event.metadata["reason"] == "position_limit_exceeded"


# ─── 11. log_pine_import includes license_status in metadata ──────────


def test_log_pine_import_includes_license_status() -> None:
    event = log_pine_import(
        user_id=uuid4(),
        success=True,
        license_status="open_source",
        metadata={"script_name": "MyEMA"},
    )
    assert event.event_type == "pine_import"
    assert event.metadata["license_status"] == "open_source"
    assert event.metadata["success"] is True
    assert event.metadata["script_name"] == "MyEMA"


# ─── 12. AST inspection: no forbidden imports ─────────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "app.services",
    "app.brokers",
    "app.db",
    "sqlalchemy",
    "openai",
    "anthropic",
    "httpx",
    "requests",
)


def _audit_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "audit"
    return sorted(p for p in pkg_root.glob("*.py"))


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


@pytest.mark.parametrize("source_file", _audit_python_files())
def test_audit_module_does_not_import_forbidden_modules(source_file: Path) -> None:
    """Walk every import in every audit *.py file and assert it does
    not pull in DB, ORM, broker SDKs, LLM SDKs, or HTTP libraries.
    The audit log is, by design, a pure stdlib module."""
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


# ─── 13. Determinism: same input → same shape (modulo uuid/ts) ────────


def test_emit_event_is_deterministic_in_shape() -> None:
    """Two identical calls produce events whose ``event_id`` and
    ``timestamp`` differ (by design) but every other field is byte-
    identical. Catches accidental hidden state in the emitter."""
    user = uuid4()
    strategy = uuid4()
    a = emit_event(
        event_type="backtest_run",
        actor="user",
        summary="run",
        severity="info",
        user_id=user,
        strategy_id=strategy,
        metadata={"k": "v"},
    )
    b = emit_event(
        event_type="backtest_run",
        actor="user",
        summary="run",
        severity="info",
        user_id=user,
        strategy_id=strategy,
        metadata={"k": "v"},
    )
    assert a.event_id != b.event_id  # uuid4 collision essentially impossible.
    # Timestamps may differ; only require monotonicity.
    assert a.timestamp <= b.timestamp
    # Every other field is stable.
    for field in ("event_type", "severity", "user_id", "strategy_id", "actor", "summary"):
        assert getattr(a, field) == getattr(b, field), field
    assert a.metadata == b.metadata


# ─── 14. clear_audit_log resets state ─────────────────────────────────


def test_clear_audit_log_resets_state() -> None:
    emit_event(event_type="strategy_created", actor="user", summary="x")
    assert query_events().total_count == 1
    clear_audit_log()
    result = query_events()
    assert result.total_count == 0
    assert result.filtered_count == 0
    assert result.events == ()


# ─── 15. Auto severity mapping (live_order_blocked, kill_switch) ──────


def test_critical_event_types_force_severity_critical() -> None:
    """Even if the caller passes severity='info', live_order_blocked
    and kill_switch_triggered are recorded as critical."""
    a = emit_event(
        event_type="live_order_blocked",
        actor="broker_guard",
        summary="blocked",
        severity="info",
    )
    b = emit_event(
        event_type="kill_switch_triggered",
        actor="kill_switch",
        summary="trip",
        severity="info",
    )
    assert a.severity == "critical"
    assert b.severity == "critical"


# ─── 16. log_paper_trade — close with negative pnl is warning ─────────


def test_log_paper_trade_negative_close_is_warning() -> None:
    losing_close = log_paper_trade(strategy_id=uuid4(), user_id=uuid4(), action="close", pnl=-25.0)
    winning_close = log_paper_trade(strategy_id=uuid4(), user_id=uuid4(), action="close", pnl=25.0)
    open_event = log_paper_trade(strategy_id=uuid4(), user_id=uuid4(), action="open", pnl=0.0)
    assert losing_close.severity == "warning"
    assert winning_close.severity == "info"
    assert open_event.severity == "info"


# ─── 17. log_live_order_attempt — blocked routes through critical ─────


def test_log_live_order_attempt_blocked_is_critical() -> None:
    allowed = log_live_order_attempt(strategy_id=uuid4(), user_id=uuid4(), allowed=True)
    blocked = log_live_order_attempt(
        strategy_id=uuid4(),
        user_id=uuid4(),
        allowed=False,
        blocking_reasons=["risk_limit", "kill_switch_active"],
    )
    assert allowed.severity == "info"
    assert allowed.event_type == "live_order_attempted"
    assert blocked.severity == "critical"
    assert blocked.event_type == "live_order_blocked"
    assert blocked.metadata["blocking_reasons"] == ["risk_limit", "kill_switch_active"]


# ─── 18. Wrappers cover the remaining loggers ─────────────────────────


def test_log_strategy_change_and_others() -> None:
    sid = uuid4()
    uid = uuid4()
    e_change = log_strategy_change(sid, uid, "updated", "tweaked params")
    assert e_change.event_type == "strategy_updated"
    assert e_change.metadata["change_type"] == "updated"

    e_bt = log_backtest_run(sid, uid, success=False, metadata={"err": "x"})
    assert e_bt.event_type == "backtest_run"
    assert e_bt.severity == "warning"
    assert e_bt.metadata["err"] == "x"
    assert e_bt.metadata["success"] is False

    e_ai = log_ai_suggestion(sid, uid, "trail_stop", accepted=None)
    assert e_ai.event_type == "ai_suggestion"
    assert e_ai.actor == "ai"

    e_ks = log_kill_switch_event(sid, uid, "triggered", "drawdown_breach")
    assert e_ks.severity == "critical"
    assert e_ks.event_type == "kill_switch_triggered"


# ─── 19. Invalid inputs raise ValueError ──────────────────────────────


def test_emit_event_rejects_invalid_event_type() -> None:
    with pytest.raises(ValueError, match="invalid event_type"):
        emit_event(event_type="not_a_real_event", actor="user", summary="x")


def test_emit_event_rejects_invalid_actor() -> None:
    with pytest.raises(ValueError, match="invalid actor"):
        emit_event(event_type="strategy_created", actor="alien", summary="x")


def test_query_events_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="limit must be non-negative"):
        query_events(limit=-1)


# ─── 20. Limit trims to most recent N ─────────────────────────────────


def test_query_events_limit_trims_to_most_recent() -> None:
    for i in range(10):
        emit_event(event_type="strategy_created", actor="user", summary=f"e-{i}")
    result = query_events(limit=3)
    assert result.total_count == 10
    assert result.filtered_count == 10
    assert [e.summary for e in result.events] == ["e-7", "e-8", "e-9"]
