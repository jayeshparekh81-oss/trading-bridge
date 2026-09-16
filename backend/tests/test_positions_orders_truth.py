"""The bot's live record, shown exactly — and only the bot's.

This page is shown to other people. Four rules, each with a falsification twin
so a blanket change (delete everything / price nothing / price everything)
cannot pass by making the assertion vacuous.

(a) ONLY the bot. Manual Dhan-app fills and other instruments never appear.
(b) The engine's own broker-side stop fill IS the bot's exit, attributed
    through the ENGINE LEDGER's order ids, never by matching on time.
(c) The 2026-09-04 duplicate exit is shown as the system's mistake, with its
    own fill-sourced number, and it counts.
(d) Legs that do not add up produce "incomplete" + a reason, never a number.

Every price below is verified against the Dhan trade book (one-off GET,
2026-09-16): all 15 fills on securityId 68456 matched to the paisa.
"""

from __future__ import annotations

from decimal import Decimal

from app.api.strategy_positions import (
    PositionLeg,
    _history_legs,
    derive_position_figures,
    duplicate_exit_of,
)

# ── The 03-Sep position (844b8037), from real fills ──────────────────────
ENTRY_ORDER = "32226090368506"  # BUY 800 @3270.00, 03-09 09:45:17
PARTIAL_ORDER = "34226090334306"  # SELL 400 @3325.40, 03-09 12:45:13
ENGINE_STOP_ORDER = "312260904412406"  # SELL 400 @3415.50, 04-09 13:11:13
DUPLICATE_ORDER = "23226090443106"  # SELL 400 @3415.80, 04-09 13:15:12 — the fault
PARENT_FOREVER = "32132609031621"


def _platform_legs() -> list[PositionLeg]:
    """What ``strategy_executions`` holds — including the duplicate."""
    return [
        PositionLeg("entry", 800, Decimal("3270.00"), ENTRY_ORDER),
        PositionLeg("direct_partial", 400, Decimal("3325.40"), PARTIAL_ORDER),
        PositionLeg("direct_sl", 400, Decimal("3415.80"), DUPLICATE_ORDER),
    ]


def _broker_stop_event() -> dict:
    """The engine-stop exit, as the reconcile run records it."""
    return {
        "ts": "2026-09-04T07:41:13+00:00",
        "action": "exit",
        "leg_role": "broker_stop",
        "side": "sell",
        "qty": 400,
        "price": 3415.50,
        "broker_fill": True,
        "broker_order_id": ENGINE_STOP_ORDER,
        "parent_forever_order_id": PARENT_FOREVER,
    }


def _duplicate_event() -> dict:
    return {
        "leg_role": "duplicate_exit",
        "label": "system galti: duplicate exit",
        "broker_order_id": DUPLICATE_ORDER,
        "side": "sell",
        "qty": 400,
        "price": 3415.80,
        "closed_by": [
            {"broker_order_id": "362260904291606", "qty": 200, "price": 3426.70},
            {"broker_order_id": "222260904331206", "qty": 200, "price": 3426.70},
        ],
        "gross_pnl": -4360.00,
    }


