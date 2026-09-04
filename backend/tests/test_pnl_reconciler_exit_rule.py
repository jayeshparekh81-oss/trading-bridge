"""Cutover-26 (2026-09-04): traded-price fix, current cost schedule, founder's exit rule.

Three things this file pins, each with the REAL fills from Dhan's trade book:

1. ``parse_fill`` prices a Dhan fill from ``averageTradedPrice`` and never from
   the order's LIMIT price (``raw.price``). The first test FAILS on the old
   code by construction: the decoy limit price is what the old code returned.
2. The founder's exit rule (:mod:`attribution`): a bot trade closes when the
   account goes FLAT on the contract by any fill, provided no manual lots
   predate the bot's entry and nothing increased exposure before the flat
   point; otherwise NULL + ``human_interfered``. No lot-matching, no guesses.
3. The write path: a LIVE trip is never written without the account's trade
   book; ``overwrite`` NULLs a value the rule marks human-interfered and a
   stored literal zero on an unpriceable trip; the tag is always stamped.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.domains.pnl_reconciler.attribution import (
    HUMAN_INTERFERED_LABEL,
    TAG_ACCOUNT_FLAT,
    TAG_BOT_ONLY,
    TAG_HUMAN_INTERFERED,
    TAG_PAPER_SIM,
    TAG_UNPRICEABLE,
    AccountFill,
    attribute,
)
from app.domains.pnl_reconciler.costs import SEGMENT_RATES, SHOWCASE_NFO_RATES
from app.domains.pnl_reconciler.service import (
    apply_write,
    parse_fill,
    reconcile,
)
from app.domains.pnl_reconciler.tradebook import (
    account_fill_from_row,
    account_fills_from_rows,
    is_futures_row,
)

# ─── 1. parse_fill: the trade, never the limit ─────────────────────────


def _dhan_raw(**raw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "orderId": "222260828171906",
        "orderStatus": "TRADED",
        "correlationId": "strategy-engine",
        "filledQty": 800,
        # REAL 28 Aug entry of 388c845e: limit 3429.0, traded 3397.525.
        "price": 3429.0,
        "averageTradedPrice": 3397.525,
    }
    base.update(raw)
    return {"raw": base, "status": "pending", "broker_order_id": base["orderId"]}


def test_parse_fill_uses_average_traded_price_not_the_limit_price() -> None:
    """FAILS on the pre-2026-09-04 code, which returned raw['price'] (3429.0)."""
    fill = parse_fill(_dhan_raw())
    assert fill is not None
    assert fill.price == Decimal("3397.525")
    assert fill.price != Decimal("3429.0")
    assert fill.qty == 800
    assert fill.order_id == "222260828171906"
    assert fill.correlation_id == "strategy-engine"
    assert fill.is_live is True


def test_parse_fill_never_falls_back_to_the_limit_price() -> None:
    # A traded order with no ATP is UNPRICEABLE — never "approximately" priced.
    for missing in (
        {"averageTradedPrice": None},
        {"averageTradedPrice": 0},
        {"averageTradedPrice": "0.0"},
    ):
        fill = parse_fill(_dhan_raw(**missing))
        assert fill is not None
        assert fill.price is None, missing
    raw = _dhan_raw()
    del raw["raw"]["averageTradedPrice"]
    fill = parse_fill(raw)
    assert fill is not None and fill.price is None


def test_cost_schedule_is_current_and_single_sourced() -> None:
    nfo = SEGMENT_RATES["NFO"]
    assert nfo.stt_sell == Decimal("0.0005")  # 0.05% sell, eff. 2026-04-01
    assert nfo.exchange_txn == Decimal("0.0000183")  # NSE futures 0.00183%
    assert nfo.sebi_fee == Decimal("0.000001")
    assert nfo.stamp_buy == Decimal("0.00002")
    assert nfo.brokerage_per_order == Decimal("20")
    assert nfo.gst == Decimal("0.18")
    # The showcase can no longer drift from the ledger: same object.
    assert SHOWCASE_NFO_RATES is nfo
    assert SEGMENT_RATES["BFO"].stt_sell == Decimal("0.0005")


# ─── 2. The founder's exit rule on the real BSE SEP / JUN / CDSL books ──

SEP = "68456"  # Dhan securityId of BSE SEP 2026 FUT
BOT_SEP = {
    "23226082049906",  # 649ec8ed entry
    "34226082139006",
    "22226082455606",
    "222260828171906",  # 388c845e entry
    "34226083131606",  # 388c845e bot SL
    "23226083168506",  # f6dff74b entry
    "222260831416606",
    "23226083174506",
    "32226090368506",  # 844b8037 entry
    "34226090334306",
    "23226090443106",
}


def _f(order: str, side: str, qty: int, price: str, ts: str, contract: str = SEP) -> AccountFill:
    return AccountFill(
        contract=contract, order_id=order, side=side, qty=qty, price=Decimal(price), ts=ts
    )


def _sep_book() -> list[AccountFill]:
    """BSE SEP FUT, 19 Aug → 4 Sep 2026, every futures fill of the account."""
    return [
        # 19 Aug manual: net +1000 by close.
        _f("m1", "BUY", 1000, "3390.0", "2026-08-19T10:00:00"),
        _f("31226082023006", "SELL", 1000, "3400.24", "2026-08-20T09:16:50"),  # flat
        # 649ec8ed — bot only.
        _f("23226082049906", "SELL", 400, "3301.8", "2026-08-20T14:45:43"),
        _f("34226082139006", "BUY", 200, "3251.8", "2026-08-21T13:30:28"),
        _f("22226082455606", "BUY", 200, "3337.8", "2026-08-24T09:30:29"),  # flat
        _f("22226082488806", "BUY", 400, "3360.25", "2026-08-24T09:49:08"),
        _f("312260824136206", "BUY", 200, "3350.3", "2026-08-24T10:08:58"),
        _f("322260824149406", "BUY", 200, "3347.4", "2026-08-24T10:30:29"),
        _f("m2", "SELL", 800, "3314.25", "2026-08-25T10:00:00"),  # flat
        # 388c845e — founder's #2 sequence.
        _f("222260828171906", "BUY", 800, "3397.525", "2026-08-28T09:45:38"),
        _f("222260828421006", "SELL", 800, "3400.075", "2026-08-28T11:10:36"),  # flat (manual)
        _f("222260828421806", "BUY", 800, "3403.4", "2026-08-28T11:10:56"),
        _f("34226083131606", "SELL", 800, "3343.325", "2026-08-31T11:00:14"),  # bot SL → flat
        # f6dff74b — manual cover took the account flat before the bot's buys.
        _f("23226083168506", "SELL", 400, "3330.1", "2026-08-31T12:15:26"),
        _f("312260831496806", "BUY", 400, "3286.8", "2026-08-31T14:12:21"),  # flat (manual)
        _f("222260831416606", "BUY", 200, "3312.9", "2026-08-31T14:15:07"),
        _f("23226083174506", "BUY", 200, "3310.8", "2026-08-31T14:15:18"),  # +400 long
        _f("362260831379806", "SELL", 200, "3308.2", "2026-08-31T14:47:09"),  # +200 carried
        # 844b8037 — entered on top of a +200 lot → not attributable.
        _f("32226090368506", "BUY", 800, "3270.0", "2026-09-03T09:45:17"),
        _f("34226090334306", "SELL", 400, "3325.4", "2026-09-03T12:45:13"),
        _f("312260904412406", "SELL", 400, "3415.5", "2026-09-04T13:11:13"),
        _f(
            "23226090443106",
            "SELL",
            200,
            "3415.8",
            "2026-09-04T13:15:12",
        ),
        _f(
            "23226090443106",
            "SELL",
            200,
            "3415.8",
            "2026-09-04T13:15:12",
        ),
        _f("362260904291606", "BUY", 200, "3426.7", "2026-09-04T13:34:03"),
        _f("222260904331206", "BUY", 200, "3426.7", "2026-09-04T13:34:18"),
    ]


def test_388c845e_closes_at_the_manual_flat_fill_plus_2040() -> None:
    out = attribute({"222260828171906"}, _sep_book(), bot_order_ids=BOT_SEP)
    assert out.tag == TAG_ACCOUNT_FLAT
    assert out.priced and out.manual_exit
    assert [f.order_id for f in out.exit_fills] == ["222260828421006"]
    assert out.gross_pnl == Decimal("2040.000")  # (3400.075 - 3397.525) * 800
    assert "222260828421006" in out.reason


def test_649ec8ed_is_bot_only_when_no_manual_fill_touches_the_trip() -> None:
    out = attribute({"23226082049906"}, _sep_book(), bot_order_ids=BOT_SEP)
    assert out.tag == TAG_BOT_ONLY
    assert out.gross_pnl == Decimal("2800.0")
    assert [f.order_id for f in out.exit_fills] == ["34226082139006", "22226082455606"]


def test_f6dff74b_closes_at_the_manual_cover_not_the_bots_later_buys() -> None:
    out = attribute({"23226083168506"}, _sep_book(), bot_order_ids=BOT_SEP)
    assert out.tag == TAG_ACCOUNT_FLAT
    assert [f.order_id for f in out.exit_fills] == ["312260831496806"]
    assert out.gross_pnl == Decimal("17320.0")  # (3330.1 - 3286.8) * 400


def test_844b8037_prior_manual_lot_means_human_interfered_null() -> None:
    out = attribute({"32226090368506"}, _sep_book(), bot_order_ids=BOT_SEP)
    assert out.tag == TAG_HUMAN_INTERFERED
    assert out.gross_pnl is None and not out.priced
    assert "+200" in out.reason and "prior lots" in out.reason


def test_exposure_increase_before_flat_is_human_interfered() -> None:
    """bb97ec50: founder added 375 @3953.6 on top of the bot's 750 → a guess."""
    jun = "35003"
    book = [
        _f("34226061278006", "BUY", 750, "3975.0", "2026-06-12T11:30:26", jun),
        _f("312260612472906", "BUY", 375, "3953.6", "2026-06-12T13:02:42", jun),
        _f("352260612417806", "SELL", 375, "4004.1", "2026-06-12T14:07:24", jun),
        _f("232260612103906", "SELL", 375, "4033.3", "2026-06-12T14:30:08", jun),
        _f("23226061543506", "SELL", 375, "4117.6", "2026-06-15T10:44:29", jun),
    ]
    out = attribute(
        {"34226061278006"},
        book,
        bot_order_ids={"34226061278006", "232260612103906", "23226061543506"},
    )
    assert out.tag == TAG_HUMAN_INTERFERED
    assert "312260612472906" in out.reason and "increased" in out.reason


