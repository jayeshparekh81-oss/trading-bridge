"""The 15:50 runner: ONE Dhan GET, one verdict, one line to the phone.

WHY THIS IS A SEPARATE FILE FROM ``truth_check``. The comparison is pure and
testable; this is the only place that touches the broker, the clock, the
database and Telegram. Keeping them apart is what makes it possible to prove
BOTH a red day and a green day without a broker, and it means the daily quota
lives at exactly one line of code that is easy to audit.

THE BROKER BUDGET, LITERALLY. ``_fetch_day`` performs ONE GET of the trade book
for one date. There is no loop, no retry-with-refetch, no paging beyond the
day, and no second call anywhere in this module. The founder's rule is "broker =
GET only, and no new recurring poll except the ONE trade-book GET per day"; this
is that one.

DRY RUN IS THE DEFAULT. ``--send`` is required to put a message on the phone,
so the check can be exercised against a live day as often as needed without
ever alerting. Nothing here writes to a position, an execution, or a signal.

IF IT STOPS. No message at 15:50 on a weekday is itself the alarm — a silent
day and a green day look identical from the outside, which is why the green
line is sent every day rather than only on a red. See the working-inventory
entry for this timer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.domains.pnl_reconciler.truth_check import (
    ATTENTION,
    RED,
    TruthCheckResult,
    already_ran,
    evaluate,
    record_run,
    stored_provenance_map,
)

_logger = get_logger("domains.pnl_reconciler.truth_check_runner")

IST = timezone(timedelta(hours=5, minutes=30))


def ist_window(day: date) -> tuple[datetime, datetime]:
    """The trading session, in IST. The window a badge may cite."""
    return (
        datetime.combine(day, time(0, 0), tzinfo=IST),
        datetime.combine(day, time(23, 59, 59), tzinfo=IST),
    )


async def _fetch_day(day: date, security_ids: set[str]) -> list[dict[str, Any]]:
    """THE ONE DHAN GET. One date, one call, nothing else in this module."""
    from sqlalchemy import select

    from app.brokers.dhan import DhanBroker
    from app.db.models.broker_credential import BrokerCredential
    from app.services.order_service import _build_broker_credentials

    async with get_sessionmaker()() as session:
        cred = (
            await session.execute(
                select(BrokerCredential)
                .where(
                    BrokerCredential.broker_name == "dhan",
                    BrokerCredential.is_active.is_(True),
                )
                .order_by(BrokerCredential.created_at.desc())
            )
        ).scalars().first()
        if cred is None:
            raise RuntimeError("no active Dhan credential")
        creds = _build_broker_credentials(cred, cred.user_id)

    broker = DhanBroker(creds)
    try:
        iso = day.isoformat()
        res = await broker._call("book", "GET", f"/trades/{iso}/{iso}/0")
    finally:
        if getattr(broker, "_http", None):
            await broker._http.aclose()

    rows = res if isinstance(res, list) else (res or {}).get("data", []) or []
    return [r for r in rows if str(r.get("securityId")) in security_ids]


async def run_check(
    day: date,
    *,
    security_ids: set[str],
    send: bool,
    fills: list[Any] | None = None,
    tape_covered: set[str] | None = None,
    tape_loaded: bool = True,
    duplicate_exit_order_ids: set[str] | None = None,
) -> TruthCheckResult:
    """One day's check, end to end. ``fills`` may be injected for a sandbox run."""
    from app.domains.pnl_reconciler.tradebook import account_fills_from_rows

    start, end = ist_window(day)

    if fills is None:
        rows = await _fetch_day(day, security_ids)
        fills = account_fills_from_rows(rows)

    order_ids = {str(getattr(f, "order_id", "")) for f in fills if getattr(f, "order_id", "")}

    async with get_sessionmaker()() as session:
        stored = await stored_provenance_map(session, order_ids)
        result = evaluate(
            fills,
            stored=stored,
            tape_covered=tape_covered if tape_covered is not None else order_ids,
            duplicate_exit_order_ids=duplicate_exit_order_ids,
            tape_loaded=tape_loaded,
        )
        result.window_start, result.window_end = start, end

        # DEDUPE. A retry, a restart or a second manual run must not send the
        # founder the same sentence twice.
        prior = await already_ran(session, start, end)
        line = result.telegram_line(day.isoformat())

        if prior is not None and prior == result.verdict:
            _logger.info("truth_check.duplicate_suppressed", verdict=result.verdict)
            print(f"[already sent today: {prior}] {line}")
            return result

        await record_run(session, result, ran_at=datetime.now(IST))
        await session.commit()

    print(line)
    if send:
        from app.services.telegram_alerts import AlertLevel, send_alert

        # Severity tracks the KIND of day, so the founder's phone can be
        # triaged at a glance: a hand-placed trade must never buzz like a
        # record that disagrees with the broker.
        level = {
            RED: AlertLevel.CRITICAL,
            ATTENTION: AlertLevel.WARNING,
        }.get(result.verdict, AlertLevel.SUCCESS)
        await send_alert(level, line)
        _logger.info("truth_check.alert_sent", verdict=result.verdict)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.domains.pnl_reconciler.truth_check_runner")
    parser.add_argument("--day", help="YYYY-MM-DD (default: today in IST)")
    parser.add_argument(
        "--security-ids",
        nargs="+",
        required=True,
        help="the strategy's contract security ids, e.g. 68456",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="actually put the line on the founder's phone (default: print only)",
    )
    parser.add_argument(
        "--book",
        metavar="JSONL",
        help=(
            "the day's trade book on disk. WITH --pull-only this is WRITTEN by "
            "the single daily GET; without it the file is READ and no broker "
            "call happens at all. That is how one day costs exactly one GET and "
            "still feeds both the ingester and this check."
        ),
    )
    parser.add_argument(
        "--pull-only",
        action="store_true",
        help=(
            "perform THE ONE Dhan GET, write --book, and stop. No verdict, no "
            "alert, nothing stored — so the ingester can run before the check "
            "that audits it."
        ),
    )
    args = parser.parse_args()
    day = date.fromisoformat(args.day) if args.day else datetime.now(IST).date()

    if args.pull_only:
        if not args.book:
            print("REFUSED: --pull-only needs --book PATH to write")
            sys.exit(2)
        rows = asyncio.run(_fetch_day(day, set(args.security_ids)))
        with open(args.book, "w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        print(f"trade book: {len(rows)} fill(s) for {day.isoformat()} -> {args.book}")
        sys.exit(0)

    preloaded = None
    if args.book:
        from app.domains.pnl_reconciler.tradebook import load_dhan_tradebook

        preloaded = load_dhan_tradebook(args.book)
        print(f"trade book: {len(preloaded)} fill(s) read from {args.book} (no broker call)")

    result = asyncio.run(
        run_check(
            day,
            security_ids=set(args.security_ids),
            send=args.send,
            fills=preloaded,
        )
    )
    # A red day exits non-zero so a timer's own failure mail is a second net.
    # A day whose only event was a hand-placed trade exits 0: our record agrees
    # with Dhan, and an exit code is not the place to report the founder's own
    # trading.
    sys.exit(0 if result.agrees_with_dhan else 1)


if __name__ == "__main__":
    main()
