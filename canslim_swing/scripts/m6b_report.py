#!/usr/bin/env python3
"""M6b report assembler — Round-2A fetch + audits."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
REPORT = TRACK / "reports" / "swing_module6b_oldera_fetch.txt"


def fmt(df, idx=False):
    if df is None or len(df) == 0:
        return "  (none)\n"
    with pd.option_context("display.width", 230, "display.max_rows", len(df) + 5):
        return df.to_string(index=idx) + "\n"


def main() -> None:
    depth = pd.read_parquet(R2 / "price_depth.parquet")
    parked = pd.read_parquet(R2 / "price_parked.parquet")
    sus = pd.read_parquet(R2 / "audit_suspects.parquet")
    cliffs = pd.read_parquet(R2 / "audit_cliffs.parquet")
    spot = pd.read_parquet(R2 / "audit_spot.parquet")
    ov = pd.read_parquet(R2 / "audit_overlap.parquet")
    vd = pd.read_parquet(R2 / "audit_verdicts.parquet")
    st = pd.read_parquet(R2 / "eps_status.parquet")
    cov = pd.read_parquet(R2 / "coverage.parquet")
    eps = pd.read_parquet(R2 / "eps_quarterly.parquet")

    L, A = [], None
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 6b — ROUND-2A OLD-ERA FETCH + AUDITS (data only)")
    A("Scan/shot belong to M6c. Cache: canslim_swing/data/round2/")
    A("SCOPE: fetch range != test range. Sealed window stays Jan-2018 -> Jul-2021;")
    A("prices reach back to 2015 only for warmup and cross-checks.")
    A("=" * 78)
    A("")
    A("1. PRICES")
    ok = depth[depth["symbol"] != "NIFTY(IDX)"]
    A(f"  fetched: {len(ok)} symbols + NIFTY index | parked: {len(parked)}")
    A(f"  range served: {ok['first'].min()} -> {ok['last'].max()}")
    A(f"  Dhan DOES serve daily back to 2015-01-01 (~1,691 bars/symbol) — this")
    A(f"  answers the question M6a could not, because its token had expired.")
    A("")
    A("  PARKED — all 15 are post-window listings (HTTP 400 DH-905), verified against")
    A("  their habitat first-trade dates. Not fetch failures; they simply did not")
    A("  exist in 2015-2021 and cannot be in a Round-2 universe:")
    A("    " + ", ".join(parked["symbol"].tolist()))
    A("")
    A("  Yearly bar counts (head; full table in data/round2/price_depth.parquet):")
    ycols = [c for c in depth.columns if c.startswith("y")]
    A(fmt(depth[["symbol", "bars", "first", "last"] + ycols].head(12)))
    A(f"  bar-count spread across symbols: min {int(ok['bars'].min())}, "
      f"median {int(ok['bars'].median())}, max {int(ok['bars'].max())}")
    short = ok[ok["bars"] < 1000]
    A(f"  symbols with <1000 bars (later listings inside the window): {len(short)}")
    if len(short):
        A(fmt(short[["symbol", "bars", "first", "last"]]))
    A("")
    A("-" * 78)
    A("2. OLD-ERA ADJUSTMENT AUDIT (report-only)")
    A("")
    A(f"  (a) GAP SCAN 2015 -> Oct-2021, |move| >= 25%: {len(sus)} suspect rows")
    A(fmt(sus.assign(date=sus["date"].dt.date).sort_values(["symbol", "date"]).reset_index(drop=True)))
    A(f"  (b) CORP-ACTION MATCH for every suspect:")
    A(f"      {cliffs['classification'].value_counts().to_dict()}")
    A("      MATCHED-CLIFFED would mean an ex-date cliff survived in the series,")
    A("      i.e. UNADJUSTED. There are NONE: every >=25% move in six years lines up")
    A("      with no split/bonus/demerger, so they are real price events (COVID,")
    A("      earnings shocks, PSU news) rather than adjustment failures.")
    A("")
    A("  (c) NAMED SPOT-CHECKS — a back-adjusted series shows NO cliff at an ex-date:")
    for ev, g in spot.groupby("event"):
        sym = g["symbol"].iloc[0]
        exrow = g[g["is_ex_date"]]
        mv = exrow["pct_move"].iloc[0] if len(exrow) else None
        naive = "-50%" if "1:1" in ev else "-33%"
        A(f"    {sym} {ev}: move ON the ex-date = {mv:+.2f}%  (raw series would show ~{naive})")
    A("")
    A(fmt(spot))
    A("  (d) HABITAT-OVERLAP RATIO (Aug -> Oct 2021, common dates)")
    ovok = ov[ov["status"] == "ok"].copy()
    ovok["consistent"] = ovok["consistent"].astype(bool)
    A(f"      symbols compared: {len(ovok)} | inconsistent (persistent step >= 4%): "
      f"{int((~ovok['consistent']).sum())}")
    A("      METHOD NOTE: an earlier version of this test also required the ratio")
    A("      LEVEL to be ~1.0 and used a 2% step threshold. That was wrong twice.")
    A("      Habitat is back-adjusted to 2026 while this fetch anchors at Oct-2021,")
    A("      so any corp action AFTER the window makes the ratio a flat constant")
    A("      != 1 — benign. And a 2% threshold lets a single-day price discrepancy")
    A("      masquerade as a missed corp action (a real one is >= 20%). Corrected to")
    A("      M1's PERSISTENT-step test; it wrongly excluded 11 symbols before the fix.")
    A("      Flat-but-shifted symbols (benign, post-window corp actions):")
    lvl = ovok[(ovok["ratio_mean"] - 1).abs() > 0.02]
    A(fmt(lvl[["symbol", "days", "ratio_mean", "persistent_step"]]))
    A("      RECLTD's 0.75000 is a textbook 1:3 bonus after the window.")
    A("")
    A("  (e) PER-SYMBOL VERDICTS")
    A(f"      {vd['verdict'].value_counts().to_dict()}")
    A("      SUSPECT = a >=25% cliff with no matching corp action; kept (the moves")
    A("      look real) but flagged so M6c can exclude them if it chooses:")
    A("      " + ", ".join(vd[vd["verdict"] == "SUSPECT"]["symbol"].tolist()))
    A("")
    A(f"      *** FINAL ROUND-2 UNIVERSE: {int((vd['verdict'] != 'EXCLUDE').sum())} symbols ***")
    A(f"      (188 frozen universe - 15 post-window listings = 173; 0 excluded by audit)")
    A("")
    A("-" * 78)
    A("3. EPS EXTENSION (2016-Q2 -> 2021-Q2)")
    A(f"  requests: 5,764 | status rows: {len(st):,} | merged parquet rows: {len(eps):,}")
    A(f"  outcome: {st['status'].value_counts().to_dict()}")
    A("")
    A("  Split by the filing's `format` field — the frontier M6a identified, now")
    A("  measured across the whole universe rather than 12 probe symbols:")
    A(fmt(st.groupby(["format", "status"]).size().unstack(fill_value=0), idx=True))
    A("  format='New' is 97.7% usable; format='Old' is 8.3%. 'stub' means the detail")
    A("  payload was empty AND the list row's xbrl link ends in '/-', so no fallback")
    A("  exists — the M2b rescue path is simply absent for old filings.")
    A("")
    A("-" * 78)
    A("4. COVERAGE DISCLOSURE — C-GATE ELIGIBILITY BY QUARTER (pre-registered)")
    A("")
    A("  Eligible = has a usable latest-announced quarter (within 200d) AND its")
    A("  year-ago pair, in the symbol's chosen series, as of that date.")
    A("")
    A(fmt(cov))
    A("  THE YEAR-AGO REQUIREMENT MOVES THE FRONTIER A FULL YEAR LATER THAN THE RAW")
    A("  EPS FRONTIER. Raw EPS becomes available around 2018 (when filings flip to")
    A("  format='New'), but the C-gate needs a year-ago pair, so a 2018-Q1 scan needs")
    A("  a 2017-Q1 filing — squarely inside the dead zone. Result: the first FIVE")
    A("  quarters of the registered window (2018-Q1 .. 2019-Q1, 15 of its 42 months)")
    A("  sit at 9-15% eligibility and are ALL flagged SKEW PERIOD.")
    A("")
    A("  The sector split shows those quarters are not merely thin — they are")
    A("  BANK-ONLY: banks run 88-94% eligible while 'other' is 0-3% and NBFCs and")
    A("  insurers are at 0%. Insurers stay at 0% for the ENTIRE window (4 symbols),")
    A("  exactly as M6a predicted from SBILIFE's missing old-regime list.")
    A("  From 2019-Q2 coverage jumps to 73% and holds 80-91% thereafter.")
    A("")
    A("-" * 78)
    A("5. NIFTY")
    n = pd.read_parquet(R2 / "nifty_daily.parquet")
    A(f"  {len(n)} sessions {n.index.min().date()} -> {n.index.max().date()}")
    A(f"  sma200 valid from {n['sma200'].first_valid_index().date()}; "
      f"ema10m (M5-corrected single lag) from {n['ema10m'].first_valid_index().date()}")
    A("  Both columns saved in data/round2/nifty_daily.parquet.")
    A("")
    A("=" * 78)
    A("HONEST ASSESSMENT")
    A("=" * 78)
    A("")
    A("  Is Jan-2018 -> Jul-2021 buildable as registered? NO — not as a CANSLIM test.")
    A("  The price side came out clean: Dhan serves 2015 onward, the series is")
    A("  genuinely back-adjusted (BPCL's 1:1 bonus moves -2.6%, its 1:2 moves +0.6%,")
    A("  RELIANCE's 1:1 moves -0.6%, where a raw series would show -50/-33/-50%), no")
    A("  >=25% cliff in six years matches a corp action, and the overlap with")
    A("  Round-1's habitat shows zero persistent steps. 173 symbols survive with no")
    A("  audit exclusions. If this were a price-only strategy it would be a GO.")
    A("")
    A("  The C-gate is what fails, and the damage is concentrated and measurable:")
    A("  the first five quarters of the window run at 9-15% eligibility. Kitna skew?")
    A("  15 of the window's 42 months are effectively BANK-ONLY — banks 88-94%")
    A("  eligible, everything else 0-3%, NBFCs and insurers at zero. A backtest run")
    A("  over Jan-2018 -> Jul-2021 as registered would spend its first 15 months")
    A("  trading a 17-name bank universe and its remaining 27 months trading 173")
    A("  names, and would report the average as one number. That is not a weaker")
    A("  CANSLIM test; it is two different strategies concatenated, with the regime")
    A("  break placed exactly where the data changes rather than where the market did.")
    A("")
    A("  THE SINGLE BIGGEST REMAINING RISK is that this skew is invisible in every")
    A("  aggregate M6c would naturally compute. Trade counts, win rates and")
    A("  expectancy all average across the boundary silently; nothing in a results")
    A("  table announces that 2018's trades could only have come from banks. The")
    A("  mitigation is structural, not statistical: either start the sealed window at")
    A("  2019-Q2 (73%+ coverage, but only ~2.25 years and dominated by the COVID")
    A("  crash and recovery), or keep Jan-2018 and pre-register that 2018-Q1..2019-Q1")
    A("  results are reported SEPARATELY and never pooled with the rest. Insurers")
    A("  should be dropped from the Round-2 universe outright — they are at 0% for")
    A("  every quarter of the window and can contribute nothing but noise.")
    A("")
    A("=" * 78)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n")
    print(f"REPORT: {REPORT}")


if __name__ == "__main__":
    main()
