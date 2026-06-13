"""Phase 3 seed script — enqueue 22 ``historical_backfill_jobs`` rows.

The Phase 3 initial backfill set: founder's two live-trade-adjacent
listings (BSE LTD, CDSL), the 5 most-watched indices, and the top-15
NIFTY 50 stocks by index weight. One job per symbol for the **daily
timeframe** covering the last calendar year. The matrix is
deliberately conservative — operator can run this multiple times
with different timeframe / window args once it's verified safe.

**NEVER executed on the 2026-06-12 overnight session.** Two things
must land first:

    (a) Migration ``030_historical_backfill_jobs`` applied to the
        target DB. (Tonight: file-only. Founder gate: Saturday AM.)
    (b) Dhan security_ids verified against the current scrip master.
        The values in ``_SYMBOLS`` below are well-known canonical
        IDs but the scrip master can rotate them — verification is
        a 5-minute SELECT against ``dhan_scrip_master`` (or via
        Dhan's instrument-list endpoint).

How to run (after both prerequisites):

    docker compose exec backend \\
        python -m scripts.phase3_seed_22_symbols_backfill

The script prints one line per enqueue + a final summary. Idempotent:
re-running creates duplicate PENDING rows — the table does not have
a uniqueness constraint by intent (a re-fetch with a different window
is a legitimate use case). Operator must dedupe manually if needed.

Exit codes:
    0 — all 22 rows inserted
    2 — migration 030 not applied yet (clear error printed)
    1 — any other DB / configuration failure
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


class _SymbolSpec(NamedTuple):
    """One row's worth of identification needed to call Dhan + persist."""

    symbol: str
    exchange: str  # Dhan exchange_segment form
    dhan_security_id: str
    category: str  # for human readability in script output


# Dhan exchange_segment values per Dhan v2 docs:
#   NSE_EQ — NSE equity
#   BSE_EQ — BSE equity
#   IDX_I  — index (Nifty / Bank Nifty / Sensex etc.)
#
# security_id values below are the commonly-known scrip-master IDs
# at time of writing. The README of dhan-historical-data and the
# instrument list at api.dhan.co both surface the same values — but
# Dhan periodically rotates IDs, so verify before live execution.
# Indices and BSE LTD specifically have been observed to drift.

_SYMBOLS: tuple[_SymbolSpec, ...] = (
    # ── Founder-live + adjacent (2) ───────────────────────────────
    _SymbolSpec("BSELTD", "BSE_EQ", "1", "founder_live"),  # ★ VERIFY before exec
    _SymbolSpec("CDSL", "NSE_EQ", "21174", "founder_adjacent"),
    # ── Indices (5) ───────────────────────────────────────────────
    _SymbolSpec("NIFTY", "IDX_I", "13", "index"),
    _SymbolSpec("BANKNIFTY", "IDX_I", "25", "index"),
    _SymbolSpec("FINNIFTY", "IDX_I", "27", "index"),  # ★ VERIFY
    _SymbolSpec("MIDCPNIFTY", "IDX_I", "26", "index"),  # ★ VERIFY
    _SymbolSpec("SENSEX", "IDX_I", "51", "index"),  # ★ VERIFY (BSE index)
    # ── Top 15 NIFTY 50 stocks (by index weight) ──────────────────
    _SymbolSpec("RELIANCE", "NSE_EQ", "2885", "nifty50"),
    _SymbolSpec("HDFCBANK", "NSE_EQ", "1333", "nifty50"),
    _SymbolSpec("ICICIBANK", "NSE_EQ", "4963", "nifty50"),
    _SymbolSpec("INFY", "NSE_EQ", "1594", "nifty50"),
    _SymbolSpec("TCS", "NSE_EQ", "11536", "nifty50"),
    _SymbolSpec("ITC", "NSE_EQ", "1660", "nifty50"),
    _SymbolSpec("BHARTIARTL", "NSE_EQ", "10604", "nifty50"),
    _SymbolSpec("KOTAKBANK", "NSE_EQ", "1922", "nifty50"),
    _SymbolSpec("SBIN", "NSE_EQ", "3045", "nifty50"),
    _SymbolSpec("LT", "NSE_EQ", "11483", "nifty50"),
    _SymbolSpec("HINDUNILVR", "NSE_EQ", "1394", "nifty50"),
    _SymbolSpec("AXISBANK", "NSE_EQ", "5900", "nifty50"),
    _SymbolSpec("M&M", "NSE_EQ", "2031", "nifty50"),
    _SymbolSpec("BAJFINANCE", "NSE_EQ", "317", "nifty50"),
    _SymbolSpec("ASIANPAINT", "NSE_EQ", "236", "nifty50"),
)

