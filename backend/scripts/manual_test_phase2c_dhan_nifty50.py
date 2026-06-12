"""Phase 2c manual smoke test — fetch one NIFTY 50 INDEX window from Dhan
and persist via the new ``historical_candles`` repository.

NOT part of the automated suite — this is an operator-run smoke test
that requires LIVE Dhan creds. Skipped on the overnight session of
2026-06-12 because creds weren't available. Phase 2c is PENDING for
the Saturday 2026-06-13 session — see
``docs/QUEUE_CCC_OVERNIGHT_BRIEF.md``.

Why NIFTY 50 INDEX:
    * Single deterministic symbol — no scrip-master lookups needed.
    * Daily timeframe → small response (≤7 bars for a week window).
    * Index instrument has no F&O / split / dividend complexity.
    * Exchange_segment=IDX_I, instrument=INDEX, security_id=13 are
      stable Dhan-side constants.

How to run (founder shell, NOT inside Claude):

    export DHAN_CLIENT_ID=<your-dhan-client-id>
    export DHAN_ACCESS_TOKEN=<your-dhan-access-token>

    docker compose exec \\
        -e DHAN_CLIENT_ID -e DHAN_ACCESS_TOKEN \\
        backend python -m scripts.manual_test_phase2c_dhan_nifty50

Expected outcome:
    1. Dhan returns ≤7 daily bars for the past 7 days.
    2. Bars round-trip through ``chart_candle_to_orm`` and persist via
       ``HistoricalCandleRepository.upsert_batch``.
    3. The coverage probe afterwards confirms the row count + first/last
       timestamps match what Dhan returned.

The script COMMITS the inserted bars — this is by design (Phase 3
backfill jobs will want them). Re-running is idempotent thanks to
``ON CONFLICT DO NOTHING``.

Exit codes:
    0 — Dhan + persistence + verification all green
    2 — DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN missing
    1 — any Dhan / DB / verification failure (traceback printed)
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# NIFTY 50 INDEX — Dhan-side constants. INDEX security_id is documented
# in Dhan's scrip master and stable across releases.
_SYMBOL = "NIFTY"
_SECURITY_ID = "13"
_EXCHANGE_SEGMENT = "IDX_I"
_INSTRUMENT = "INDEX"

# Placeholder UUID used only for per-user rate-limit keying inside
# DhanHistoricalClient (the field is required by the constructor but
# the smoke test is not bound to any real user).
_SMOKE_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _run() -> int:
    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token:
        print(
            "ERROR: DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set "
            "in the environment before running this script.",
            file=sys.stderr,
        )
        return 2

    # Late imports — keep error path (missing env) fast and dependency-free.
    from app.brokers.dhan_historical import DhanHistoricalClient
    from app.db.session import dispose_engine, get_sessionmaker
    from app.schemas.candle import Timeframe
    from app.services.historical_candles.repository import (
        HistoricalCandleRepository,
    )
    from app.services.historical_candles.schema_bridge import chart_candle_to_orm

    to_ts = datetime.now(UTC).replace(microsecond=0)
    from_ts = to_ts - timedelta(days=7)

    print(
        f"[Phase 2c] Fetching {_SYMBOL} daily bars  "
        f"{from_ts.date().isoformat()} → {to_ts.date().isoformat()}"
    )

    async with DhanHistoricalClient(
        client_id=client_id,
        access_token=access_token,
        user_id=_SMOKE_TEST_USER_ID,
    ) as dhan:
        candles = await dhan.get_historical_ohlc(
            symbol=_SYMBOL,
            security_id=_SECURITY_ID,
            exchange_segment=_EXCHANGE_SEGMENT,
            instrument=_INSTRUMENT,
            timeframe=Timeframe.ONE_DAY,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    print(f"[Phase 2c] Dhan returned {len(candles)} bar(s).")
    if not candles:
        print(
            "[Phase 2c] WARNING: empty response. NIFTY 50 may be on a holiday "
            "stretch or Dhan rejected the window. Not a script failure — "
            "verify the date range manually."
        )
        await dispose_engine()
        return 0

    # Print up to 5 bars for human inspection.
    for c in candles[:5]:
        print(
            f"           {c.timestamp.date().isoformat()}  "
            f"O={c.open}  H={c.high}  L={c.low}  C={c.close}  V={c.volume}"
        )
    if len(candles) > 5:
        print(f"           … and {len(candles) - 5} more")

    # Persist via the bridge + repository.
    maker = get_sessionmaker()
    async with maker() as session:
        repo = HistoricalCandleRepository(session)
        orm_candles = [
            chart_candle_to_orm(
                c,
                exchange=_EXCHANGE_SEGMENT,
                dhan_security_id=_SECURITY_ID,
                fetched_by_user_id=None,
            )
            for c in candles
        ]
        inserted = await repo.upsert_batch(orm_candles)
        await session.commit()
        print(
            f"[Phase 2c] upsert_batch  submitted={len(candles)}  "
            f"inserted={inserted}  skipped={len(candles) - inserted}"
        )

        report = await repo.coverage(
            symbol=_SYMBOL,
            exchange=_EXCHANGE_SEGMENT,
            timeframe="1d",
            from_ts=from_ts,
            to_ts=to_ts,
        )
        print(
            f"[Phase 2c] coverage      bar_count={report.bar_count}  "
            f"first={report.first_bar_ts}  last={report.last_bar_ts}"
        )

        if report.bar_count < len(candles):
            print(
                f"[Phase 2c] ERROR: coverage bar_count ({report.bar_count}) "
                f"< Dhan response count ({len(candles)}). Investigate.",
                file=sys.stderr,
            )
            await dispose_engine()
            return 1

    await dispose_engine()
    print("[Phase 2c] OK — Dhan → bridge → repo → coverage round-trip green.")
    return 0


def main() -> None:
    rc = asyncio.run(_run())
    sys.exit(rc)


if __name__ == "__main__":
    main()
