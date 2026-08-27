#!/usr/bin/env python3
"""M6c pre-step — build the Round-2 scan root in the shape m5_engine expects.

Universe: M6b's 173 MINUS the 4 insurers (0% C-gate coverage for every quarter of
the window, per M6b's disclosure) = 169.

Emits data/round2/root/{daily_scan.parquet, nifty_daily.parquet,
eps_quarterly.parquet, daily/<SYM>.parquet}. Scan rows are produced for the whole
history so indicators are warm; the WINDOW restriction is applied by the runner's
calendar, never here.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
ROOT = R2 / "root"
INSURERS = {"HDFCLIFE", "ICICIGI", "ICICIPRULI", "SBILIFE", "LICI"}

MIN_HISTORY = 252
RS_LOOKBACK = 126
BASE_W = 35
BASE_MAX_TIGHT = 0.25
T6, T7 = 1.30, 0.75


def features(d: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    f = pd.DataFrame(index=d.index)
    f["close"] = c
    sma50, sma150, sma200 = (c.rolling(n).mean() for n in (50, 150, 200))
    f["t1"] = (c > sma150) & (c > sma200)
    f["t2"] = sma150 > sma200
    f["t3"] = sma200 > sma200.shift(21)
    f["t4"] = (sma50 > sma150) & (sma150 > sma200)
    f["t5"] = c > sma50
    hi252, lo252 = h.rolling(MIN_HISTORY).max(), l.rolling(MIN_HISTORY).min()
    f["t6"] = c >= T6 * lo252
    f["t7"] = c >= T7 * hi252
    f["dist_52wh"] = c / hi252 - 1
    f["dist_52wl"] = c / lo252 - 1
    f["pivot"] = h.rolling(BASE_W).max()
    base_low = l.rolling(BASE_W).min()
    f["base_tightness"] = (f["pivot"] - base_low) / base_low
    f["base_pass"] = f["base_tightness"] <= BASE_MAX_TIGHT
    f["median_turnover_20d"] = (c * v).rolling(20).median()
    f["ret126"] = c / c.shift(RS_LOOKBACK) - 1
    return f


def main() -> None:
    vd = pd.read_parquet(R2 / "audit_verdicts.parquet")
    keep = [s for s in vd[vd["verdict"] != "EXCLUDE"]["symbol"] if s not in INSURERS]
    universe = sorted(keep)
    print(f"universe: {len(universe)} (173 audited - insurers)")
    (ROOT / "daily").mkdir(parents=True, exist_ok=True)

    feats, ret = {}, {}
    for sym in universe:
        d = pd.read_parquet(R2 / "daily" / f"{sym}.parquet").sort_index()
        shutil.copyfile(R2 / "daily" / f"{sym}.parquet", ROOT / "daily" / f"{sym}.parquet")
        f = features(d)
        feats[sym] = f
        ret[sym] = f["ret126"]

    # cross-sectional RS percentile WITHIN the Round-2 universe
    rs_pct = pd.DataFrame(ret).rank(axis=1, pct=True, na_option="keep") * 100.0

    frames = []
    for sym in universe:
        f = feats[sym]
        if len(f) < MIN_HISTORY:
            continue
        days = f.index[MIN_HISTORY - 1:]
        part = f.loc[days, ["close", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
                            "dist_52wh", "dist_52wl", "pivot", "base_tightness",
                            "base_pass", "median_turnover_20d"]].copy()
        part.insert(0, "symbol", sym)
        part["rs_pct"] = rs_pct[sym].reindex(days)
        frames.append(part.reset_index().rename(columns={"index": "date"}))
    scan = pd.concat(frames, ignore_index=True)
    if "date" not in scan.columns:
        scan = scan.rename(columns={scan.columns[0]: "date"})
    for c in ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "base_pass"):
        scan[c] = scan[c].fillna(False).astype(bool)
    scan = scan.sort_values(["date", "symbol"]).reset_index(drop=True)
    scan.to_parquet(ROOT / "daily_scan.parquet")

    shutil.copyfile(R2 / "nifty_daily.parquet", ROOT / "nifty_daily.parquet")
    eps = pd.read_parquet(R2 / "eps_quarterly.parquet")
    eps[eps["symbol"].isin(universe)].to_parquet(ROOT / "eps_quarterly.parquet")
    print(f"scan rows {len(scan):,} ({scan['date'].min().date()} -> {scan['date'].max().date()})")
    print(f"root: {ROOT}")


if __name__ == "__main__":
    main()
