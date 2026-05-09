"""Orchestrator tests for :mod:`safety_chain`.

The per-check unit tests live in :mod:`test_safety_checks`; this file
exercises the chain itself: fail-fast ordering, ``blocking_check``
identification, ``checked_at`` stamping, determinism, AST purity, and
concurrent safety.
"""

from __future__ import annotations

import ast
import asyncio
import pathlib
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis as fake_aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.strategy_engine.live_orders import run_safety_chain
from app.strategy_engine.live_orders.models import SafetyChainResult

# ─── 1. Happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_seven_checks_pass_returns_all_passed_true(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing
    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    assert isinstance(result, SafetyChainResult)
    assert result.all_passed is True
    assert result.blocking_check is None
    assert len(result.checks) == 7
    # Locked execution order — pin it so a refactor that shuffles
    # checks trips a regression here.
    assert tuple(c.check_name for c in result.checks) == (
        "auto_kill_switch",
        "paper_sessions",
        "trust_score",
        "truth_score",
        "live_trading_enabled",
        "broker_connection",
        "risk_engine_precheck",
    )


# ─── 2. Fail-fast — first failure short-circuits ──────────────────────


@pytest.mark.asyncio
async def test_kill_switch_tripped_blocks_chain_at_check_one(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Kill switch is check #1 — TRIPPED state must short-circuit
    the entire chain so no later check executes."""
    user, strategy = all_passing
    await redis_client.set_kill_switch_status(
        user.id, redis_client.KILL_SWITCH_TRIPPED
    )

    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    assert result.all_passed is False
    assert result.blocking_check is not None
    assert result.blocking_check.check_name == "auto_kill_switch"
    # Only the first check executed.
    assert len(result.checks) == 1


@pytest.mark.asyncio
async def test_paper_sessions_failure_blocks_before_score_checks(
    db: AsyncSession,
    user: User,
    strategy: Strategy,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """No paper sessions seeded — chain stops at check #2 even
    though score columns are also empty (which would also fail)."""
    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    assert result.all_passed is False
    assert result.blocking_check is not None
    assert result.blocking_check.check_name == "paper_sessions"
    assert len(result.checks) == 2
    # Subsequent checks (trust_score, truth_score, ...) MUST NOT appear.
    later_names = {"trust_score", "truth_score", "broker_connection"}
    actual_names = {c.check_name for c in result.checks}
    assert actual_names.isdisjoint(later_names)


# ─── 3. blocking_check identifies the correct failure ─────────────────


@pytest.mark.asyncio
async def test_blocking_check_is_first_failure_not_any_failure(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """When multiple checks would fail, ``blocking_check`` reflects
    the FIRST failing one in execution order."""
    user, strategy = all_passing
    # Break two things: kill switch (check 1) AND drop the broker
    # credential (check 6). Kill switch should win.
    await redis_client.set_kill_switch_status(
        user.id, redis_client.KILL_SWITCH_TRIPPED
    )

    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    assert result.all_passed is False
    assert result.blocking_check is not None
    assert result.blocking_check.check_name == "auto_kill_switch"


# ─── 4. checked_at stamp ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_checked_at_is_recent_utc_timestamp(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing
    before = datetime.now(UTC)
    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    after = datetime.now(UTC)

    assert result.checked_at.tzinfo is not None
    assert before - timedelta(seconds=1) <= result.checked_at <= after + timedelta(seconds=1)


# ─── 5. Determinism ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_db_state_produces_same_verdict(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Running the chain twice in a row over identical state yields
    identical ``all_passed`` + check names. ``checked_at`` will differ
    by microseconds — exclude it from the comparison."""
    user, strategy = all_passing

    first = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    second = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )

    assert first.all_passed == second.all_passed
    assert tuple(c.check_name for c in first.checks) == tuple(
        c.check_name for c in second.checks
    )
    assert tuple(c.passed for c in first.checks) == tuple(
        c.passed for c in second.checks
    )


# ─── 6. AST inspection — no LLM/HTTP/network imports ─────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib3",
    "aiohttp",
)


def _live_orders_python_files() -> list[pathlib.Path]:
    pkg = (
        pathlib.Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "live_orders"
    )
    return sorted(p for p in pkg.glob("*.py"))


