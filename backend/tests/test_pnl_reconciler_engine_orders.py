"""pine_replica IS the bot, so its stop orders are the bot's orders.

FOUNDER'S RULING, 2026-09-10:

    "pine_replica IS the bot. It's my engine; its FOVR stop orders are bot
     orders. The missing TRADETRI correlationId is an artifact of the bridge,
     not evidence of a human. So attribution must widen: a fill is the bot's
     if correlationId=strategy-engine* OR its order id appears in
     pine_replica's own ledger. That's evidence, not a guess."

WHAT THIS COST BEFORE THE RULING. Two real, fully-automated round trips were
published as ``human_interfered`` — a tag that by rule leaves ``final_pnl``
NULL — because the order that CLOSED each of them was placed by the founder's
own engine directly at Dhan and therefore carried no TRADETRI correlationId:

    844b8037  BUY 800 @3270.00  closed by 312260904412406 (engine stop child)
    a13ddeb0  BUY 800 @3470.30  closed by 312260908126806 (engine stop child)

Both children are tied to a stop PARENT recorded in pine_replica's own
``BROKER_STOP_SPENT.json`` (32132609031621 and 23132609071677 respectively),
and ``stop_child_fired.json`` records the second one firing at
2026-09-08T09:42:33+05:30. That is a ledger entry, not an inference from the
shape of the order — which is exactly the distinction the founder drew.

WHY IT IS SUPPLIED, NEVER SNIFFED. ``engine_order_ids`` is an explicit input.
Nothing tries to recognise "an order that looks like a stop": the trade book
carries no ``algoOrdNo``, so any such recognition would be a guess, and a
guess that mislabels a MANUAL fill as the bot's would publish a number the
founder never traded.
"""

from __future__ import annotations

from decimal import Decimal

from app.domains.pnl_reconciler.attribution import (
    TAG_ACCOUNT_FLAT,
    TAG_BOT_ONLY,
    AccountFill,
    attribute,
)

CONTRACT = "68456"  # Dhan securityId for BSE-SEP2026-FUT

#: The bot's entry, placed through TRADETRI — carries a correlationId.
ENTRY = "322260907150406"
#: The close, placed by pine_replica straight at Dhan — no correlationId.
ENGINE_STOP_CHILD = "312260908126806"


def _book() -> list[AccountFill]:
    """The account's fills for the a13ddeb0 round trip, entry then close."""
    return [
        AccountFill(
            contract=CONTRACT,
            order_id=ENTRY,
            side="BUY",
            qty=800,
            price=Decimal("3470.30"),
            ts="2026-09-07T10:30:21",
        ),
        AccountFill(
            contract=CONTRACT,
            order_id=ENGINE_STOP_CHILD,
            side="SELL",
            qty=800,
            price=Decimal("3394.025"),
            ts="2026-09-08T09:42:32",
        ),
    ]


class TestTheEngineCountsAsTheBot:
    def test_without_the_ledger_the_engine_close_reads_as_not_the_bot(self) -> None:
        """🔴 THE OLD BEHAVIOUR, kept as the contrast.

        Knowing only the TRADETRI correlationId, the engine's own stop is
        indistinguishable from a stranger's order, and the trip is not
        bot-only.
        """
        out = attribute({ENTRY}, _book(), bot_order_ids={ENTRY})
        assert out.tag == TAG_ACCOUNT_FLAT
        assert not out.priced or out.tag != TAG_BOT_ONLY

    def test_with_the_ledger_it_is_the_bot_and_the_trip_prices(self) -> None:
        """🔴 THE RULING. The same fills, plus the engine's ledger entry."""
        out = attribute(
            {ENTRY},
            _book(),
            bot_order_ids={ENTRY, ENGINE_STOP_CHILD},
        )
        assert out.tag == TAG_BOT_ONLY, (
            "the engine's own stop child must count as the bot — pine_replica "
            "IS the bot; the absent correlationId is a bridge artifact"
        )
        assert out.priced, "a bot-only trip must be priceable"

    def test_the_gross_is_the_founders_number(self) -> None:
        """(3394.025 - 3470.30) x 800 = -61,020."""
        out = attribute({ENTRY}, _book(), bot_order_ids={ENTRY, ENGINE_STOP_CHILD})
        assert out.gross_pnl == Decimal("-61020.000")

    def test_widening_never_prices_a_genuinely_manual_close(self) -> None:
        """The rule widens on EVIDENCE only.

        An order absent from the engine's ledger stays not-the-bot's, so a
        real manual fill can never be laundered into the record by this
        change. This is the guard on the guard.
        """
        book = _book()
        book[1] = AccountFill(
            contract=CONTRACT,
            order_id="362260908140706",  # a FAST manual fill, in nobody's ledger
            side="SELL",
            qty=800,
            price=Decimal("3389.20"),
            ts="2026-09-08T10:03:46",
        )
        out = attribute(
            {ENTRY},
            book,
            bot_order_ids={ENTRY, ENGINE_STOP_CHILD},  # ledger does NOT contain it
        )
        assert out.tag != TAG_BOT_ONLY, (
            "a manual close must never be counted as the bot's just because "
            "some other engine order was supplied"
        )