_TIMEFRAME = "1d"
_LOOKBACK_DAYS = 365


def _windows() -> tuple[datetime, datetime]:
    """Default Phase 3 seed window: last 365 calendar days, ending now.

    Founder can override by editing this function or by inserting
    bespoke rows after running the seed.
    """
    to_ts = datetime.now(UTC).replace(microsecond=0, second=0, minute=0)
    from_ts = to_ts - timedelta(days=_LOOKBACK_DAYS)
    return from_ts, to_ts


async def _enqueue_all() -> int:
    """Bulk-enqueue PENDING jobs. Returns count actually inserted.

    Each row is created via
    :meth:`HistoricalBackfillJobsRepository.create` so any future
    structured logging stays consistent with the Celery task path.
    """
    from app.db.session import dispose_engine, get_sessionmaker
    from app.services.historical_candles.jobs_repository import (
        HistoricalBackfillJobsRepository,
    )

    from_ts, to_ts = _windows()
    maker = get_sessionmaker()
    inserted = 0
    try:
        async with maker() as session:
            repo = HistoricalBackfillJobsRepository(session)
            for spec in _SYMBOLS:
                try:
                    job = await repo.create(
                        symbol=spec.symbol,
                        exchange=spec.exchange,
                        timeframe=_TIMEFRAME,
                        dhan_security_id=spec.dhan_security_id,
                        from_ts=from_ts,
                        to_ts=to_ts,
                    )
                except Exception as exc:  # narrow at orchestrator layer
                    print(
                        f"  [FAIL] {spec.symbol:>12} {spec.category:<18}"
                        f"  → {exc.__class__.__name__}: {exc}",
                        file=sys.stderr,
                    )
                    raise
                print(f"  [enq]  {spec.symbol:>12} {spec.category:<18}  job_id={job.id}")
                inserted += 1
            await session.commit()
    finally:
        await dispose_engine()
    return inserted


def _check_migration_applied_hint(exc: BaseException) -> bool:
    """Heuristic: did the failure look like 'table does not exist'?"""
    msg = str(exc).lower()
    return "historical_backfill_jobs" in msg and (
        "does not exist" in msg or "undefinedtable" in msg
    )


def main() -> None:
    from_ts, to_ts = _windows()
    print(
        f"Phase 3 seed — enqueueing {len(_SYMBOLS)} backfill jobs "
        f"(timeframe={_TIMEFRAME}, window={from_ts.date()} → {to_ts.date()})"
    )
    print()
    try:
        inserted = asyncio.run(_enqueue_all())
    except Exception as exc:
        if _check_migration_applied_hint(exc):
            print(
                "\nERROR: historical_backfill_jobs table is not present. "
                "Migration 030 has not been applied yet. Run:\n"
                "    docker compose exec backend alembic upgrade head\n"
                "after the founder G2 review for migration 030. See "
                "docs/QUEUE_CCC_OVERNIGHT_BRIEF.md parked-gate (a).",
                file=sys.stderr,
            )
            sys.exit(2)
        print(f"\nERROR: unexpected failure: {exc!r}", file=sys.stderr)
        sys.exit(1)

    print()
    print(f"Phase 3 seed — OK, {inserted}/{len(_SYMBOLS)} PENDING rows enqueued.")


if __name__ == "__main__":
    main()