class TestTheEngineStopIsTheBotsExit:
    def test_it_is_read_as_a_real_priced_leg(self) -> None:
        [leg] = _history_legs([_broker_stop_event()])
        assert leg.leg_role == "broker_stop"
        assert leg.price == Decimal("3415.50")
        assert leg.quantity == 400
        assert leg.broker_fill is True
        assert leg.broker_order_id == ENGINE_STOP_ORDER

    def test_the_position_prices_from_it(self) -> None:
        """🔴 (b) + (c) together. The real exit is 3415.50; the duplicate at
        3415.80 belongs to a different round trip and is excluded by order id."""
        legs = [
            leg for leg in _platform_legs() if leg.broker_order_id != DUPLICATE_ORDER
        ] + _history_legs([_broker_stop_event()])
        out = derive_position_figures(
            side="buy", total_quantity=800, remaining_quantity=0, legs=legs
        )
        # 400 x (3325.40-3270) + 400 x (3415.50-3270) = 22,160 + 58,200
        assert out.gross_pnl == Decimal("80360.00")
        assert out.quantity == 800

    def test_falsification_twin_evidence_without_an_id_or_price_is_refused(self) -> None:
        """The twin. A broker_stop leg is trusted ONLY with both a fill price and
        the broker's own order id — otherwise it is not evidence, and a leg
        invented here would price a position against a number nobody filled."""
        assert _history_legs([{k: v for k, v in _broker_stop_event().items() if k != "price"}]) == []
        assert (
            _history_legs(
                [{k: v for k, v in _broker_stop_event().items() if k != "broker_order_id"}]
            )
            == []
        )

    def test_falsification_twin_it_is_not_matched_on_time(self) -> None:
        """The twin that matters most. Attribution is by recorded id, so an
        event with no timestamp at all still attributes, and a timestamp alone
        never does."""
        no_ts = {k: v for k, v in _broker_stop_event().items() if k != "ts"}
        assert len(_history_legs([no_ts])) == 1
        time_only = {"ts": "2026-09-04T07:41:13+00:00", "qty": 400, "side": "sell"}
        assert _history_legs([time_only]) == []


class TestTheDuplicateExitIsShownNotHidden:
    def test_it_is_found_and_carries_its_own_fill_sourced_number(self) -> None:
        dup = duplicate_exit_of([_broker_stop_event(), _duplicate_event()])
        assert dup is not None
        assert dup["broker_order_id"] == DUPLICATE_ORDER
        # 400 x (3415.80 - 3426.70) = -4,360. A loss, shown like any other.
        assert Decimal(str(dup["gross_pnl"])) == Decimal("-4360.00")
        assert len(dup["closed_by"]) == 2

    def test_it_is_not_a_position_leg(self) -> None:
        """It is a different round trip — folding it in is how the 03-Sep row
        came to be priced against 3415.80."""
        assert _history_legs([_duplicate_event()]) == []

    def test_falsification_twin_a_position_without_one_reports_none(self) -> None:
        assert duplicate_exit_of([_broker_stop_event()]) is None
        assert duplicate_exit_of(None) is None


class TestLegsMustAddUp:
    def test_an_unbalanced_closed_row_is_not_priced(self) -> None:
        """🔴 (d). 800 left the position but only 400 of exits are recorded."""
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=_platform_legs()[:2],
        )
        assert out.realised_pnl is None
        assert out.quantity is None
        assert "do not reconcile" in out.reason

    def test_falsification_twin_a_balanced_row_still_prices(self) -> None:
        legs = [
            leg for leg in _platform_legs() if leg.broker_order_id != DUPLICATE_ORDER
        ] + _history_legs([_broker_stop_event()])
        out = derive_position_figures(
            side="buy", total_quantity=800, remaining_quantity=0, legs=legs
        )
        assert out.realised_pnl is not None


class TestOnlyTheBotsOwnOrders:
    def test_a_manual_fill_has_no_route_onto_the_page(self) -> None:
        """(a) Manual Dhan-app fills are not a leg shape this reads. The only
        events it accepts are operator_reconcile and broker_stop; a FAST fill
        recorded with any other role is ignored."""
        manual = {
            "leg_role": "manual",
            "qty": 200,
            "price": 3215.40,
            "broker_fill": True,
            "broker_order_id": "35226091145606",
        }
        assert _history_legs([manual]) == []

    def test_falsification_twin_the_two_accepted_roles_still_work(self) -> None:
        operator = {"leg_role": "operator_reconcile", "qty": 200, "broker_fill": False}
        assert len(_history_legs([operator])) == 1
        assert len(_history_legs([_broker_stop_event()])) == 1


