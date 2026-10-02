"""Data loading for the backtest harness.

load(symbol) → tz-aware (Asia/Kolkata) OHLCV DataFrame indexed by timestamp,
validated sorted + de-duplicated.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
_COLS = ["open", "high", "low", "close", "volume"]


def load(symbol: str, data_dir: Path | None = None) -> pd.DataFrame:
    path = (data_dir or DATA_DIR) / f"{symbol}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — fetch it first (fetch_dhan_futures.py).")

    df = pd.read_parquet(path)
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")

    missing = [c for c in _COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{symbol}: missing columns {missing}")
    df = df[_COLS].copy()

    # Validate: sorted + unique. Repair (sort/dedup) rather than trust the file blindly.
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    dupes = int(df.index.duplicated().sum())
    if dupes:
        df = df[~df.index.duplicated(keep="first")]
    print(f"[data] {symbol}: {len(df):,} bars  {df.index.min()} → {df.index.max()}"
          f"  (deduped {dupes})")
    return df