def test_crossing_zero_and_never_flat_are_not_guessed() -> None:
    c = "c"
    crossing = [
        _f("e", "BUY", 750, "100", "2026-01-01T10:00:00", c),
        _f("m", "SELL", 1500, "110", "2026-01-01T11:00:00", c),
    ]
    out = attribute({"e"}, crossing, bot_order_ids={"e"})
    assert out.tag == TAG_HUMAN_INTERFERED and "crossed" in out.reason
    never = [_f("e", "BUY", 750, "100", "2026-01-01T10:00:00", c)]
    out = attribute({"e"}, never, bot_order_ids={"e"})
    assert out.tag == TAG_HUMAN_INTERFERED and "never went flat" in out.reason
    out = attribute({"absent"}, never, bot_order_ids={"e"})
    assert out.tag == TAG_UNPRICEABLE


def test_cdsl_43920293_closed_by_the_manual_sell_three_hours_before_the_bot_sl() -> None:
    cd = "cdsl"
    book = [
        _f("322260717449006", "BUY", 950, "1420.0", "2026-07-17T15:00:10", cd),
        _f("31226072090006", "SELL", 950, "1399.85", "2026-07-20T09:33:41", cd),
        _f("222260720396106", "SELL", 950, "1386.55", "2026-07-20T12:49:02", cd),
        _f("222260720397406", "BUY", 950, "1388.4", "2026-07-20T12:49:56", cd),
    ]
    out = attribute({"322260717449006"}, book, bot_order_ids={"322260717449006", "222260720396106"})
    assert out.tag == TAG_ACCOUNT_FLAT
    assert out.gross_pnl == Decimal("-19142.50")
    assert [f.order_id for f in out.exit_fills] == ["31226072090006"]


