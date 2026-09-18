"""Provenance comes from the tape, and a gap in it is a RED.

Founder's rulings, 2026-09-16:

  (2)  orderPlatform from the WS order-update tape joined on orderId: APPROVED.
  (2b) Tape gap = truth-check RED. If the tape is missing or incomplete for any
       session, or a fill's orderId is absent from it, the 15:50 check sends
       MISMATCH with the gap named, and affected fills stay "pehchaan nahi".

Why the join is necessary at all, measured 2026-09-16: Dhan's trade book
carries no ``orderPlatform``, no ``correlationId`` and no ``algoOrdNo``. Its
keys are orderId / tradedPrice / tradedQuantity / the six charge fields / times
and nothing else. The tape carries all three.

Every rule below has a falsification twin.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.order_tape import (
    apply_provenance,
    coverage_gaps,
    load_tape,
    tape_files,
)

#: The two real stop children, and a real manual fill, in the tape's own shape.
ENGINE_STOP = {
    "orderNo": "312260904412406",
    "algoOrdNo": 32132609031621,
    "orderPlatform": "FOVR",
    "correlationId": "NR",
    "status": "Traded",
}
MANUAL = {
    "orderNo": "35226091145606",
    "algoOrdNo": None,
    "orderPlatform": "FAST",
    "correlationId": "NA",
    "status": "Traded",
}
OURS = {
    "orderNo": "34226090862006",
    "algoOrdNo": None,
    "orderPlatform": "API",
    "correlationId": "strategy-engine",
    "status": "Traded",
}


def _write_tape(tmp_path: Path, *frames: dict) -> Path:
    p = tmp_path / "order_updates_2026-09-04.jsonl"
    with p.open("w") as fh:
        for f in frames:
            fh.write(json.dumps({"at": "2026-09-04T13:11:16+05:30", "raw": json.dumps({"Data": f})}) + "\n")
    return p


def _fill(order_id: str, ts: str = "2026-09-04T13:11:13") -> AccountFill:
    return AccountFill(
        contract="68456", order_id=order_id, side="SELL", qty=400,
        price=Decimal("3415.5"), ts=ts,
    )


class TestTheTapeSuppliesWhatTheTradeBookCannot:
    def test_platform_and_parent_are_read(self, tmp_path: Path) -> None:
        tape = load_tape(_write_tape(tmp_path, ENGINE_STOP, MANUAL, OURS))
        assert tape["312260904412406"].platform == "FOVR"
        assert tape["312260904412406"].parent_order_id == "32132609031621"
        assert tape["35226091145606"].platform == "FAST"
        assert tape["34226090862006"].platform == "API"

    def test_a_null_parent_is_none_not_the_string_none(self, tmp_path: Path) -> None:
        """``algoOrdNo`` is null on a non-stop order. Storing "None" would make
        every ordinary order look like a child of a parent called None."""
        tape = load_tape(_write_tape(tmp_path, MANUAL))
        assert tape["35226091145606"].parent_order_id is None

    def test_the_join_sets_the_platform_on_the_fill(self, tmp_path: Path) -> None:
        tape = load_tape(_write_tape(tmp_path, MANUAL))
        [joined] = apply_provenance([_fill("35226091145606")], tape)
        assert joined.order_platform == "FAST"
        assert joined.provenance(bot_order_ids=set()) == "manual"

    def test_falsification_twin_an_unknown_fill_is_left_unknown(self, tmp_path: Path) -> None:
        """🔴 THE ONE THAT MATTERS. A fill the tape does not know must come back
        with NO platform — so it reads "unknown", never "manual". Defaulting it
        to manual would blame a human for the bot's own exit."""
        tape = load_tape(_write_tape(tmp_path, OURS))
        [joined] = apply_provenance([_fill("999999999999")], tape)
        assert joined.order_platform is None
        assert joined.provenance(bot_order_ids=set()) == "unknown"

    def test_falsification_twin_the_ledger_still_beats_the_tape(self, tmp_path: Path) -> None:
        """An engine stop is FOVR in the tape, but once the ledger claims it, it
        is the bot's exit. If the platform ever overrode the ledger, every
        engine stop would stop being the bot's."""
        tape = load_tape(_write_tape(tmp_path, ENGINE_STOP))
        [joined] = apply_provenance([_fill("312260904412406")], tape)
        assert joined.provenance(bot_order_ids={"312260904412406"}) == "bot"


class TestATapeGapIsReported:
    def test_a_missing_order_is_named(self, tmp_path: Path) -> None:
        tape = load_tape(_write_tape(tmp_path, OURS))
        gaps = coverage_gaps([_fill("999999999999")], tape)
        assert len(gaps) == 1
        assert "999999999999" in gaps[0]
        assert "no WS order-update record" in gaps[0]

    def test_a_missing_tape_file_makes_every_fill_a_gap(self, tmp_path: Path) -> None:
        """A whole session with no tape (the 2026-09-01 case) must not pass
        silently — every fill of that session is unidentifiable."""
        assert tape_files(tmp_path / "does-not-exist") == []
        gaps = coverage_gaps([_fill("A"), _fill("B")], load_tape())
        assert len(gaps) == 2

    def test_falsification_twin_full_coverage_reports_nothing(self, tmp_path: Path) -> None:
        """The twin. A checker that always reported a gap would pass the two
        tests above and turn the 15:50 check into a permanent red nobody reads."""
        tape = load_tape(_write_tape(tmp_path, ENGINE_STOP, MANUAL, OURS))
        fills = [_fill("312260904412406"), _fill("35226091145606"), _fill("34226090862006")]
        assert coverage_gaps(fills, tape) == []

    def test_the_archive_does_not_raise_a_gap_every_day(self, tmp_path: Path) -> None:
        """155 real fills predate the tape (2026-05-04..2026-08-31), all of them
        before the record starts. Scoping to the record keeps the daily check
        about today's truth instead of a permanent historical red."""
        tape = load_tape(_write_tape(tmp_path, OURS))
        old = _fill("pre-tape-order", ts="2026-08-19T10:18:29")
        assert coverage_gaps([old], tape, since="2026-09-01") == []
        assert len(coverage_gaps([old], tape)) == 1, "unscoped, it is still a gap"