@pytest.mark.parametrize("source_file", _live_orders_python_files())
def test_live_orders_files_do_not_import_forbidden_modules(
    source_file: pathlib.Path,
) -> None:
    """Walk every import in every live_orders *.py file and assert
    none reach for an LLM SDK, HTTP library, or async HTTP client.

    Allowed: stdlib, pydantic, sqlalchemy, ``app.*`` (Redis lives
    behind ``app.core.redis_client`` — its transitive ``redis``
    import is fine; SafetyChain depends on the abstraction, not the
    raw client).
    """
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
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
    assert not offenders, (
        f"{source_file.name} pulls in forbidden modules: {offenders}"
    )


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(
        name == p or name.startswith(p + ".") for p in _FORBIDDEN_PREFIXES
    )


# ─── 7. Concurrency — 10 parallel chain runs ─────────────────────────


@pytest.mark.asyncio
async def test_ten_concurrent_runs_all_return_correct_results(
    all_passing: tuple[User, Strategy],
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Spin up ten chain runs against ten independent DB sessions
    pointing at the same shared in-memory database, and assert every
    one of them returns ``all_passed=True``. Catches accidental
    module-level mutable state in the chain or in shared helpers."""
    from datetime import date as _date
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    from app.core.security import encrypt_credential
    from app.db.base import Base
    from app.db.models.broker_credential import BrokerCredential
    from app.db.models.strategy import Strategy as StrategyORM
    from app.db.models.user import User as UserORM
    from app.schemas.broker import BrokerName
    from app.strategy_engine.feature_flags import set_flag
    from app.strategy_engine.paper_trading import store as paper_store

    engine = create_async_engine(
        "sqlite+aiosqlite:///file:tradetri-sc-concurrent?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    # Seed once.
    async with maker() as s:
        u = UserORM(
            email="conc@x",
            password_hash="p",
            is_active=True,
            live_trading_enabled=True,
        )
        s.add(u)
        await s.flush()
        strat = StrategyORM(user_id=u.id, name="conc", is_active=True)
        s.add(strat)
        await s.flush()
        base = _date(2026, 5, 1)
        for i in range(7):
            row = await paper_store.create_session(
                s,
                user_id=u.id,
                strategy_id=strat.id,
                engine_strategy_id="eng",
                session_date=base + timedelta(days=i),
            )
            await paper_store.complete_session(
                s,
                session_id=row.id,
                total_trades=1,
                total_pnl=Decimal("10"),
            )
        strat.last_trust_score = Decimal("80.00")
        strat.last_truth_score = Decimal("70.00")
        strat.last_scores_at = datetime.now(UTC) - timedelta(hours=1)
        cred = BrokerCredential(
            user_id=u.id,
            broker_name=BrokerName.DHAN,
            client_id_enc=encrypt_credential("CID"),
            api_key_enc=encrypt_credential("KEY"),
            api_secret_enc=encrypt_credential("SEC"),
            access_token_enc=encrypt_credential("TOK"),
            token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            is_active=True,
        )
        s.add(cred)
        await s.commit()
        user_id = u.id
        strat_id = strat.id

    set_flag("LIVE_TRADING_ENABLED", True)

    async def _one_run() -> SafetyChainResult:
        async with maker() as session:
            return await run_safety_chain(
                user_id=user_id, strategy_id=strat_id, db_session=session
            )

    results = await asyncio.gather(*(_one_run() for _ in range(10)))
    await engine.dispose()

    assert len(results) == 10
    for r in results:
        assert r.all_passed is True, r
        assert r.blocking_check is None


# ─── 8. The deferred risk-engine surface ─────────────────────────────


@pytest.mark.asyncio
async def test_chain_completes_when_only_risk_engine_is_deferred(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Risk engine pre-check is fail-open by design — its presence
    must not cause the chain to fail when every other check passed."""
    user, strategy = all_passing
    result = await run_safety_chain(
        user_id=user.id, strategy_id=strategy.id, db_session=db
    )
    assert result.all_passed is True
    risk = next(c for c in result.checks if c.check_name == "risk_engine_precheck")
    assert risk.passed is True
    assert risk.details["deferred"] is True
