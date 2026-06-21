"""Unit tests for the post-hoc P&L reconciler (pure logic — no DB).

Two verification layers:

* a synthetic PAPER round trip whose P&L is hand-checked, and
* a faithful reproduction of BSE strategy ``89423ecc``'s real rows (real Dhan
  fills + duplicate rows + a TRANSIT entry + a manual-Dhan-exit position) that
  asserts the exact per-trip and net numbers the reconciler must report.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.domains.pnl_reconciler.costs import (
    DEFAULT_SEGMENT,
    SEGMENT_RATES,
    compute_costs,
)
from app.domains.pnl_reconciler.service import (
    build_fill_index,
    parse_fill,
    plan_reconciliation,
    reconcile,
    reconcile_unrecorded,
)

# ─── Builders ──────────────────────────────────────────────────────────


def _dhan_fill(order_status: str, price: float | None, filled_qty: int | None) -> dict[str, Any]:
    raw: dict[str, Any] = {"orderId": "x", "orderStatus": order_status}
    if price is not None:
        raw["price"] = price
    if filled_qty is not None:
        raw["filledQty"] = filled_qty
    return {"raw": raw, "status": "pending", "broker_order_id": "x"}


def _paper_entry(avg_price: str, qty: int) -> dict[str, Any]:
    return {
        "raw": {"source": "strategy_executor", "paper_mode": True},
        "status": "complete",
        "message": "paper-mode simulated fill",
        "quantity": qty,
        "avg_price": avg_price,
    }


def _paper_exit(fill_price: str, qty: int) -> dict[str, Any]:
    return {
        "raw": {"source": "direct_exit", "paper_mode": True},
        "status": "complete",
        "message": "paper-mode simulated close",
        "fill_price": fill_price,
        "filled_qty": qty,
    }


def _execution(
    signal_id: uuid.UUID, leg_role: str, side: str, response: dict[str, Any]
) -> StrategyExecution:
    return StrategyExecution(
        signal_id=signal_id,
        broker_order_id="o",
        leg_number=1,
        leg_role=leg_role,
        symbol="X",
        side=side,
        quantity=1,
        order_type="MARKET",
        broker_response=response,
    )


def _event(action: str, leg_role: str, qty: int, side: str, signal_id: uuid.UUID) -> dict[str, Any]:
    return {
        "action": action,
        "leg_role": leg_role,
        "qty": qty,
        "side": side,
        "signal_id": str(signal_id),
    }


def _position(symbol: str, side: str, qty: int, history: list[dict[str, Any]]) -> StrategyPosition:
    return StrategyPosition(
        id=uuid.uuid4(),
        symbol=symbol,
        side=side,
        total_quantity=qty,
        remaining_quantity=0,
        status="closed",
        action_history=history,
    )


# ─── parse_fill ────────────────────────────────────────────────────────


def test_parse_fill_handles_three_shapes_and_none() -> None:
    dhan = parse_fill(_dhan_fill("TRADED", 4014.8, 750))
    assert dhan is not None
    assert dhan.status == "FILLED"
    assert dhan.price == Decimal("4014.8")
    assert dhan.qty == 750
    assert dhan.source == "dhan"

    pentry = parse_fill(_paper_entry("100", 50))
    assert pentry is not None
    assert pentry.status == "FILLED"
    assert pentry.price == Decimal("100")
    assert pentry.qty == 50
    assert pentry.source == "paper_entry"

    pexit = parse_fill(_paper_exit("110", 50))
    assert pexit is not None
    assert pexit.price == Decimal("110")
    assert pexit.source == "paper_exit"

    transit = parse_fill(_dhan_fill("TRANSIT", None, None))
    assert transit is not None
    assert transit.status == "PENDING"
    assert transit.price is None

    assert parse_fill(None) is None
    assert parse_fill({}) is None


# ─── Paper round trip (hand-checked) ───────────────────────────────────


def test_paper_long_round_trip_pnl_is_hand_checked() -> None:
    # LONG 50 @ 100 -> exit 50 @ 110  =>  (110 - 100) * 50 = +500.00
    entry_sig, exit_sig = uuid.uuid4(), uuid.uuid4()
    position = _position(
        "TESTPAPER",
        "buy",
        50,
        [
            _event("entry", "entry", 50, "buy", entry_sig),
            _event("exit", "direct_exit", 50, "long", exit_sig),
        ],
    )
    executions = [
        _execution(entry_sig, "entry", "buy", _paper_entry("100", 50)),
        _execution(exit_sig, "direct_exit", "sell", _paper_exit("110", 50)),
    ]

    [trip] = reconcile([position], executions)

    assert trip.complete is True
    assert trip.direction == "long"
    assert trip.entry_price == Decimal("100")
    assert trip.gross_pnl == Decimal("500")
    # Net = gross minus the estimated cost stack; fully auditable.
    assert trip.costs is not None
    assert trip.net_pnl == Decimal("500") - trip.costs.total
    assert trip.flags == []


def test_incomplete_when_exit_leg_missing_from_db() -> None:
    # Entry filled, but the close leg has no execution row (manual broker exit).
    entry_sig, exit_sig = uuid.uuid4(), uuid.uuid4()
    position = _position(
        "TESTPAPER",
        "buy",
        50,
        [
            _event("entry", "entry", 50, "buy", entry_sig),
            _event("exit", "direct_exit", 50, "long", exit_sig),
        ],
    )
    executions = [_execution(entry_sig, "entry", "buy", _paper_entry("100", 50))]

    [trip] = reconcile([position], executions)

    assert trip.complete is False
    assert trip.gross_pnl is None
    assert trip.net_pnl is None
    assert trip.costs is None
    assert any("missing from DB" in f for f in trip.flags)


# ─── BSE reproduction (real fills) ─────────────────────────────────────


def _bse_fixture() -> tuple[list[StrategyPosition], list[StrategyExecution]]:
    """Rebuild BSE 89423ecc's closed rows exactly as they exist in prod."""
    # signal ids (entry + each close leg) — values arbitrary but consistent.
    p1_entry = uuid.uuid4()
    p2_entry, p2_partial, p2_sl = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    p3_entry, p3_exit = uuid.uuid4(), uuid.uuid4()
    p4_entry, p4_sl = uuid.uuid4(), uuid.uuid4()
    pt_entry = uuid.uuid4()

    positions = [
        # Jun 4 LONG 750 — exited MANUALLY on Dhan (only an entry event).
        _position(
            "BSE-JUN2026-FUT",
            "buy",
            750,
            [_event("entry", "entry", 750, "buy", p1_entry)],
        ),
        # Jun 12 LONG 750 — partial 375 + SL 375.
        _position(
            "BSE-JUN2026-FUT",
            "buy",
            750,
            [
                _event("entry", "entry", 750, "buy", p2_entry),
                _event("partial", "direct_partial", 375, "long", p2_partial),
                _event("sl_hit", "direct_sl", 375, "long", p2_sl),
            ],
        ),
        # Jun 15 LONG 750 — full exit 750.
        _position(
            "BSE-JUN2026-FUT",
            "buy",
            750,
            [
                _event("entry", "entry", 750, "buy", p3_entry),
                _event("exit", "direct_exit", 750, "long", p3_exit),
            ],
        ),
        # Jun 17 SHORT 750 — SL cover 750.
        _position(
            "BSE-JUN2026-FUT",
            "sell",
            750,
            [
                _event("entry", "entry", 750, "sell", p4_entry),
                _event("sl_hit", "direct_sl", 750, "short", p4_sl),
            ],
        ),
        # May 20 — TRANSIT entry, never filled (noise; must be skipped).
        _position(
            "BSE-MAY2026-FUT",
            "buy",
            1500,
            [_event("entry", "entry", 1500, "buy", pt_entry)],
        ),
    ]

    executions = [
        # Jun 4 entry — TRADED 4136.7 (duplicate row included).
        _execution(p1_entry, "entry", "buy", _dhan_fill("TRADED", 4136.7, 750)),
        _execution(p1_entry, "entry", "buy", _dhan_fill("TRADED", 4136.7, 750)),
        # Jun 12 entry 4014.8 (dup) + partial 3993.1 + SL 4076.9.
        _execution(p2_entry, "entry", "buy", _dhan_fill("TRADED", 4014.8, 750)),
        _execution(p2_entry, "entry", "buy", _dhan_fill("TRADED", 4014.8, 750)),
        _execution(p2_partial, "direct_partial", "sell", _dhan_fill("TRADED", 3993.1, 375)),
        _execution(p2_sl, "direct_sl", "sell", _dhan_fill("TRADED", 4076.9, 375)),
        # Jun 15 entry 4212.0 (dup) + exit 4105.2.
        _execution(p3_entry, "entry", "buy", _dhan_fill("TRADED", 4212.0, 750)),
        _execution(p3_entry, "entry", "buy", _dhan_fill("TRADED", 4212.0, 750)),
        _execution(p3_exit, "direct_exit", "sell", _dhan_fill("TRADED", 4105.2, 750)),
        # Jun 17 short entry 3972.0 (dup) + SL cover 4111.6.
        _execution(p4_entry, "entry", "sell", _dhan_fill("TRADED", 3972.0, 750)),
        _execution(p4_entry, "entry", "sell", _dhan_fill("TRADED", 3972.0, 750)),
        _execution(p4_sl, "direct_sl", "buy", _dhan_fill("TRADED", 4111.6, 750)),
        # May 20 — TRANSIT, 4 duplicate rows, no fill price.
        _execution(pt_entry, "entry", "buy", _dhan_fill("TRANSIT", None, None)),
        _execution(pt_entry, "entry", "buy", _dhan_fill("TRANSIT", None, None)),
        _execution(pt_entry, "entry", "buy", _dhan_fill("TRANSIT", None, None)),
        _execution(pt_entry, "entry", "buy", _dhan_fill("TRANSIT", None, None)),
    ]
    return positions, executions


