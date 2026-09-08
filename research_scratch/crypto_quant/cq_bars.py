"""Build 1-minute bars with delta and CVD from the raw aggTrades zips."""
import glob, json, zipfile
import numpy as np, pandas as pd
from pathlib import Path

files = sorted(glob.glob("raw/BTCUSDT-aggTrades-*.zip"))
print(f"  files: {len(files)}", flush=True)
frames, tot_rows = [], 0
for i, f in enumerate(files):
    df = pd.read_csv(f, compression="zip",
                     usecols=["price", "quantity", "transact_time", "is_buyer_maker"],
                     dtype={"price": "float64", "quantity": "float64",
                            "transact_time": "int64", "is_buyer_maker": "object"})
    tot_rows += len(df)
    ibm = df["is_buyer_maker"].astype(str).str.lower().eq("true").to_numpy()
    # is_buyer_maker True  -> taker was the SELLER -> signed volume negative
    sign = np.where(ibm, -1.0, 1.0)
    df["signed"] = df["quantity"].to_numpy() * sign
    df["taker_buy"] = (~ibm).astype(np.int64)
    df["minute"] = df["transact_time"] // 60000
    g = df.groupby("minute", sort=True)
    bar = pd.DataFrame({
        "open": g["price"].first(), "high": g["price"].max(),
        "low": g["price"].min(), "close": g["price"].last(),
        "volume": g["quantity"].sum(), "delta": g["signed"].sum(),
        "trades": g["price"].size(), "taker_buys": g["taker_buy"].sum(),
    })
    frames.append(bar)
    if i % 30 == 0:
        print(f"  [{i+1:3d}/{len(files)}] {Path(f).stem[-10:]} rows={tot_rows:,}", flush=True)
bars = pd.concat(frames).sort_index()
bars = bars[~bars.index.duplicated(keep="first")]
bars["cvd"] = bars["delta"].cumsum()
bars["ts_ms"] = bars.index.to_numpy() * 60000
bars.to_parquet("raw/bars_1m.parquet")
rec = {"files": len(files), "raw_trades": int(tot_rows), "bars": int(len(bars)),
       "first_bar_ms": int(bars["ts_ms"].iloc[0]), "last_bar_ms": int(bars["ts_ms"].iloc[-1]),
       "span_days": (int(bars["ts_ms"].iloc[-1]) - int(bars["ts_ms"].iloc[0])) / 86400000,
       "expected_bars_if_continuous": int((int(bars["ts_ms"].iloc[-1]) - int(bars["ts_ms"].iloc[0]))/60000)+1,
       "taker_buy_share": float(bars["taker_buys"].sum() / bars["trades"].sum()),
       "trades_per_second": float(tot_rows / ((int(bars["ts_ms"].iloc[-1]) - int(bars["ts_ms"].iloc[0]))/1000)),
       "bytes_parquet": Path("raw/bars_1m.parquet").stat().st_size}
json.dump(rec, open("receipts/cp_bars.json", "w"), indent=2)
print(json.dumps(rec, indent=2))
