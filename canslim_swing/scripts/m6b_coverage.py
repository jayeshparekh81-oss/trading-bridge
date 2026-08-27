#!/usr/bin/env python3
"""M6b step 4 — pre-registered coverage disclosure.

For each calendar quarter Jan-2018 -> Jul-2021: the % of the Round-2 universe
that is C-GATE-ELIGIBLE as of that date, i.e. has BOTH a usable latest-announced
quarter AND its year-ago pair in the symbol's chosen series. Any quarter under
60% is flagged SKEW PERIOD. Split by sector bucket so the sector-correlation
M6a warned about is visible rather than averaged away.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
R1_RAW = TRACK / "data" / "eps" / "raw"
STALE_DAYS = 200
SKEW_BAR = 60.0
INSURERS = {"HDFCLIFE", "ICICIGI", "ICICIPRULI", "SBILIFE", "LICI"}


def sector_bucket(sym: str) -> str:
    """bank / NBFC / insurer / other, from the XBRL taxonomy NSE itself used."""
    if sym in INSURERS:
        return "insurer"
    ig = R1_RAW / sym / "integrated.json"
    if ig.exists():
        names = " ".join((r.get("xbrl") or "") for r in (json.loads(ig.read_text()).get("rows") or []))
        if "INTEGRATED_FILING_BANKING" in names:
            return "bank"
        if "NBFC_INDAS" in names:
            return "NBFC"
        if "_LI_" in names:
            return "insurer"
    lp = R1_RAW / sym / "list.json"
    if lp.exists():
        inds = {(r.get("indAs") or "") for r in (json.loads(lp.read_text()).get("rows") or [])}
        if any("NBFC" in i for i in inds):
            return "NBFC"
    return "other"


def chosen_series(eps: pd.DataFrame, sym: str) -> str:
    s = eps[(eps["symbol"] == sym) & (~eps["is_revision"])]
    nc = s[(s["variant"] == "cons") & (s["eps_basic_cons"].notna()
                                       | s["eps_dil_cons"].notna())]["period_end"].nunique()
    ns = s[(s["variant"] == "stand") & (s["eps_basic_stand"].notna()
                                        | s["eps_dil_stand"].notna())]["period_end"].nunique()
    return "cons" if nc >= ns else "stand"


def main() -> None:
    eps = pd.read_parquet(R2 / "eps_quarterly.parquet")
    universe = sorted(p.stem for p in (R2 / "daily").glob("*.parquet"))
    vd = pd.read_parquet(R2 / "audit_verdicts.parquet")
    universe = [s for s in universe if s in set(vd[vd["verdict"] != "EXCLUDE"]["symbol"])]

    buckets = {s: sector_bucket(s) for s in universe}
    pd.Series(buckets).rename("bucket").to_frame().to_parquet(R2 / "sector_buckets.parquet")

    tables = {}
    for sym in universe:
        ser = chosen_series(eps, sym)
        bcol, dcol = (("eps_basic_cons", "eps_dil_cons") if ser == "cons"
                      else ("eps_basic_stand", "eps_dil_stand"))
        t = eps[(eps["symbol"] == sym) & (~eps["is_revision"]) & (eps["variant"] == ser)].copy()
        t = t[t["announce_ts"].notna()]
        t["eps"] = t[bcol].where(t[bcol].notna(), t[dcol])
        t = t[t["eps"].notna()].sort_values("announce_ts").drop_duplicates("period_end", keep="first")
        tables[sym] = (ser, t)

    # quarter-end reference dates Jan-2018 .. Jul-2021
    refs = pd.date_range("2018-03-31", "2021-06-30", freq="QE")
    rows = []
    for ref in refs:
        per_bucket = {}
        elig_syms = 0
        for sym in universe:
            ser, t = tables[sym]
            ok = False
            if not t.empty:
                known = t[t["announce_ts"] <= ref + pd.Timedelta(days=1)]
                if not known.empty:
                    latest_pe = known["period_end"].cummax().iloc[-1]
                    if (ref - latest_pe).days <= STALE_DAYS:
                        bpe = latest_pe - pd.DateOffset(years=1)
                        m = known[(known["period_end"].dt.year == bpe.year)
                                  & (known["period_end"].dt.month == bpe.month)]
                        cur = known[known["period_end"] == latest_pe]
                        ok = (not m.empty and not cur.empty
                              and pd.notna(m.iloc[0]["eps"]) and pd.notna(cur.iloc[0]["eps"]))
            elig_syms += ok
            b = buckets[sym]
            per_bucket.setdefault(b, [0, 0])
            per_bucket[b][0] += ok
            per_bucket[b][1] += 1
        pct = 100 * elig_syms / max(len(universe), 1)
        row = {"quarter": ref.strftime("%Y-Q%q").replace("Q1", "Q1") if False else
               f"{ref.year}-Q{(ref.month - 1) // 3 + 1}",
               "ref_date": str(ref.date()), "eligible": elig_syms,
               "universe": len(universe), "pct": round(pct, 1),
               "SKEW": "SKEW PERIOD" if pct < SKEW_BAR else ""}
        for b, (n, tot) in sorted(per_bucket.items()):
            row[f"{b}_pct"] = round(100 * n / max(tot, 1), 1)
            row[f"{b}_n"] = tot
        rows.append(row)
    cov = pd.DataFrame(rows)
    cov.to_parquet(R2 / "coverage.parquet")
    print(cov.to_string(index=False))
    print("\nsector buckets:", pd.Series(buckets).value_counts().to_dict())


if __name__ == "__main__":
    main()