def test_dedup_collapses_duplicate_rows() -> None:
    _positions, executions = _bse_fixture()
    index = build_fill_index(executions)
    # 16 execution rows but only 9 distinct signal ids.
    assert len(index) == 9


def test_bse_real_fills_reproduce_reported_numbers() -> None:
    positions, executions = _bse_fixture()
    trips = reconcile(positions, executions)  # default segment NFO
    by_first_flag = {(t.symbol, t.direction, t.position_qty): t for t in trips}

    # Jun 12 LONG — gross +15,150; NFO costs 866.65; net +14,283.35.
    jun12 = trips[1]
    assert jun12.complete is True
    assert jun12.entry_price == Decimal("4014.8")
    assert jun12.gross_pnl == Decimal("15150.0")
    assert jun12.costs is not None
    assert jun12.costs.total == Decimal("866.65")
    assert jun12.net_pnl == Decimal("14283.35")

    # Jun 15 LONG — gross -80,100; costs 860.87; net -80,960.87.
    jun15 = trips[2]
    assert jun15.gross_pnl == Decimal("-80100.0")
    assert jun15.costs is not None and jun15.costs.total == Decimal("860.87")
    assert jun15.net_pnl == Decimal("-80960.87")

    # Jun 17 SHORT — gross -104,700; costs 835.58; net -105,535.58.
    jun17 = trips[3]
    assert jun17.direction == "short"
    assert jun17.gross_pnl == Decimal("-104700.0")
    assert jun17.costs is not None and jun17.costs.total == Decimal("835.58")
    assert jun17.net_pnl == Decimal("-105535.58")

    # Jun 4 LONG — manual Dhan exit, no close leg -> incomplete, not costed.
    jun4 = trips[0]
    assert jun4.complete is False
    assert jun4.gross_pnl is None and jun4.net_pnl is None and jun4.costs is None
    assert any("no close legs" in f for f in jun4.flags)

    # May 20 — TRANSIT entry never filled -> incomplete.
    may20 = by_first_flag[("BSE-MAY2026-FUT", "long", 1500)]
    assert may20.complete is False
    assert may20.net_pnl is None
    assert any("not filled" in f for f in may20.flags)

    # Totals across the 3 fully-reconciled round trips: gross / costs / net.
    gross = sum((t.gross_pnl for t in trips if t.gross_pnl is not None), Decimal(0))
    costs = sum((t.costs.total for t in trips if t.costs is not None), Decimal(0))
    net = sum((t.net_pnl for t in trips if t.net_pnl is not None), Decimal(0))
    assert gross == Decimal("-169650.0")
    assert costs == Decimal("2563.10")
    assert net == Decimal("-172213.10")
    assert sum(1 for t in trips if t.complete) == 3


