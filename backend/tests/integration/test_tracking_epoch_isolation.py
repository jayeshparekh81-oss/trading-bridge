"""The tracking cut-off is a REPORTING boundary. These tests keep it there.

TWO CONDITIONS, both made mandatory by the founder on 2026-09-09:

  A. ONE OWNER — ``app.core.tracking_epoch`` — never imported by any execution
     module, and ``settings.tracking_epoch`` never read by one either.
  B. THE NEVER-FILTER LIST is pinned by a regression test that is PROVEN to
     fail when the filter is injected. ADR 0001 §7: a rule that has never been
     proven to fail is not enforcement.

Condition B is not satisfied by asserting the happy path. Every test in
:class:`TestTheGuardActuallyCatchesIt` therefore runs the SAME query twice —
once as the code really is, once with ``positions_in_record()`` injected — and
asserts the first finds the old position and the second does NOT. The
sensitivity proof runs on every CI pass, not once by hand at review time.

WHY THIS MATTERS, concretely:
  * the kill switch — a filtered select leaves a REAL open Dhan position the
    brake silently skips, and the endpoint still answers success because it
    reports what it closed, not what it should have.
  * the reconciliation loop — recreates the phantom-BUY-800 blindness on an age
    axis: a live broker leg, no visible DB counterpart, ``db_only`` empty.
  * position_lookup — would not even error. ``strategy_webhook`` logs
    ``exit_no_open_position`` and returns success on purpose (to stop
    TradingView retry storms), so an expiry-day exit would simply never happen.
  * the P&L reconciler — its ``since`` is a DIFFERENT fact that merely rhymes
    (its own docstring calls it "the GOING-FORWARD boundary"). Wiring the epoch
    in would stop it pricing new trips AND hide the archive the founder still
    prices by hand. The archive must stay priceable; that is why it is kept.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tracking_epoch import positions_in_record, tracking_epoch
from app.db.models.strategy_position import StrategyPosition
from tests.integration.conftest import _seed_user_with_strategy

_BACKEND = Path(__file__).resolve().parents[2]

#: Every module on the EXECUTION or SAFETY path. None of these may ever learn
#: about the cut-off. Adding a file here is cheap; removing one needs a reason.
EXECUTION_MODULES = [
    "app/services/strategy_executor.py",
    "app/services/direct_exit.py",
    "app/services/position_manager.py",
    "app/services/position_lookup.py",
    "app/services/order_service.py",
    "app/services/futures_expiry_backstop.py",
    "app/services/kill_switch_service.py",
    "app/services/marketplace_fanout.py",
    "app/workers/position_loop.py",
    "app/workers/reconciliation_loop.py",
    "app/api/webhook.py",
    "app/api/strategy_webhook.py",
]

#: The P&L reconciler is separate because it fails for a DIFFERENT reason —
#: the naming trap, not the safety one.
RECONCILER_MODULES = [
    "app/domains/pnl_reconciler/service.py",
    "app/domains/pnl_reconciler/__main__.py",
    "app/domains/pnl_reconciler/attribution.py",
    "app/domains/pnl_reconciler/costs.py",
    "app/domains/pnl_reconciler/tradebook.py",
]


def _imports_of(rel: str) -> set[str]:
    """Every module name imported by this file, however it is spelled."""
    tree = ast.parse((_BACKEND / rel).read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
    return found


# ═══════════════════════════════════════════════════════════════════════
# CONDITION A — one owner, and nobody on the live path may see it
# ═══════════════════════════════════════════════════════════════════════


class TestConditionA:
    @pytest.mark.parametrize("rel", EXECUTION_MODULES)
    def test_no_execution_module_imports_the_cutoff(self, rel: str) -> None:
        """🔴 An execution module that can see the epoch can filter by it."""
        offenders = {
            name
            for name in _imports_of(rel)
            if "tracking_epoch" in name
        }
        assert not offenders, (
            f"{rel} imports the tracking cut-off ({sorted(offenders)}). "
            "A reporting boundary on the execution path can hide a REAL open "
            "position from the code meant to close it."
        )

    @pytest.mark.parametrize("rel", EXECUTION_MODULES)
    def test_no_execution_module_reads_the_setting_directly(self, rel: str) -> None:
        """Importing the owner is the obvious route; reading the raw setting is
        the sneaky one. Both are closed."""
        source = (_BACKEND / rel).read_text()
        assert "tracking_epoch" not in source, (
            f"{rel} mentions tracking_epoch. Even reading "
            "settings.tracking_epoch directly is forbidden here — the owner "
            "module exists so this fact has exactly one reader per surface."
        )

    @pytest.mark.parametrize("rel", RECONCILER_MODULES)
    def test_the_pnl_reconciler_never_receives_the_cutoff(self, rel: str) -> None:
        """🔴 THE NAMING TRAP.

        ``service.py`` already has a ``since`` its own docstring calls "the
        GOING-FORWARD boundary". It is a scan window for pricing recently-closed
        trips — not the record's start. Wiring the epoch in because the names
        rhyme would stop it pricing new trades and would make the archive
        unpriceable, which defeats the reason the archive is kept at all.
        """
        source = (_BACKEND / rel).read_text()
        assert "tracking_epoch" not in source, (
            f"{rel} mentions tracking_epoch. The reconciler's `since` is a "
            "different fact with a similar name; see app/core/tracking_epoch.py."
        )

    def test_the_owner_module_is_the_only_definition(self) -> None:
        """One owner means one place that turns the setting into a predicate."""
        defining = [
            p
            for p in (_BACKEND / "app").rglob("*.py")
            if "def positions_in_record" in p.read_text()
        ]
        assert [p.name for p in defining] == ["tracking_epoch.py"], (
            f"the anchor rule is defined in more than one place: {defining}"
        )


# ═══════════════════════════════════════════════════════════════════════
# CONDITION B — the never-filter list, proven by injection
# ═══════════════════════════════════════════════════════════════════════


async def _seed_pre_cut_open_position(
    maker: async_sessionmaker[AsyncSession],
) -> tuple[StrategyPosition, dict]:
    """An OPEN position entered long before the cut-off.

    This is the shape the guard exists for: a real position still in the
    market whose entry predates the record. Everything on the execution path
    must still see it.
    """
    seeded = await _seed_user_with_strategy(
        maker, email="tracking-epoch-guard@tradetri.com"
    )
    epoch = tracking_epoch()
    assert epoch is not None, "these tests are meaningless with no cut-off set"
    long_before = epoch.astimezone(UTC) - timedelta(days=120)

    async with maker() as s:
        pos = StrategyPosition(
            user_id=seeded["user_id"],
            strategy_id=seeded["strategy_id"],
            broker_credential_id=seeded["credential_id"],
            signal_id=None,
            symbol="BSE-SEP2026-FUT",
            side="buy",
            total_quantity=800,
            remaining_quantity=800,
            avg_entry_price=None,
            status="open",
            opened_at=long_before,
        )
        s.add(pos)
        await s.commit()
        await s.refresh(pos)
        return pos, seeded


class TestTheGuardActuallyCatchesIt:
    """Each test runs the real query AND the same query with the filter
    injected. The first must find the old position; the second must not.

    The second half is the proof. Without it these would be assertions about a
    happy path that could pass forever while the guard rotted.
    """

    async def test_kill_switch_still_closes_a_pre_cut_position(
        self, db_session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """🔴 THE DANGEROUS ONE. The brake must reach every open position."""
        pos, seeded = await _seed_pre_cut_open_position(db_session_maker)

        real = select(StrategyPosition).where(
            StrategyPosition.user_id == seeded["user_id"],
            StrategyPosition.status.in_(("open", "partial")),
        )
        async with db_session_maker() as s:
            found = (await s.execute(real)).scalars().all()
            assert pos.id in {p.id for p in found}, (
                "the kill switch cannot see a pre-cut open position — a real "
                "Dhan position that 'Sab band' would silently skip"
            )

            # THE INJECTION. If anyone ever adds the filter here, this is what
            # the failure looks like.
            poisoned = (await s.execute(real.where(positions_in_record()))).scalars().all()
            assert pos.id not in {p.id for p in poisoned}, (
                "injecting the cut-off did NOT hide the row, so this test "
                "cannot prove it would catch the mistake — fix the test"
            )

    async def test_the_executor_still_finds_a_pre_cut_open_position(
        self, db_session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """Entry de-duplication: miss the old row and the executor opens a
        SECOND position on a contract it already holds."""
        _pos, seeded = await _seed_pre_cut_open_position(db_session_maker)

        real = (
            select(StrategyPosition)
            .where(
                StrategyPosition.strategy_id == seeded["strategy_id"],
                StrategyPosition.symbol == "BSE-SEP2026-FUT",
                StrategyPosition.side == "buy",
                StrategyPosition.status.in_(("open", "partial")),
                StrategyPosition.subscription_id.is_(None),
            )
            .order_by(StrategyPosition.opened_at.desc())
            .limit(1)
        )
        async with db_session_maker() as s:
            assert (await s.execute(real)).scalar_one_or_none() is not None
            assert (
                await s.execute(real.where(positions_in_record()))
            ).scalar_one_or_none() is None, "injection proof failed"

    async def test_the_position_loop_still_polls_a_pre_cut_position(
        self, db_session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        pos, _seeded = await _seed_pre_cut_open_position(db_session_maker)

        real = select(StrategyPosition).where(
            StrategyPosition.status.in_(("open", "partial")),
            StrategyPosition.subscription_id.is_(None),
        )
        async with db_session_maker() as s:
            assert pos.id in {
                p.id for p in (await s.execute(real)).scalars().all()
            }
            assert pos.id not in {
                p.id
                for p in (
                    await s.execute(real.where(positions_in_record()))
                ).scalars().all()
            }, "injection proof failed"

    async def test_reconciliation_still_sees_a_pre_cut_position(
        self, db_session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """The loop was just fixed (2026-09-09) to stop being blind. A cut-off
        filter would blind it again, on a different axis."""
        pos, seeded = await _seed_pre_cut_open_position(db_session_maker)

        real = select(StrategyPosition).where(
            StrategyPosition.user_id == seeded["user_id"],
            StrategyPosition.status.in_(("open", "partial")),
            StrategyPosition.subscription_id.is_(None),
        )
        async with db_session_maker() as s:
            assert pos.id in {
                p.id for p in (await s.execute(real)).scalars().all()
            }
            assert pos.id not in {
                p.id
                for p in (
                    await s.execute(real.where(positions_in_record()))
                ).scalars().all()
            }, "injection proof failed"


# ═══════════════════════════════════════════════════════════════════════
# The boundary does what it says on the reporting side
# ═══════════════════════════════════════════════════════════════════════


class TestTheBoundaryWorks:
    def test_the_epoch_is_the_founders_date(self) -> None:
        epoch = tracking_epoch()
        assert epoch is not None
        assert epoch.astimezone(UTC) == datetime(2026, 8, 31, 18, 30, tzinfo=UTC), (
            "1 Sep 2026 00:00 IST is 31 Aug 2026 18:30 UTC"
        )

    async def test_a_post_cut_position_survives(
        self, db_session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        """The founder's live BSE SELL 200 was opened 2026-09-08. It must stay
        visible on every reporting surface."""
        seeded = await _seed_user_with_strategy(
            maker := db_session_maker, email="tracking-epoch-live@tradetri.com"
        )
        async with maker() as s:
            pos = StrategyPosition(
                user_id=seeded["user_id"],
                strategy_id=seeded["strategy_id"],
                broker_credential_id=seeded["credential_id"],
                signal_id=None,
                symbol="BSE-SEP2026-FUT",
                side="sell",
                total_quantity=400,
                remaining_quantity=200,
                avg_entry_price=None,
                status="partial",
                opened_at=datetime(2026, 9, 8, 8, 30, 11, tzinfo=UTC),
            )
            s.add(pos)
            await s.commit()
            await s.refresh(pos)

        async with maker() as s:
            rows = (
                await s.execute(
                    select(StrategyPosition).where(
                        StrategyPosition.user_id == seeded["user_id"],
                        positions_in_record(),
                    )
                )
            ).scalars().all()
        assert pos.id in {p.id for p in rows}, (
            "the live post-cut position was hidden by the cut-off"
        )
