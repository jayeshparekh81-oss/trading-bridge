"""CLI entrypoint: ``python -m app.domains.pnl_reconciler --strategy <uuid>``.

Dry-run by default — reads + computes + prints, writes nothing. Pass
``--write`` to record ``final_pnl`` + the attribution tag on CLOSED positions
(founder-gated; never run against a live strategy without an explicit
go-ahead).

Founder's exit rule (2026-09-04): a LIVE position is priced from the whole
ACCOUNT's fills, so a live strategy needs the broker's trade book —
``--tradebook <jsonl> [<jsonl> ...]`` (Dhan ``/trades`` rows, futures only;
see :mod:`app.domains.pnl_reconciler.tradebook`). Without it, live trips are
reported but never written (fail closed); paper trips need no book.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date

from app.db.session import get_sessionmaker
from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.service import format_report, reconcile_strategy
from app.domains.pnl_reconciler.tradebook import load_dhan_tradebook


async def _run(
    strategy_id: uuid.UUID,
    *,
    write: bool,
    overwrite: bool,
    csv: bool,
    account_fills: list[AccountFill] | None,
    book_covers_from: date | None,
) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        try:
            result = await reconcile_strategy(
                session,
                strategy_id,
                write=write,
                overwrite=overwrite,
                account_fills=account_fills,
                book_covers_from=book_covers_from,
            )
        except ValueError as exc:  # coverage refusal — fail closed, nothing written
            print(f"REFUSED: {exc}")
            sys.exit(3)
    print(format_report(result, write=write))
    if csv:
        # Machine-readable per-position rows (everything already on RoundTrip;
        # no new computation, no writes) — for the founder's per-position table.
        print(
            "position_id,symbol,direction,qty,entry_price,gross,costs_est,net,complete,"
            "attribution,fills_used,flags"
        )
        for trip in result.trips:
            flags = "; ".join(trip.flags).replace('"', "'")
            fills_used = ""
            if trip.attribution is not None:
                fills_used = " | ".join(
                    f"{f.order_id} {f.side} {f.qty} @{f.price} {f.ts}"
                    for f in (*trip.attribution.entry_fills, *trip.attribution.exit_fills)
                )
            print(
                f"{trip.position_id},{trip.symbol},{trip.direction},{trip.position_qty},"
                f"{trip.entry_price if trip.entry_price is not None else ''},"
                f"{trip.gross_pnl if trip.gross_pnl is not None else ''},"
                f"{trip.costs.total if trip.costs is not None else ''},"
                f"{trip.net_pnl if trip.net_pnl is not None else ''},"
                f'{trip.complete},{trip.attribution_tag or ""},"{fills_used}","{flags}"'
            )


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.domains.pnl_reconciler")
    parser.add_argument("--strategy", required=True, help="strategy UUID")
    parser.add_argument(
        "--write",
        action="store_true",
        help="record final_pnl + attribution on closed positions (default: dry-run)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "with --write: recompute positions that already carry a final_pnl, NULL a "
            "value the rule marks human_interfered, NULL a stored literal zero on an "
            "unpriceable trip (explicit correction path; default is append-only)"
        ),
    )
    parser.add_argument(
        "--tradebook",
        nargs="+",
        metavar="JSONL",
        help=(
            "Dhan trade-book JSONL file(s) covering EVERY fill of the account on the "
            "strategy's contracts from their first fill through past the last close — "
            "required to price a LIVE strategy under the founder's exit rule"
        ),
    )
    parser.add_argument(
        "--book-covers-from",
        metavar="YYYY-MM-DD",
        help=(
            "the day the founder attests the trade book is COMPLETE from (every fill of the "
            "account on these contracts from that day on is in the file). Required with "
            "--write when --tradebook is given; the reconciler refuses to write unless every "
            "contract's first fill is at least a day later and the book extends past every close"
        ),
    )
    parser.add_argument("--csv", action="store_true", help="also print one CSV row per position")
    args = parser.parse_args()
    account_fills = load_dhan_tradebook(*args.tradebook) if args.tradebook else None
    if account_fills is not None:
        print(
            f"trade book: {len(account_fills)} futures fill(s) loaded from {len(args.tradebook)} file(s)"
        )
    covers_from = date.fromisoformat(args.book_covers_from) if args.book_covers_from else None
    if args.write and account_fills is not None and covers_from is None:
        print("REFUSED: --write with --tradebook requires --book-covers-from")
        sys.exit(3)
    asyncio.run(
        _run(
            uuid.UUID(args.strategy),
            write=args.write,
            overwrite=args.overwrite,
            csv=args.csv,
            account_fills=account_fills,
            book_covers_from=covers_from,
        )
    )


if __name__ == "__main__":
    main()
