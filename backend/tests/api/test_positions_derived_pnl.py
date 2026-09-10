"""The positions row must say how it closed, at what price, and for how much.

``strategy_positions`` has no exit-price column, and ``final_pnl`` is written
by the reconciler for ``status=closed`` rows only — so a PARTIAL showed a
dash where a real, already-banked number existed. Both figures are DERIVED
here from the position's own order legs.

Two rules are pinned hard because breaking either of them puts a wrong number
on a live money screen:

* a figure that cannot be resolved is NULL **with a reason**, never a mean
  taken over whatever subset of the legs happened to resolve;
* charges are counted PER REAL BROKER ORDER — the 07-Sep entry is FOUR
  execution rows of 200 sharing ONE broker order id, and that is ONE ₹20
  brokerage, not four.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.api.strategy_positions import (
    PositionLeg,
    _legs_by_signal,
    _signal_ids_from_history,
    derive_position_figures,
)
from app.domains.pnl_reconciler.costs import compute_costs
from app.schemas.strategy_position import StrategyPositionRead

ENTRY_ORDER = "322260907150406"  # the real 07-Sep entry order
EXIT_ORDER = "322260908150999"


def _entry(qty: int, price: str | None, order_id: str | None = ENTRY_ORDER):
    return PositionLeg(
        leg_role="entry",
        quantity=qty,
        price=None if price is None else Decimal(price),
        broker_order_id=order_id,
    )


def _exit(
    qty: int,
    price: str | None,
    role: str = "direct_partial",
    order_id: str | None = EXIT_ORDER,
):
    return PositionLeg(
        leg_role=role,
        quantity=qty,
        price=None if price is None else Decimal(price),
        broker_order_id=order_id,
    )


class TestExitPriceDerivation:
    def test_quantity_weighted_mean_of_the_exit_legs(self) -> None:
        """Two exits of different sizes — the mean is WEIGHTED, not simple."""
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[
                _entry(800, "3400.00"),
                _exit(600, "3450.00", role="direct_partial", order_id="A"),
                _exit(200, "3350.00", role="direct_exit", order_id="B"),
            ],
        )
        # (600*3450 + 200*3350) / 800 = 3425, not the simple mean 3400.
        assert out.exit_price == Decimal("3425.0000")

    @pytest.mark.parametrize("role", ["direct_exit", "direct_sl", "direct_partial"])
    def test_every_non_entry_role_counts_as_an_exit(self, role: str) -> None:
        out = derive_position_figures(
            side="sell",
            total_quantity=400,
            remaining_quantity=0,
            legs=[_entry(400, "3400.00"), _exit(400, "3390.00", role=role)],
        )
        assert out.exit_price == Decimal("3390.0000")

    def test_an_unpriced_exit_leg_returns_null_not_a_partial_mean(self) -> None:
        """🔴 The guess this test exists to forbid.

        One of two exit legs has no price. Averaging the one that resolved
        would print a confident 3450 for an exit that was half done elsewhere.
        """
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[
                _entry(800, "3400.00"),
                _exit(400, "3450.00", order_id="A"),
                _exit(400, None, order_id="B"),
            ],
        )
        assert out.exit_price is None
        assert out.realised_pnl is None
        assert "no recorded price" in out.reason

    def test_no_exit_legs_at_all_is_null(self) -> None:
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=800,
            legs=[_entry(800, "3400.00")],
        )
        assert out.exit_price is None
        assert out.realised_pnl is None
        assert "still open" in out.reason

    def test_legs_that_do_not_add_up_price_nothing(self) -> None:
        """The legs say 200 left; the position row says 400 did. No number."""
        out = derive_position_figures(
            side="sell",
            total_quantity=800,
            remaining_quantity=400,
            legs=[_entry(800, "3400.00"), _exit(200, "3390.00")],
        )
        # The exit price still describes the legs we DO have...
        assert out.exit_price == Decimal("3390.0000")
        # ...but the P&L would be pricing a quantity that is in dispute.
        assert out.realised_pnl is None
        assert "do not reconcile" in out.reason


class TestRealisedOnTheClosedPortion:
    def test_a_partial_prices_its_closed_half(self) -> None:
        """d0086394-shaped: SELL 400, 200 exited, 200 still in the market."""
        legs = [
            _entry(200, "3400.00", order_id=ENTRY_ORDER),
            _entry(200, "3400.00", order_id=ENTRY_ORDER),
            _exit(200, "3350.00", order_id=EXIT_ORDER),
        ]
        out = derive_position_figures(
            side="sell",
            total_quantity=400,
            remaining_quantity=200,
            legs=legs,
        )
        # Short: sold at 3400, bought back 200 at 3350 → +50 * 200 gross.
        assert out.gross_pnl == Decimal("10000.00")
        assert out.quantity == 200
        expected = compute_costs(
            buy_turnover=Decimal("670000"),  # 200 bought back @ 3350
            sell_turnover=Decimal("680000"),  # 200 sold @ 3400
            orders=2,  # one entry order + one exit order
        )
        assert out.charges == expected.total
        assert out.realised_pnl == Decimal("10000.00") - expected.total
        assert "the closed 200 of 400" in out.reason

    def test_a_long_and_a_short_get_opposite_signs(self) -> None:
        long_side = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[_entry(800, "3400.00"), _exit(800, "3450.00")],
        )
        short_side = derive_position_figures(
            side="sell",
            total_quantity=800,
            remaining_quantity=0,
            legs=[_entry(800, "3400.00"), _exit(800, "3450.00")],
        )
        assert long_side.gross_pnl == Decimal("40000.00")
        assert short_side.gross_pnl == Decimal("-40000.00")

    def test_four_entry_rows_on_one_broker_order_are_one_brokerage(self) -> None:
        """🔴 The over-charge this test exists to forbid.

        The 07-Sep entry is FOUR execution rows of 200 sharing ONE broker
        order id. Brokerage is per EXECUTED ORDER, so that is ONE ₹20 charge
        plus ONE for the exit — costing it per leg bills five orders.
        """
        legs = [_entry(200, "3400.00") for _ in range(4)]
        legs.append(_exit(800, "3450.00", role="direct_exit"))
        out = derive_position_figures(
            side="buy", total_quantity=800, remaining_quantity=0, legs=legs
        )
        two_orders = compute_costs(
            buy_turnover=Decimal("2720000"),
            sell_turnover=Decimal("2760000"),
            orders=2,
        )
        five_orders = compute_costs(
            buy_turnover=Decimal("2720000"),
            sell_turnover=Decimal("2760000"),
            orders=5,
        )
        assert out.charges == two_orders.total
        assert out.charges != five_orders.total

    def test_each_real_exit_order_carries_its_own_charge(self) -> None:
        """A partial exit is its own order — never pro-rata, never spread."""
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[
                _entry(800, "3400.00"),
                _exit(400, "3450.00", order_id="EXIT-A"),
                _exit(400, "3460.00", order_id="EXIT-B"),
            ],
        )
        assert out.charges == compute_costs(
            buy_turnover=Decimal("2720000"),
            sell_turnover=Decimal("2764000"),
            orders=3,  # entry + two real exit orders
        ).total

    def test_the_net_is_always_gross_minus_the_charges(self) -> None:
        out = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[_entry(800, "3400.00"), _exit(800, "3450.00")],
        )
        assert out.realised_pnl == out.gross_pnl - out.charges


class TestItAlwaysSaysWhy:
    @pytest.mark.parametrize(
        ("legs", "needle"),
        [
            ([_exit(800, "3450.00")], "no entry leg"),
            ([_entry(800, None), _exit(800, "3450.00")], "no recorded price"),
        ],
    )
    def test_an_unpriceable_closed_portion_is_null_with_a_reason(
        self, legs: list[PositionLeg], needle: str
    ) -> None:
        out = derive_position_figures(
            side="buy", total_quantity=800, remaining_quantity=0, legs=legs
        )
        assert out.realised_pnl is None
        assert needle in out.reason

    def test_an_unknown_side_is_never_priced(self) -> None:
        out = derive_position_figures(
            side="", total_quantity=800, remaining_quantity=0,
            legs=[_entry(800, "3400.00"), _exit(800, "3450.00")],
        )
        assert out.realised_pnl is None
        assert "unknown position side" in out.reason

    def test_the_reason_is_never_blank(self) -> None:
        priced = derive_position_figures(
            side="buy",
            total_quantity=800,
            remaining_quantity=0,
            legs=[_entry(800, "3400.00"), _exit(800, "3450.00")],
        )
        assert priced.reason.strip()

    def test_human_interfered_still_prices_the_unambiguous_portion(self) -> None:
        """The founder's rule: the tag may cover the ambiguous PART only.

        A human-interfered verdict is about the ACCOUNT. The bot's own legs
        are still on the record, so the closed portion is priced — and the
        row says whose legs the number came from.
        """
        out = derive_position_figures(
            side="sell",
            total_quantity=400,
            remaining_quantity=200,
            legs=[_entry(400, "3400.00"), _exit(200, "3350.00")],
            pnl_attribution="human_interfered",
        )
        assert out.realised_pnl is not None
        assert "the bot's own legs" in out.reason
        assert "human_interfered" in out.reason
        assert "ACCOUNT" in out.reason


class TestNoRawBrokerPayloadEscapes:
    FORBIDDEN = (
        "broker_response",
        "raw_response",
        "orderStatus",
        "averageTradedPrice",
        "dhanClientId",
        "access_token",
    )

    def test_the_response_schema_has_no_broker_envelope_field(self) -> None:
        for name in self.FORBIDDEN:
            assert name not in StrategyPositionRead.model_fields

    def test_a_serialised_row_carries_no_broker_envelope(self) -> None:
        row = StrategyPositionRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            strategy_id=uuid.uuid4(),
            broker_credential_id=uuid.uuid4(),
            signal_id=uuid.uuid4(),
            symbol="BSE-SEP2026-FUT",
            side="sell",
            total_quantity=400,
            remaining_quantity=200,
            avg_entry_price=Decimal("3400.00"),
            target_price=None,
            stop_loss_price=None,
            trail_offset=None,
            highest_price_seen=None,
            status="partial",
            opened_at="2026-09-07T09:20:00+00:00",
            closed_at=None,
            final_pnl=None,
            created_at="2026-09-07T09:20:00+00:00",
            exit_reason=None,
            last_action="partial",
            last_action_at="2026-09-08T09:20:00+00:00",
            exit_price=Decimal("3350.0000"),
            derived_realised_pnl=Decimal("9500.00"),
        )
        dumped = row.model_dump_json()
        for name in self.FORBIDDEN:
            assert name not in dumped

    def test_the_leg_value_object_cannot_carry_one(self) -> None:
        """The pricing path never even loads the envelope out of the DB."""
        assert "broker_response" not in PositionLeg.__dataclass_fields__


class TestTheQueryIsCheapAndScoped:
    def test_signal_ids_come_from_the_action_history_chain(self) -> None:
        sid = uuid.uuid4()
        ids = _signal_ids_from_history(
            [
                {"action": "entry", "signal_id": str(sid)},
                {"action": "partial", "signal_id": str(sid)},  # de-duplicated
                {"action": "exit", "signal_id": "not-a-uuid"},
                {"action": "exit"},
                "junk",
            ]
        )
        assert ids == [sid]

    async def test_one_query_for_the_page_and_no_broker_payload_in_it(self) -> None:
        captured: list[object] = []

        class _FakeSession:
            async def execute(self, stmt):
                captured.append(stmt)
                return iter(())

        sids = {uuid.uuid4() for _ in range(3)}
        out = await _legs_by_signal(_FakeSession(), sids)

        assert out == {}
        assert len(captured) == 1, "one query for the whole page, never one per row"
        sql = str(captured[0]).lower()
        # A subscriber's simulated fan-out fill shares the OWNER's signal id;
        # without this filter it would be averaged into a real exit price.
        assert "subscription_id is null" in sql
        assert "broker_response" not in sql

    async def test_no_signal_ids_means_no_query_at_all(self) -> None:
        class _Boom:
            async def execute(self, stmt):  # pragma: no cover - must not run
                raise AssertionError("a page with nothing to price must not query")

        assert await _legs_by_signal(_Boom(), set()) == {}
