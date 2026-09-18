"""The 15:50 truth check — the site must equal Dhan, or the founder hears today.

THE PROMISE THIS KEEPS
──────────────────────
Any difference between what tradetri.com shows and what Dhan's own book says is
caught the SAME DAY. Never a silent wrong number, and never a number nobody
checked.

FOUR WAYS THE DAY CAN GO RED, and each one names the fill it is about:

  1. UNRECORDED   — a Dhan fill on the strategy's contract that we have no
                    provenance row for. We did not see it happen.
  2. PEHCHAAN NAHI— a fill that is neither ours nor demonstrably manual. It is
                    NOT filed as manual. A guess here would blame a human for
                    the bot's own exit, or credit the bot with a human's trade.
  3. MANUAL       — a hand-placed trade on the bot's own symbol. Not an error,
                    but the founder must know, because a manual fill between a
                    position's entry and close makes that position's P&L
                    unpublishable ("manual se band").
  4. DUPLICATE    — two exits where one position closed once. The 04-Sep case
                    cost 4,360 and opened a short 400 from flat.

ONE MESSAGE, NOT FOUR. Everything found is collapsed into a single line, so a
bad day produces one alert the founder reads rather than a burst he learns to
swipe away.

BUDGET: ONE Dhan GET PER DAY. The fills are passed IN. This module performs no
broker call of its own, so it cannot become a second poll by accident — the
single trade-book GET lives in the runner, once, at 15:50.

EVIDENCE OUTLIVES THE MESSAGE. Every run is written to ``truth_check_runs``
with the window it covered, because the "Dhan se verified ✅" badge may only be
shown for a position a STORED run actually covers. A badge with no run behind
it is the same class of claim as a modelled number labelled as billed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

_logger = get_logger("domains.pnl_reconciler.truth_check")

GREEN = "green"
RED = "red"

#: THE TWO CHECKS, and why there are two (founder, 18 Sep 2026).
#:
#: One check could not do both jobs, because Dhan's trade book does not settle
#: in time. MEASURED: the 17-Sep session was absent from /trades at 18-Sep
#: 04:33 IST and present by 20:20 — roughly forty hours. A 15:50 check that
#: needs the book would therefore be blind about the session it just watched,
#: every single day. That is how the false green happened.
#:
#: So the work is split by what each hour can actually know:
#:
#:   SAME_DAY (15:50 IST) — "did we RECORD what the account did today?"
#:       Sources: the WS tape, our own strategy_executions, and Dhan
#:       /positions day quantities. The BOOK IS NOT REQUIRED and is not read.
#:       /positions is authoritative for "did anything trade today", so this
#:       check can prove a quiet day rather than shrugging at one.
#:
#:   MORNING (08:30 IST next day) — "do the NUMBERS match Dhan's settled book?"
#:       Sources: the trade book for yesterday's session, its billed charges,
#:       and what the site stored. This is the one that can see money.
#:
#: 🔴 THE BADGE BELONGS TO THE MORNING CHECK. "Dhan se verified ✅" is a claim
#: about numbers, and only the morning check ever sees the settled numbers. A
#: green same-day run means "we wrote down what happened", which is a smaller
#: and different promise.
SAME_DAY = "same_day"
MORNING = "morning"
#: The book told us NOTHING and no witness contradicts it. NOT green.
#:
#: 🔴 WHY THIS EXISTS (18 Sep 2026). The check used to return GREEN from an
#: empty trade book: `evaluate([])` produced "TRADETRI = DHAN ✅ 0 fills". On
#: 2026-09-17 Dhan's /trades returned ZERO rows for the session — all pages,
#: unfiltered — while the account demonstrably traded 400 + 800 and a live
#: position silently desynced. The founder would have been told everything
#: matched, on the one day it did not, and the green would have been STORED,
#: later licensing a "Dhan se verified ✅" badge for a day nothing was checked.
#:
#: Silence is not agreement. A day we could not see is its own answer.
NO_DATA = "no_data"
#: The record AGREES with Dhan, but something happened the founder must know
#: about — today, only a hand-placed trade on the bot's own symbol.
#:
#: 🔴 WHY THIS IS NOT RED. A manual trade is not a mismatch. The site is not
#: wrong: the position is correctly marked "manual se band" and its P&L is
#: correctly withheld. Filing it under MISMATCH would teach the founder that
#: the red means "you traded by hand" — and then the day our record really IS
#: wrong, the message looks exactly like the ones he has learned to dismiss.
ATTENTION = "attention"

#: Dhan's ``orderPlatform`` for a hand-placed order in the Dhan app.
MANUAL_PLATFORM = "FAST"


@dataclass
class TruthCheckResult:
    """One day's verdict, in the founder's own terms."""

    verdict: str = GREEN
    #: which of the two checks produced this. The badge only honours MORNING.
    kind: str = MORNING
    fills_checked: int = 0
    window_start: datetime | None = None
    window_end: datetime | None = None
    unrecorded: list[str] = field(default_factory=list)
    unidentified: list[str] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)
    duplicate_exits: list[str] = field(default_factory=list)
    tape_gap: bool = False
    #: The trade book returned nothing for the session.
    book_empty: bool = False
    #: An independent witness saw activity anyway — named, so the red is
    #: actionable rather than a shrug.
    witnesses_seen: list[str] = field(default_factory=list)
    #: A3. Positions the PLATFORM shows open while the BROKER is flat on that
    #: symbol. Never auto-corrected — reported until a human fixes it.
    phantom_positions: list[str] = field(default_factory=list)

    @property
    def green(self) -> bool:
        return self.verdict == GREEN

    @property
    def licenses_badge(self) -> bool:
        """A.2 — ONLY a stored GREEN run may put a ✅ on a position.

        RED and NO-DATA obviously cannot. ATTENTION cannot either, and that is
        deliberate: on a day the founder traded by hand we can say our record
        matched the broker, but the founder's rule for the badge is GREEN and
        nothing else. A badge is the strongest claim this page makes.

        And it must be a MORNING run. A green SAME-DAY run means "we wrote down
        what happened" — it never saw a settled number or a billed charge, so
        it cannot support a claim about money.
        """
        return self.verdict == GREEN and self.kind == MORNING

    @property
    def agrees_with_dhan(self) -> bool:
        """True when nothing contradicts Dhan's book.

        This — not ``green`` — is what licenses the "Dhan se verified ✅" badge:
        a day on which the founder traded by hand is still a day our record
        matched the broker.
        """
        return self.verdict in (GREEN, ATTENTION)

    def details(self) -> str:
        """Everything wrong, in one string. Empty when the day is clean."""
        parts: list[str] = []
        if self.book_empty and self.witnesses_seen:
            parts.append(
                "Dhan trade book EMPTY for the session but activity seen ("
                + ", ".join(self.witnesses_seen)
                + ") — we are blind, not clean"
            )
        elif self.book_empty:
            parts.append("Dhan trade book returned nothing and no witness saw activity")
        if self.phantom_positions:
            parts.append(
                "Dhan pe band, site pe khula: "
                + ", ".join(self.phantom_positions)
            )
        if self.tape_gap:
            parts.append("tape missing/incomplete for the session")
        if self.unrecorded:
            parts.append(f"{len(self.unrecorded)} fill(s) not in our record: "
                         + ", ".join(self.unrecorded[:5]))
        if self.unidentified:
            parts.append(f"PEHCHAAN NAHI {len(self.unidentified)}: "
                         + ", ".join(self.unidentified[:5]))
        if self.manual:
            parts.append("manual trade on the bot's symbol: "
                         + ", ".join(self.manual[:5]))
        if self.duplicate_exits:
            parts.append("duplicate exit: " + ", ".join(self.duplicate_exits[:5]))
        return "; ".join(parts)

    def telegram_line(self, day: str) -> str:
        """The ONE line that reaches the phone.

        Deliberately boring on a good day. An alert the founder can read in a
        second, every day, is worth more than a report he stops opening — and
        the headline says which KIND of day it was, so a red never has to
        compete for attention with a routine hand-placed trade.
        """
        if self.verdict == NO_DATA:
            # Deliberately NOT a tick. The founder must be able to tell
            # "nothing happened" from "we could not look".
            return f"DEKHA NAHI JA SAKA ⬜ {day} — {self.details()}"
        if self.verdict == GREEN:
            return f"TRADETRI = DHAN ✅ {day} {self.fills_checked} fills"
        if self.verdict == ATTENTION:
            return (
                f"TRADETRI = DHAN ✅ {day} {self.fills_checked} fills"
                f" — HAATH SE TRADE ⚠️ {', '.join(self.manual)}"
                " (us position ka P&L nahi gina)"
            )
        return f"MISMATCH 🔴 {day} {self.details()}"


#: What counts as an independent witness that a session was NOT quiet. Each is
#: a source the trade book cannot silence, and each is already collected
#: elsewhere in this system — none of them costs a new recurring broker poll.
_WITNESS_LABELS = {
    "tape_frames": "WS tape frames",
    "day_qty_moved": "Dhan /positions day quantity",
    "platform_executions": "our own strategy_executions rows",
}


def _active_witnesses(witnesses: dict[str, Any]) -> list[str]:
    """Which witnesses saw activity. Named, so a red says WHAT it saw.

    A witness counts only when it reports a positive count. Absent or zero is
    "quiet", never "agrees" — the whole point of NO-DATA is that we refuse to
    read silence as confirmation.
    """
    seen: list[str] = []
    for key, label in _WITNESS_LABELS.items():
        try:
            value = int(witnesses.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            seen.append(f"{label}={value}")
    return seen


def evaluate_same_day(
    *,
    tape_orders: set[str],
    platform_orders: set[str],
    day_qty_moved: int | None,
    phantom_positions: list[str] | None = None,
    tape_loaded: bool = True,
) -> TruthCheckResult:
    """The 15:50 check. Did we RECORD what the account did today?

    It never reads the trade book — measured, the book does not settle for
    roughly forty hours, so at 15:50 it is silent about the session that just
    ended and cannot answer anything.

    What it CAN answer, from sources that are current:
      * every order the WS tape saw Traded should have a row in ours;
      * if Dhan's /positions says quantity moved today, we should hold rows;
      * a position we show open while the broker is flat is a phantom.

    🔴 A QUIET DAY IS PROVABLE HERE, and that matters. ``day_qty_moved == 0``
    from the broker is positive evidence that nothing traded — not the absence
    of evidence an empty book gives. So a quiet day is GREEN, and only a
    broker we could not reach at all is NO-DATA.
    """
    result = TruthCheckResult(kind=SAME_DAY, fills_checked=len(tape_orders))
    result.phantom_positions = sorted(set(phantom_positions or []))

    if not tape_loaded:
        # The tape is the only witness to WHICH orders filled. Without it we
        # cannot say the record is complete — one red about the load, never a
        # verdict on the account (addition B, 16 Sep).
        result.verdict = RED
        result.tape_gap = True
        return result

    missing = sorted(tape_orders - platform_orders)
    result.unrecorded = missing

    if day_qty_moved is None:
        # We could not ask the broker. Say so; do not guess either way.
        result.verdict = NO_DATA
        result.witnesses_seen = ["broker /positions unreachable"]
        return result

    result.witnesses_seen = [f"Dhan /positions day quantity={day_qty_moved}"]
    if day_qty_moved > 0 and not platform_orders:
        # The account traded and we hold nothing at all for the day.
        result.unrecorded = result.unrecorded or ["<no platform rows for a day that traded>"]

    result.verdict = (
        RED if (result.unrecorded or result.phantom_positions or result.tape_gap) else GREEN
    )
    return result


def evaluate(
    fills: list[Any],
    *,
    stored: dict[str, dict[str, Any]],
    tape_covered: set[str],
    duplicate_exit_order_ids: set[str] | None = None,
    tape_loaded: bool = True,
    witnesses: dict[str, Any] | None = None,
    phantom_positions: list[str] | None = None,
) -> TruthCheckResult:
    """Compare the day's Dhan fills against what we hold. Pure — no I/O.

    ``stored`` is what ``broker_fill_provenance`` says, keyed by broker order
    id. ``tape_covered`` is the set of order ids the WS tape knows.

    🔴 ADDITION B. A tape that did not load is ONE red about the LOAD. It must
    not be reported as every fill being unidentifiable — that turns a mount
    problem into a page full of alarm about the account.
    """
    result = TruthCheckResult(fills_checked=len(fills))
    result.phantom_positions = sorted(set(phantom_positions or []))

    if fills and not tape_loaded:
        result.verdict = RED
        result.tape_gap = True
        return result

    # ── A.1. AN EMPTY BOOK IS NEVER GREEN ────────────────────────────
    #
    # The trade book is the fill-of-record, and it can be silent about a
    # session that really happened: MEASURED 2026-09-17, /trades returned zero
    # rows for the whole day (all pages, unfiltered) while the account traded
    # 400 + 800. dhan.py:944 already warns the endpoint "can be
    # paginated/incomplete and must NOT be used" as ground truth.
    #
    # So when the book says nothing, ask somebody else before speaking:
    #   * the WS order-update tape (frames that session),
    #   * Dhan's own /positions day quantities (did anything move?),
    #   * our own strategy_executions rows for that day.
    #
    # Any witness with activity  -> RED. We are demonstrably blind.
    # Every witness quiet        -> NO-DATA. Might be a holiday, might be a
    #                               broken pull; either way we did not check.
    if not fills:
        result.book_empty = True
        seen = _active_witnesses(witnesses or {})
        result.witnesses_seen = seen
        # A phantom is itself activity we can see — it counts as a witness.
        result.verdict = RED if (seen or result.phantom_positions) else NO_DATA
        return result

    dupes = duplicate_exit_order_ids or set()
    for fill in fills:
        order_id = str(getattr(fill, "order_id", "") or "")
        if not order_id:
            continue
        row = stored.get(order_id)
        if row is None:
            result.unrecorded.append(order_id)
            continue
        prov = str(row.get("provenance") or "")
        if prov == "unknown":
            result.unidentified.append(order_id)
        elif prov == "manual":
            result.manual.append(order_id)
        if order_id not in tape_covered and prov != "manual":
            # A fill we claim as the bot's, with no tape record behind it.
            result.tape_gap = True

    for order_id in sorted(dupes):
        result.duplicate_exits.append(order_id)

    # The verdict is the WORST thing found, and a manual trade is not the worst
    # thing — it is the one case where the record is right and the founder still
    # needs telling.
    if (
        result.unrecorded
        or result.unidentified
        or result.duplicate_exits
        or result.tape_gap
        or result.phantom_positions
    ):
        result.verdict = RED
    elif result.manual:
        result.verdict = ATTENTION
    # De-duplicated and stable, so the same day cannot read differently twice.
    result.unrecorded = sorted(set(result.unrecorded))
    result.unidentified = sorted(set(result.unidentified))
    result.manual = sorted(set(result.manual))
    return result


async def already_ran(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    kind: str = MORNING,
) -> str | None:
    """The verdict already stored for this window, if any.

    DEDUPE. A timer that fires twice — a retry, a manual re-run, a restart —
    must not send the founder the same line twice. The stored run is the
    record; a second identical verdict is not news.
    """
    row = (
        await session.execute(
            text(
                "SELECT verdict FROM truth_check_runs "
                "WHERE window_start = :a AND window_end = :b AND kind = :kind "
                "ORDER BY ran_at DESC LIMIT 1"
            ),
            {"a": window_start, "b": window_end, "kind": kind},
        )
    ).first()
    return str(row[0]) if row is not None else None


async def record_run(
    session: AsyncSession, result: TruthCheckResult, *, ran_at: datetime
) -> int:
    """Write the verdict down. The badge may only cite a run that is here."""
    row = (
        await session.execute(
            text(
                """
                INSERT INTO truth_check_runs
                    (ran_at, window_start, window_end, verdict, kind,
                     fills_checked, details, phantom_positions)
                VALUES (:ran_at, :a, :b, :verdict, :kind, :n, :details,
                        CAST(:phantom AS jsonb))
                RETURNING id
                """
            ),
            {
                "ran_at": ran_at,
                "a": result.window_start,
                "b": result.window_end,
                "verdict": result.verdict,
                "kind": result.kind,
                "n": result.fills_checked,
                "details": result.details() or None,
                "phantom": json.dumps(result.phantom_positions) if result.phantom_positions else None,
            },
        )
    ).first()
    _logger.info(
        "truth_check.recorded",
        kind=result.kind,
        verdict=result.verdict,
        fills=result.fills_checked,
        details=result.details() or "-",
    )
    return int(row[0]) if row is not None else 0


async def stored_provenance_map(
    session: AsyncSession, order_ids: set[str]
) -> dict[str, dict[str, Any]]:
    """What we hold about these fills — read from the DB, never from the tape."""
    if not order_ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT broker_order_id, provenance, order_platform, parent_order_id "
                "FROM broker_fill_provenance WHERE broker_order_id = ANY(:ids)"
            ),
            {"ids": list(order_ids)},
        )
    ).mappings()
    return {str(r["broker_order_id"]): dict(r) for r in rows}


__all__ = [
    "ATTENTION",
    "GREEN",
    "MORNING",
    "NO_DATA",
    "RED",
    "SAME_DAY",
    "TruthCheckResult",
    "already_ran",
    "evaluate",
    "evaluate_same_day",
    "record_run",
    "stored_provenance_map",
]
