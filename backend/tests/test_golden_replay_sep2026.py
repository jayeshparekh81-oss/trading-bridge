"""GOLDEN REPLAY — the real 1..16 Sep 2026 fills must produce the P4 table.

WHAT THIS PINS. Every number the founder is shown for the BSE Ltd bot's live
record, replayed from the ACTUAL Dhan trade book and the ACTUAL WS order-update
tape, both committed as fixtures under ``tests/fixtures/golden_bse_sep2026/``.
No network, no database, no clock: the same bytes in, the same table out.

ADDITION E (founder, 2026-09-16). The two headline figures are asserted
EXACTLY, to the paisa:

    TOTAL CHARGES  6,653.58     TOTAL NET  77,486.42

They are not spot-checks. A refactor that moves any leg, drops any charge field
or re-attributes any fill moves one of them, and this file goes red.

WHY BILLED, NEVER MODELLED. The model was optimistic by 1,029.84 (it produced
78,516.26). It cannot be repaired: on 04-Sep it charges STT on BOTH 400-lot
sells, while Dhan billed 1366.40 on 312260904412406 and 0.00 on
23226090443106. Every charge here is what Dhan's own book says it billed.

THE FIXTURE IS THE ACCOUNT'S, NOT THE BOT'S. All 17 fills of security 68456 in
the window are present, including the founder's four hand-placed FAST trades —
because the point of the exercise is that the ingester separates them, and a
fixture that omitted them could not prove that.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.domains.pnl_reconciler.attribution import attribute
from app.domains.pnl_reconciler.ingest import classify
from app.domains.pnl_reconciler.order_tape import apply_provenance, coverage_gaps, load_tape
from app.domains.pnl_reconciler.tradebook import load_dhan_tradebook

FIXTURES = Path(__file__).parent / "fixtures" / "golden_bse_sep2026"

#: Order ids THIS platform placed (correlationId strategy-engine*). Evidence
#: from our own strategy_executions, not a guess from the order's shape.
PLATFORM_ORDERS = {
    "32226090368506", "34226090334306", "23226090443106", "322260907150406",
    "34226090862006", "32226090941906", "23226091175306", "23226091180006",
    "222260915111506", "34226091617106",
}

#: THE P4 TABLE. gross is fill-sourced; charges are Dhan's billed total for
#: every order id in the round trip; net is gross - charges. Nothing modelled.
P4 = {
    "844b8037": {
        "gross": Decimal("80360.00"), "charges": Decimal("2302.2784"),
        "orders": ["32226090368506", "34226090334306", "312260904412406"],
    },
    "a13ddeb0": {
        "gross": Decimal("-61020.00"), "charges": Decimal("2602.9570"),
        "orders": ["322260907150406", "312260908126806"],
    },
    "9165ebbe": {
        "gross": Decimal("69160.00"), "charges": Decimal("1615.2172"),
        "orders": ["23226091175306", "23226091180006", "222260915111506"],
    },
    # Not a trade the strategy took: the platform's SL fired 4 minutes after the
    # engine's stop had already taken the position to zero, opening a short 400
    # from flat. Counted, because the founder pays for the system's mistakes the
    # same as for its wins — gross with gross, net with net.
    "dup-exit": {
        "gross": Decimal("-4360.00"), "charges": Decimal("133.1296"),
        "orders": ["23226090443106", "362260904291606", "222260904331206"],
    },
}

TOTAL_GROSS = Decimal("84140.00")
TOTAL_CHARGES = Decimal("6653.58")
TOTAL_NET = Decimal("77486.42")

CHARGE_FIELDS = (
    "brokerageCharges", "exchangeTransactionCharges", "sebiTax",
    "serviceTax", "stampDuty", "stt",
)


@pytest.fixture(scope="module")
def fills():
    return load_dhan_tradebook(FIXTURES / "tradebook.jsonl")


@pytest.fixture(scope="module")
def tape():
    return load_tape(FIXTURES / "order_tape.jsonl")


@pytest.fixture(scope="module")
def ledger() -> set[str]:
    ids = json.loads((FIXTURES / "engine_orders.json").read_text())
    return {str(i) for i in ids}


def _billed(order_ids) -> Decimal:
    """Dhan's billed total for these orders — THROUGH THE PRODUCTION LOADER.

    Deliberately not a re-summation of the raw JSON. If this file added up the
    charge fields itself, the two Addition-E totals would be pinned to the
    FIXTURE and not to the code: ``_billed_charges`` could drop a field, or
    start coalescing a missing charge to zero, and the headline assertions
    would sail through. Reading ``AccountFill.charges`` puts the real parser on
    the hook for the founder's number.
    """
    want = set(order_ids)
    total = Decimal("0")
    for fill in load_dhan_tradebook(FIXTURES / "tradebook.jsonl"):
        if fill.order_id in want:
            assert fill.charges is not None, f"{fill.order_id} lost its billed charges"
            total += fill.charges
    return total


class TestTheFixtureIsTheRealRecord:
    def test_the_window_holds_seventeen_fills_of_the_strategys_future(self, fills) -> None:
        assert len(fills) == 17
        assert {f.contract for f in fills} == {"68456"}

    def test_every_fill_is_covered_by_the_tape(self, fills, tape) -> None:
        """No gap. If this ever fails, the 15:50 check would be red that day and
        the affected fills would read 'pehchaan nahi'."""
        assert len(tape) == 16
        assert coverage_gaps(fills, tape) == []

    def test_todays_fills_are_unbilled_and_that_is_null_not_zero(self, fills) -> None:
        """🔴 THE RULE, CAUGHT LIVE. The two 16-Sep fills came back from Dhan
        with NO charge fields at all — same day, not yet billed. Every settled
        fill has them; today's do not.

        So ``charges`` is None, net is NULL, and the page says "charges baaki".
        This is precisely why ``_billed_charges`` returns None rather than zero:
        a zero here would let today's open position claim it cost nothing to
        trade, and the headline would quietly flatter itself by that much every
        single day the record is read before settlement."""
        unbilled = sorted({f.order_id for f in fills if f.charges is None})
        assert unbilled == ["34226091617106"], (
            "only today's unsettled order may lack charges"
        )
        billed = [f for f in fills if f.charges is not None]
        assert len(billed) == 15
        assert all(f.charges > 0 for f in billed), "a settled fill billed at 0 is a red"

    def test_falsification_twin_unbilled_is_not_silently_zero(self, fills) -> None:
        """The twin. If the loader ever coalesced a missing charge to Decimal(0),
        the assertion above would still pass while net became a confident,
        wrong number. So check the type, not just the truthiness."""
        todays = [f for f in fills if f.order_id == "34226091617106"]
        assert len(todays) == 2
        assert all(f.charges is None for f in todays)
        assert not any(f.charges == Decimal("0") for f in todays)


class TestWhoPlacedWhat:
    def test_the_three_way_split_is_twelve_bot_four_manual_none_unknown(
        self, fills, tape, ledger
    ) -> None:
        """🔴 THE ONE THAT MATTERS. Twelve of the account's orders are the bot's,
        four are the founder's own Dhan-app trades, and NOTHING is unidentified.
        A single 'unknown' here is an alert, not a rounding difference."""
        joined = apply_provenance(fills, tape)
        claimed = ledger | PLATFORM_ORDERS
        verdicts = {
            f.order_id: classify(f.order_id, tape.get(f.order_id), ledger_order_ids=claimed)
            for f in joined
        }
        assert sorted(o for o, v in verdicts.items() if v == "manual") == [
            "222260904331206",   # BUY 200 @3426.70 — cleaning up the duplicate short
            "35226091145606",    # BUY 200 @3215.40 — the close of d0086394
            "362260904291606",   # BUY 200 @3426.70 — cleaning up the duplicate short
            "362260908140706",   # SELL 200 @3389.20 — a standalone hand-placed trade
        ]
        assert [o for o, v in verdicts.items() if v == "unknown"] == []
        assert sum(1 for v in verdicts.values() if v == "bot") == 12

    def test_the_engine_stops_are_the_bots_through_their_parents(
        self, fills, tape, ledger
    ) -> None:
        """Both are FOVR — pine_replica places its trailing stops straight at
        Dhan, so they carry no TRADETRI correlationId. They are the bot's
        because the ENGINE'S OWN LEDGER claims them, not because of their shape."""
        for child in ("312260904412406", "312260908126806"):
            assert tape[child].platform == "FOVR"
            assert child in ledger
            assert classify(child, tape[child], ledger_order_ids=ledger) == "bot"

    def test_falsification_twin_without_the_ledger_they_are_not_manual(
        self, tape
    ) -> None:
        """Strip the ledger and an engine stop must become 'pehchaan nahi' — an
        alert — never 'manual'. Filing it as manual would publish the founder as
        having hand-closed his own bot's trade."""
        for child in ("312260904412406", "312260908126806"):
            assert classify(child, tape[child], ledger_order_ids=PLATFORM_ORDERS) == "unknown"

    def test_the_manual_trade_on_08_sep_sits_between_positions(self, fills) -> None:
        """362260908140706 closed nothing of ours: a13ddeb0's engine stop had
        already fired at 09:42:32 and d0086394 did not open until 14:00:10. A
        manual fill in a GAP taints no position — it is simply not our business."""
        by_id = {f.order_id: f for f in fills}
        assert by_id["312260908126806"].ts < by_id["362260908140706"].ts
        assert by_id["362260908140706"].ts < by_id["34226090862006"].ts


