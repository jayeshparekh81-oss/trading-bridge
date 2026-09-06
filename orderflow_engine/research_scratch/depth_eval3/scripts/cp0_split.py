"""CP0 (run 3) — independent re-verification of the clean-session list (every date, both instruments, all 66 columns
streamed, direct counts), chronological 70/30 split, quarantine file. Runs BEFORE the split exists, so it is the only
script in depth_eval3 allowed to read S3 without the quarantine guard.
USABLE threshold (stated before classification): UNUSABLE if rows with any price_N<=0 > 1.0% of rows, or non-monotonic
ladder rows > 1.0%, or zero qty/orders at valid-price levels > 1.0%, or crossed 5-s bars (sides aligned, age<=2 s) > 1.0%
of defined bars. A date is CLEAN only if BOTH instruments are USABLE. Split rule: sort clean dates; DISCOVERY = the
oldest floor(0.7*N); CONFIRMATION = the rest (newest)."""
import json, re, sys, time, math, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
from pyarrow import fs
BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"; PREFIX = "orderflow/r0"; INSTS = ("NIFTY_FUT", "BANKNIFTY_FUT")
D3 = Path(__file__).resolve().parent.parent; IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); BAR_S = 5; MAX_AGE = 2_000_000_000; THRESH = 0.01
s3 = fs.S3FileSystem(region="ap-south-1"); PCOLS = [f"price_{i}" for i in range(1, 21)]; QCOLS = [f"qty_{i}" for i in range(1, 21)]; OCOLS = [f"orders_{i}" for i in range(1, 21)]
def grid(date):
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15); c = d.replace(hour=15, minute=30)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(int((c - o).total_seconds() // BAR_S))], dtype=np.int64)
def sweep_numpy(date, key):
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    n = len(t); ts = t.ts_recv_ns.to_numpy(np.int64); side = t.side.to_numpy(); isb, isa = side == 0, side == 1
    P = t[PCOLS].to_numpy(float); Q = t[QCOLS].to_numpy(float); O = t[OCOLS].to_numpy(float); vp = P > 0
    r_price = int(np.sum(~vp.all(axis=1))); d = P[:, 1:] - P[:, :-1]; both = vp[:, 1:] & vp[:, :-1]
    r_mono = int(np.sum(isb & np.any(both & (d >= 0), axis=1)) + np.sum(isa & np.any(both & (d <= 0), axis=1)))
    r_zero = int(np.sum(np.any(vp & ~(Q > 0), axis=1) | np.any(vp & ~(O > 0), axis=1)))
    ends = grid(date); bts, ats = ts[isb], ts[isa]; bp, ap = P[isb, 0], P[isa, 0]
    bi = np.searchsorted(bts, ends, side="right") - 1; ai = np.searchsorted(ats, ends, side="right") - 1
    bok = (bi >= 0) & (ends - bts[np.clip(bi, 0, None)] <= MAX_AGE) & (bp[np.clip(bi, 0, None)] > 0); aok = (ai >= 0) & (ends - ats[np.clip(ai, 0, None)] <= MAX_AGE) & (ap[np.clip(ai, 0, None)] > 0)
    defined = bok & aok; crossed = int(np.sum(defined & (bp[np.clip(bi, 0, None)] >= ap[np.clip(ai, 0, None)])))
    return {"rows": n, "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "bars_defined": int(defined.sum()), "bars_crossed": crossed}
def sweep_pandas(date, key):
    t = pq.read_table(s3.open_input_file(key)).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    Pd = t[PCOLS]; vp = Pd.gt(0); r_price = int((~vp.all(axis=1)).sum()); diffs = Pd.diff(axis=1).iloc[:, 1:]; both = (vp.iloc[:, 1:].values & vp.iloc[:, :-1].values)
    r_mono = int((((diffs.values >= 0) & both).any(axis=1) & (t.side.values == 0)).sum() + (((diffs.values <= 0) & both).any(axis=1) & (t.side.values == 1)).sum())
    r_zero = int(((vp.values & ~t[QCOLS].gt(0).values).any(axis=1) | (vp.values & ~t[OCOLS].gt(0).values).any(axis=1)).sum())
    ends = pd.DataFrame({"ts_recv_ns": grid(date)}); b = t.loc[t.side == 0, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "b1", "ts_recv_ns": "bts"}); a = t.loc[t.side == 1, ["ts_recv_ns", "price_1"]].rename(columns={"price_1": "a1", "ts_recv_ns": "ats"})
    m = pd.merge_asof(ends, b, left_on="ts_recv_ns", right_on="bts", direction="backward"); m = pd.merge_asof(m, a, left_on="ts_recv_ns", right_on="ats", direction="backward")
    ok = (m.ts_recv_ns - m.bts <= MAX_AGE) & (m.ts_recv_ns - m.ats <= MAX_AGE) & (m.b1 > 0) & (m.a1 > 0)
    return {"rows": len(t), "price_nonpos_rows": r_price, "nonmono_rows": r_mono, "zero_qty_or_orders_rows": r_zero, "bars_defined": int(ok.sum()), "bars_crossed": int((ok & (m.b1 >= m.a1)).sum())}
if __name__ == "__main__":
    t0 = time.time(); top = s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}", recursive=False)); dates = sorted(i.path.rsplit("/", 1)[-1] for i in top if i.type == fs.FileType.Directory)
    print(f"  date prefixes: {len(dates)} ({dates[0]} .. {dates[-1]}); threshold {THRESH:.0%} per defect class (stated in the docstring before classification)", flush=True); inv = []
    for d in dates:
        objs = [o for o in s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}/{d}/depth", recursive=False, allow_not_found=True)) if o.type == fs.FileType.File]
        for inst in INSTS:
            cons = [o for o in objs if re.search(rf"/depth/{inst}_\d+\.parquet$", o.path)]
            if not cons: inv.append({"date": d, "inst": inst, "status": "ABSENT"}); print(f"  {d} {inst:<13} ABSENT", flush=True); continue
            o = cons[0]; r = sweep_numpy(d, o.path); n = r["rows"]; bd = max(r["bars_defined"], 1)
            pct = {"price": r["price_nonpos_rows"] / n, "mono": r["nonmono_rows"] / n, "zero": r["zero_qty_or_orders_rows"] / n, "crossed": r["bars_crossed"] / bd}
            r.update({"date": d, "inst": inst, "key": o.path, "bytes": o.size, "sid": int(re.search(r"_(\d+)\.parquet$", o.path).group(1)), "pct": pct, "status": "USABLE" if all(v <= THRESH for v in pct.values()) else "UNUSABLE"}); inv.append(r)
            print(f"  {d} {inst:<13} sid={r['sid']} rows={n:>7} price<=0 {r['price_nonpos_rows']:>6} ({pct['price']:6.2%}) nonmono {r['nonmono_rows']:>3} zero {r['zero_qty_or_orders_rows']:>3} crossed {r['bars_crossed']:>2}/{r['bars_defined']} | {r['status']}", flush=True)
    by = {}
    for x in inv: by.setdefault(x["date"], {})[x["inst"]] = x.get("status")
    with_obj = [d for d in dates if any("rows" in x for x in inv if x["date"] == d)]; clean = [d for d in with_obj if all(by[d].get(i) == "USABLE" for i in INSTS)]; corrupt = [d for d in with_obj if any(by[d].get(i) == "UNUSABLE" for i in INSTS)]
    n_disc = math.floor(0.7 * len(clean)); disc, conf = clean[:n_disc], clean[n_disc:]
    print(f"\n  dates with objects: {len(with_obj)} | CLEAN (both instruments): {len(clean)} | CORRUPT: {corrupt} ({len(corrupt)/len(with_obj):.1%}) | ABSENT: {[d for d in dates if d not in with_obj]}", flush=True)
    print(f"  DISCOVERY ({len(disc)} = floor(0.7*{len(clean)})): {disc}\n  CONFIRMATION ({len(conf)}): {conf}", flush=True)
    # self-check BEFORE the quarantine file exists: independent pandas path on 3 dates (a clean early, the corrupt 08-17, a clean discovery late)
    stored = {(x["date"], x["inst"]): x for x in inv if "rows" in x}; keys = ["rows", "price_nonpos_rows", "nonmono_rows", "zero_qty_or_orders_rows", "bars_defined", "bars_crossed"]; ok_all = True
    for d in ("2026-07-14", "2026-08-17", "2026-08-14"):
        for inst in INSTS:
            r = stored[(d, inst)]; alt = sweep_pandas(d, r["key"]); same = all(alt[k] == r[k] for k in keys); ok_all &= same
            print(f"  self-check {d} {inst:<13} numpy {[r[k] for k in keys]} pandas {[alt[k] for k in keys]} -> {'MATCH' if same else 'MISMATCH'}", flush=True)
    (D3 / "cp0_split.json").write_text(json.dumps({"inventory": inv, "clean": clean, "corrupt": corrupt, "discovery": disc, "confirmation": conf, "self_check_match": ok_all}, indent=1))
    (D3 / "QUARANTINE.json").write_text(json.dumps({"confirmation": conf, "discovery": disc, "allowed_stages_for_confirmation": ["CP6"], "created_ist": dt.datetime.now(IST).isoformat()}, indent=1))
    print(f"  written cp0_split.json + QUARANTINE.json | self-check {'ALL MATCH' if ok_all else 'MISMATCH'} | {time.time()-t0:.0f}s", flush=True)
