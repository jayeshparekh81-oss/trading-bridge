"""ELIGIBLE refill features per session/instrument, streamed from S3. Uses research/depth_proxies.py
UNMODIFIED (DepthProxyEngine defaults: levels=5, k_refill=5, near_ticks=2, tick=0.05, gap_guard=5s).
The trade tape is NEVER fed (on_trade never called). cancel/wall events the engine still emits are
DISQUALIFIED and only counted, never stored as features. No forward return is computed here."""
import sys, re, json, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, pyarrow as pa, pyarrow.parquet as pq
from pyarrow import fs
OE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(OE))
from research.depth_proxies import DepthProxyEngine, snapshot_to_book          # unmodified
DE = OE / "research_scratch" / "depth_eval"; FEAT = DE / "features"; FEAT.mkdir(exist_ok=True)
sch = (OE / "recorder" / "depth_schema.py").read_text()
SIDE_BID = int(re.search(r"^SIDE_BID\s*=\s*(\d+)", sch, re.M).group(1)); SIDE_ASK = int(re.search(r"^SIDE_ASK\s*=\s*(\d+)", sch, re.M).group(1))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); BAR_S = 5; W = 10; LEVELS = 5; MID_MAX_AGE_NS = 2_000_000_000
COLS = ["ts_recv_ns", "seq_local", "side"] + [f"price_{i}" for i in range(1, LEVELS + 1)] + [f"qty_{i}" for i in range(1, LEVELS + 1)]

def grid(date):
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15); c = d.replace(hour=15, minute=30)
    n = int((c - o).total_seconds() // BAR_S)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(n)], dtype=np.int64)

def compute(date, inst, key, out_path=None):
    s3 = fs.S3FileSystem(region="ap-south-1")
    df = pq.read_table(s3.open_input_file(key), columns=COLS).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
    ts = df.ts_recv_ns.to_numpy(np.int64); side = df.side.to_numpy()
    P = [df[f"price_{i}"].to_numpy(dtype=float) for i in range(1, LEVELS + 1)]; Q = [df[f"qty_{i}"].to_numpy(dtype=float) for i in range(1, LEVELS + 1)]
    nan_or_zero = int(sum(np.sum(~(x > 0)) for x in P + Q))
    isb, isa = side == SIDE_BID, side == SIDE_ASK
    order_viol = int(np.sum(isb & (P[0] < P[1]))) + int(np.sum(isa & (P[0] > P[1])))   # bid: p1>=p2 ; ask: p1<=p2
    eng = DepthProxyEngine()
    for k in range(len(df)):
        parsed = {}
        for i in range(LEVELS):
            parsed[f"price_{i+1}"] = P[i][k]; parsed[f"qty_{i+1}"] = Q[i][k]
        eng.on_snapshot(int(ts[k]), "bid" if isb[k] else "ask", snapshot_to_book(parsed))
    ends = grid(date); starts = ends - BAR_S * 1_000_000_000
    ref = [e for e in eng.events if e.kind == "refill"]
    n_other = {"cancel": sum(1 for e in eng.events if e.kind == "cancel"), "wall": sum(1 for e in eng.events if e.kind == "wall")}
    nb = len(ends); feat = {"bar_end_ns": ends, "slot": ((ends - ends[0]) // (15 * 60 * 1_000_000_000)).astype(np.int16)}
    for sd in ("bid", "ask"):
        ets = np.array([e.ts_ns for e in ref if e.side == sd], dtype=np.int64); rem = np.array([e.removed for e in ref if e.side == sd], float); res = np.array([e.restored for e in ref if e.side == sd], float)
        idx = np.searchsorted(ends, ets, side="left"); ok = (ets > starts[0]) & (ets <= ends[-1]); idx, rem, res = idx[ok], rem[ok], res[ok]
        cnt = np.bincount(idx, minlength=nb).astype(np.int32); srem = np.bincount(idx, weights=rem, minlength=nb); sres = np.bincount(idx, weights=res, minlength=nb)
        with np.errstate(divide="ignore", invalid="ignore"): ratio = np.where(srem > 0, np.round(sres / srem, 6), np.nan)
        cs = np.cumsum(cnt); roll = cs - np.concatenate([np.zeros(W, dtype=cs.dtype), cs[:-W]])
        feat[f"{sd}_refills"] = cnt; feat[f"{sd}_refill_ratio"] = ratio; feat[f"{sd}_refills_w"] = roll.astype(np.int32)
    # mid at bar end from the depth rows themselves: last snapshot of each side with ts <= bar_end, max age 2 s
    bts, bp = ts[isb], P[0][isb]; ats, ap = ts[isa], P[0][isa]
    bi = np.searchsorted(bts, ends, side="right") - 1; ai = np.searchsorted(ats, ends, side="right") - 1
    bok = (bi >= 0) & (ends - bts[np.clip(bi, 0, None)] <= MID_MAX_AGE_NS); aok = (ai >= 0) & (ends - ats[np.clip(ai, 0, None)] <= MID_MAX_AGE_NS)
    bid1 = np.where(bok, bp[np.clip(bi, 0, None)], np.nan); ask1 = np.where(aok, ap[np.clip(ai, 0, None)], np.nan)
    feat["bid1"] = bid1; feat["ask1"] = ask1; feat["mid"] = (bid1 + ask1) / 2.0
    crossed = int(np.sum((ask1 - bid1) <= 0)); valid_mid = int(np.sum(~np.isnan(feat["mid"])))
    out = pd.DataFrame(feat)
    if out_path: out.to_parquet(out_path, index=False)
    summ = {"date": date, "inst": inst, "rows_in": int(len(df)), "nan_or_zero_top5": nan_or_zero, "side_order_violations": order_viol,
            "refill_events": {"bid": int(sum(1 for e in ref if e.side == "bid")), "ask": int(sum(1 for e in ref if e.side == "ask"))},
            "ignored_disqualified_events": n_other, "bars": nb, "bars_with_valid_mid": valid_mid, "crossed_or_locked_at_bar_end": crossed,
            "side_bid_value": SIDE_BID, "side_ask_value": SIDE_ASK}
    return out, summ

if __name__ == "__main__":
    inv = [r for r in json.loads((DE / "cp1_inventory.json").read_text()) if "key" in r]
    summaries = []; t0 = time.time()
    for r in inv:
        t1 = time.time(); out, s = compute(r["date"], r["inst"], r["key"], FEAT / f"{r['date']}_{r['inst']}.parquet"); summaries.append(s)
        print(f"  {s['date']} {s['inst']:<13} rows={s['rows_in']:>7} nan0={s['nan_or_zero_top5']} order_viol={s['side_order_violations']} refills bid/ask={s['refill_events']['bid']}/{s['refill_events']['ask']} "
              f"ignored cancel/wall={s['ignored_disqualified_events']['cancel']}/{s['ignored_disqualified_events']['wall']} bars={s['bars']} valid_mid={s['bars_with_valid_mid']} crossed={s['crossed_or_locked_at_bar_end']} {time.time()-t1:.0f}s", flush=True)
    (FEAT / "_summary.json").write_text(json.dumps(summaries, indent=1))
    print(f"  sessions: {len(summaries)} | SIDE_BID={SIDE_BID} SIDE_ASK={SIDE_ASK} | {time.time()-t0:.0f}s")