# ─── Going-forward scan (grouping + write-gating) ──────────────────────


def test_plan_reconciliation_routes_each_position_to_its_strategys_fills() -> None:
    strat_a, strat_b = uuid.uuid4(), uuid.uuid4()
    a_entry, a_exit = uuid.uuid4(), uuid.uuid4()
    b_entry, b_exit = uuid.uuid4(), uuid.uuid4()

    pos_a = _position(
        "AAA",
        "buy",
        50,
        [
            _event("entry", "entry", 50, "buy", a_entry),
            _event("exit", "direct_exit", 50, "long", a_exit),
        ],
    )
    pos_a.strategy_id = strat_a
    pos_b = _position(
        "BBB",
        "sell",
        50,
        [
            _event("entry", "entry", 50, "sell", b_entry),
            _event("sl_hit", "direct_sl", 50, "short", b_exit),
        ],
    )
    pos_b.strategy_id = strat_b

    fills = {
        strat_a: build_fill_index(
            [
                _execution(a_entry, "entry", "buy", _paper_entry("100", 50)),
                _execution(a_exit, "direct_exit", "sell", _paper_exit("110", 50)),
            ]
        ),
        strat_b: build_fill_index(
            [
                _execution(b_entry, "entry", "sell", _paper_entry("200", 50)),
                _execution(b_exit, "direct_sl", "buy", _paper_exit("190", 50)),
            ]
        ),
    }

    trips = plan_reconciliation([pos_a, pos_b], fills)
    assert trips[0].gross_pnl == Decimal("500")  # long  (110-100)*50
    assert trips[1].gross_pnl == Decimal("500")  # short (200-190)*50