def test_human_interfered_label_is_the_founders_wording() -> None:
    assert HUMAN_INTERFERED_LABEL == "human-interfered — not attributable"


# ─── tradebook parsing: options and equity excluded, both row shapes ────


def test_tradebook_rows_exclude_options_and_equity() -> None:
    history_fut = {
        "securityId": "68456",
        "customSymbol": "BSE SEP FUT",
        "drvOptionType": "NA",
        "exchangeSegment": "NSE_FNO",
        "transactionType": "SELL",
        "tradedQuantity": 800,
        "tradedPrice": 3343.325,
        "exchangeTime": "2026-08-31 11:00:14",
        "orderId": "34226083131606",
        "exchangeTradeId": "0",
    }
    today_fut = {**history_fut, "customSymbol": None, "tradingSymbol": "BSE-Sep2026-FUT"}
    today_pe = {
        **history_fut,
        "customSymbol": None,
        "tradingSymbol": "BSE-Oct2026-3400-PE",
        "drvOptionType": "NA",
    }
    history_call = {**history_fut, "customSymbol": "BSE 26 MAY 3600 CALL", "drvOptionType": "CALL"}
    equity = {**history_fut, "customSymbol": "BSE", "exchangeSegment": "NSE_EQ"}
    assert is_futures_row(history_fut) and is_futures_row(today_fut)
    assert not is_futures_row(today_pe)
    assert not is_futures_row(history_call)
    assert not is_futures_row(equity)
    fill = account_fill_from_row(today_fut)
    assert fill is not None and fill.contract == "68456" and fill.price == Decimal("3343.325")
    # De-dup: the same trade pulled twice (window overlap) is one fill.
    fills = account_fills_from_rows([history_fut, history_fut, today_pe, equity])
    assert len(fills) == 1
    # Today's page stamps "YYYY-MM-DD HH:MM:SS", history "YYYY-MM-DDTHH:MM:SS":
    # normalised so both shapes sort together and de-duplicate.
    assert fill.ts == "2026-08-31T11:00:14"
    spaced = {**history_fut, "exchangeTime": "2026-08-31 11:00:14"}
    assert len(account_fills_from_rows([history_fut, spaced])) == 1
    later = {**history_fut, "orderId": "later", "exchangeTime": "2026-08-31 14:00:00"}
    earlier = {**history_fut, "orderId": "earlier", "exchangeTime": "2026-08-31T12:00:00"}
    assert [f.order_id for f in account_fills_from_rows([later, earlier])] == ["earlier", "later"]


