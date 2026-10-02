#!/usr/bin/env python3
"""canslim-swing MODULE 3 — daily scan engine (C-gate + Trend Template + base + market).

Plumbing + ONE frozen-default run. NO parameter tuning here (grids belong to M5).
No network. Deterministic + idempotent. Scan only — no entries/exits/portfolio.

Inputs (all local, read-only):
  canslim_swing/data/swing/daily/<SYM>.parquet   (M1)
  canslim_swing/data/eps/eps_quarterly.parquet   (M2b)
  canslim_swing/data/swing/nifty_daily.parquet   (M1)
  canslim_swing/reports/swing_module1_data_audit.txt  (M1 verdicts -> universe freeze)

Outputs:
  canslim_swing/config/universe_frozen.txt
  canslim_swing/config/eps_series_choice.csv
  canslim_swing/data/scan/daily_scan.parquet
  canslim_swing/reports/swing_module3_scan.txt
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
DAILY_DIR = TRACK / "data" / "swing" / "daily"
EPS_PARQUET = TRACK / "data" / "eps" / "eps_quarterly.parquet"
NIFTY_PARQUET = TRACK / "data" / "swing" / "nifty_daily.parquet"
M1_REPORT = TRACK / "reports" / "swing_module1_data_audit.txt"
CONFIG = TRACK / "config"
SCAN_PARQUET = TRACK / "data" / "scan" / "daily_scan.parquet"
REPORT_PATH = TRACK / "reports" / "swing_module3_scan.txt"

# ---------------------------------------------------------------- FROZEN CONSTANTS
C_GROWTH = 1.25          # latest EPS >= 1.25 x year-ago  (25%)
RS_MIN_PCT = 80.0        # T8 threshold
T6_ABOVE_LOW = 1.30      # close >= 1.30 x 52w low
T7_BELOW_HIGH = 0.75     # close >= 0.75 x 52w high
BASE_W = 35              # base window, sessions
BASE_MAX_TIGHT = 0.25    # tightness <= 25%
STALE_DAYS = 200         # latest filing older than this -> C fails
RS_LOOKBACK = 126        # sessions (~6 months)
MIN_HISTORY = 252        # sessions needed before ANY row is emitted
SMA200_SLOPE_LAG = 21    # T3 comparison lag, sessions
TURNOVER_W = 20

# M1 annotation: INDUSINDBK's 2025-03-11 cliff was a REAL crash (derivatives
# disclosure), not an unadjusted corp action — its price series is clean, so it
# is kept despite the mechanical UNADJUSTED verdict. SIEMENS/VEDL are genuine
# unadjusted demergers and are dropped.
KEEP_DESPITE_UNADJUSTED = {"INDUSINDBK"}


# ---------------------------------------------------------------- universe freeze
def parse_m1_verdicts() -> dict:
    txt = M1_REPORT.read_text()
    out = {}
    for key in ("UNADJUSTED", "SUSPECT"):
        m = re.search(rf"^  {key}\s*\(\d+\):\s*(.+)$", txt, re.M)
        out[key] = [s.strip() for s in m.group(1).split(",")] if m else []
    return out


def freeze_universe() -> tuple[list[str], dict]:
    all_syms = sorted(p.stem for p in DAILY_DIR.glob("*.parquet"))
    v = parse_m1_verdicts()
    dropped_unadj = [s for s in v["UNADJUSTED"] if s not in KEEP_DESPITE_UNADJUSTED]
    dropped_susp = list(v["SUSPECT"])
    drop = set(dropped_unadj) | set(dropped_susp)
    universe = [s for s in all_syms if s not in drop]
    CONFIG.mkdir(parents=True, exist_ok=True)
    (CONFIG / "universe_frozen.txt").write_text("\n".join(universe) + "\n")
    return universe, {"all": len(all_syms), "unadj_dropped": dropped_unadj,
                      "suspect_dropped": dropped_susp,
                      "kept_despite": sorted(KEEP_DESPITE_UNADJUSTED & set(v["UNADJUSTED"]))}


# ---------------------------------------------------------------- EPS / C-gate
def choose_series(eps: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    """One series per symbol for its WHOLE timeline (M2b caveat 2: mixing
    consolidated and standalone mid-history manufactures fake EPS jumps).
    More canonical quarters wins; tie -> consolidated."""
    canon = eps[~eps["is_revision"]]
    rows = []
    for sym in universe:
        s = canon[canon["symbol"] == sym]
        n_c = s[(s["variant"] == "cons")
                & (s["eps_basic_cons"].notna() | s["eps_dil_cons"].notna())]["period_end"].nunique()
        n_s = s[(s["variant"] == "stand")
                & (s["eps_basic_stand"].notna() | s["eps_dil_stand"].notna())]["period_end"].nunique()
        rows.append({"symbol": sym, "n_cons": n_c, "n_stand": n_s,
                     "series": "cons" if n_c >= n_s else "stand"})
    df = pd.DataFrame(rows).set_index("symbol")
    df.to_csv(CONFIG / "eps_series_choice.csv")
    return df


def symbol_eps_table(eps_sym: pd.DataFrame, series: str) -> pd.DataFrame:
    """Canonical filings of the chosen series: period_end, announce_ts, eps, field tag.

    basic preferred; diluted used when basic is absent (insurers file ONE combined
    fact that M2b writes into both, so they must not silently drop here)."""
    bcol, dcol = (("eps_basic_cons", "eps_dil_cons") if series == "cons"
                  else ("eps_basic_stand", "eps_dil_stand"))
    s = eps_sym[(~eps_sym["is_revision"]) & (eps_sym["variant"] == series)].copy()
    s = s[s["announce_ts"].notna()]
    basic, dil = s[bcol], s[dcol]
    s["eps"] = basic.where(basic.notna(), dil)
    s["field"] = np.where(basic.notna(), "basic", np.where(dil.notna(), "diluted", "none"))
    s = s[s["eps"].notna()]
    # one canonical row per period_end: the FIRST announced
    s = s.sort_values("announce_ts").drop_duplicates("period_end", keep="first")
    return s[["period_end", "announce_ts", "eps", "field"]].sort_values("announce_ts")


def c_gate_for_days(tbl: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Point-in-time C-gate per day. Fail-closed everywhere.

    'Latest quarter' on day D = max period_end among filings ANNOUNCED by end of D.
    Using a cumulative max (not the last announcement) is load-bearing: a late
    filing can disclose an OLD quarter (M2b found HDFCBANK's consolidated Mar-2021
    broadcast 391 days late), and that must not roll the known quarter backwards.
    """
    n = len(days)
    empty = pd.DataFrame({"c_pass": np.zeros(n, bool), "eps_growth": np.full(n, np.nan),
                          "eps_field_tag": np.array([""] * n, object),
                          "c_fail_reason": np.array(["no-eps-data"] * n, object)},
                         index=days)
    if tbl.empty:
        return empty
    ann = tbl["announce_ts"].to_numpy("datetime64[ns]")
    pe = tbl["period_end"].to_numpy("datetime64[ns]")
    known_pe = np.maximum.accumulate(pe)                      # max period_end known so far
    eod = (days + pd.Timedelta(days=1)).to_numpy("datetime64[ns]")   # end of day D (IST dates)
    idx = np.searchsorted(ann, eod, side="left") - 1          # last filing announced by D
    eps_by_pe = dict(zip(tbl["period_end"], tbl["eps"]))
    field_by_pe = dict(zip(tbl["period_end"], tbl["field"]))
    growth = np.full(n, np.nan)
    passed = np.zeros(n, bool)
    field = np.array([""] * n, object)
    reason = np.array(["no-filing-yet"] * n, object)
    for i in range(n):
        j = idx[i]
        if j < 0:
            continue
        latest_pe = pd.Timestamp(known_pe[j])
        # staleness: a company that stopped filing must not pass on ancient numbers
        if (days[i] - latest_pe).days > STALE_DAYS:
            reason[i] = "stale"
            continue
        base_pe = latest_pe - pd.DateOffset(years=1)
        # match the same quarter one year earlier by (year, month) — quarter ends
        # are month-ends, so day-of-month drift must not break the match
        base_key = next((p for p in eps_by_pe
                         if p.year == base_pe.year and p.month == base_pe.month), None)
        if base_key is None:
            reason[i] = "no-year-ago"
            continue
        cur, base = eps_by_pe[latest_pe], eps_by_pe[base_key]
        field[i] = field_by_pe[latest_pe]
        if base <= 0:
            reason[i] = "base-eps<=0"
            continue
        g = cur / base - 1.0
        growth[i] = g
        if cur >= C_GROWTH * base:
            passed[i] = True
            reason[i] = "pass"
        else:
            reason[i] = "growth-short"
    return pd.DataFrame({"c_pass": passed, "eps_growth": growth,
                         "eps_field_tag": field, "c_fail_reason": reason}, index=days)


