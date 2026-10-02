#!/usr/bin/env python3
"""M6b step 3 — EPS extension to 2016-Q2 .. 2021-Q2, reusing M2b's chains.

Round-1's cache is treated as IMMUTABLE: new detail/xbrl files land in
data/round2/eps_raw/ so nothing already audited is mutated. The M2b filing LISTS
(which already reach back to 2005) are read from the Round-1 cache, not re-fetched.

Per (symbol, quarter, variant) the outcome is recorded as:
  usable            - an EPS value was extracted (detail API or XBRL fallback)
  empty-no-fallback - detail payload empty AND the list row's xbrl link is a stub
  stub              - no xbrl link at all and no detail data
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m6a_probe_eps as P  # noqa: E402

TRACK = Path(__file__).resolve().parents[1]
R1_RAW = TRACK / "data" / "eps" / "raw"
R2 = TRACK / "data" / "round2"
R2_RAW = R2 / "eps_raw"
FIRST = datetime(2016, 4, 1)
LAST = datetime(2021, 7, 31)
NSE = "https://www.nseindia.com"

EPS_B = ("re_basic_eps_for_cont_dic_opr", "re_basic_eps", "re_bsc_eps_bfr_exi")
EPS_D = ("re_dilut_eps_for_cont_dic_opr", "re_diluted_eps", "re_dil_eps_bfr_exi")


def xbrl_quarter_eps(text: str, qe: datetime) -> dict:
    """M2b's taxonomy-aware extraction (INDAS / NBFC / BANKING / LI) + the
    same-file sibling-context inference for NSE's structurally invalid files."""
    ctx = {}
    import re
    for m in re.finditer(r'<(?:[\w-]+:)?context id="([^"]+)">(.*?)</(?:[\w-]+:)?context>', text, re.S):
        b = m.group(2)
        sd = re.search(r'<(?:[\w-]+:)?startDate>([\d-]+)<', b)
        ed = re.search(r'<(?:[\w-]+:)?endDate>([\d-]+)<', b)
        if sd and ed:
            ctx[m.group(1)] = (sd.group(1), ed.group(1))

    def resolve(cid):
        if cid in ctx:
            return ctx[cid]
        pre = re.match(r'^([A-Z][a-z]+)', cid)
        if not pre:
            return None
        sib = {v for k, v in ctx.items() if k.startswith(pre.group(1))}
        return next(iter(sib)) if len(sib) == 1 else None

    out = {}
    for kind in ("Basic", "Diluted"):
        pats = [
            rf'<in-capmkt:{kind}EarningsLossPerShareFromContinuingAndDiscontinuedOperations[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<in-capmkt:{kind}EarningsLossPerShareFromContinuingOperations[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}EarningsPerShareAfterExtraordinaryItems[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}EarningsPerShareBeforeExtraordinaryItems[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}Earnings(?:Loss)?PerShare[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            r'<(?:[\w-]+:)?BasicAndDilutedEPSAfterExtraordinaryItems[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            r'<(?:[\w-]+:)?BasicAndDilutedEPSBeforeExtraordinaryItems[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
        ]
        facts = []
        for p in pats:
            facts = re.findall(p, text)
            if facts:
                break
        val = None
        for c, v in facts:
            per = resolve(c)
            if not per:
                continue
            try:
                sd, ed = datetime.fromisoformat(per[0]), datetime.fromisoformat(per[1])
            except ValueError:
                continue
            if abs((ed - qe).days) <= 6 and 60 <= (ed - sd).days <= 130:
                val = v
                break
        out[kind.lower()] = val
    return out


def main() -> None:
    R2_RAW.mkdir(parents=True, exist_ok=True)
    universe = sorted(p.stem for p in (R2 / "daily").glob("*.parquet"))
    s = requests.Session()
    P.warm(s)
    q = requests.utils.quote
    status_rows, eps_rows = [], []
    n_req = 0
    streak = 0
    for si, sym in enumerate(universe, 1):
        lp = R1_RAW / sym / "list.json"
        if not lp.exists():
            status_rows.append({"symbol": sym, "quarter": None, "variant": None,
                                "status": "no-list-cache"})
            continue
        rows = json.loads(lp.read_text()).get("rows") or []
        want = []
        for x in rows:
            d = P.pdate(x.get("toDate"))
            if d and FIRST <= d <= LAST and x.get("period") == "Quarterly":
                want.append((d, x))
        parked_here = False
        for d, x in want:
            seq = str(x["seqNumber"])
            variant = "cons" if x.get("consolidated") == "Consolidated" else "stand"
            outp = R2_RAW / sym / f"detail_{seq}.json"
            if outp.exists():
                rec = json.loads(outp.read_text())
            else:
                url = (f"{NSE}/api/corporates-financial-results-data?index=equities"
                       f"&params={q(x['params'], safe='')}&seq_id={seq}"
                       f"&industry={q(x.get('industry') or '-', safe='')}"
                       f"&ind={q(x.get('indAs') or '', safe='')}&format={x.get('format') or ''}")
                r = P.get(s, url)
                n_req += 1
                j = {}
                if r is not None and r.text.strip().startswith("{"):
                    try:
                        j = r.json()
                    except ValueError:
                        j = {}
                rd = j.get("resultsData2") or j.get("resultsData") or {}
                eps = {k: rd.get(k) for k in set(EPS_B) | set(EPS_D)} if isinstance(rd, dict) else {}
                basic = next((P.fnum(eps.get(k)) for k in EPS_B
                              if P.fnum(eps.get(k)) is not None), None)
                dil = next((P.fnum(eps.get(k)) for k in EPS_D
                            if P.fnum(eps.get(k)) is not None), None)
                xb = (x.get("xbrl") or "")
                fb = None
                if basic is None and dil is None and xb and not xb.endswith("/-"):
                    rx = P.get(s, xb)
                    n_req += 1
                    if rx is not None:
                        fb = xbrl_quarter_eps(rx.text, d)
                        basic = P.fnum(fb.get("basic"))
                        dil = P.fnum(fb.get("diluted"))
                rec = {"seq": seq, "toDate": x.get("toDate"), "variant": variant,
                       "basic": basic, "diluted": dil,
                       "broadCastDate": x.get("broadCastDate"),
                       "filingDate": x.get("filingDate"), "reInd": x.get("reInd"),
                       "audited": x.get("audited"), "format": x.get("format"),
                       "xbrl_stub": bool(not xb or xb.endswith("/-")),
                       "used_xbrl": fb is not None}
                if r is None:
                    parked_here = True
                outp.parent.mkdir(parents=True, exist_ok=True)
                tmp = outp.with_suffix(".tmp")
                tmp.write_text(json.dumps(rec))
                os.replace(tmp, outp)
            st = ("usable" if (rec["basic"] is not None or rec["diluted"] is not None)
                  else ("stub" if rec["xbrl_stub"] else "empty-no-fallback"))
            status_rows.append({"symbol": sym, "quarter": str(d.date()),
                                "variant": rec["variant"], "status": st,
                                "format": rec.get("format")})
            if st == "usable":
                ts = P.pdate(rec.get("broadCastDate")) or P.pdate(rec.get("filingDate"))
                eps_rows.append({"symbol": sym, "period_end": pd.Timestamp(d),
                                 "announce_ts": pd.Timestamp(ts) if ts else pd.NaT,
                                 "eps_basic_cons": rec["basic"] if rec["variant"] == "cons" else np.nan,
                                 "eps_dil_cons": rec["diluted"] if rec["variant"] == "cons" else np.nan,
                                 "eps_basic_stand": rec["basic"] if rec["variant"] == "stand" else np.nan,
                                 "eps_dil_stand": rec["diluted"] if rec["variant"] == "stand" else np.nan,
                                 "source_regime": "old", "is_revision": rec.get("reInd") == "I",
                                 "revised_ts": pd.NaT, "variant": rec["variant"],
                                 "audited": rec.get("audited")})
        streak = streak + 1 if parked_here else 0
        if streak >= 2:
            print(f"  ! throttle signature — pausing 300s", flush=True)
            time.sleep(300)
            s = requests.Session()
            P.warm(s)
            streak = 0
        if si % 10 == 0:
            print(f"[{si}/{len(universe)}] {sym} req={n_req:,}", flush=True)
            pd.DataFrame(status_rows).to_parquet(R2 / "eps_status.parquet")

    st = pd.DataFrame(status_rows)
    st.to_parquet(R2 / "eps_status.parquet")
    new = pd.DataFrame(eps_rows)
    # merge with Round-1 rows (first-filed wins, revisions kept) into round2 parquet
    r1 = pd.read_parquet(TRACK / "data" / "eps" / "eps_quarterly.parquet")
    keep = [c for c in r1.columns if c in new.columns] if not new.empty else list(r1.columns)
    merged = pd.concat([r1[keep], new[keep]], ignore_index=True) if not new.empty else r1[keep]
    merged = merged.sort_values(["symbol", "period_end", "variant", "announce_ts"],
                                na_position="last")
    merged = merged.drop_duplicates(subset=["symbol", "period_end", "variant", "announce_ts"],
                                    keep="first").reset_index(drop=True)
    merged.to_parquet(R2 / "eps_quarterly.parquet")
    print(f"\nrequests {n_req:,} | status rows {len(st):,} | new eps rows {len(new):,} "
          f"| merged {len(merged):,}")
    print(st["status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
