"""``operator_estimate`` is a LABEL, never a price. The reversal, pinned.

HISTORY, kept because the reversal is the point.

On 2026-09-11 position d0086394 was closed by hand and given a figure the
engine had derived but never dispatched (exit 3264.90, ``final_pnl``
41,769.71). A tag ``operator_estimate`` was added, put INTO the priced sets so
the number reached Analytics / the ledger / the public showcase, and a guard
was added to ``apply_write`` so an automated pass could never overwrite it.

The stated premise was "a re-run would find no fill". It was false. A real Dhan
fill existed — order ``35226091145606``, BUY 200 @3215.40, 2026-09-11 09:31:17
IST, ``orderPlatform=FAST`` (manual, Dhan app) — placed about three hours AFTER
the estimate was recorded. The guard then made the row permanently
uncorrectable: the one mechanism that could have found that fill was the CLI
with ``--tradebook --overwrite``, and the guard turned it into a no-op.

The founder's standing rule governs and is narrower: *every P&L must come from
an actual Dhan fill; if a fill cannot be found the value stays NULL with a
reason, never a guess.*

So, as of 2026-09-16:
  * the tag still EXISTS — the row keeps its disclosure and its history —
  * it is NOT in any priced set, so it reaches no money surface,
  * it does NOT block the reconciler, so the real fill is discoverable,
  * and a quantity with no fill behind it makes the row UNPRICEABLE with a
    stated reason, instead of being averaged into an exit price.

Every test below carries a falsification twin: a case that must still behave
the old way, so a blanket change cannot pass by making everything inert.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.api.strategy_positions import (
    PositionLeg,
    _count_orders,
    _history_legs,
    derive_position_figures,
)
from app.domains.pnl_reconciler.attribution import (
    ATTRIBUTION_TAGS,
    TAG_ACCOUNT_FLAT,
    TAG_BOT_ONLY,
    TAG_OPERATOR_ESTIMATE,
)
from app.domains.pnl_reconciler.service import apply_write
from app.services.owner_executions import PRICED_ATTRIBUTION_TAGS as EXECUTIONS_PRICED
from app.strategy_engine.ledger.snapshots import PRICED_ATTRIBUTION_TAGS as LEDGER_PRICED

#: The real row, as it stands on prod.
ENTRY_PRICE = Decimal("3393.15")
REAL_EXIT_PRICE = Decimal("3310.40")  # the 09-Sep partial — a genuine fill
ENTRY_ORDER = "34226090862006"
PARTIAL_ORDER = "32226090941906"


def _history() -> list[dict]:
    """``action_history`` of d0086394 after the 11-Sep operator close."""
    return [
        {"ts": "2026-09-08T08:30:11+00:00", "qty": 400, "side": "sell", "action": "entry"},
        {"ts": "2026-09-09T04:00:14+00:00", "qty": 200, "side": "short", "action": "partial"},
        {
            "ts": "2026-09-10T06:15:00+00:00",
            "qty": 200,
            "side": "short",
            "action": "closed",
            "leg_role": "operator_reconcile",
            "estimated": True,
            "broker_fill": False,
            "exit_price": 3264.9,
        },
    ]


def _real_legs() -> list[PositionLeg]:
    return [
        PositionLeg("entry", 200, ENTRY_PRICE, ENTRY_ORDER),
        PositionLeg("entry", 200, ENTRY_PRICE, ENTRY_ORDER),
        PositionLeg("direct_partial", 200, REAL_EXIT_PRICE, PARTIAL_ORDER),
    ]


class TestTheEstimateReachesNoMoneySurface:
    def test_it_is_still_a_known_tag(self) -> None:
        """The label survives — the row must keep saying what happened to it."""
        assert TAG_OPERATOR_ESTIMATE in ATTRIBUTION_TAGS

    def test_it_is_not_priced_on_the_executions_surface(self) -> None:
        """🔴 THE REVERSAL. Analytics / trades stats gate on this set."""
        assert TAG_OPERATOR_ESTIMATE not in EXECUTIONS_PRICED

    def test_it_is_not_priced_on_the_ledger(self) -> None:
        """A hash-chained row that folded in an estimate could never be annotated."""
        assert TAG_OPERATOR_ESTIMATE not in LEDGER_PRICED

    def test_falsification_twin_the_real_tags_are_untouched(self) -> None:
        """The twin. Removing the estimate must not empty the sets — a change
        that made everything unpriced would pass the two tests above."""
        for tag in (TAG_BOT_ONLY, TAG_ACCOUNT_FLAT):
            assert tag in EXECUTIONS_PRICED
            assert tag in LEDGER_PRICED


class TestTheReconcilerCanReachTheRowAgain:
    """🔴 The guard that made a money row permanently uncorrectable is gone."""

    @dataclass
    class _Position:
        final_pnl: Decimal | None
        pnl_attribution: str | None
        pnl_attribution_detail: str | None = None

    @dataclass
    class _Trip:
        writable: bool
        net_pnl: Decimal | None
        attribution_tag: str | None
        attribution_detail: str | None = None

    def test_overwrite_can_now_reprice_an_operator_estimate(self) -> None:
        pos = self._Position(
            final_pnl=Decimal("41769.71"), pnl_attribution=TAG_OPERATOR_ESTIMATE
        )
        changed = apply_write(
            pos,  # type: ignore[arg-type]
            self._Trip(
                writable=True, net_pnl=Decimal("52100.00"), attribution_tag=TAG_ACCOUNT_FLAT
            ),  # type: ignore[arg-type]
            overwrite=True,
        )
        assert changed is not None, (
            "the reconciler is still blocked from correcting an operator estimate"
        )
        assert pos.final_pnl == Decimal("52100.00")
        assert pos.pnl_attribution == TAG_ACCOUNT_FLAT

    def test_overwrite_can_now_null_an_operator_estimate(self) -> None:
        """The other direction: the founder's manual-touch rule NULLs it."""
        from app.domains.pnl_reconciler.attribution import TAG_HUMAN_INTERFERED

        pos = self._Position(
            final_pnl=Decimal("41769.71"), pnl_attribution=TAG_OPERATOR_ESTIMATE
        )
        apply_write(
            pos,  # type: ignore[arg-type]
            self._Trip(
                writable=False, net_pnl=None, attribution_tag=TAG_HUMAN_INTERFERED
            ),  # type: ignore[arg-type]
            overwrite=True,
        )
        assert pos.final_pnl is None
        assert pos.pnl_attribution == TAG_HUMAN_INTERFERED

    def test_falsification_twin_append_only_still_holds_without_overwrite(self) -> None:
        """The twin. Removing the guard must not make every row writable: a
        stored value is still append-only unless --overwrite is passed."""
        pos = self._Position(final_pnl=Decimal("41769.71"), pnl_attribution=None)
        apply_write(
            pos,  # type: ignore[arg-type]
            self._Trip(
                writable=True, net_pnl=Decimal("999.00"), attribution_tag=TAG_BOT_ONLY
            ),  # type: ignore[arg-type]
            overwrite=False,
        )
        assert pos.final_pnl == Decimal("41769.71"), "append-only was broken"