# ─── Fake async session for the scan wrapper (writes-nothing proof) ────


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """Returns queued result sets in call order; records commits."""

    def __init__(self, result_sets: list[list[Any]]) -> None:
        self._queue = list(result_sets)
        self.commits = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self._queue.pop(0))

    async def commit(self) -> None:
        self.commits += 1


def test_reconcile_unrecorded_dry_run_computes_but_writes_nothing() -> None:
    positions, executions = _bse_fixture()  # all one strategy (id unset -> None)
    session = _FakeSession([positions, executions])

    result = asyncio.run(
        reconcile_unrecorded(session, since=datetime(2026, 6, 19, tzinfo=UTC), write=False)  # type: ignore[arg-type]
    )

    # Nothing written.
    assert session.commits == 0
    assert result.wrote is False
    assert result.annotated == 0
    assert all(p.final_pnl is None for p in positions)
    # But P&L IS computed + reported (the "would record" lines): gross/costs/net.
    assert len(result.complete_trips) == 3
    assert result.gross_realized == Decimal("-169650.0")
    assert result.total_costs == Decimal("2563.10")
    assert result.net_realized == Decimal("-172213.10")


def test_reconcile_unrecorded_write_annotates_complete_only() -> None:
    positions, executions = _bse_fixture()
    session = _FakeSession([positions, executions])

    result = asyncio.run(
        reconcile_unrecorded(session, since=datetime(2026, 6, 19, tzinfo=UTC), write=True)  # type: ignore[arg-type]
    )

    assert session.commits == 1
    assert result.annotated == 3
    # final_pnl receives NET (gross minus estimated costs), not gross.
    written = sorted(p.final_pnl for p in positions if p.final_pnl is not None)
    assert written == [Decimal("-105535.58"), Decimal("-80960.87"), Decimal("14283.35")]
    # The manual-exit + TRANSIT positions are left untouched (never guessed).
    assert sum(1 for p in positions if p.final_pnl is None) == 2


