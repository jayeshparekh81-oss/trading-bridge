"""Addition A, proven the only way it can be: delete the tape, ask again.

THE CLAIM. Whether a fill is the bot's, the founder's, or unidentifiable is
decided from ``orderPlatform`` and ``algoOrdNo``. Dhan's trade book carries
NEITHER (measured 2026-09-16: 27 keys, none of them these). They exist only in
pine_replica's WS order-update tape — files with NO retention policy: no
logrotate rule names them, no cron line deletes them, no cleanup code exists in
``executor/*.py``. They survive by luck, on a box that runs structurally
near-full.

So the founder's addition A: store the verdict at ingest. This file proves it by
DELETING the tape between the write and the read. A test that merely re-read the
answer while the file still sat on disk would pass without proving anything.

WHY AGAINST REAL POSTGRES. Idempotency here is not a convention, it is
``broker_order_id PRIMARY KEY`` + ``ON CONFLICT DO NOTHING``. Only a real
database can refuse the second insert; a hand-written fake session proves that
the code CALLS the database, never that the database HOLDS the line.

RUNNING IT. ``docker compose -f docker-compose-test.yml up -d postgres_test``,
then pytest. Unreachable DB skips loudly, or FAILS under ``REQUIRE_POSTGRES=1``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.ingest import ingest_fills, stored_provenance
from app.domains.pnl_reconciler.order_tape import load_tape

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/trading_bridge_test",
)
REQUIRE = os.environ.get("REQUIRE_POSTGRES") == "1"

pytestmark = pytest.mark.postgres

#: The real ids, from the real record.
ENGINE_CHILD = "312260904412406"   # pine_replica's stop child — FOVR
ENGINE_PARENT = "32132609031621"   # its parent Forever order
MANUAL_FILL = "35226091145606"     # the founder's own Dhan-app fill — FAST
OUR_ORDER = "34226090862006"       # placed by this platform — API


def _reachable() -> bool:
    async def probe() -> bool:
        engine = create_async_engine(TEST_DB_URL)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(probe())


if not _reachable():
    msg = (
        f"Postgres test DB unreachable at {TEST_DB_URL}. "
        "Start it: docker compose -f docker-compose-test.yml up -d postgres_test"
    )
    if REQUIRE:
        pytest.fail(msg + " (REQUIRE_POSTGRES=1 — a skipped Postgres test is the bug)")
    pytest.skip(msg, allow_module_level=True)


def _migrate_to_head() -> None:
    """Apply the REAL chain in a subprocess (see the tz test for why)."""
    backend_dir = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir, env=env, capture_output=True, text=True, timeout=600, check=False,
    )
    assert proc.returncode == 0, f"alembic upgrade head failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.fixture(scope="module", autouse=True)
def _schema() -> None:
    _migrate_to_head()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DB_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(text("DELETE FROM broker_fill_provenance"))
        await s.commit()
        yield s
        await s.rollback()
    await engine.dispose()


def _write_tape(tmp_path: Path) -> Path:
    """A tape in its real on-disk shape: one JSON envelope per line, the broker
    frame itself a JSON STRING inside ``raw``."""
    frames = [
        {"orderNo": ENGINE_CHILD, "algoOrdNo": int(ENGINE_PARENT), "orderPlatform": "FOVR",
         "correlationId": "NR", "status": "Traded"},
        {"orderNo": MANUAL_FILL, "algoOrdNo": None, "orderPlatform": "FAST",
         "correlationId": "NA", "status": "Traded"},
        {"orderNo": OUR_ORDER, "algoOrdNo": None, "orderPlatform": "API",
         "correlationId": "strategy-engine-1", "status": "Traded"},
    ]
    p = tmp_path / "order_updates_2026-09-04.jsonl"
    with p.open("w") as fh:
        for f in frames:
            fh.write(json.dumps({"at": "2026-09-04T13:11:16+05:30",
                                 "raw": json.dumps({"Data": f})}) + "\n")
    return p


def _fills() -> list[AccountFill]:
    return [
        AccountFill(contract="68456", order_id=ENGINE_CHILD, side="SELL", qty=400,
                    price=Decimal("3415.5"), ts="2026-09-04T13:11:13",
                    charges=Decimal("1366.40")),
        AccountFill(contract="68456", order_id=MANUAL_FILL, side="BUY", qty=200,
                    price=Decimal("3264.9"), ts="2026-09-11T09:31:17",
                    charges=Decimal("20.00")),
        AccountFill(contract="68456", order_id=OUR_ORDER, side="BUY", qty=400,
                    price=Decimal("3214.6"), ts="2026-09-04T09:20:11",
                    charges=Decimal("935.88")),
    ]


class TestTheVerdictOutlivesTheTape:
    @pytest.mark.asyncio
    async def test_delete_the_tape_and_the_answer_is_unchanged(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """🔴 THE ONE THAT MATTERS. Ingest with the tape present, then DELETE the
        tape, then ask again. If provenance were recomputed from the files, this
        is the day the record forgets who placed what."""
        tape_file = _write_tape(tmp_path)
        tape = load_tape(tape_file)
        assert len(tape) == 3, "precondition: the tape really loaded"

        out = await ingest_fills(
            session, _fills(), tape,
            ledger_order_ids={ENGINE_PARENT}, platform_order_ids={OUR_ORDER},
        )
        await session.commit()
        assert out.written == 3
        assert (out.bot, out.manual, out.unknown) == (2, 1, 0)

        # ── the tape is destroyed ──────────────────────────────────────
        tape_file.unlink()
        assert not tape_file.exists()
        assert load_tape(tape_file) == {}, "the evidence is genuinely gone"

        # ── and the record still answers, from the database ────────────
        child = await stored_provenance(session, ENGINE_CHILD)
        assert child is not None
        assert child["provenance"] == "bot"
        assert child["order_platform"] == "FOVR", "the RAW field survived too"
        assert child["parent_order_id"] == ENGINE_PARENT

        manual = await stored_provenance(session, MANUAL_FILL)
        assert manual is not None and manual["provenance"] == "manual"
        assert manual["order_platform"] == "FAST"

        ours = await stored_provenance(session, OUR_ORDER)
        assert ours is not None and ours["provenance"] == "bot"

    @pytest.mark.asyncio
    async def test_the_answer_survives_a_whole_new_connection(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """The twin for the test above. Reading back through the SAME session
        could be served by SQLAlchemy's identity map rather than by the DB — the
        test would pass with nothing persisted. This opens a brand-new engine."""
        tape = load_tape(_write_tape(tmp_path))
        await ingest_fills(session, _fills(), tape,
                           ledger_order_ids={ENGINE_PARENT}, platform_order_ids={OUR_ORDER})
        await session.commit()

        engine = create_async_engine(TEST_DB_URL)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with maker() as fresh:
                row = await stored_provenance(fresh, MANUAL_FILL)
            assert row is not None and row["provenance"] == "manual"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_billed_charges_are_stored_to_the_paisa(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """Net is what Dhan billed. A Numeric that silently rounded would move
        the headline, so the stored value is compared exactly."""
        tape = load_tape(_write_tape(tmp_path))
        await ingest_fills(session, _fills(), tape,
                           ledger_order_ids={ENGINE_PARENT}, platform_order_ids={OUR_ORDER})
        await session.commit()
        row = await stored_provenance(session, ENGINE_CHILD)
        assert row is not None
        assert row["billed_charges"] == Decimal("1366.40")


class TestTheDatabaseHoldsTheLine:
    @pytest.mark.asyncio
    async def test_a_second_ingest_writes_nothing(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """Idempotency is the PRIMARY KEY's job, not the caller's. Running the
        ingester twice over one tape must not double a leg — and here the real
        database is the one refusing, not a fake session counting calls."""
        tape = load_tape(_write_tape(tmp_path))
        first = await ingest_fills(session, _fills(), tape,
                                   ledger_order_ids={ENGINE_PARENT},
                                   platform_order_ids={OUR_ORDER})
        await session.commit()
        assert first.written == 3 and first.already_present == 0

        second = await ingest_fills(session, _fills(), tape,
                                    ledger_order_ids={ENGINE_PARENT},
                                    platform_order_ids={OUR_ORDER})
        await session.commit()
        assert second.written == 0, "the second run inserted rows"
        assert second.already_present == 3

        count = (
            await session.execute(text("SELECT count(*) FROM broker_fill_provenance"))
        ).scalar_one()
        assert count == 3

    @pytest.mark.asyncio
    async def test_falsification_twin_a_different_fill_does_get_written(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """The twin. A guard that refused EVERY second write would pass the test
        above and quietly stop the ingester ever recording a new fill."""
        tape = load_tape(_write_tape(tmp_path))
        await ingest_fills(session, _fills(), tape,
                           ledger_order_ids={ENGINE_PARENT}, platform_order_ids={OUR_ORDER})
        await session.commit()

        newcomer = AccountFill(contract="68456", order_id="99990001112223", side="SELL",
                               qty=200, price=Decimal("3300.0"),
                               ts="2026-09-15T10:00:00", charges=Decimal("11.11"))
        out = await ingest_fills(session, [*_fills(), newcomer], tape,
                                 ledger_order_ids={ENGINE_PARENT},
                                 platform_order_ids={OUR_ORDER})
        await session.commit()
        assert out.written == 1, "the new fill must land"
        assert out.already_present == 3
        assert out.unknown == 1, "and it is pehchaan nahi — the tape never saw it"
        assert out.unknown_order_ids == ("99990001112223",)

    @pytest.mark.asyncio
    async def test_an_unidentified_fill_is_recorded_as_unknown_not_manual(
        self, session: AsyncSession, tmp_path: Path
    ) -> None:
        """Never silently filed. The row exists, and it says 'unknown' — so the
        15:50 check can find it tomorrow even if the tape is gone tonight."""
        tape = load_tape(_write_tape(tmp_path))
        stranger = AccountFill(contract="68456", order_id="77770001112223", side="BUY",
                               qty=100, price=Decimal("3100.0"),
                               ts="2026-09-15T11:00:00", charges=None)
        await ingest_fills(session, [stranger], tape, ledger_order_ids=set())
        await session.commit()
        row = await stored_provenance(session, "77770001112223")
        assert row is not None
        assert row["provenance"] == "unknown"
        assert row["order_platform"] is None, "no platform is NOT the same as manual"
        assert row["billed_charges"] is None, "unbilled is NULL, never a flattering zero"
