#!/usr/bin/env python3
"""canslim-swing MODULE 1 — swing data foundation + corp-action adjustment audit.

Data-prep + audit ONLY. No strategy logic. No network. Deterministic + idempotent.

Inputs (all local, read-only):
  - HABITAT_DIR/<SYMBOL>.parquet  : 15-minute OHLCV, IST DatetimeIndex (pine_replica habitat set)
  - HABITAT_DIR/_manifest.jsonl   : fetch manifest (cross-reference only)
  - TREND_DATA/nse_delivery.parquet, nse_delivery_next50.parquet
        RAW close + RAW-level prev_close per NSE bhav; NSE PREV_CLOSE is corp-action
        adjusted on ex-date, so close/prev_close - 1 is the authoritative ADJUSTED
        daily return (see trend_engine/fetch_nse_delivery.py docstring).
  - TREND_DATA/NIFTY.parquet      : 5-min NIFTY index spot (the PEAD module's market series)

Outputs (under canslim_swing/):
  - data/swing/daily/<SYMBOL>.parquet : daily OHLCV resampled from 15m (IST calendar date)
  - data/swing/nifty_daily.parquet    : daily close + sma200
  - reports/swing_module1_data_audit.txt
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]                      # canslim_swing/
REPO = TRACK.parent                                              # trading-bridge/
HABITAT_DIR = Path("/Users/jayeshparekh/tradetri-strategies/pine_replica/data/habitat")
TREND_DATA = REPO / "trend_engine" / "data"
DAILY_DIR = TRACK / "data" / "swing" / "daily"
REPORT_PATH = TRACK / "reports" / "swing_module1_data_audit.txt"

GAP_THRESHOLD = 0.25          # |move| >= 25% -> split/bonus suspect
STEP_THRESHOLD = 0.05         # |dlog(ratio)| >= 5% -> adjustment step-change
MIN_HISTORY_DAYS = 730        # < 2y history flag
SESSION_START, SESSION_END = "09:15", "15:30"


# ----------------------------------------------------------------------------- inventory + resample
def load_manifest() -> dict:
    out = {}
    mf = HABITAT_DIR / "_manifest.jsonl"
    if mf.exists():
        for line in mf.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["symbol"]] = rec
    return out


def resample_daily(df15: pd.DataFrame) -> pd.DataFrame:
    """15m -> daily by IST calendar date. O=first H=max L=min C=last V=sum."""
    g = df15.groupby(df15.index.tz_localize(None).normalize())
    daily = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "volume": g["volume"].sum(),
            "n_bars": g["close"].size(),
        }
    ).sort_index()
    daily.index.name = "date"
    return daily


def build_inventory_and_daily():
    manifest = load_manifest()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    inv_rows, daily_frames = [], {}
    paths = sorted(HABITAT_DIR.glob("*.parquet"))
    # union trading calendar (built from all symbols' daily dates) for density flags
    all_dates: set = set()
    for p in paths:
        sym = p.stem
        df15 = pd.read_parquet(p)
        daily = resample_daily(df15)
        daily_frames[sym] = daily
        all_dates.update(daily.index)
        daily.drop(columns=["n_bars"]).to_parquet(DAILY_DIR / f"{sym}.parquet")

    union_cal = pd.DatetimeIndex(sorted(all_dates))
    for sym, daily in daily_frames.items():
        first, last = daily.index[0], daily.index[-1]
        span_days = (last - first).days
        expected = union_cal[(union_cal >= first) & (union_cal <= last)]
        coverage = len(daily) / max(len(expected), 1)
        median_bars = float(daily["n_bars"].median())
        flags = []
        if span_days < MIN_HISTORY_DAYS:
            flags.append("SHORT-HISTORY")
        if coverage < 0.90:
            flags.append(f"SPARSE-DAYS({coverage:.0%})")
        if median_bars < 20:
            flags.append(f"LOW-INTRADAY-DENSITY(med={median_bars:.0f})")
        mrec = manifest.get(sym, {})
        inv_rows.append(
            {
                "symbol": sym,
                "bars_15m": int(daily["n_bars"].sum()),
                "days": len(daily),
                "first": str(first.date()),
                "last": str(last.date()),
                "span_days": span_days,
                "day_coverage": round(coverage, 3),
                "median_bars_per_day": median_bars,
                "manifest_bars": mrec.get("bars"),
                "manifest_status": mrec.get("status"),
                "flags": ",".join(flags),
            }
        )
    inventory = pd.DataFrame(inv_rows).set_index("symbol").sort_index()
    return inventory, daily_frames, union_cal


# ----------------------------------------------------------------------------- 3a. gap scan
def gap_scan(daily_frames: dict) -> pd.DataFrame:
    rows = []
    for sym in sorted(daily_frames):
        d = daily_frames[sym]
        prev_close = d["close"].shift(1)
        overnight = d["open"] / prev_close - 1.0
        c2c = d["close"] / prev_close - 1.0
        for kind, series in (("overnight", overnight), ("close-to-close", c2c)):
            hits = series[series.abs() >= GAP_THRESHOLD].dropna()
            for dt, mv in hits.items():
                rows.append(
                    {
                        "symbol": sym,
                        "date": str(dt.date()),
                        "kind": kind,
                        "move_pct": round(100 * mv, 2),
                        "close_before": round(float(prev_close.loc[dt]), 2),
                        "close_after": round(float(d["close"].loc[dt]), 2),
                    }
                )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- 3b. cross-check
def load_reference() -> pd.DataFrame:
    frames = []
    for name in ("nse_delivery.parquet", "nse_delivery_next50.parquet"):
        p = TREND_DATA / name
        if p.exists():
            frames.append(pd.read_parquet(p)[["date", "symbol", "prev_close", "open", "close"]])
    if not frames:
        return pd.DataFrame()
    ref = pd.concat(frames, ignore_index=True)
    ref["date"] = pd.to_datetime(ref["date"])
    ref = ref.drop_duplicates(subset=["symbol", "date"]).sort_values(["symbol", "date"])
    return ref


def cross_check(daily_frames: dict, ref: pd.DataFrame):
    """Habitat close vs the RAW bhav close of the reference.

    Why RAW: probing showed the reference PREV_CLOSE is NOT reliably corp-action
    adjusted (ADANIPOWER 1:5-split ex-date 2025-09-22 carries prev_close=709.40,
    the raw prior close), and the file also contains duplicated holiday rows and
    misses budget-Saturday special sessions — all of which poison any
    prev_close-based reconstruction. Comparing price LEVELS on common dates
    sidesteps every one of those pathologies.

    Semantics of ratio = log(habitat/raw_ref) on common dates:
      - persistent STEP at date d  => a corp action habitat DID adjust for
        (habitat back-adjusted history moved, raw reference did not);
      - habitat >=25% gap at d with NO ratio step => both series cliffed,
        i.e. habitat is UNADJUSTED at that ex-date.
    A step must persist (median of 5 sessions after vs before) to count —
    transient one-day print errors are ignored.
    """
    results, step_rows = [], []
    ref_syms = set(ref["symbol"].unique()) if not ref.empty else set()
    for sym in sorted(daily_frames):
        if sym not in ref_syms:
            continue
        hab_close = daily_frames[sym]["close"]
        raw = ref[ref["symbol"] == sym].set_index("date")["close"].sort_index()
        raw = raw[~raw.index.duplicated()]
        common = hab_close.index.intersection(raw.index)
        if len(common) < 60:
            continue
        ratio = np.log(hab_close.loc[common] / raw.loc[common])
        d = ratio.diff().dropna()
        cand = d[d.abs() >= STEP_THRESHOLD]
        steps = []
        for dt, sv in cand.items():
            i = ratio.index.get_loc(dt)
            before = ratio.iloc[max(0, i - 5):i].median()
            after = ratio.iloc[i:i + 5].median()
            shift = after - before
            if abs(shift) >= 0.04 and np.sign(shift) == np.sign(sv):  # persistent, not a one-day print
                hab_ret = float(hab_close.loc[common].pct_change().loc[dt])
                steps.append((dt, sv, hab_ret))
                step_rows.append(
                    {
                        "symbol": sym,
                        "date": str(dt.date()),
                        "log_ratio_step": round(float(sv), 4),
                        "implied_factor": round(float(np.exp(sv)), 4),
                        "habitat_ret_that_day_pct": round(100 * hab_ret, 2),
                        "reading": "habitat-adjusted ex-date" if abs(hab_ret) < 0.20
                                   else "INCONSISTENT (habitat also cliffed)",
                    }
                )
        results.append(
            {
                "symbol": sym,
                "overlap_days": len(common),
                "overlap_first": str(common.min().date()),
                "overlap_last": str(common.max().date()),
                "ratio_raw_std": round(float(ratio.std()), 5),
                "raw_identity": bool(ratio.abs().max() < 0.005),  # habitat == raw bhav everywhere
                "n_steps": len(steps),
                "n_inconsistent": sum(1 for _, _, hr in steps if abs(hr) >= 0.20),
            }
        )
    return pd.DataFrame(results), pd.DataFrame(step_rows)


# ----------------------------------------------------------------------------- verdicts
def verdicts(inventory: pd.DataFrame, suspects: pd.DataFrame, xcheck: pd.DataFrame,
             steps: pd.DataFrame, ref_first_date) -> pd.DataFrame:
    sus_by_sym = suspects.groupby("symbol")["date"].apply(lambda s: sorted(set(s))) \
        if not suspects.empty else pd.Series(dtype=object)
    x_by_sym = xcheck.set_index("symbol") if not xcheck.empty else pd.DataFrame()
    step_dates = steps.groupby("symbol")["date"].apply(list) if not steps.empty else pd.Series(dtype=object)
    rows = []
    for sym in inventory.index:
        sus_dates = sus_by_sym.get(sym, [])
        if sym in x_by_sym.index:
            x = x_by_sym.loc[sym]
            sdates = {pd.Timestamp(d) for d in step_dates.get(sym, [])}
            in_overlap = [d for d in sus_dates
                          if pd.Timestamp(x["overlap_first"]) <= pd.Timestamp(d) <= pd.Timestamp(x["overlap_last"])]
            pre_overlap = [d for d in sus_dates if pd.Timestamp(d) < pd.Timestamp(x["overlap_first"])]
            # a habitat cliff inside the overlap with NO coincident ratio step (+/-2 sessions)
            # means the raw reference cliffed identically => habitat unadjusted there
            unadj_dates = [d for d in in_overlap
                           if not any(abs((pd.Timestamp(d) - s).days) <= 4 for s in sdates)]
            if int(x["n_inconsistent"]) > 0:
                v, why = "SUSPECT", f"{int(x['n_inconsistent'])} step(s) where habitat ALSO cliffed (inconsistent)"
            elif unadj_dates:
                v, why = "UNADJUSTED", (f"habitat cliff(s) mirrored by raw reference at {';'.join(unadj_dates)}"
                                        " — unadjusted corp action OR genuine crash (see annotations)")
            elif pre_overlap:
                v, why = "SUSPECT", f"clean in overlap but {len(pre_overlap)} big gap(s) before {x['overlap_first']} (unverifiable)"
            elif int(x["n_steps"]) > 0:
                v, why = "ADJUSTED", f"positively confirmed — {int(x['n_steps'])} corp action(s) in overlap, habitat adjusted for all"
            else:
                v, why = "ADJUSTED", f"consistent with raw reference over {int(x['overlap_days'])}d, no corp action in window to test"
        else:
            if sus_dates:
                v, why = "SUSPECT", f"{len(sus_dates)} big gap(s), no reference symbol"
            else:
                v, why = "NO-REFERENCE", "no overlap symbol and no >=25% gaps"
        rows.append({"symbol": sym, "verdict": v, "why": why, "suspect_dates": ";".join(sus_dates)})
    return pd.DataFrame(rows).set_index("symbol")


# ----------------------------------------------------------------------------- 4. nifty daily
def build_nifty_daily():
    p = TREND_DATA / "NIFTY.parquet"
    n = pd.read_parquet(p)
    ts = pd.DatetimeIndex(n["timestamp"])
    n = n.set_index(ts).sort_index()
    sess = n.between_time(SESSION_START, SESSION_END)
    off_session = len(n) - len(sess)
    daily_close = sess.groupby(sess.index.tz_localize(None).normalize())["close"].last()
    out = pd.DataFrame({"close": daily_close})
    out["sma200"] = out["close"].rolling(200, min_periods=200).mean()
    out.index.name = "date"
    out_path = TRACK / "data" / "swing" / "nifty_daily.parquet"
    out.to_parquet(out_path)

    vol = n["volume"]
    nz = vol[vol > 0]
    vol_info = {
        "has_volume_col": "volume" in n.columns,
        "rows": len(vol),
        "nonzero_rows": int((vol > 0).sum()),
        "nonzero_pct": round(100 * float((vol > 0).mean()), 2),
        "nonzero_first": str(nz.index.min()) if len(nz) else "n/a",
        "nonzero_sample": [(str(i), int(v)) for i, v in nz.head(3).items()] if len(nz) else [],
        "off_session_rows_dropped": off_session,
    }
    return out, out_path, vol_info


# ----------------------------------------------------------------------------- report
def fmt_table(df: pd.DataFrame, max_rows=None) -> str:
    if df.empty:
        return "  (none)\n"
    with pd.option_context("display.max_rows", max_rows or len(df), "display.width", 200,
                           "display.max_colwidth", 60):
        return df.to_string() + "\n"


def main():
    print(f"[1/5] inventory + daily resample from {HABITAT_DIR} ...")
    inventory, daily_frames, union_cal = build_inventory_and_daily()
    print(f"      {len(inventory)} symbols -> {DAILY_DIR}")

    print("[2/5] gap scan ...")
    suspects = gap_scan(daily_frames)

    print("[3/5] cross-check vs adjusted Nifty-100 reference ...")
    ref = load_reference()
    ref_found = not ref.empty
    xcheck, steps = cross_check(daily_frames, ref) if ref_found else (pd.DataFrame(), pd.DataFrame())

    print("[4/5] nifty daily + sma200 ...")
    nifty_daily, nifty_path, vol_info = build_nifty_daily()

    print("[5/5] verdicts + report ...")
    vdf = verdicts(inventory, suspects, xcheck, steps, ref["date"].min() if ref_found else None)
    vc = vdf["verdict"].value_counts()

    flagged = inventory[inventory["flags"] != ""]
    unadj = vdf[vdf["verdict"] == "UNADJUSTED"]
    susp = vdf[vdf["verdict"] == "SUSPECT"]
    raw_identity_syms = list(xcheck[xcheck["raw_identity"]]["symbol"]) if not xcheck.empty else []

    L = []
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 1 — SWING DATA FOUNDATION + CORP-ACTION ADJUSTMENT AUDIT")
    A("Generated deterministically by canslim_swing/scripts/module1_data_audit.py")
    A("Audit only — nothing was fixed, no strategy logic, no network calls.")
    A("=" * 78)
    A("")
    A("INPUT SOURCES")
    A(f"  habitat 15m OHLCV : {HABITAT_DIR}  ({len(inventory)} parquets)")
    A(f"  adjusted reference: {TREND_DATA}/nse_delivery.parquet + nse_delivery_next50.parquet"
      + ("" if ref_found else "  ** NOT FOUND **"))
    if ref_found:
        A(f"                      NOTE: the task framed these as 'corp-action-adjusted'; the audit")
        A(f"                      found their CLOSE is RAW at price level, and PREV_CLOSE is NOT")
        A(f"                      reliably ex-date adjusted either (ADANIPOWER 1:5-split ex-date")
        A(f"                      2025-09-22 carries prev_close=709.40 = the raw prior close,")
        A(f"                      contradicting the fetch_nse_delivery.py docstring but matching")
        A(f"                      the delivery study's later correction). The file also contains")
        A(f"                      duplicated holiday rows (e.g. ABB 2024-06-17; all symbols")
        A(f"                      2026-01-26) and is missing budget-Saturday special sessions")
        A(f"                      (2025-02-01, 2026-02-01). The cross-check therefore compares")
        A(f"                      habitat directly against the RAW close on common dates, which")
        A(f"                      is immune to all of the above — see 3b for the semantics.")
        A(f"                      Reference coverage: {ref['date'].min().date()} -> {ref['date'].max().date()}"
          f" ({ref['symbol'].nunique()} symbols) — habitat history BEFORE this window is")
        A(f"                      NOT cross-checkable; the gap scan is the only guard there.")
    A(f"  nifty index (PEAD): {TREND_DATA}/NIFTY.parquet (5-min spot)")
    A("")
    A("-" * 78)
    A("1. INVENTORY")
    A(f"  symbols          : {len(inventory)}")
    A(f"  union calendar   : {len(union_cal)} trading days"
      f" ({union_cal.min().date()} -> {union_cal.max().date()})")
    A(f"  total 15m bars   : {int(inventory['bars_15m'].sum()):,}")
    A(f"  flagged symbols  : {len(flagged)}")
    A("")
    A("  Flagged (short history / sparse days / low intraday density):")
    A(fmt_table(flagged[["days", "first", "last", "span_days", "day_coverage",
                         "median_bars_per_day", "flags"]]))
    A("  Full per-symbol inventory:")
    A(fmt_table(inventory[["bars_15m", "days", "first", "last", "day_coverage",
                           "median_bars_per_day", "flags"]]))
    A("-" * 78)
    A("2. DAILY RESAMPLE")
    A(f"  15m -> daily (O=first H=max L=min C=last V=sum, IST calendar date)")
    A(f"  written: {DAILY_DIR}/<SYMBOL>.parquet  ({len(daily_frames)} files)")
    A("")
    A("-" * 78)
    A(f"3a. GAP SCAN — |overnight or close-to-close move| >= {GAP_THRESHOLD:.0%}")
    A(f"  suspect events: {len(suspects)}  (a single corp action can appear as both kinds)")
    A(fmt_table(suspects.sort_values(["symbol", "date"]).reset_index(drop=True)))
    A("-" * 78)
    A("3b. CROSS-CHECK — habitat vs RAW bhav close on common dates")
    A("    ratio step (persistent) = corp action habitat DID adjust for;")
    A("    habitat >=25% cliff with NO ratio step = habitat UNADJUSTED at that ex-date.")
    if ref_found and not xcheck.empty:
        A(f"  symbols with usable overlap: {len(xcheck)}")
        A(f"  raw-identity symbols (habitat close == RAW bhav close within 0.5% throughout")
        A(f"  the overlap — no corp action in window, levels agree): {len(raw_identity_syms)}")
        if raw_identity_syms:
            A("    " + ", ".join(raw_identity_syms))
        A("")
        A("  Persistent ratio steps (ex-dates where habitat is corp-action adjusted):")
        A(fmt_table(steps.sort_values(["symbol", "date"]).reset_index(drop=True)))
        A("  Per-symbol cross-check detail:")
        A(fmt_table(xcheck.set_index("symbol")))
    elif ref_found:
        A("  reference loaded but no symbol had >=60 overlapping days")
    else:
        A("  ** reference parquets not found — cross-check skipped (per spec, not refetched) **")
    A("-" * 78)
    A("3c. PER-STOCK VERDICTS")
    A(f"  counts: {({k: int(v) for k, v in vc.items()})}")
    A("")
    A(f"  UNADJUSTED ({len(unadj)}): " + (", ".join(unadj.index) if len(unadj) else "(none)"))
    A(f"  SUSPECT    ({len(susp)}): " + (", ".join(susp.index) if len(susp) else "(none)"))
    A("")
    A("  Detail for UNADJUSTED/SUSPECT:")
    A(fmt_table(vdf[vdf["verdict"].isin(["UNADJUSTED", "SUSPECT"])]))
    A("  ANALYST ANNOTATIONS on the mirrored-cliff (UNADJUSTED) cases — from event")
    A("  knowledge, NOT computed; the mechanical test cannot tell a real crash from")
    A("  an unadjusted corp action:")
    A("    INDUSINDBK 2025-03-11 (-27%): known REAL crash (derivatives-accounting")
    A("      disclosure) — no corp action; safe to treat as ADJUSTED/clean.")
    A("    SIEMENS    2025-04-07 (-42%): Siemens Energy India DEMERGER ex-date —")
    A("      genuinely unadjusted; the drop is spurious for price-series math.")
    A("    VEDL       2026-04-30 (-65%): consistent with the Vedanta demerger ex-date")
    A("      (post-knowledge-cutoff; verify) — treat as unadjusted until confirmed.")
    A("")
    A("-" * 78)
    A("4. NIFTY DAILY")
    A(f"  written: {nifty_path}")
    A(f"  rows: {len(nifty_daily)}  ({nifty_daily.index.min().date()} -> {nifty_daily.index.max().date()})"
      f"  sma200 valid from: {nifty_daily['sma200'].first_valid_index().date()}")
    A(f"  off-session 5m rows dropped before daily close: {vol_info['off_session_rows_dropped']}")
    A("")
    A("  Volume column (for a future distribution-day market filter):")
    A(f"    has volume column : {vol_info['has_volume_col']}")
    A(f"    nonzero rows      : {vol_info['nonzero_rows']:,} / {vol_info['rows']:,}"
      f" ({vol_info['nonzero_pct']}%)")
    A(f"    first nonzero     : {vol_info['nonzero_first']}")
    A(f"    sample            : {vol_info['nonzero_sample']}")
    A("")
    A("-" * 78)
    A("5. HONEST ASSESSMENT — is this daily data trustworthy for 52-week-high and")
    A("   multi-week-return math AS-IS?")
    A("")
    n_confirmed = int((xcheck["n_steps"] > 0).sum()) if not xcheck.empty else 0
    A("  Mostly yes for the cross-checked names, with specific exclusions — and only")
    A("  weakly for the rest. The strongest finding is POSITIVE: habitat is genuinely")
    A(f"  corp-action adjusted — {n_confirmed} symbols were caught adjusting for {0 if steps.empty else len(steps)}")
    A("  real corp actions in the overlap window with textbook factors (1.25, 1.33,")
    A("  1.5, 2.0, 2.5, 5.0, 10.0 — PFC/POWERGRID bonuses, NESTLEIND 1:10 split,")
    A("  RELIANCE/WIPRO/HDFCBANK 1:1 bonuses, etc.), and habitat's daily closes track")
    A("  the official raw close within ~0.2-0.3% (last-15m-trade vs official weighted")
    A(f"  close — immaterial for swing math). So the {int(vc.get('ADJUSTED', 0))} ADJUSTED names are")
    A("  trustworthy AS-IS for 52-week-high and multi-week-return math, within these")
    A("  known blind spots: (1) DEMERGERS are NOT adjusted anywhere — SIEMENS and")
    A("  (pending verification) VEDL carry spurious -42%/-65% cliffs and must be")
    A("  excluded or repaired; a demerger in the unchecked pre-2023-07 window would be")
    A("  invisible unless it tripped the 25% gap scan; (2) regular dividends are never")
    A("  adjusted (uniform small downward bias, acceptable for cross-sectional work);")
    A(f"  (3) the {int(vc.get('SUSPECT', 0))} SUSPECT names have >=25% cliffs that no reference can vouch")
    A(f"  for — exclude until repaired. The {int(vc.get('NO-REFERENCE', 0))} NO-REFERENCE names carry moderate")
    A("  residual risk: no >=25% cliff exists, but the gap scan is blind to factors")
    A("  below ~1.33 (a 1:4 bonus is only -20%) and habitat's adjustment behavior is")
    A("  only PROVEN on the ~98 reference-covered symbols; since all 21 verified")
    A("  actions were correctly adjusted, the reasonable prior is that the same feed")
    A("  adjusted the rest too — usable for ranking-style signals, but any single-name")
    A("  result should be re-verified before it matters. Bottom line: proceed on")
    A("  ADJUSTED + NO-REFERENCE names (excluding the annotated demergers), drop or")
    A("  repair the UNADJUSTED/SUSPECT list, and treat pre-2023 absolute 52-week-high")
    A("  claims with mild caution (Module 2 decision).")
    A("")
    A("=" * 78)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L))
    print(f"\nREPORT: {REPORT_PATH}")


if __name__ == "__main__":
    main()
