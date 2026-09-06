"""CP0 (run 4) — tape integrity, fresh code path (independent of runs 2/3). Every date, both instruments, all 66 depth
columns streamed from S3 and discarded. Direct counts, no sampling.
THRESHOLD, stated before classification: a date-instrument is UNUSABLE if ANY of
  (a) rows with any price_N <= 0 (or null)                       > 1.0% of rows
  (b) rows with a non-monotonic ladder within a side              > 1.0% of rows
  (c) rows with zero/null qty_N or orders_N at a valid-price level> 1.0% of rows
  (d) crossed 5-s bars (sides aligned at bar end, max age 2 s)    > 1.0% of defined bars
A DATE is CLEAN only if BOTH instruments are USABLE."""
import json, re, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
from pyarrow import fs
BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"; PREFIX = "orderflow/r0"; INSTS = ("NIFTY_FUT", "BANKNIFTY_FUT")
D4 = Path(__file__).resolve().parent.parent; IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); BAR_S = 5; MAX_AGE = 2_000_000_000; THRESH = 0.01
PC = [f"price_{i}" for i in range(1, 21)]; QC = [f"qty_{i}" for i in range(1, 21)]; OC = [f"orders_{i}" for i in range(1, 21)]
s3 = fs.S3FileSystem(region="ap-south-1")
def grid(date):
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(4500)], dtype=np.int64)
def sweep(date, key):
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    n = len(t); ts = t.ts_recv_ns.to_numpy(np.int64); sd = t.side.to_numpy(); isb, isa = sd == 0, sd == 1
    P = t[PC].to_numpy(float); Q = t[QC].to_numpy(float); O = t[OC].to_numpy(float); vp = P > 0
    r_price = int((~vp.all(1)).sum()); d = np.diff(P, axis=1); both = vp[:, 1:] & vp[:, :-1]
    r_mono = int((isb & ((both & (d >= 0)).any(1))).sum() + (isa & ((both & (d <= 0)).any(1))).sum())
    r_zero = int(((vp & ~(Q > 0)).any(1) | (vp & ~(O > 0)).any(1)).sum())
    ends = grid(date); bts, ats = ts[isb], ts[isa]; bp, ap = P[isb, 0], P[isa, 0]
    bi = np.clip(np.searchsorted(bts, ends, "right") - 1, 0, None); ai = np.clip(np.searchsorted(ats, ends, "right") - 1, 0, None)
    bok = (np.searchsorted(bts, ends, "right") > 0) & (ends - bts[bi] <= MAX_AGE) & (bp[bi] > 0); aok = (np.searchsorted(ats, ends, "right") > 0) & (ends - ats[ai] <= MAX_AGE) & (ap[ai] > 0)
    defi = bok & aok
    return {"rows": n, "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "bars_defined": int(defi.sum()), "bars_crossed": int((defi & (bp[bi] >= ap[ai])).sum())}
def sweep_alt(date, key):
    """Independent path: pandas boolean frames + merge_asof."""
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    Pd = t[PC]; vp = Pd.gt(0); r_price = int((~vp.all(axis=1)).sum())
    df_ = Pd.diff(axis=1).iloc[:, 1:]; both = vp.iloc[:, 1:].values & vp.iloc[:, :-1].values
    r_mono = int((((df_.values >= 0) & both).any(1) & (t.side.values == 0)).sum() + (((df_.values <= 0) & both).any(1) & (t.side.values == 1)).sum())
    r_zero = int(((vp.values & ~t[QC].gt(0).values).any(1) | (vp.values & ~t[OC].gt(0).values).any(1)).sum())
    e = pd.DataFrame({"ts_recv_ns": grid(date)}); b = t.loc[t.side == 0, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "b1", "ts_recv_ns": "bts"}); a = t.loc[t.side == 1, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "a1", "ts_recv_ns": "ats"})
    m = pd.merge_asof(e, b, left_on="ts_recv_ns", right_on="bts"); m = pd.merge_asof(m, a, left_on="ts_recv_ns", right_on="ats")
    ok = (m.ts_recv_ns - m.bts <= MAX_AGE) & (m.ts_recv_ns - m.ats <= MAX_AGE) & (m.b1 > 0) & (m.a1 > 0)
    return {"rows": len(t), "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "bars_defined": int(ok.sum()), "bars_crossed": int((ok & (m.b1 >= m.a1)).sum())}
if __name__ == "__main__":
    t0 = time.time(); dates = sorted(i.path.rsplit("/", 1)[-1] for i in s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}", recursive=False)) if i.type == fs.FileType.Directory)
    print(f"  {len(dates)} date prefixes ({dates[0]}..{dates[-1]}); threshold {THRESH:.0%} per class, stated before classification", flush=True); inv = []
    for d in dates:
        objs = [o for o in s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}/{d}/depth", recursive=False, allow_not_found=True)) if o.type == fs.FileType.File]
        for inst in INSTS:
            cons = [o for o in objs if re.search(rf"/depth/{inst}_\d+\.parquet$", o.path)]
            if not cons: inv.append({"date": d, "inst": inst, "status": "ABSENT"}); print(f"  {d} {inst:<13} ABSENT", flush=True); continue
            o = cons[0]; r = sweep(d, o.path); n = r["rows"]; bd = max(r["bars_defined"], 1)
            pct = {"price": r["price_nonpos_rows"] / n, "mono": r["nonmono_rows"] / n, "zero": r["zero_qty_or_orders_rows"] / n, "crossed": r["bars_crossed"] / bd}
            r.update({"date": d, "inst": inst, "key": o.path, "sid": int(re.search(r"_(\d+)\.parquet$", o.path).group(1)), "pct": pct, "status": "USABLE" if all(v <= THRESH for v in pct.values()) else "UNUSABLE"}); inv.append(r)
            print(f"  {d} {inst:<13} sid={r['sid']} rows={n:>7} price<=0 {r['price_nonpos_rows']:>6} ({pct['price']:6.2%}) nonmono {r['nonmono_rows']:>3} zero {r['zero_qty_or_orders_rows']:>3} crossed {r['bars_crossed']:>2}/{r['bars_defined']} | {r['status']}", flush=True)
    by = {}
    for x in inv: by.setdefault(x["date"], {})[x["inst"]] = x.get("status")
    withobj = [d for d in dates if any("rows" in x for x in inv if x["date"] == d)]; clean = [d for d in withobj if all(by[d].get(i) == "USABLE" for i in INSTS)]; corrupt = [d for d in withobj if any(by[d].get(i) == "UNUSABLE" for i in INSTS)]
    print(f"\n  dates with objects {len(withobj)} | CLEAN {len(clean)} | CORRUPT {corrupt} ({len(corrupt)/len(withobj):.1%}) | ABSENT {[d for d in dates if d not in withobj]}", flush=True)
    st = {(x["date"], x["inst"]): x for x in inv if "rows" in x}; keys = ["rows", "price_nonpos_rows", "nonmono_rows", "zero_qty_or_orders_rows", "bars_defined", "bars_crossed"]; ok = True
    for d in ("2026-07-15", "2026-08-24", "2026-09-02"):
        for inst in INSTS:
            r = st[(d, inst)]; alt = sweep_alt(d, r["key"]); same = all(alt[k] == r[k] for k in keys); ok &= same
            print(f"  self-check {d} {inst:<13} A {[r[k] for k in keys]} | B {[alt[k] for k in keys]} -> {'MATCH' if same else 'MISMATCH'}", flush=True)
    (D4 / "cp0_integrity.json").write_text(json.dumps({"inventory": inv, "clean": clean, "corrupt": corrupt, "selfcheck_match": ok}, indent=1))
    print(f"  CLEAN={len(clean)} written cp0_integrity.json | self-check {'ALL MATCH' if ok else 'MISMATCH'} | {time.time()-t0:.0f}s", flush=True)