# ─── 3. Write path ──────────────────────────────────────────────────────


def _position(
    symbol: str, side: str, qty: int, history: list[dict[str, Any]], **kw: Any
) -> StrategyPosition:
    return StrategyPosition(
        id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        total_quantity=qty,
        remaining_quantity=0,
        status="closed",
        action_history=history,
        **kw,
    )


def _exec(
    signal_id: uuid.UUID,
    order_id: str,
    side: str,
    price: str,
    qty: int,
    corr: str = "strategy-engine",
) -> StrategyExecution:
    return StrategyExecution(
        signal_id=signal_id,
        broker_order_id=order_id,
        leg_number=1,
        leg_role="x",
        symbol="X",
        side=side,
        quantity=qty,
        order_type="LIMIT",
        broker_response={
            "raw": {
                "orderId": order_id,
                "orderStatus": "TRADED",
                "correlationId": corr,
                "price": str(Decimal(price) + 40),
                "averageTradedPrice": price,
                "filledQty": qty,
            },
            "status": "pending",
            "broker_order_id": order_id,
        },
    )


def _ev(action: str, qty: int, side: str, sid: uuid.UUID) -> dict[str, Any]:
    return {"action": action, "leg_role": action, "qty": qty, "side": side, "signal_id": str(sid)}


def test_live_trip_without_tradebook_is_reported_but_not_writable() -> None:
    e, x = uuid.uuid4(), uuid.uuid4()
    pos = _position(
        "BSE-SEP2026-FUT", "buy", 800, [_ev("entry", 800, "buy", e), _ev("sl_hit", 800, "long", x)]
    )
    execs = [
        _exec(e, "222260828171906", "buy", "3397.525", 800),
        _exec(x, "34226083131606", "sell", "3343.325", 800, "strategy-engine-direct-exit"),
    ]
    [trip] = reconcile([pos], execs)
    assert trip.complete and trip.gross_pnl == Decimal("-43360.000")
    assert trip.live and trip.attribution is None and trip.writable is False
    assert any("attribution required" in f for f in trip.flags)
    assert apply_write(pos, trip, overwrite=True) is None
    assert pos.final_pnl is None and pos.pnl_attribution is None


def test_live_trip_with_tradebook_is_priced_by_the_rule_and_written() -> None:
    e, x = uuid.uuid4(), uuid.uuid4()
    pos = _position(
        "BSE-SEP2026-FUT",
        "buy",
        800,
        [_ev("entry", 800, "buy", e), _ev("sl_hit", 800, "long", x)],
        final_pnl=Decimal("-94748.34"),
    )
    execs = [
        _exec(e, "222260828171906", "buy", "3397.525", 800),
        _exec(x, "34226083131606", "sell", "3343.325", 800, "strategy-engine-direct-exit"),
    ]
    [trip] = reconcile([pos], execs, account_fills=_sep_book())
    assert trip.attribution_tag == TAG_ACCOUNT_FLAT
    assert trip.gross_pnl == Decimal("2040.000")
    assert trip.costs is not None and trip.costs.total == Decimal("1585.44")
    assert trip.net_pnl == Decimal("454.560")
    assert trip.writable
    # Append-only: the wrong old value is kept unless overwrite.
    assert apply_write(pos, trip, overwrite=False) == "tag"
    assert pos.final_pnl == Decimal("-94748.34") and pos.pnl_attribution == TAG_ACCOUNT_FLAT
    assert apply_write(pos, trip, overwrite=True) == "pnl"
    assert pos.final_pnl == Decimal("454.560")
    assert (
        pos.pnl_attribution_detail is not None and "222260828421006" in pos.pnl_attribution_detail
    )


