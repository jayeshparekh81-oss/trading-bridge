"""CLI entrypoint: ``python -m app.domains.pnl_reconciler --strategy <uuid>``.

Dry-run by default — reads + computes + prints, writes nothing. Pass
``--write`` to annotate ``final_pnl`` on completely-reconciled CLOSED
positions (founder-gated; never run against a live strategy without an
explicit go-ahead).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.db.session import get_sessionmaker
from app.domains.pnl_reconciler.service import format_report, reconcile_strategy


async def _run(strategy_id: uuid.UUID, *, write: bool, csv: bool) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        result = await reconcile_strategy(session, strategy_id, write=write)
    print(format_report(result, write=write))
    if csv:
        # Machine-readable per-position rows (everything already on RoundTrip;
        # no new computation, no writes) — for the founder's per-position table.
        print("position_id,symbol,direction,qty,entry_price,gross,costs_est,net,complete,flags")
        for trip in result.trips:
            flags = "; ".join(trip.flags).replace('"', "'")
            print(
                f"{trip.position_id},{trip.symbol},{trip.direction},{trip.position_qty},"
                f"{trip.entry_price if trip.entry_price is not None else ''},"
                f"{trip.gross_pnl if trip.gross_pnl is not None else ''},"
                f"{trip.costs.total if trip.costs is not None else ''},"
                f"{trip.net_pnl if trip.net_pnl is not None else ''},"
                f'{trip.complete},"{flags}"'
            )


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.domains.pnl_reconciler")
    parser.add_argument("--strategy", required=True, help="strategy UUID")
    parser.add_argument(
        "--write",
        action="store_true",
        help="annotate final_pnl on fully-reconciled closed positions (default: dry-run)",
    )
    parser.add_argument("--csv", action="store_true", help="also print one CSV row per position")
    args = parser.parse_args()
    asyncio.run(_run(uuid.UUID(args.strategy), write=args.write, csv=args.csv))


if __name__ == "__main__":
    main()
