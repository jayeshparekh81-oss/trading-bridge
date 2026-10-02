#!/usr/bin/env python3
"""M6b step 2 — old-era adjustment audit (report-only; fixes nothing).

(a) gap scan 2015 -> Oct-2021
(b) match every suspect to an NSE corp action -> adjusted / CLIFFED / UNMATCHED
(c) named spot-checks (BPCL 2016 & 2017 bonuses, RELIANCE 2017 bonus)
(d) habitat-overlap ratio (Aug -> Oct 2021) — same adjustment regime as Round-1?
(e) per-symbol verdict OK / SUSPECT / EXCLUDE
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m6a_probe_eps as P  # noqa: E402  (NSE session/throttle reuse)

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
DAILY = R2 / "daily"
HAB = TRACK / "data" / "swing" / "daily"
CA = R2 / "corpactions"
GAP = 0.25
CA_PAT = re.compile(r"split|bonus|demerg|face value|consolidat", re.I)
OVERLAP = ("2021-08-01", "2021-10-31")


def load(sym) -> pd.DataFrame:
    return pd.read_parquet(DAILY / f"{sym}.parquet")


def gap_scan(symbols) -> pd.DataFrame:
    rows = []
    for sym in symbols:
        d = load(sym)
        pc = d["close"].shift(1)
        on = d["open"] / pc - 1
        cc = d["close"] / pc - 1
        for kind, ser in (("overnight", on), ("close-to-close", cc)):
            for dt, mv in ser[ser.abs() >= GAP].dropna().items():
                rows.append({"symbol": sym, "date": dt, "kind": kind,
                             "move_pct": round(100 * mv, 2),
                             "close_before": round(float(pc.loc[dt]), 2),
                             "close_after": round(float(d["close"].loc[dt]), 2)})
    return pd.DataFrame(rows)


def fetch_ca(s, sym):
    p = CA / f"{sym}.json"
    if p.exists():
        return json.loads(p.read_text())
    q = requests.utils.quote
    r = P.get(s, "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
                 f"&symbol={q(sym, safe='')}&from_date=01-01-2015&to_date=31-12-2021")
    acts = []
    if r is not None:
        try:
            acts = r.json()
        except ValueError:
            acts = []
    CA.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(acts))
    os.replace(tmp, p)
    return acts


def classify(suspects: pd.DataFrame) -> pd.DataFrame:
    """A corp action on/near the cliff date means the series is UNADJUSTED there:
    a back-adjusted series shows no cliff at an ex-date at all."""
    if suspects.empty:
        return suspects
    s = requests.Session()
    P.warm(s)
    out = []
    for sym, grp in suspects.groupby("symbol"):
        acts = fetch_ca(s, sym) or []
        evs = []
        for a in acts:
            sub = a.get("subject") or ""
            if not CA_PAT.search(sub):
                continue
            d = P.pdate(a.get("exDate"))
            if d:
                evs.append((pd.Timestamp(d), sub[:60]))
        for _, r in grp.iterrows():
            near = [(d, sub) for d, sub in evs if abs((r["date"] - d).days) <= 4]
            if near:
                d0, sub = near[0]
                cls, why = "MATCHED-CLIFFED(unadjusted)", f"{sub} ex {d0.date()}"
            else:
                cls, why = "UNMATCHED-CLIFF", "no split/bonus/demerger within +/-4d"
            out.append({**r.to_dict(), "classification": cls, "detail": why})
    return pd.DataFrame(out)


def spot_checks() -> pd.DataFrame:
    targets = [("BPCL", "2016-07-13", "Bonus 1:1"), ("BPCL", "2017-07-13", "Bonus 1:2"),
               ("RELIANCE", "2017-09-07", "Bonus 1:1")]
    rows = []
    for sym, ex, label in targets:
        d = load(sym)
        w = d.loc[pd.Timestamp(ex) - pd.Timedelta(days=6):pd.Timestamp(ex) + pd.Timedelta(days=6)]
        ret = w["close"].pct_change()
        for dt, c in w["close"].items():
            rows.append({"symbol": sym, "event": f"{label} ex {ex}", "date": str(dt.date()),
                         "close": round(float(c), 2),
                         "pct_move": (None if pd.isna(ret.loc[dt]) else round(100 * ret.loc[dt], 2)),
                         "is_ex_date": str(dt.date()) == ex})
    return pd.DataFrame(rows)


def habitat_overlap(symbols) -> pd.DataFrame:
    rows = []
    for sym in symbols:
        hp = HAB / f"{sym}.parquet"
        if not hp.exists():
            rows.append({"symbol": sym, "status": "no-habitat-file"})
            continue
        a = load(sym)["close"].loc[OVERLAP[0]:OVERLAP[1]]
        b = pd.read_parquet(hp)["close"].loc[OVERLAP[0]:OVERLAP[1]]
        common = a.index.intersection(b.index)
        if len(common) < 10:
            rows.append({"symbol": sym, "status": f"overlap {len(common)}d (too few)"})
            continue
        ratio = (a.loc[common] / b.loc[common])
        lr = np.log(ratio)
        # A LEVEL difference is expected and benign: habitat is back-adjusted to
        # 2026 while this fetch is anchored at Oct-2021, so any corp action AFTER
        # the fetch window makes the ratio a flat constant != 1 (RECLTD sits at
        # exactly 0.75 — a 1:3 bonus). What would signal a real disagreement is a
        # PERSISTENT STEP inside the overlap. Test for that, M1-style, not for
        # ratio_mean == 1; and use a threshold big enough that a one-day price
        # discrepancy cannot masquerade as a missed corp action (>= 4%).
        d1 = lr.diff()
        persistent = 0.0
        for i in range(1, len(lr)):
            before = lr.iloc[max(0, i - 5):i].median()
            after = lr.iloc[i:i + 5].median()
            if abs(after - before) > abs(persistent):
                persistent = float(after - before)
        rows.append({"symbol": sym, "status": "ok", "days": len(common),
                     "ratio_mean": round(float(ratio.mean()), 5),
                     "ratio_std": round(float(ratio.std()), 6),
                     "max_log_step": round(float(d1.abs().max()), 5),
                     "persistent_step": round(persistent, 5),
                     "level_shift_only": bool(abs(persistent) < 0.04),
                     "consistent": bool(abs(persistent) < 0.04)})
    return pd.DataFrame(rows)


def verdicts(symbols, cliffs: pd.DataFrame, ov: pd.DataFrame) -> pd.DataFrame:
    cl = (cliffs.groupby("symbol")["classification"].apply(list)
          if not cliffs.empty else pd.Series(dtype=object))
    ovi = ov.set_index("symbol") if not ov.empty else pd.DataFrame()
    rows = []
    for sym in symbols:
        cs = cl.get(sym, [])
        bad = [c for c in cs if c.startswith("MATCHED-CLIFFED")]
        unm = [c for c in cs if c == "UNMATCHED-CLIFF"]
        o = ovi.loc[sym] if sym in ovi.index else None
        inconsistent = bool(o is not None and o.get("status") == "ok"
                            and not bool(o.get("consistent")))
        if bad:
            v, why = "EXCLUDE", f"{len(bad)} corp-action cliff(s) => series UNADJUSTED there"
        elif inconsistent:
            v, why = "EXCLUDE", ("habitat-overlap ratio shows a PERSISTENT step => "
                                 "adjustment regime differs from Round-1")
        elif unm:
            v, why = "SUSPECT", f"{len(unm)} >=25% cliff(s) with no matching corp action"
        else:
            v, why = "OK", "no corp-action cliff; overlap ratio flat"
        rows.append({"symbol": sym, "verdict": v, "reason": why})
    return pd.DataFrame(rows)


def main() -> None:
    symbols = sorted(p.stem for p in DAILY.glob("*.parquet"))
    print(f"[audit] {len(symbols)} symbols")
    sus = gap_scan(symbols)
    print(f"[a] suspects: {len(sus)}")
    cls = classify(sus)
    print(f"[b] classified: {len(cls)}")
    sc = spot_checks()
    ov = habitat_overlap(symbols)
    vd = verdicts(symbols, cls, ov)
    for name, df in (("suspects", sus), ("cliffs", cls), ("spot", sc),
                     ("overlap", ov), ("verdicts", vd)):
        df.to_parquet(R2 / f"audit_{name}.parquet")
    print(vd["verdict"].value_counts().to_dict())
    print(f"final Round-2 universe: {int((vd['verdict'] != 'EXCLUDE').sum())}")


if __name__ == "__main__":
    main()