def test_overwrite_nulls_a_value_the_rule_marks_human_interfered() -> None:
    e, p, x = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    pos = _position(
        "BSE-SEP2026-FUT",
        "buy",
        800,
        [
            _ev("entry", 800, "buy", e),
            _ev("partial", 400, "long", p),
            _ev("sl_hit", 400, "long", x),
        ],
        final_pnl=Decimal("28667.82"),
    )
    execs = [
        _exec(e, "32226090368506", "buy", "3270.0", 800),
        _exec(p, "34226090334306", "sell", "3325.4", 400, "strategy-engine-direct-exit"),
        _exec(x, "23226090443106", "sell", "3415.8", 400, "strategy-engine-direct-exit"),
    ]
    [trip] = reconcile([pos], execs, account_fills=_sep_book())
    assert trip.attribution_tag == TAG_HUMAN_INTERFERED
    assert trip.complete is False and trip.net_pnl is None
    assert apply_write(pos, trip, overwrite=False) == "tag"
    assert pos.final_pnl == Decimal("28667.82")  # append-only keeps it
    assert apply_write(pos, trip, overwrite=True) == "nulled"
    assert pos.final_pnl is None and pos.pnl_attribution == TAG_HUMAN_INTERFERED


def test_overwrite_nulls_a_literal_zero_on_an_unpriceable_paper_trip() -> None:
    e = uuid.uuid4()
    pos = _position(
        "BSE-MAY2026-FUT", "buy", 2, [_ev("entry", 2, "buy", e)], final_pnl=Decimal("0")
    )
    [trip] = reconcile([pos], [], account_fills=[])
    assert trip.attribution_tag == TAG_UNPRICEABLE and trip.live is False
    assert apply_write(pos, trip, overwrite=False) == "tag"
    assert pos.final_pnl == Decimal("0")
    assert apply_write(pos, trip, overwrite=True) == "nulled"
    assert pos.final_pnl is None


def test_paper_trip_needs_no_tradebook_and_is_bot_only() -> None:
    e, x = uuid.uuid4(), uuid.uuid4()
    pos = _position(
        "TESTPAPER", "buy", 50, [_ev("entry", 50, "buy", e), _ev("exit", 50, "long", x)]
    )
    execs = [
        StrategyExecution(
            signal_id=e,
            broker_order_id="PAPER-1",
            leg_number=1,
            leg_role="entry",
            symbol="X",
            side="buy",
            quantity=50,
            order_type="MARKET",
            broker_response={
                "raw": {"source": "strategy_executor", "paper_mode": True},
                "status": "complete",
                "quantity": 50,
                "avg_price": "100",
            },
        ),
        StrategyExecution(
            signal_id=x,
            broker_order_id="PAPER-2",
            leg_number=1,
            leg_role="direct_exit",
            symbol="X",
            side="sell",
            quantity=50,
            order_type="MARKET",
            broker_response={
                "raw": {"source": "direct_exit", "paper_mode": True},
                "status": "complete",
                "filled_qty": 50,
                "fill_price": "110",
            },
        ),
    ]
    [trip] = reconcile([pos], execs)
    assert trip.live is False and trip.attribution_tag == TAG_PAPER_SIM and trip.writable
    assert apply_write(pos, trip, overwrite=False) == "pnl"
    assert pos.final_pnl == trip.net_pnl and pos.pnl_attribution == TAG_PAPER_SIM
    # The live ledger never counts a simulated P&L.
    from app.strategy_engine.ledger.snapshots import PRICED_ATTRIBUTION_TAGS

    assert TAG_PAPER_SIM not in PRICED_ATTRIBUTION_TAGS
    # And on a LIVE strategy (trade book supplied) the same paper-era row is
    # unpriceable — a sim fill has no entry in the broker's book.
    pos2 = _position(
        "TESTPAPER", "buy", 50, [_ev("entry", 50, "buy", e), _ev("exit", 50, "long", x)]
    )
    [trip2] = reconcile([pos2], execs, account_fills=_sep_book())
    assert trip2.attribution_tag == TAG_UNPRICEABLE and trip2.net_pnl is None