class TestTheArchiveIsNotRewrittenByAccident:
    """A4, founder ruling 2026-09-16: the four pre-1-Sep rows keep their values.

    The 2026-09-16 attribution change made this concrete. Four archived rows
    carry ``account_flat`` — a tag ``attribute()`` can no longer produce — so a
    single ``--overwrite`` run across this strategy would NULL all four
    (03f597b7 -198,265.66 | f6ab0934 +17,639.37 | 388c845e +454.56 |
    f6dff74b +16,520.20). It refuses LOUDLY: a silent skip would look like the
    archive had been considered and found correct.
    """

    @staticmethod
    def _pos(opened_iso: str):
        from datetime import datetime
        from types import SimpleNamespace
        from uuid import uuid4

        return SimpleNamespace(id=uuid4(), opened_at=datetime.fromisoformat(opened_iso))

    #: The boundary is TOLD to the reconciler, never known by it (ADR 0003 —
    #: a first cut hardcoded 2026-09-01 inside the domain and the isolation
    #: test caught it). Every call here supplies it, exactly as the CLI does.
    ARCHIVE_BEFORE = __import__("datetime").datetime(
        2026, 9, 1,
        tzinfo=__import__("datetime").timezone(__import__("datetime").timedelta(hours=5, minutes=30)),
    )

    async def _run(self, positions, *, overwrite: bool, allow_archive: bool):
        import app.domains.pnl_reconciler.service as svc

        async def _fake_load(session, strategy_id):
            return positions

        original = svc._load_closed_positions
        svc._load_closed_positions = _fake_load  # type: ignore[assignment]
        try:
            return await svc.reconcile_strategy(
                None,  # type: ignore[arg-type]
                __import__("uuid").uuid4(),
                write=True,
                overwrite=overwrite,
                allow_archive=allow_archive,
                archive_before=self.ARCHIVE_BEFORE,
            )
        finally:
            svc._load_closed_positions = original  # type: ignore[assignment]

    async def test_overwrite_refuses_a_pre_cutoff_row(self) -> None:
        import pytest

        from app.domains.pnl_reconciler.service import ArchiveProtectedError

        archived = self._pos("2026-08-31T12:15:00+05:30")
        with pytest.raises(ArchiveProtectedError) as excinfo:
            await self._run([archived], overwrite=True, allow_archive=False)
        assert "--allow-archive" in str(excinfo.value)
        assert str(archived.id)[:8] in str(excinfo.value), "it must name the rows"

    async def test_falsification_twin_a_post_cutoff_row_is_not_blocked(self) -> None:
        """The twin. A guard that refused everything would pass the test above
        and make the correction path unusable on the live record."""
        from app.domains.pnl_reconciler.service import ArchiveProtectedError

        recent = self._pos("2026-09-08T14:00:11+05:30")
        try:
            await self._run([recent], overwrite=True, allow_archive=False)
        except ArchiveProtectedError:  # pragma: no cover
            raise AssertionError("the guard blocked a row inside the record") from None
        except Exception:
            pass  # any later failure is out of scope; the guard did not fire

    async def test_falsification_twin_allow_archive_lets_it_through(self) -> None:
        """The escape hatch has to actually work, or the guard is a wall."""
        from app.domains.pnl_reconciler.service import ArchiveProtectedError

        archived = self._pos("2026-08-31T12:15:00+05:30")
        try:
            await self._run([archived], overwrite=True, allow_archive=True)
        except ArchiveProtectedError:  # pragma: no cover
            raise AssertionError("--allow-archive did not lift the guard") from None
        except Exception:
            pass

    async def test_a_plain_append_only_run_is_never_blocked(self) -> None:
        """Without --overwrite nothing is rewritten, so the archive is safe and
        the guard must not fire — otherwise ordinary pricing would break."""
        from app.domains.pnl_reconciler.service import ArchiveProtectedError

        archived = self._pos("2026-08-31T12:15:00+05:30")
        try:
            await self._run([archived], overwrite=False, allow_archive=False)
        except ArchiveProtectedError:  # pragma: no cover
            raise AssertionError("the guard fired on an append-only run") from None
        except Exception:
            pass

    async def test_an_append_only_run_does_not_RETAG_the_archive(self) -> None:
        """🔴 THE SUBTLE ONE, found by the dry run and not by reading the code.

        ``apply_write`` stamps ``pnl_attribution`` whenever the tag differs,
        REGARDLESS of ``overwrite``. So a plain append-only run re-tagged all
        four archived rows account_flat -> human_interfered. Their ``final_pnl``
        survived (only the overwrite branch NULLs it) but ``human_interfered``
        is not a priced tag, so ~-163k of settled money silently stopped
        counting on every surface. "Keeps its value" has to mean the tag too.
        """
        import app.domains.pnl_reconciler.service as svc

        applied: list[str] = []

        def _spy(position, trip, *, overwrite):  # type: ignore[no-untyped-def]
            applied.append(str(position.id)[:8])
            return "tag"

        archived = self._pos("2026-08-31T12:15:00+05:30")
        recent = self._pos("2026-09-08T14:00:11+05:30")

        async def _fake_load(session, strategy_id):
            return [archived, recent]

        def _fake_reconcile(position, index, **kw):  # type: ignore[no-untyped-def]
            return object()

        orig_load, orig_apply, orig_rec = (
            svc._load_closed_positions,
            svc.apply_write,
            svc.reconcile_position,
        )
        svc._load_closed_positions = _fake_load  # type: ignore[assignment]
        svc.apply_write = _spy  # type: ignore[assignment]
        svc.reconcile_position = _fake_reconcile  # type: ignore[assignment]
        try:
            await svc.reconcile_strategy(
                _NullSession(),  # type: ignore[arg-type]
                __import__("uuid").uuid4(),
                write=True,
                overwrite=False,
                allow_archive=False,
                archive_before=self.ARCHIVE_BEFORE,
            )
        finally:
            svc._load_closed_positions = orig_load  # type: ignore[assignment]
            svc.apply_write = orig_apply  # type: ignore[assignment]
            svc.reconcile_position = orig_rec  # type: ignore[assignment]

        assert str(archived.id)[:8] not in applied, "the archive was written to"
        assert str(recent.id)[:8] in applied, "the live record was skipped too"


