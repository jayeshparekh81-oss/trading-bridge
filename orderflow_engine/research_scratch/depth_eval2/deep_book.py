"""deep_book.py — RUN 2: aggressor-free features of the DEEP book (levels 6-20). NEW module; research/depth_proxies.py
is not imported and not modified. Inputs: price_N, qty_N, orders_N (N=1..20), side, ts_recv_ns. No trade tape, no
aggressor tag, no eaten-vs-pulled: walls are counted as APPEAR / DISAPPEAR only.

Features (per 5-second bar, both sides aligned at bar end = last snapshot of each side with age <= 2 s):
  STATE (signed, sampled at bar end)
    deep_imb_qty     = (Σ qty_6..20 bid − Σ qty_6..20 ask) / (Σ bid + Σ ask)
    deep_imb_orders  = same with orders_6..20
    slope_diff       = slope_bid − slope_ask, slope = OLS slope of log(qty_N) on N over levels 1..20 with price>0 & qty>0 (>=3 levels)
    conc_diff        = conc_bid − conc_ask, conc = Σ qty_6..20 / Σ qty_1..20 per side
  EVENTS (per bar counts and trailing 10-bar sums), per side, diff BY PRICE between consecutive snapshots of the same side:
    wall_appear      : a price present now, absent before, at level index >= 6 now, qty >= rolling P90 of deep level sizes
                       (last 500 deep sizes per side, P90 refreshed every 25 snapshots), lying STRICTLY INSIDE the previous
                       snapshot's price span (so window entry at the far end is not an event)
    wall_disappear   : a price present before at level index >= 6 with qty >= P90, absent now, STRICTLY INSIDE the current span
    deep_refill      : run-1 refill construction at deep levels — price present in BOTH snapshots at level index >= 6 in both,
                       qty drops (pending for k=5 snapshots), then rises at the same price -> refill (ratio restored/removed)
  Gap guard 5 s (a longer gap discards the diff and pending state), as in run 1.
"""
from __future__ import annotations
import re, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
from pyarrow import fs

OE = Path(__file__).resolve().parents[2]
_sch = (OE / "recorder" / "depth_schema.py").read_text()
SIDE_BID = int(re.search(r"^SIDE_BID\s*=\s*(\d+)", _sch, re.M).group(1)); SIDE_ASK = int(re.search(r"^SIDE_ASK\s*=\s*(\d+)", _sch, re.M).group(1))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
L = 20; DEEP0 = 5; BAR_S = 5; W = 10; MID_MAX_AGE_NS = 2_000_000_000; K_REFILL = 5; GAP_GUARD_NS = 5_000_000_000; WALL_LOOKBACK = 500; P90_EVERY = 25; MIN_SIZES = 50
PCOLS = [f"price_{i}" for i in range(1, L + 1)]; QCOLS = [f"qty_{i}" for i in range(1, L + 1)]; OCOLS = [f"orders_{i}" for i in range(1, L + 1)]
SIGNED = ["deep_imb_qty", "deep_imb_orders", "slope_diff", "conc_diff"]
COUNT_SIDES = ["wall_appear", "wall_disappear", "deep_refill"]

