"""R1 — the fixes from the founder's check of the C5 render.

Each rule has a falsification twin, so a blanket change (format everything the
same / write nothing / write everything) cannot pass by making the assertion
vacuous.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.api.strategy_positions import ist_display, leg_label


class TestR1_1_EveryTimeIsIST:
    """The render printed ``2026-09-04T07:41:13`` — the raw UTC instant — for
    the broker stop, beside rows showing local time. Two clocks on one page is
    worse than either alone: the engine stop looked like it fired at 7am."""

    def test_the_broker_stop_reads_as_the_founder_reads_it(self) -> None:
        assert ist_display("2026-09-04T07:41:13+00:00") == "04/09/26, 01:11 pm"

    def test_the_08_sep_stop_and_the_manual_close(self) -> None:
        assert ist_display("2026-09-08T04:12:32+00:00") == "08/09/26, 09:42 am"
        assert ist_display("2026-09-11T04:01:17+00:00") == "11/09/26, 09:31 am"

    def test_a_naive_stamp_is_read_as_utc_not_as_local(self) -> None:
        """Every stored timestamp on this platform is UTC. Reading a naive one
        as local would shift every leg by 5h30m in the flattering direction for
        morning fills and nobody would notice."""
        assert ist_display("2026-09-11T04:01:17") == "11/09/26, 09:31 am"

    def test_a_datetime_object_works_too(self) -> None:
        assert (
            ist_display(datetime(2026, 9, 4, 7, 41, 13, tzinfo=UTC)) == "04/09/26, 01:11 pm"
        )

    def test_falsification_twin_it_actually_converts(self) -> None:
        """The twin. A formatter that ignored the timezone would render 07:41
        and still 'look formatted'. The whole point is that the number MOVES."""
        out = ist_display("2026-09-04T07:41:13+00:00")
        assert "07:41" not in out
        assert "01:11 pm" in out

    def test_falsification_twin_unparseable_is_none_not_a_guess(self) -> None:
        """A dash on screen beats a wrong time. Never substitute 'now'."""
        assert ist_display("not a time") is None
        assert ist_display(None) is None
        assert ist_display("") is None


class TestR1_4_TheLegLabelsAreTheCustomersWords:
    def test_the_engine_stop_is_named_plainly(self) -> None:
        assert leg_label("broker_stop") == "broker stop (auto)"

    def test_a_manual_close_says_which_app(self) -> None:
        assert leg_label("manual_close") == "manual close (Dhan app)"

    def test_falsification_twin_an_unmapped_role_prints_itself(self) -> None:
        """Never invent a friendly name for a role nobody has named. A wrong
        label is a claim about who placed the order."""
        assert leg_label("some_new_role") == "some_new_role"


@dataclass
class _Trip:
    """Just enough of RoundTrip to exercise ``writable``."""

    complete: bool = True
    net_pnl: Decimal | None = Decimal("100")
    live: bool = False
    attribution: object | None = None
    legs_balanced: bool | None = True

    @property
    def writable(self) -> bool:
        from app.domains.pnl_reconciler.service import RoundTrip

        return RoundTrip.writable.fget(self)  # type: ignore[attr-defined]


class TestR1_5_LegsMustBalanceBeforeAnythingIsWritten:
    """Attribution walks the ACCOUNT's book and can price a trip perfectly while
    OUR record of it is short a leg — exactly the 03-Sep shape, where the
    engine's broker-stop exit existed at Dhan and nowhere in
    strategy_executions. A final_pnl on a row whose legs do not add up is a
    number the page cannot show its working for."""

    def test_unbalanced_legs_block_the_write(self) -> None:
        assert _Trip(legs_balanced=False).writable is False

    def test_balanced_legs_allow_it(self) -> None:
        assert _Trip(legs_balanced=True).writable is True

    def test_no_billed_charges_blocks_it_without_any_extra_rule(self) -> None:
        """Net IS billed now, so a trip whose fills carry no charges has
        net_pnl None and is excluded by the first condition alone."""
        assert _Trip(net_pnl=None).writable is False

    def test_falsification_twin_the_check_is_not_a_blanket_no(self) -> None:
        """The twin. A guard that returned False always would pass the first
        test and silently stop the reconciler writing anything, ever."""
        assert _Trip().writable is True
        assert _Trip(legs_balanced=None).writable is True, (
            "unchecked must not mean unwritable — paper trips never set it"
        )

    def test_a_live_trip_still_needs_a_priced_attribution(self) -> None:
        """R1.5 ADDS a condition; it must not replace the live-money one."""

        class _Unpriced:
            priced = False

        assert _Trip(live=True, attribution=_Unpriced(), legs_balanced=True).writable is False
