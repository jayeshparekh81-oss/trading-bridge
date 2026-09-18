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
        """
        return self.verdict == GREEN

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


async def already_ran(session: AsyncSession, window_start: datetime, window_end: datetime) -> str | None:
    """The verdict already stored for this window, if any.

    DEDUPE. A timer that fires twice — a retry, a manual re-run, a restart —
    must not send the founder the same line twice. The stored run is the
    record; a second identical verdict is not news.
    """
    row = (
        await session.execute(
            text(
                "SELECT verdict FROM truth_check_runs "
                "WHERE window_start = :a AND window_end = :b "
                "ORDER BY ran_at DESC LIMIT 1"
            ),
            {"a": window_start, "b": window_end},
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
                    (ran_at, window_start, window_end, verdict, fills_checked,
                     details, phantom_positions)
                VALUES (:ran_at, :a, :b, :verdict, :n, :details,
                        CAST(:phantom AS jsonb))
                RETURNING id
                """
            ),
            {
                "ran_at": ran_at,
                "a": result.window_start,
                "b": result.window_end,
                "verdict": result.verdict,
                "n": result.fills_checked,
                "details": result.details() or None,
                "phantom": json.dumps(result.phantom_positions) if result.phantom_positions else None,
            },
        )
    ).first()
    _logger.info(
        "truth_check.recorded",
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
    "NO_DATA",
    "RED",
    "TruthCheckResult",
    "already_ran",
    "evaluate",
    "record_run",
    "stored_provenance_map",
]