class _NullSession:
    """Enough of an AsyncSession for the guard path; it must never reach a DB."""

    async def commit(self) -> None:
        return None

    async def execute(self, *a: object, **k: object) -> _NullResult:
        return _NullResult()


class _NullResult:
    def scalars(self) -> _NullResult:
        return self

    def all(self) -> list:
        return []

    async def test_no_boundary_means_no_protection_and_that_is_why_the_cli_refuses(
        self,
    ) -> None:
        """🔴 THE TRADE-OFF, made explicit so nobody re-discovers it.

        ADR 0003 forbids this domain from KNOWING the record's start date, so
        the boundary is a parameter. That means ``archive_before=None`` gives no
        protection at all — which would be a silent hole if the CLI did not
        refuse ``--overwrite`` without either ``--archive-before`` or an
        explicit ``--allow-archive``. This test pins the hole so the CLI-side
        refusal can never be removed as "redundant".
        """
        import app.domains.pnl_reconciler.service as svc

        applied: list[str] = []

        def _spy(position, trip, *, overwrite):  # type: ignore[no-untyped-def]
            applied.append(str(position.id)[:8])
            return "tag"

        archived = self._pos("2026-08-31T12:15:00+05:30")

        async def _fake_load(session, strategy_id):
            return [archived]

        orig_load, orig_apply, orig_rec = (
            svc._load_closed_positions,
            svc.apply_write,
            svc.reconcile_position,
        )
        svc._load_closed_positions = _fake_load  # type: ignore[assignment]
        svc.apply_write = _spy  # type: ignore[assignment]
        svc.reconcile_position = lambda *a, **k: object()  # type: ignore[assignment]
        try:
            await svc.reconcile_strategy(
                _NullSession(),  # type: ignore[arg-type]
                __import__("uuid").uuid4(),
                write=True,
                overwrite=False,
                allow_archive=False,
                archive_before=None,
            )
        finally:
            svc._load_closed_positions = orig_load  # type: ignore[assignment]
            svc.apply_write = orig_apply  # type: ignore[assignment]
            svc.reconcile_position = orig_rec  # type: ignore[assignment]

        assert applied == [str(archived.id)[:8]], (
            "with no boundary supplied the archive IS writable — if this ever "
            "stops being true, the CLI refusal has silently become the only "
            "guard and this test should be re-thought, not deleted"
        )