class TestTheP4TableToThePaisa:
    @pytest.mark.parametrize("row", sorted(P4))
    def test_each_rows_billed_charges(self, row: str) -> None:
        assert _billed(P4[row]["orders"]) == P4[row]["charges"]

    @pytest.mark.parametrize("row", sorted(P4))
    def test_each_rows_net_is_gross_minus_billed(self, row: str) -> None:
        expected = P4[row]["gross"] - P4[row]["charges"]
        assert P4[row]["gross"] - _billed(P4[row]["orders"]) == expected

    def test_addition_e_total_charges_is_exactly_6653_58(self) -> None:
        """🔴 ADDITION E. The founder's figure, to the paisa."""
        total = sum((_billed(P4[r]["orders"]) for r in P4), Decimal("0"))
        assert total.quantize(Decimal("0.01")) == TOTAL_CHARGES

    def test_addition_e_total_net_is_exactly_77486_42(self) -> None:
        """🔴 ADDITION E. The headline. If this moves, the page is wrong."""
        gross = sum((P4[r]["gross"] for r in P4), Decimal("0"))
        charges = sum((_billed(P4[r]["orders"]) for r in P4), Decimal("0"))
        assert gross == TOTAL_GROSS
        assert (gross - charges).quantize(Decimal("0.01")) == TOTAL_NET

    def test_falsification_twin_the_modelled_total_is_not_what_we_publish(self) -> None:
        """The twin, and the reason this file exists. The modelled net was
        78,516.26 — optimistic by 1,029.84. If a modelled fallback ever creeps
        back onto a customer page, the headline drifts up by that much and looks
        entirely plausible."""
        gross = sum((P4[r]["gross"] for r in P4), Decimal("0"))
        charges = sum((_billed(P4[r]["orders"]) for r in P4), Decimal("0"))
        net = (gross - charges).quantize(Decimal("0.01"))
        assert net != Decimal("78516.26")
        assert (Decimal("78516.26") - net).quantize(Decimal("0.01")) == Decimal("1029.84")

    def test_the_model_cannot_be_repaired_the_04_sep_proof(self) -> None:
        """Two SELL 400s, four minutes apart, same contract, same day. A model
        charges STT on both. Dhan billed it on one and not the other — so no
        per-fill formula can reproduce the bill, at any level of care."""
        billed = {
            "312260904412406": _billed(["312260904412406"]),
            "23226090443106": _billed(["23226090443106"]),
        }
        stt = {}
        for line in (FIXTURES / "tradebook.jsonl").read_text().splitlines():
            row = json.loads(line)
            if str(row["orderId"]) in billed:
                stt[str(row["orderId"])] = Decimal(str(row.get("stt") or 0))
        assert stt["312260904412406"] == Decimal("1366.40")
        assert stt["23226090443106"] == Decimal("0.0")


class TestTheAttributionAgrees:
    def test_the_bot_only_trips_price_and_the_manual_one_does_not(
        self, fills, tape, ledger
    ) -> None:
        """The exit rule, run over the real fills. 844b8037's exits are the
        bot's, so it prices. d0086394's close is a FAST fill, so it does not —
        final_pnl NULL, 'manual se band'."""
        joined = apply_provenance(fills, tape)
        by_id = {f.order_id: f for f in joined}
        bot_ids = ledger | PLATFORM_ORDERS

        priced = attribute(
            {"32226090368506"},
            [by_id[o] for o in ("32226090368506", "34226090334306", "312260904412406")],
            bot_order_ids=bot_ids,
        )
        assert priced.priced is True
        assert priced.billed_charges == P4["844b8037"]["charges"]

        tainted = attribute(
            {"34226090862006"},
            [by_id[o] for o in ("34226090862006", "32226090941906", "35226091145606")],
            bot_order_ids=bot_ids,
        )
        assert tainted.priced is False
        assert tainted.tag == "human_interfered"
