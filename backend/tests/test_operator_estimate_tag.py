"""The 6th attribution tag, and the three things it must and must not do.

FOUNDER'S RULING, 2026-09-11. Position d0086394 was closed by hand: the engine
derived an RR_TP exit that its own guard then refused to dispatch, so there was
no broker fill for the closing 200 and the exit price is the engine's level.

None of the five existing tags could carry that. ``bot_only`` / ``account_flat``
MEAN "priced from the account's real fills" — using one would publish an
estimate as a reconciled fill. ``human_interfered`` is honest about the human
but its rule NULLs ``final_pnl``, which discards the number the founder chose
to record.

So ``operator_estimate`` is priced — it reaches the aggregates — but it can
never be mistaken for a broker-sourced figure, and an automated pass may never
erase it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.api.strategy_positions import (
    PositionLeg,
    _count_orders,
    _estimated_legs_from_history,
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
REAL_EXIT_PRICE = Decimal("3310.40")  # the 09-Sep partial, a genuine fill
ESTIMATED_EXIT_PRICE = Decimal("3264.90")  # the engine's RR level — never a fill
ENTRY_ORDER = "34226090862006"
PARTIAL_ORDER = "32226090941906"


def _history() -> list[dict]:
    """``action_history`` of d0086394 after the operator close."""
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


class TestTheTagReachesTheAggregates:
    def test_it_is_a_known_tag(self) -> None:
        assert TAG_OPERATOR_ESTIMATE in ATTRIBUTION_TAGS

    def test_the_executions_surface_prices_it(self) -> None:
        """Analytics / trades stats gate on this set."""
        assert TAG_OPERATOR_ESTIMATE in EXECUTIONS_PRICED

    def test_the_ledger_prices_it(self) -> None:
        assert TAG_OPERATOR_ESTIMATE in LEDGER_PRICED

    def test_it_did_not_displace_the_broker_sourced_tags(self) -> None:
        """The guard on the guard — widening must not drop anything."""
        for tag in (TAG_BOT_ONLY, TAG_ACCOUNT_FLAT):
            assert tag in EXECUTIONS_PRICED
            assert tag in LEDGER_PRICED


class TestAnAutomatedPassNeverErasesIt:
    """🔴 The destructive interaction this guard exists to stop.

    The reconciler prices from the account's trade book. On a re-run it would
    find NO fill for the estimated leg, classify the trip ``human_interfered``
    and — under ``--overwrite`` — NULL the number. That is not a correction,
    it is silent data loss on a money row.
    """

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

    def test_overwrite_leaves_an_operator_estimate_untouched(self) -> None:
        pos = self._Position(final_pnl=Decimal("41769.71"), pnl_attribution=TAG_OPERATOR_ESTIMATE)
        changed = apply_write(
            pos,  # type: ignore[arg-type]
            self._Trip(writable=False, net_pnl=None, attribution_tag="human_interfered"),  # type: ignore[arg-type]
            overwrite=True,
        )
        assert changed is None
        assert pos.final_pnl == Decimal("41769.71"), "the operator's number was erased"
        assert pos.pnl_attribution == TAG_OPERATOR_ESTIMATE, "the tag was overwritten"

    def test_an_untagged_row_is_still_overwritable(self) -> None:
        """Sensitivity: the guard must be specific, not a blanket no-op."""
        pos = self._Position(final_pnl=Decimal("100"), pnl_attribution=None)
        changed = apply_write(
            pos,  # type: ignore[arg-type]
            self._Trip(writable=True, net_pnl=Decimal("250"), attribution_tag=TAG_BOT_ONLY),  # type: ignore[arg-type]
            overwrite=True,
        )
        assert changed is not None
        assert pos.final_pnl == Decimal("250")


class TestTheExitPriceIsTheOneTheOperatorRecorded:
    def test_history_yields_one_estimated_leg(self) -> None:
        legs = _estimated_legs_from_history(_history())
        assert len(legs) == 1
        assert legs[0].price == ESTIMATED_EXIT_PRICE
        assert legs[0].quantity == 200
        assert legs[0].broker_fill is False
        assert legs[0].broker_order_id is None, "a broker order id must never be invented"

    def test_without_it_the_row_shows_the_wrong_exit(self) -> None:
        """🔴 THE BUG, kept as the contrast. 3310.40 was the 09-Sep partial."""
        out = derive_position_figures(
            side="sell", total_quantity=400, remaining_quantity=0, legs=_real_legs()
        )
        assert out.exit_price == REAL_EXIT_PRICE
        assert out.realised_pnl is None
        assert "do not reconcile" in out.reason

    def test_with_it_the_quantities_reconcile_and_the_price_is_blended(self) -> None:
        legs = _real_legs() + _estimated_legs_from_history(_history())
        out = derive_position_figures(
            side="sell", total_quantity=400, remaining_quantity=0, legs=legs
        )
        # (3310.40 * 200 + 3264.90 * 200) / 400
        assert out.exit_price == Decimal("3287.6500")
        assert out.quantity == 400
        assert out.realised_pnl is not None

    def test_the_caveat_is_inseparable_from_the_number(self) -> None:
        legs = _real_legs() + _estimated_legs_from_history(_history())
        out = derive_position_figures(
            side="sell", total_quantity=400, remaining_quantity=0, legs=legs
        )
        assert "OPERATOR ESTIMATE" in out.reason
        assert "200 of 400" in out.reason

    def test_no_brokerage_is_charged_on_an_order_that_never_existed(self) -> None:
        real = _real_legs()
        with_estimate = real + _estimated_legs_from_history(_history())
        assert _count_orders(real) == 2  # entry order + partial order
        assert _count_orders(with_estimate) == 2, (
            "the estimated leg was billed brokerage — Dhan never placed it"
        )


class TestOnlyADisclosedOperatorEventIsRead:
    """It reads EVIDENCE, never shape. A guess here would fabricate a price."""

    def test_a_normal_event_is_ignored(self) -> None:
        assert _estimated_legs_from_history(_history()[:2]) == []

    def test_a_broker_filled_event_is_ignored(self) -> None:
        history = [dict(_history()[2], broker_fill=True)]
        assert _estimated_legs_from_history(history) == []

    def test_an_event_without_a_price_is_skipped_not_guessed(self) -> None:
        history = [{k: v for k, v in _history()[2].items() if k != "exit_price"}]
        assert _estimated_legs_from_history(history) == []

    def test_an_event_without_a_quantity_is_skipped(self) -> None:
        history = [{k: v for k, v in _history()[2].items() if k != "qty"}]
        assert _estimated_legs_from_history(history) == []

    def test_junk_history_never_raises(self) -> None:
        assert _estimated_legs_from_history(None) == []
        assert _estimated_legs_from_history(["not a dict", 42]) == []
        assert _estimated_legs_from_history([dict(_history()[2], exit_price="nonsense")]) == []
