"""Integration: replay a REAL recorded day end-to-end.

Data-gated (like tests/services/historical_candles/test_repository.py needs live
Postgres): market-data parquet is never committed, so this SKIPS unless the day
dir exists locally. Point it at real data with ORDERFLOW_REPLAY_DATA=<day dir>
(default: orderflow_engine/data/2026-07-09). Asserts:
  * events emitted == total tick rows + event rows (per coverage)
  * determinism (G1) on real data — two replays hash identically
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from replayer.consumer import CountingConsumer, HashingConsumer
from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

HERE = Path(__file__).resolve().parents[2]  # orderflow_engine/
_DEFAULT = HERE / "data" / "2026-07-09"
_DAY = Path(os.environ.get("ORDERFLOW_REPLAY_DATA", str(_DEFAULT)))


@pytest.mark.skipif(not _DAY.is_dir(),
                    reason=f"no recorded data at {_DAY} (set ORDERFLOW_REPLAY_DATA)")
def test_replay_real_day_count_and_determinism():
    src = ReplaySource(_DAY)
    cov = src.coverage()
    expected = cov.total_tick_rows + cov.total_event_rows

    c = CountingConsumer()
    summary = ReplayEngine(src).drive(c, speed="max")
    assert c.total == expected, (c.packets, c.events, expected)
    assert summary.total == expected

    h1 = HashingConsumer()
    ReplayEngine(src).drive(h1, speed="max")
    h2 = HashingConsumer()
    ReplayEngine(src).drive(h2, speed="max")
    assert h1.hexdigest() == h2.hexdigest()
    assert h1.count == expected