# ---------------------------------------------------------------- price features
def price_features(d: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    f = pd.DataFrame(index=d.index)
    f["close"] = c
    f["sma50"] = c.rolling(50).mean()
    f["sma150"] = c.rolling(150).mean()
    f["sma200"] = c.rolling(200).mean()
    f["sma200_lag"] = f["sma200"].shift(SMA200_SLOPE_LAG)
    f["high252"] = h.rolling(MIN_HISTORY).max()
    f["low252"] = l.rolling(MIN_HISTORY).min()
    f["ret126"] = c / c.shift(RS_LOOKBACK) - 1.0
    f["pivot"] = h.rolling(BASE_W).max()
    f["base_low"] = l.rolling(BASE_W).min()
    f["base_tightness"] = (f["pivot"] - f["base_low"]) / f["base_low"]
    f["sessions_in_base"] = BASE_W
    f["median_turnover_20d"] = (c * v).rolling(TURNOVER_W).median()
    f["t1"] = (c > f["sma150"]) & (c > f["sma200"])
    f["t2"] = f["sma150"] > f["sma200"]
    f["t3"] = f["sma200"] > f["sma200_lag"]
    f["t4"] = (f["sma50"] > f["sma150"]) & (f["sma150"] > f["sma200"])
    f["t5"] = c > f["sma50"]
    f["t6"] = c >= T6_ABOVE_LOW * f["low252"]
    f["t7"] = c >= T7_BELOW_HIGH * f["high252"]
    f["dist_52wh"] = c / f["high252"] - 1.0
    f["dist_52wl"] = c / f["low252"] - 1.0
    f["base_pass"] = f["base_tightness"] <= BASE_MAX_TIGHT
    return f


def main() -> None:
    universe, freeze_info = freeze_universe()
    print(f"[1/5] universe frozen: {len(universe)} symbols")

    eps = pd.read_parquet(EPS_PARQUET)
    series_df = choose_series(eps, universe)
    print(f"[2/5] eps series chosen: {series_df['series'].value_counts().to_dict()}")

    nifty = pd.read_parquet(NIFTY_PARQUET)
    nifty_on = (nifty["close"] > nifty["sma200"]).rename("nifty_on")

    feats: dict[str, pd.DataFrame] = {}
    ret126: dict[str, pd.Series] = {}
    print("[3/5] price features ...")
    for sym in universe:
        d = pd.read_parquet(DAILY_DIR / f"{sym}.parquet")
        f = price_features(d)
        feats[sym] = f
        ret126[sym] = f["ret126"]

    # cross-sectional RS percentile: rank each day among universe symbols that have
    # a valid 126-session lookback that day (missing symbols simply don't rank)
    rs_wide = pd.DataFrame(ret126)
    rs_pct = rs_wide.rank(axis=1, pct=True, na_option="keep") * 100.0

    print("[4/5] C-gate + assembly ...")
    frames = []
    eps_by_sym = {s: g for s, g in eps[eps["symbol"].isin(universe)].groupby("symbol")}
    for sym in universe:
        f = feats[sym]
        if len(f) < MIN_HISTORY:
            continue
        days = f.index[MIN_HISTORY - 1:]
        tbl = symbol_eps_table(eps_by_sym.get(sym, eps.iloc[:0]), series_df.loc[sym, "series"])
        cg = c_gate_for_days(tbl, days)
        part = f.loc[days, ["close", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
                            "dist_52wh", "dist_52wl", "pivot", "base_tightness",
                            "sessions_in_base", "base_pass", "median_turnover_20d"]].copy()
        part.insert(0, "symbol", sym)
        part["rs_pct"] = rs_pct[sym].reindex(days)
        part["t8"] = part["rs_pct"] >= RS_MIN_PCT
        part["series_used"] = series_df.loc[sym, "series"]
        for col in ("c_pass", "eps_growth", "eps_field_tag", "c_fail_reason"):
            part[col] = cg[col]
        # Muhurat/special sessions exist in stock data but are missing from the
        # Nifty 5-min source, so nifty_on is UNKNOWN there. Treat unknown as OFF
        # (fail-closed) but flag it, or the zero-candidate day looks like a real
        # market-filter rejection instead of missing reference data.
        aligned = nifty_on.reindex(days)
        part["nifty_data_missing"] = aligned.isna().to_numpy()
        part["nifty_on"] = aligned.fillna(False).astype(bool).to_numpy()
        frames.append(part.reset_index().rename(columns={"date": "date", "index": "date"}))

    scan = pd.concat(frames, ignore_index=True)
    for c in ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "base_pass", "c_pass", "nifty_on"):
        scan[c] = scan[c].fillna(False).astype(bool)
    scan["all_t"] = scan[["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"]].all(axis=1)
    scan["candidate"] = scan["all_t"] & scan["c_pass"] & scan["base_pass"] & scan["nifty_on"]
    scan = scan.sort_values(["date", "symbol"]).reset_index(drop=True)
    SCAN_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    scan.to_parquet(SCAN_PARQUET)
    print(f"      scan rows: {len(scan):,} -> {SCAN_PARQUET}")

    print("[5/5] report ...")
    write_report(scan, universe, freeze_info, series_df, nifty_on)
    print(f"\nREPORT: {REPORT_PATH}")


