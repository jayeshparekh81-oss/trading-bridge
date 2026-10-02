#!/usr/bin/env python3
"""MODULE 1 — "1% Club" 52-week-high breakout: SIGNAL CENSUS.

Census only. No trades, no PnL, no portfolio, no parameter search, no tuning,
no variants. Reads data/panel_v2/daily (the single-source adjusted panel).

REGISTERED DEFINITIONS (declared, not chosen here):
  "52 week"            = 252 trading sessions
  "past 90 days" (F5)  = the last 90 trading sessions, inclusive of today
  "dipped below 220EMA"= that session's LOW < that session's EMA220
  warmup               = no signal until >= 300 sessions of history

INDICATORS
  SMA50, SMA150, EMA220 (pandas ewm span=220, adjust=False)
  hh252_excl = rolling max of CLOSE over the prior 252 sessions, EXCLUDING today
  ll252      = rolling min of LOW over the prior 252 sessions
  ret126     = close / close 126 sessions ago - 1

FILTERS
  F1 SMA150 > EMA220        F2 close > SMA50        F3 SMA50 > SMA150
  F4 close > 1.25 * ll252   F5 any(low < EMA220) over the last 90 sessions
  SIGNAL = F1..F5 and close > hh252_excl
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
DAILY = TRACK / "data" / "panel_v2" / "daily"
OUT = TRACK / "data" / "panel_v2"
UNI = [l.strip() for l in (TRACK / "config" / "universe_frozen.txt").read_text().splitlines() if l.strip()]

WARMUP = 300
LOOKBACK = 252
F5_WIN = 90
RET_N = 126


def build() -> pd.DataFrame:
    frames = []
    for s in UNI:
        d = pd.read_parquet(DAILY / f"{s}.parquet")
        d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).normalize()
        d = d.sort_index()
        c, lo = d["close"], d["low"]
        d["sma50"] = c.rolling(50).mean()
        d["sma150"] = c.rolling(150).mean()
        d["ema220"] = c.ewm(span=220, adjust=False).mean()
        d["hh252_excl"] = c.shift(1).rolling(LOOKBACK).max()
        d["ll252"] = lo.rolling(LOOKBACK).min()
        d["ret126"] = c / c.shift(RET_N) - 1
        d["dip"] = lo < d["ema220"]
        d["f5"] = d["dip"].rolling(F5_WIN).sum() > 0
        d["session_no"] = np.arange(1, len(d) + 1)
        d["symbol"] = s
        frames.append(d.reset_index())
    P = pd.concat(frames, ignore_index=True)

    P["F1"] = P["sma150"] > P["ema220"]
    P["F2"] = P["close"] > P["sma50"]
    P["F3"] = P["sma50"] > P["sma150"]
    P["F4"] = P["close"] > 1.25 * P["ll252"]
    P["F5"] = P["f5"]
    P["BRK"] = P["close"] > P["hh252_excl"]
    P["eligible"] = (P["session_no"] >= WARMUP) & P["hh252_excl"].notna() & P["sma150"].notna()
    P["signal"] = P["eligible"] & P[["F1", "F2", "F3", "F4", "F5", "BRK"]].all(axis=1)
    return P


def main() -> None:
    P = build()
    E = P[P["eligible"]]
    sessions = E["date"].nunique()
    print("=" * 78)
    print("MODULE 1 — SIGNAL CENSUS   (panel_v2, 188 symbols)")
    print("=" * 78)
    print(f"panel rows            : {len(P):,}   symbols {P['symbol'].nunique()}")
    print(f"panel date range      : {P['date'].min().date()} -> {P['date'].max().date()}")
    print(f"warmup-eligible rows  : {len(E):,}  over {sessions:,} sessions")
    print(f"eligible symbols/session: mean {len(E)/sessions:.1f}  "
          f"first eligible session {E['date'].min().date()}  last {E['date'].max().date()}")
    fe = P[P["eligible"]].groupby("symbol")["date"].min()
    print(f"first-eligible date per symbol: earliest {fe.min().date()}, "
          f"latest {fe.max().date()}, median {fe.median().date()}")
    print()

    # ---- 1. attrition funnel
    print("-" * 78)
    print("1. ATTRITION FUNNEL — average qualifying symbol-days per session")
    print("-" * 78)
    steps = [("eligible universe", []), ("F1", ["F1"]), ("F1+F2", ["F1", "F2"]),
             ("F1+F2+F3", ["F1", "F2", "F3"]), ("F1..F4", ["F1", "F2", "F3", "F4"]),
             ("F1..F5", ["F1", "F2", "F3", "F4", "F5"]),
             ("F1..F5 + breakout", ["F1", "F2", "F3", "F4", "F5", "BRK"])]
    prev = None
    print(f"{'stage':<20}{'avg/session':>13}{'% of eligible':>15}{'% kept vs prev':>16}")
    for name, cols in steps:
        m = E[cols].all(axis=1) if cols else pd.Series(True, index=E.index)
        avg = m.sum() / sessions
        pct = 100 * m.mean()
        keep = "" if prev is None else f"{100*avg/prev:>15.1f}%"
        print(f"{name:<20}{avg:>13.2f}{pct:>14.1f}%{keep:>16}")
        prev = avg
    print()

    # ---- 2. totals
    S = P[P["signal"]].copy()
    print("-" * 78)
    print("2. TOTAL SIGNALS")
    print("-" * 78)
    print(f"total signals over the panel: {len(S):,}")
    yr = S.groupby(S["date"].dt.year).size()
    el_yr = E.groupby(E["date"].dt.year)["date"].nunique()
    t = pd.DataFrame({"signals": yr, "sessions": el_yr}).fillna(0).astype(int)
    t["per_session"] = (t["signals"] / t["sessions"]).round(2)
    print(t.to_string())
    print()

    # ---- 3. per-session distribution
    print("-" * 78)
    print("3. SIGNALS PER SESSION")
    print("-" * 78)
    per = S.groupby("date").size().reindex(sorted(E["date"].unique()), fill_value=0)
    print(f"average signals per session: {per.mean():.3f}   median {per.median():.0f}   max {per.max()}")
    bins = pd.cut(per, [-1, 0, 5, 10, np.inf], labels=["0", "1-5", "6-10", ">10"])
    vc = bins.value_counts().reindex(["0", "1-5", "6-10", ">10"])
    d = pd.DataFrame({"sessions": vc, "pct": (100 * vc / len(per)).round(1)})
    print(d.to_string())
    print(f"(total sessions counted: {len(per):,})")
    print()

    # ---- 4. breadth
    print("-" * 78)
    print("4. SYMBOL BREADTH")
    print("-" * 78)
    print(f"distinct symbols that ever fire a signal: {S['symbol'].nunique()} of {len(UNI)}")
    print(f"symbols that never fire: {len(UNI) - S['symbol'].nunique()}")
    print("\ntop 15 by signal count:")
    print(S["symbol"].value_counts().head(15).to_string())
    print()

    # ---- 5. F5 isolation
    print("-" * 78)
    print("5. F5 IN ISOLATION — does it cancel the breakout?")
    print("-" * 78)
    base = E[E[["F1", "F2", "F3", "F4", "BRK"]].all(axis=1)]
    with5 = base[base["F5"]]
    print(f"F1-F4 + breakout, WITHOUT F5 : {len(base):,} signals")
    print(f"F1-F4 + breakout, WITH F5    : {len(with5):,} signals")
    print(f"lost to F5 alone             : {len(base)-len(with5):,}  "
          f"({100*(1-len(with5)/len(base)):.1f}% of the F5-free count)")
    print(f"F5 pass-rate on the eligible universe at large: {100*E['F5'].mean():.1f}%")
    print(f"F5 pass-rate conditional on F1-F4 + breakout  : {100*len(with5)/len(base):.1f}%")
    print()

    # ---- 6. distance above EMA220
    print("-" * 78)
    print("6. HOW FAR ABOVE THE 220 EMA DOES A BREAKOUT ENTRY SIT?")
    print("-" * 78)
    S["pct_above_ema220"] = 100 * (S["close"] / S["ema220"] - 1)
    q = S["pct_above_ema220"].quantile([0.25, 0.5, 0.75])
    print(f"median {q[0.5]:.2f}%   IQR {q[0.25]:.2f}% .. {q[0.75]:.2f}%   "
          f"(width {q[0.75]-q[0.25]:.2f} pts)")
    print(f"min {S['pct_above_ema220'].min():.2f}%   max {S['pct_above_ema220'].max():.2f}%   "
          f"mean {S['pct_above_ema220'].mean():.2f}%")
    print("\n20 most recent signals:")
    print(S.nlargest(20, "date")[["symbol", "date", "close", "ema220", "pct_above_ema220"]]
          .assign(date=lambda x: x["date"].dt.date,
                  close=lambda x: x["close"].round(2),
                  ema220=lambda x: x["ema220"].round(2),
                  pct_above_ema220=lambda x: x["pct_above_ema220"].round(2))
          .to_string(index=False))
    print()

    # ---- 7. gap-contaminated signals
    print("-" * 78)
    print("7. SIGNALS WHOSE 252-SESSION LOOKBACK CROSSES A DATA GAP (flagged, not dropped)")
    print("-" * 78)
    pat = S[(S["symbol"] == "PATANJALI") & (S["date"] >= "2019-11-14") & (S["date"] <= "2021-01-31")]
    print(f"PATANJALI signals dated 2019-11-14 .. 2021-01-31: {len(pat)}")
    if len(pat):
        print(pat[["symbol", "date", "close", "ema220"]].assign(
            date=lambda x: x["date"].dt.date).to_string(index=False))
    # general form: lookback window start earlier than the gap end
    for sym, g0, g1 in (("PATANJALI", "2019-11-14", "2020-01-24"),
                        ("DALBHARAT", "2019-01-07", "2019-01-21")):
        sub = P[P["symbol"] == sym].sort_values("date").reset_index(drop=True)
        sig = sub.index[sub["signal"]]
        gap_end = pd.Timestamp(g1)
        hits = []
        for i in sig:
            start = sub.loc[max(0, i - LOOKBACK), "date"]
            if start <= gap_end <= sub.loc[i, "date"]:
                hits.append(sub.loc[i, "date"].date())
        print(f"\n{sym}: signals whose prior-252-session window spans the {g0}..{g1} gap: {len(hits)}")
        if hits:
            print("   ", hits)
    print()

    # ---- 8. write
    pan = OUT / "module1_panel.parquet"
    sig = OUT / "module1_signals.parquet"
    P.to_parquet(pan, index=False)
    S.to_parquet(sig, index=False)
    print("-" * 78)
    print("8. OUTPUTS")
    print("-" * 78)
    print(f"panel  : {pan}   ({len(P):,} rows)")
    print(f"signals: {sig}   ({len(S):,} rows)")


if __name__ == "__main__":
    main()