class TestAQuantityWithNoFillIsNeverPriced:
    def test_the_operator_leg_carries_no_price(self) -> None:
        legs = _history_legs(_history())
        assert len(legs) == 1
        assert legs[0].price is None, "the operator's recorded price is being used"
        assert legs[0].quantity == 200
        assert legs[0].broker_fill is False
        assert legs[0].broker_order_id is None, "a broker order id must never be invented"

    def test_the_row_refuses_to_price_and_says_why(self) -> None:
        """🔴 THE RULE. 3287.65 / 41,769.71 used to come out of this call."""
        legs = _real_legs() + _history_legs(_history())
        out = derive_position_figures(
            side="sell", total_quantity=400, remaining_quantity=0, legs=legs
        )
        assert out.exit_price is None
        assert out.realised_pnl is None
        assert out.gross_pnl is None
        assert "NO BROKER FILL" in out.reason
        assert "200 of 400" in out.reason

    def test_falsification_twin_a_fully_filled_row_still_prices(self) -> None:
        """The twin. If the guard were a blanket refusal, this would go NULL
        too — and every honest row on the page would lose its number.

        Since D (2026-09-16) "prices" means GROSS always, and net once Dhan's
        bill is in. The unfilled-quantity guard is about the QUANTITY being in
        dispute, which is a different thing from the bill not having arrived —
        so both are checked separately here."""
        out = derive_position_figures(
            side="sell",
            total_quantity=400,
            remaining_quantity=200,
            legs=_real_legs(),
        )
        assert out.exit_price == REAL_EXIT_PRICE
        assert out.gross_pnl is not None, "the quantity is not in dispute"
        assert out.quantity == 200
        assert out.realised_pnl is None, "…but the bill has not arrived"

        orders = {leg.broker_order_id for leg in _real_legs() if leg.broker_order_id}
        with_bill = derive_position_figures(
            side="sell",
            total_quantity=400,
            remaining_quantity=200,
            legs=_real_legs(),
            billed_charges={o: Decimal("25.00") for o in orders},
        )
        assert with_bill.realised_pnl is not None
        assert with_bill.realised_pnl == with_bill.gross_pnl - with_bill.charges

    def test_no_brokerage_is_charged_on_an_order_that_never_existed(self) -> None:
        real = _real_legs()
        with_unfilled = real + _history_legs(_history())
        assert _count_orders(real) == 2
        assert _count_orders(with_unfilled) == 2


class TestOnlyADisclosedOperatorEventIsRead:
    """It reads EVIDENCE, never shape. A guess here would invent a quantity."""

    def test_a_normal_event_is_ignored(self) -> None:
        assert _history_legs(_history()[:2]) == []

    def test_a_broker_filled_event_is_ignored(self) -> None:
        assert _history_legs([dict(_history()[2], broker_fill=True)]) == []

    def test_an_event_without_a_quantity_is_skipped(self) -> None:
        history = [{k: v for k, v in _history()[2].items() if k != "qty"}]
        assert _history_legs(history) == []

    def test_a_missing_exit_price_no_longer_matters(self) -> None:
        """It never reads the operator's price now, so its absence cannot skip
        the leg — the QUANTITY is what makes the row unpriceable."""
        history = [{k: v for k, v in _history()[2].items() if k != "exit_price"}]
        assert len(_history_legs(history)) == 1

    def test_junk_history_never_raises(self) -> None:
        assert _history_legs(None) == []
        assert _history_legs(["not a dict", 42]) == []
        assert _history_legs([dict(_history()[2], qty="nonsense")]) == []