def write_report(scan, universe, freeze_info, series_df, nifty_on) -> None:
    g = scan.groupby("date")
    daily = pd.DataFrame({
        "have_price": g.size(),
        "all_t": g["all_t"].sum(),
        "t_and_c": (scan["all_t"] & scan["c_pass"]).groupby(scan["date"]).sum(),
        "t_c_base": (scan["all_t"] & scan["c_pass"] & scan["base_pass"]).groupby(scan["date"]).sum(),
        "candidates": g["candidate"].sum(),
        "nifty_on": g["nifty_on"].max(),
    })
    n_days = len(daily)
    L, A = [], None
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 3 — DAILY SCAN ENGINE (frozen defaults, no tuning)")
    A(f"scan parquet: {SCAN_PARQUET}")
    A("=" * 78)
    A("")
    A("0. UNIVERSE FREEZE")
    A(f"  habitat symbols            : {freeze_info['all']}")
    A(f"  dropped — UNADJUSTED       : {len(freeze_info['unadj_dropped'])}"
      f"  ({', '.join(freeze_info['unadj_dropped'])})")
    A(f"  dropped — SUSPECT          : {len(freeze_info['suspect_dropped'])}")
    A(f"    {', '.join(freeze_info['suspect_dropped'])}")
    A(f"  kept despite UNADJUSTED    : {', '.join(freeze_info['kept_despite'])}"
      f"  (M1: real crash, price series clean)")
    A(f"  FROZEN UNIVERSE            : {len(universe)}  -> {CONFIG / 'universe_frozen.txt'}")
    A("")
    A("1. EPS SERIES CHOICE (one per symbol, fixed for the whole timeline)")
    vc = series_df["series"].value_counts().to_dict()
    A(f"  consolidated: {vc.get('cons', 0)}   standalone: {vc.get('stand', 0)}"
      f"   -> {CONFIG / 'eps_series_choice.csv'}")
    tags = scan["eps_field_tag"].value_counts().to_dict()
    A(f"  scan rows by EPS field used: {tags}")
    A(f"  symbols whose chosen series has ZERO usable quarters: "
      f"{int(((series_df['n_cons'] == 0) & (series_df['n_stand'] == 0)).sum())}")
    A("")
    A("  C-gate outcome mix across all scan rows (fail-closed reasons):")
    for k, v in scan["c_fail_reason"].value_counts().items():
        A(f"    {k:<16}{v:>9,}  ({100 * v / len(scan):5.1f}%)")
    A("")
    A("-" * 78)
    A("2. GATE ATTRITION FUNNEL (average symbols per trading day)")
    A(f"  trading days covered: {n_days}  "
      f"({daily.index.min():%d-%b-%Y} -> {daily.index.max():%d-%b-%Y})")
    A("")
    A(f"    {'stage':<34}{'avg/day':>10}{'% of universe':>15}")
    u = len(universe)
    for label, col in (("universe (frozen)", None),
                       ("valid price history (>=252 sess)", "have_price"),
                       ("pass all T1-T8", "all_t"),
                       ("  + C-gate", "t_and_c"),
                       ("  + base", "t_c_base"),
                       ("  + nifty_on  = CANDIDATES", "candidates")):
        val = u if col is None else daily[col].mean()
        A(f"    {label:<34}{val:>10.1f}{100 * val / u:>14.1f}%")
    A("")
    A("  Same funnel restricted to NIFTY-ON days (market filter not binding):")
    on = daily[daily["nifty_on"]]
    A(f"    nifty_on days: {len(on)}/{n_days} ({100 * len(on) / max(n_days, 1):.0f}%)"
      f"   avg candidates on those days: {on['candidates'].mean():.1f}")
    off = daily[~daily["nifty_on"]]
    A(f"    nifty_off days: {len(off)}   avg pre-market-filter (T+C+base) on those days:"
      f" {off['t_c_base'].mean():.1f}  -> candidates forced to 0")
    miss = scan[scan["nifty_data_missing"]]
    A("")
    A("  Days with stock data but NO Nifty reference row (Muhurat/special sessions —")
    A("  the Nifty 5-min source omits them). nifty_on is UNKNOWN, treated as OFF:")
    if len(miss):
        for d, sub in miss.groupby("date"):
            A(f"    {d:%d-%b-%Y}: {len(sub)} symbols, "
              f"{int((sub['all_t'] & sub['c_pass'] & sub['base_pass']).sum())} passing T+C+base"
              f" -> forced to 0 candidates")
    else:
        A("    (none)")
    A("")
    A("-" * 78)
    A("3. MONTHLY CANDIDATE COUNTS (per-day min / median / max within each month)")
    m = daily["candidates"].groupby(pd.Grouper(freq="ME"))
    mm = pd.DataFrame({"days": m.size(), "min": m.min(), "median": m.median(),
                       "max": m.max(), "mean": m.mean().round(1),
                       "nifty_on_days": daily["nifty_on"].groupby(pd.Grouper(freq="ME")).sum()})
    mm.index = mm.index.strftime("%Y-%m")
    A(fmt_table(mm))
    A("-" * 78)
    A("4. TOP-15 MOST FREQUENT CANDIDATE SYMBOLS (sanity eyeball)")
    top = scan[scan["candidate"]].groupby("symbol").agg(
        days_as_candidate=("candidate", "size"),
        median_eps_growth=("eps_growth", "median"),
        median_rs=("rs_pct", "median")).sort_values("days_as_candidate", ascending=False).head(15)
    top["median_eps_growth"] = (100 * top["median_eps_growth"]).round(1)
    top["median_rs"] = top["median_rs"].round(1)
    A(fmt_table(top))
    A(f"  distinct symbols ever a candidate: {scan[scan['candidate']]['symbol'].nunique()}"
      f" / {len(universe)}")
    A("-" * 78)
    A("5. FROZEN CONSTANTS (echoed; tuning belongs to M5)")
    A(f"  C growth      : {C_GROWTH:.2f}x  (+{100 * (C_GROWTH - 1):.0f}% YoY quarterly EPS)")
    A(f"  RS percentile : >= {RS_MIN_PCT:.0f}   (metric: {RS_LOOKBACK}-session return, cross-sectional)")
    A(f"  T6 above low  : >= {T6_ABOVE_LOW:.2f}x 52w low")
    A(f"  T7 below high : >= {T7_BELOW_HIGH:.2f}x 52w high")
    A(f"  base window W : {BASE_W} sessions      tightness <= {100 * BASE_MAX_TIGHT:.0f}%")
    A(f"  staleness     : latest filing older than {STALE_DAYS} calendar days -> C fails")
    A(f"  min history   : {MIN_HISTORY} sessions before any row is emitted")
    A("")
    A("-" * 78)
    A("HONEST ASSESSMENT — does the funnel breathe?")
    A("")
    cand_mean = daily["candidates"].mean()
    on_mean = on["candidates"].mean() if len(on) else 0.0
    zero_days = int((daily["candidates"] == 0).sum())
    on_zero = int((on["candidates"] == 0).sum()) if len(on) else 0
    regime = "a STREAM" if 2 <= on_mean <= 10 else ("a TRICKLE" if on_mean < 2 else "a FLOOD")
    A(f"  Across all {n_days} trading days the scan averages {cand_mean:.1f} candidates/day;")
    A(f"  on the {len(on)} nifty_on days it averages {on_mean:.1f}/day — {regime} by the")
    A("  trickle/stream/flood test. The count is HARD regime-dependent by construction:")
    A(f"  nifty_on is an AND term, so all {len(off)} nifty_off days are exactly zero")
    A(f"  candidates regardless of stock-level quality — and those days still carried")
    A(f"  {off['t_c_base'].mean():.1f} symbols passing T+C+base on average, so the market filter alone")
    A("  is discarding real setups. Whether that is protection or over-filtering is an")
    A("  M4/M5 question, not one this module can answer.")
    A(f"  Even on nifty_on days, {on_zero} ({100 * on_zero / max(len(on), 1):.0f}%) produce zero candidates,")
    A(f"  and {zero_days} of {n_days} days overall are empty. The binding constraint is visible in")
    A("  the funnel above: the trend template is the coarse filter, and the C-gate then")
    A("  removes most of what survives it. That ordering is expected for CANSLIM, but it")
    A("  means candidate counts are sensitive to the 25% growth threshold — a parameter")
    A("  M5 must sweep before anyone reads significance into the trade count.")
    A("")
    cand = scan[scan["candidate"]]
    big = cand[cand["eps_growth"] > 5.0]
    A("  ONE THING TO FLAG FOR M5 (observed, not fixed here — the spec is frozen):")
    A(f"  the C-gate requires base EPS > 0 but nothing about base MAGNITUDE, so growth")
    A(f"  off a near-zero base passes easily. {len(big):,} of {len(cand):,} candidate-days"
      f" ({100 * len(big) / max(len(cand), 1):.1f}%)")
    A("  show >500% YoY growth; the median candidate-day is +{:.0f}% and the 99th is +{:.0f}%."
      .format(100 * cand["eps_growth"].median(), 100 * cand["eps_growth"].quantile(0.99)))
    A("  LAURUSLABS is the clearest case — its quarterly EPS oscillates between roughly")
    A("  Rs 0.23 and Rs 1.90, so a one-rupee swing off a depressed base reads as several")
    A("  hundred percent. That is arithmetic, not earnings acceleration. A minimum")
    A("  absolute base-EPS floor is worth adding to the M5 sweep alongside the growth")
    A("  threshold; without it the C-gate systematically favours recovering-from-bad-")
    A("  quarter names over steady compounders.")
    A("")
    A("  Caveats inherited and honoured here (from M2b): the C-gate FAILS CLOSED on")
    A("  every missing quarter (no interpolation, no carry-forward); each symbol uses")
    A("  ONE EPS series for its whole timeline; and the as-of rule keys on announce_ts,")
    A("  never on period_end, so late filings (HDFCBANK's 391-day-late Mar-2021")
    A("  consolidated result) cannot leak future information into a scan day.")
    A("")
    A("=" * 78)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L) + "\n")


def fmt_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "  (none)\n"
    with pd.option_context("display.max_rows", len(df), "display.width", 200):
        return df.to_string() + "\n"


if __name__ == "__main__":
    main()
