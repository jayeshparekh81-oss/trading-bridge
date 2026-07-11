"""OHLCV bar model + parquet load/save (Module R4, daily/historical path)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

OHLCV_SCHEMA = pa.schema([
    pa.field("ts", pa.int64()),          # epoch seconds (bar start)
    pa.field("open", pa.float64()),
    pa.field("high", pa.float64()),
    pa.field("low", pa.float64()),
    pa.field("close", pa.float64()),
    pa.field("volume", pa.int64()),
])
OHLCV_COLUMNS = [f.name for f in OHLCV_SCHEMA]


@dataclass
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: int


def bars_to_table(bars: list[Bar]) -> pa.Table:
    rows = [{"ts": b.ts, "open": b.open, "high": b.high, "low": b.low,
             "close": b.close, "volume": b.volume} for b in bars]
    return pa.Table.from_pylist(rows, schema=OHLCV_SCHEMA)


def load_ohlcv(path: Path) -> list[Bar]:
    t = pq.read_table(str(path))
    cols = {c: t.column(c).to_pylist() for c in OHLCV_COLUMNS}
    return [Bar(cols["ts"][i], cols["open"][i], cols["high"][i], cols["low"][i],
                cols["close"][i], cols["volume"][i]) for i in range(t.num_rows)]
