"""R2 + additions A and B: provenance is decided once and written down.

A — the verdict must survive the tape. Retention of
``executor/logs/order_updates_*.jsonl`` was MEASURED on 2026-09-16 and there is
none: no logrotate rule, no cron deletion, no cleanup code. The files persist by
luck on a box that runs near-full. So the decision is stored at ingest and the
page never reads them again.

B — an EMPTY tape is ONE red, not a verdict on every fill. When the tape last
loaded empty (a glob expanded on the host, where the container's path does not
exist) every non-bot fill would have been re-labelled "pehchaan nahi" at once —
a page full of alarm caused by a mount, not by the account.

Every rule has a falsification twin.
"""

from __future__ import annotations

from decimal import Decimal

from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.ingest import IngestResult, classify
from app.domains.pnl_reconciler.order_tape import OrderProvenance

#: The real ids.
ENGINE_CHILD = "312260904412406"
ENGINE_PARENT = "32132609031621"
MANUAL_FILL = "35226091145606"
OUR_ORDER = "34226090862006"


def _prov(order_id: str, platform: str | None, parent: str | None = None) -> OrderProvenance:
    return OrderProvenance(
        order_id=order_id, platform=platform, parent_order_id=parent, correlation_id=None
    )


def _fill(order_id: str, charges: str | None = "20.00") -> AccountFill:
    return AccountFill(
        contract="68456",
        order_id=order_id,
        side="SELL",
        qty=400,
        price=Decimal("3415.5"),
        ts="2026-09-04T13:11:13",
        charges=None if charges is None else Decimal(charges),
    )


class TestTheThreeWayVerdict:
    def test_a_stop_child_is_the_bots_via_its_parent(self) -> None:
        """🔴 THE ATTRIBUTION CHAIN, and not a timestamp in sight: the child's
        own algoOrdNo names a parent the engine ledger claims."""
        v = classify(
            ENGINE_CHILD,
            _prov(ENGINE_CHILD, "FOVR", ENGINE_PARENT),
            ledger_order_ids={ENGINE_PARENT},
        )
        assert v == "bot"

    def test_a_fast_fill_is_manual(self) -> None:
        assert classify(MANUAL_FILL, _prov(MANUAL_FILL, "FAST"), ledger_order_ids=set()) == "manual"

    def test_our_own_order_is_the_bots_without_any_tape(self) -> None:
        """A platform order is the bot's by definition — it does not need the
        tape at all, which matters because the tape can be short."""
        assert classify(OUR_ORDER, None, ledger_order_ids={OUR_ORDER}) == "bot"

    def test_falsification_twin_an_unclaimed_fovr_is_unknown_not_manual(self) -> None:
        """🔴 THE ONE THAT MATTERS. An unclaimed FOVR is far more likely to be
        pine_replica's own stop with its parent unsupplied than a hand-placed
        trade. Calling it manual blames a human for the bot's own exit."""
        v = classify(ENGINE_CHILD, _prov(ENGINE_CHILD, "FOVR", "99999"), ledger_order_ids=set())
        assert v == "unknown"

    def test_falsification_twin_no_tape_record_is_unknown_not_manual(self) -> None:
        assert classify("nobody-knows", None, ledger_order_ids=set()) == "unknown"

    def test_falsification_twin_the_ledger_beats_the_platform_field(self) -> None:
        """If the platform ever overrode the ledger, every engine stop would
        stop being the bot's and two round trips would go unpriced."""
        v = classify(ENGINE_CHILD, _prov(ENGINE_CHILD, "FOVR"), ledger_order_ids={ENGINE_CHILD})
        assert v == "bot"


class TestAnEmptyTapeIsOneRed:
    async def test_it_stops_and_classifies_nothing(self) -> None:
        """Addition B. No writes, no mass re-flagging — one verdict about the
        LOAD, not 15 verdicts about the account."""
        from app.domains.pnl_reconciler.ingest import ingest_fills

        class _Session:
            async def execute(self, *a: object, **k: object):  # pragma: no cover
                raise AssertionError("an empty tape must not write anything")

        out = await ingest_fills(
            _Session(),  # type: ignore[arg-type]
            [_fill(ENGINE_CHILD), _fill(MANUAL_FILL)],
            {},
            ledger_order_ids=set(),
        )
        assert out.tape_empty is True
        assert out.written == 0
        assert out.unknown_order_ids == (), "it must not label fills it refused to classify"
        assert out.clean is False

    async def test_falsification_twin_a_loaded_tape_does_classify(self) -> None:
        """The twin. A guard that always short-circuited would pass the test
        above and silently stop the ingester working at all."""
        from app.domains.pnl_reconciler.ingest import ingest_fills

        seen: list[dict] = []

        class _Result:
            def first(self):
                return ("x",)

        class _Session:
            async def execute(self, _stmt, params=None):
                seen.append(params or {})
                return _Result()

        out = await ingest_fills(
            _Session(),  # type: ignore[arg-type]
            [_fill(MANUAL_FILL)],
            {MANUAL_FILL: _prov(MANUAL_FILL, "FAST")},
            ledger_order_ids=set(),
        )
        assert out.tape_empty is False
        assert out.written == 1 and out.manual == 1
        assert seen[0]["provenance"] == "manual"
        assert seen[0]["platform"] == "FAST", "the RAW field is stored beside the verdict"

    async def test_no_fills_at_all_is_not_an_empty_tape_red(self) -> None:
        """A quiet day is not a fault. 05-Sep and 12-Sep had zero fills and no
        tape file, which is normal — the tape only gets a file when an order
        update arrives."""
        from app.domains.pnl_reconciler.ingest import ingest_fills

        class _Session:
            async def execute(self, *a: object, **k: object):  # pragma: no cover
                raise AssertionError("nothing to write")

        out = await ingest_fills(
            _Session(), [], {}, ledger_order_ids=set()  # type: ignore[arg-type]
        )
        assert out.tape_empty is False and out.clean is True


class TestIdempotency:
    async def test_a_second_run_writes_nothing(self) -> None:
        """Not "usually" — the database refuses. broker_order_id is the PRIMARY
        KEY and the insert is ON CONFLICT DO NOTHING, so a re-ingest of the same
        tape cannot double a leg even if someone runs it twice by mistake."""
        from app.domains.pnl_reconciler.ingest import ingest_fills

        stored: set[str] = set()

        class _Result:
            def __init__(self, inserted: bool) -> None:
                self._inserted = inserted

            def first(self):
                return ("x",) if self._inserted else None

        class _Session:
            async def execute(self, _stmt, params=None):
                oid = (params or {})["oid"]
                fresh = oid not in stored
                stored.add(oid)
                return _Result(fresh)

        fills = [_fill(MANUAL_FILL), _fill(OUR_ORDER)]
        tape = {MANUAL_FILL: _prov(MANUAL_FILL, "FAST"), OUR_ORDER: _prov(OUR_ORDER, "API")}

        first = await ingest_fills(_Session(), fills, tape, ledger_order_ids={OUR_ORDER})  # type: ignore[arg-type]
        assert first.written == 2 and first.already_present == 0

        second = await ingest_fills(_Session(), fills, tape, ledger_order_ids={OUR_ORDER})  # type: ignore[arg-type]
        assert second.written == 0, "the second run inserted rows"
        assert second.already_present == 2

    def test_an_unknown_fill_is_reported_not_swallowed(self) -> None:
        out = IngestResult(seen=1, unknown=1, unknown_order_ids=("mystery",))
        assert out.clean is False
        assert "mystery" in out.unknown_order_ids