def grid(date: str) -> np.ndarray:
    d = dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST); o = d.replace(hour=9, minute=15); c = d.replace(hour=15, minute=30)
    return np.array([int((o + dt.timedelta(seconds=BAR_S * (i + 1))).timestamp() * 1e9) for i in range(int((c - o).total_seconds() // BAR_S))], dtype=np.int64)

def load_session(key: str) -> pd.DataFrame:
    s3 = fs.S3FileSystem(region="ap-south-1")
    t = pq.read_table(s3.open_input_file(key), columns=["ts_recv_ns", "seq_local", "side"] + PCOLS + QCOLS + OCOLS).to_pandas()
    return t.sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)

def row_state(P: np.ndarray, Q: np.ndarray, O: np.ndarray) -> dict:
    """Per-row (per-snapshot) deep-book state, vectorised. Levels with price<=0 or qty<=0 are ignored."""
    v = (P > 0) & (Q > 0); Qv = np.where(v, Q, 0.0); Ov = np.where(v & (O > 0), O, 0.0)
    deep_q = Qv[:, DEEP0:].sum(1); tot_q = Qv.sum(1); deep_o = Ov[:, DEEP0:].sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        conc = np.where(tot_q > 0, deep_q / tot_q, np.nan)
        x = np.arange(1, L + 1, dtype=float)[None, :]; y = np.where(v, np.log(np.where(v, Q, 1.0)), 0.0); nm = v.sum(1)
        xm = (x * v).sum(1) / np.maximum(nm, 1); ym = y.sum(1) / np.maximum(nm, 1)
        cov = (((x - xm[:, None]) * (y - ym[:, None])) * v).sum(1); var = (((x - xm[:, None]) ** 2) * v).sum(1)
        slope = np.where(nm >= 3, cov / np.where(var > 0, var, np.nan), np.nan)
    return {"deep_q": deep_q, "deep_o": deep_o, "conc": conc, "slope": slope}

def deep_events(ts: np.ndarray, side: np.ndarray, P: np.ndarray, Q: np.ndarray) -> list[tuple]:
    """Per-snapshot loop per side. Returns (ts, side_label, kind, price, removed, restored)."""
    events = []; prev = {}; pending = {"bid": {}, "ask": {}}; sizes = {"bid": [], "ask": []}; p90 = {"bid": None, "ask": None}; nsnap = {"bid": 0, "ask": 0}
    for k in range(len(ts)):
        sd = "bid" if side[k] == SIDE_BID else "ask"; t = int(ts[k])
        book = {}                                                       # price -> (qty, level index 1..20)
        for i in range(L):
            p, q = P[k, i], Q[k, i]
            if p > 0 and q > 0: book[float(p)] = (float(q), i + 1)
        deep_sizes = [q for q, lv in book.values() if lv > DEEP0]
        sizes[sd].extend(deep_sizes)
        if len(sizes[sd]) > WALL_LOOKBACK: del sizes[sd][: len(sizes[sd]) - WALL_LOOKBACK]
        nsnap[sd] += 1
        if nsnap[sd] % P90_EVERY == 0 and len(sizes[sd]) >= MIN_SIZES: p90[sd] = float(np.percentile(sizes[sd], 90))
        pv = prev.get(sd); prev[sd] = (t, book)
        if pv is None: continue
        t0, pbook = pv
        if t - t0 > GAP_GUARD_NS: pending[sd] = {}; continue
        if not book or not pbook: continue
        lo_c, hi_c = min(book), max(book); lo_p, hi_p = min(pbook), max(pbook); thr = p90[sd]
        pend_sd = pending[sd]                                            # {price: [[removed, snaps_left], ...]} FIFO per price
        for price in set(pbook) & set(book):                             # deep refill: present in both, deep in both
            (q0, l0), (q1, l1) = pbook[price], book[price]
            if l0 <= DEEP0 or l1 <= DEEP0: continue
            d = q0 - q1
            if d > 0: pend_sd.setdefault(price, []).append([d, K_REFILL])
            elif d < 0 and pend_sd.get(price):
                removed = pend_sd[price].pop(0)[0]; events.append((t, sd, "deep_refill", price, removed, -d))
        if thr is not None:
            for price, (q, lv) in book.items():                          # appear: new deep price, large, strictly inside previous span
                if lv > DEEP0 and q >= thr and price not in pbook and lo_p < price < hi_p: events.append((t, sd, "wall_appear", price, 0.0, q))
            for price, (q, lv) in pbook.items():                         # disappear: previously deep, large, gone, strictly inside current span
                if lv > DEEP0 and q >= thr and price not in book and lo_c < price < hi_c: events.append((t, sd, "wall_disappear", price, q, 0.0))
        for price in list(pend_sd):                                      # age out pending refills (k snapshots)
            lst = [x for x in pend_sd[price] if (x.__setitem__(1, x[1] - 1) or x[1] > 0)]
            if lst: pend_sd[price] = lst
            else: del pend_sd[price]
    return events

def compute_session(date: str, inst: str, key: str, out_path: Path | None = None):
    df = load_session(key); ts = df.ts_recv_ns.to_numpy(np.int64); side = df.side.to_numpy()
    P = df[PCOLS].to_numpy(float); Q = df[QCOLS].to_numpy(float); O = df[OCOLS].to_numpy(float)
    st = row_state(P, Q, O); isb, isa = side == SIDE_BID, side == SIDE_ASK
    ends = grid(date); starts = ends - BAR_S * 1_000_000_000; nb = len(ends)
    feat = {"bar_end_ns": ends, "slot": ((ends - ends[0]) // (15 * 60 * 1_000_000_000)).astype(np.int16)}
    idx = {}; okm = {}
    for lab, m in (("bid", isb), ("ask", isa)):
        tsm = ts[m]; i = np.searchsorted(tsm, ends, side="right") - 1; ic = np.clip(i, 0, None)
        ok = (i >= 0) & (ends - tsm[ic] <= MID_MAX_AGE_NS) & (P[m, 0][ic] > 0); idx[lab] = ic; okm[lab] = ok
        feat[f"{lab}1"] = np.where(ok, P[m, 0][ic], np.nan)
        for name in ("deep_q", "deep_o", "conc", "slope"): feat[f"{name}_{lab}"] = np.where(ok, st[name][m][ic], np.nan)
    feat["mid"] = (feat["bid1"] + feat["ask1"]) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        feat["deep_imb_qty"] = (feat["deep_q_bid"] - feat["deep_q_ask"]) / (feat["deep_q_bid"] + feat["deep_q_ask"])
        feat["deep_imb_orders"] = (feat["deep_o_bid"] - feat["deep_o_ask"]) / (feat["deep_o_bid"] + feat["deep_o_ask"])
    feat["slope_diff"] = feat["slope_bid"] - feat["slope_ask"]; feat["conc_diff"] = feat["conc_bid"] - feat["conc_ask"]
    ev = deep_events(ts, side, P, Q); counts = {}
    for kind in COUNT_SIDES:
        for lab in ("bid", "ask"):
            ets = np.array([e[0] for e in ev if e[1] == lab and e[2] == kind], dtype=np.int64)
            bi = np.searchsorted(ends, ets, side="left"); ok = (ets > starts[0]) & (ets <= ends[-1])
            cnt = np.bincount(bi[ok], minlength=nb).astype(np.int32); cs = np.cumsum(cnt); roll = cs - np.concatenate([np.zeros(W, dtype=cs.dtype), cs[:-W]])
            feat[f"{kind}_{lab}"] = cnt; feat[f"{kind}_{lab}_w"] = roll.astype(np.int32); counts[f"{kind}_{lab}"] = int(len(ets))
    out = pd.DataFrame(feat)
    if out_path is not None: out.to_parquet(out_path, index=False)
    summ = {"date": date, "inst": inst, "rows_in": int(len(df)), "bars": nb, "bars_with_valid_mid": int(np.sum(~np.isnan(out.mid))), "crossed_at_bar_end": int(np.sum(out.ask1 - out.bid1 <= 0)),
            "events": counts, "side_bid_value": SIDE_BID, "side_ask_value": SIDE_ASK}
    return out, summ
