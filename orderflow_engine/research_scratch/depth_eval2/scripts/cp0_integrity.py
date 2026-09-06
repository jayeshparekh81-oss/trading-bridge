"""CP0 — TAPE INTEGRITY SWEEP. Every available date in the bucket, both instruments, ALL 66 columns streamed from S3
and discarded (zero raw bytes stored). Direct counts, no sampling.

USABLE / UNUSABLE THRESHOLD — stated here, before any classification runs:
  a date-instrument is UNUSABLE if ANY of
    (a) rows with any price_N <= 0 (or null)           > 1.0% of rows
    (b) rows with a non-monotonic ladder within a side  > 1.0% of rows
    (c) rows with zero/null qty_N or orders_N at a level carrying a valid price > 1.0% of rows
    (d) bars (5 s, 09:15-15:30, sides aligned at bar end, max age 2 s) with best bid >= best ask > 1.0% of defined bars
  a DATE is USABLE only if BOTH instruments are USABLE.
Monotonic check: adjacent levels that BOTH carry a valid price must be strictly decreasing (bid) / strictly increasing (ask).
"""
import json, re, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
from pyarrow import fs
BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"; PREFIX = "orderflow/r0"; INSTS = ("NIFTY_FUT", "BANKNIFTY_FUT")
D2 = Path(__file__).resolve().parent.parent; IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); BAR_S = 5; MAX_AGE = 2_000_000_000; THRESH = 0.01
s3 = fs.S3FileSystem(region="ap-south-1")
PCOLS = [f"price_{i}" for i in range(1, 21)]; QCOLS = [f"qty_{i}" for i in range(1, 21)]; OCOLS = [f"orders_{i}" for i in range(1, 21)]
def ist(ns): return dt.datetime.fromtimestamp(ns / 1e9, IST).strftime("%H:%M:%S")
def grid(date):
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15); c = d.replace(hour=15, minute=30)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(int((c - o).total_seconds() // BAR_S))], dtype=np.int64)

def sweep_numpy(date, key):
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    n = len(t); ts = t.ts_recv_ns.to_numpy(np.int64); side = t.side.to_numpy(); isb, isa = side == 0, side == 1
    P = t[PCOLS].to_numpy(float); Q = t[QCOLS].to_numpy(float); O = t[OCOLS].to_numpy(float)
    vp = P > 0                                                     # NaN -> False
    r_price = int(np.sum(~vp.all(axis=1)))
    d = P[:, 1:] - P[:, :-1]; both = vp[:, 1:] & vp[:, :-1]
    r_mono = int(np.sum(isb & np.any(both & (d >= 0), axis=1)) + np.sum(isa & np.any(both & (d <= 0), axis=1)))
    zq = np.any(vp & ~(Q > 0), axis=1); zo = np.any(vp & ~(O > 0), axis=1); r_zero = int(np.sum(zq | zo))
    ends = grid(date); bts, ats = ts[isb], ts[isa]; bp, ap = P[isb, 0], P[isa, 0]
    bi = np.searchsorted(bts, ends, side="right") - 1; ai = np.searchsorted(ats, ends, side="right") - 1
    bok = (bi >= 0) & (ends - bts[np.clip(bi, 0, None)] <= MAX_AGE) & (bp[np.clip(bi, 0, None)] > 0); aok = (ai >= 0) & (ends - ats[np.clip(ai, 0, None)] <= MAX_AGE) & (ap[np.clip(ai, 0, None)] > 0)
    defined = bok & aok; crossed = int(np.sum(defined & (bp[np.clip(bi, 0, None)] >= ap[np.clip(ai, 0, None)])))
    sides = {}
    for sv, m in (("bid", isb), ("ask", isa)):
        sides[sv] = {"rows": int(m.sum()), "first": ist(ts[m].min()) if m.any() else None, "last": ist(ts[m].max()) if m.any() else None}
    return {"rows": n, "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "zero_qty_rows": int(zq.sum()), "zero_orders_rows": int(zo.sum()),
            "bars_defined": int(defined.sum()), "bars_crossed": crossed, "sides": sides}

def sweep_pandas(date, key):
    """Independent code path (pandas ops, merge_asof alignment) for the self-check."""
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    Pd = t[PCOLS]; vp = Pd.gt(0)
    r_price = int((~vp.all(axis=1)).sum())
    diffs = Pd.diff(axis=1).iloc[:, 1:]; both = (vp.iloc[:, 1:].values & vp.iloc[:, :-1].values)
    bad_bid = ((diffs.values >= 0) & both).any(axis=1) & (t.side.values == 0); bad_ask = ((diffs.values <= 0) & both).any(axis=1) & (t.side.values == 1)
    r_mono = int(bad_bid.sum() + bad_ask.sum())
    zq = (vp.values & ~t[QCOLS].gt(0).values).any(axis=1); zo = (vp.values & ~t[OCOLS].gt(0).values).any(axis=1); r_zero = int((zq | zo).sum())
    ends = pd.DataFrame({"ts_recv_ns": grid(date)})
    b = t.loc[t.side == 0, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "b1", "ts_recv_ns": "bts"}); a = t.loc[t.side == 1, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "a1", "ts_recv_ns": "ats"})
    m = pd.merge_asof(ends, b, left_on="ts_recv_ns", right_on="bts", direction="backward"); m = pd.merge_asof(m, a, left_on="ts_recv_ns", right_on="ats", direction="backward")
    ok = (m.ts_recv_ns - m.bts <= MAX_AGE) & (m.ts_recv_ns - m.ats <= MAX_AGE) & (m.b1 > 0) & (m.a1 > 0)
    return {"rows": len(t), "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "bars_defined": int(ok.sum()), "bars_crossed": int((ok & (m.b1 >= m.a1)).sum())}

if __name__ == "__main__":
    t0 = time.time()
    top = s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}", recursive=False)); dates = sorted(i.path.rsplit("/", 1)[-1] for i in top if i.type == fs.FileType.Directory)
    print(f"  date prefixes in bucket: {len(dates)} ({dates[0]} .. {dates[-1]}) | threshold per defect class: {THRESH:.0%} (stated in the module docstring before classification)", flush=True)
    out = []
    for d in dates:
        objs = [o for o in s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}/{d}/depth", recursive=False, allow_not_found=True)) if o.type == fs.FileType.File]
        for inst in INSTS:
            cons = [o for o in objs if re.search(rf"/depth/{inst}_\d+\.parquet$", o.path)]
            if not cons: out.append({"date": d, "inst": inst, "status": "ABSENT"}); print(f"  {d} {inst:<13} ABSENT", flush=True); continue
            o = cons[0]; r = sweep_numpy(d, o.path); r.update({"date": d, "inst": inst, "key": o.path, "bytes": o.size, "sid": int(re.search(r"_(\d+)\.parquet$", o.path).group(1))})
            n = r["rows"]; bd = max(r["bars_defined"], 1)
            pct = {"price": r["price_nonpos_rows"] / n, "mono": r["nonmono_rows"] / n, "zero": r["zero_qty_or_orders_rows"] / n, "crossed": r["bars_crossed"] / bd}
            r["pct"] = pct; r["usable"] = all(v <= THRESH for v in pct.values()); r["status"] = "USABLE" if r["usable"] else "UNUSABLE"
            out.append(r)
            print(f"  {d} {inst:<13} sid={r['sid']} rows={n:>7} price<=0: {r['price_nonpos_rows']:>6} ({pct['price']:6.2%}) nonmono: {r['nonmono_rows']:>6} ({pct['mono']:6.2%}) zero q/o: {r['zero_qty_or_orders_rows']:>6} ({pct['zero']:6.2%}) crossed bars: {r['bars_crossed']:>4}/{r['bars_defined']} ({pct['crossed']:6.2%}) | bid {r['sides']['bid']['first']}-{r['sides']['bid']['last']} | {r['status']}", flush=True)
    (D2 / "cp0_integrity.json").write_text(json.dumps(out, indent=1))
    print(f"  swept {sum(1 for r in out if 'rows' in r)} objects in {time.time()-t0:.0f}s -> cp0_integrity.json", flush=True)
