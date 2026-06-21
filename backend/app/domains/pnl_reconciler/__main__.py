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


async def _run(strategy_id: uuid.UUID, *, write: bool) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        result = await reconcile_strategy(session, strategy_id, write=write)
    print(format_report(result, write=write))


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.domains.pnl_reconciler")
    parser.add_argument("--strategy", required=True, help="strategy UUID")
    parser.add_argument(
        "--write",
        action="store_true",
        help="annotate final_pnl on fully-reconciled closed positions (default: dry-run)",
    )
    args = parser.parse_args()
    asyncio.run(_run(uuid.UUID(args.strategy), write=args.write))


if __name__ == "__main__":
    main()