# ─── Beat registration + config flag ───────────────────────────────────


def test_beat_schedule_registers_pnl_reconciler() -> None:
    from app.tasks import pnl_reconciler_tasks
    from app.tasks.celery_app import celery_app

    task_name = "app.tasks.pnl_reconciler_tasks.reconcile_recent_pnl"
    assert pnl_reconciler_tasks.reconcile_recent_pnl.name == task_name

    schedule = celery_app.conf.beat_schedule
    assert schedule["pnl-reconciler-intraday"]["task"] == task_name
    assert schedule["pnl-reconciler-eod"]["task"] == task_name


def test_pnl_reconciler_flag_defaults_to_log_only() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.pnl_reconciler_write is False
    assert settings.pnl_reconciler_lookback_hours == 48


# ─── Cost model ────────────────────────────────────────────────────────


def test_segment_rate_table_present_and_default_nfo() -> None:
    assert {"NFO", "BFO", "MCX", "CDS"} <= set(SEGMENT_RATES)
    assert DEFAULT_SEGMENT == "NFO"


def test_cost_model_hand_checked_nfo() -> None:
    # Known turnover -> known charge stack (NFO futures).
    #   buy 10,00,000 / sell 10,10,000 / 2 orders
    #   brokerage = 20 * 2                         = 40.00
    #   STT       = 0.02%  * sell 10,10,000        = 202.00
    #   exch txn  = 0.00173% * total 20,10,000     = 34.77
    #   SEBI      = Rs10/cr * total 20,10,000      = 2.01
    #   stamp     = 0.002% * buy 10,00,000         = 20.00
    #   GST       = 18% * (40 + 34.77 + 2.01)      = 13.82
    #   total                                      = 312.60
    costs = compute_costs(
        buy_turnover=Decimal("1000000"),
        sell_turnover=Decimal("1010000"),
        orders=2,
        segment="NFO",
    )
    assert costs.brokerage == Decimal("40.00")
    assert costs.stt == Decimal("202.00")
    assert costs.exchange_txn == Decimal("34.77")
    assert costs.sebi_fee == Decimal("2.01")
    assert costs.stamp_duty == Decimal("20.00")
    assert costs.gst == Decimal("13.82")
    assert costs.total == Decimal("312.60")
    assert costs.estimated is True

    # Glass Box: the itemised charges sum to total.
    parts = (
        costs.brokerage
        + costs.stt
        + costs.exchange_txn
        + costs.sebi_fee
        + costs.stamp_duty
        + costs.gst
    )
    assert parts == costs.total

    # And net on a hypothetical +10,000 gross trip.
    gross = Decimal("10000")
    assert gross - costs.total == Decimal("9687.40")


def test_cds_segment_has_no_stt() -> None:
    costs = compute_costs(
        buy_turnover=Decimal("1000000"),
        sell_turnover=Decimal("1000000"),
        orders=2,
        segment="CDS",
    )
    assert costs.stt == Decimal("0.00")
