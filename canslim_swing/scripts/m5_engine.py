#!/usr/bin/env python3
"""M5 shared engine — configurable trade simulator over a partitioned data root.

Same cost model, slippage, 6 slots, 1% risk, 25% cap and chase-cap as M4.
Everything the pre-registered grid varies is a CONFIG field; nothing else moves.

SEALED SAFETY: load_market(root, max_date=...) asserts that no loaded frame
contains a row beyond max_date. The sweep passes the build boundary, so a
harness bug cannot read the future — the rows are not in build/ at all, and the
assertion is a second, independent guard.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
BOUNDARY = pd.Timestamp("2024-12-31")

# ---- fixed (not swept) -----------------------------------------------------
START_EQUITY = 1_000_000.0
MAX_POSITIONS = 6
RISK_PER_TRADE = 0.01
MAX_POSITION_PCT = 0.25
TRIGGER_MULT = 1.001
CHASE_CAP = 1.05
STT, EXCH_TXN, SEBI_FEE, STAMP_BUY = 0.0010, 0.0000297, 0.000001, 0.00015
GST_RATE, BROKERAGE, DP_SELL = 0.18, 0.0, 15.93
STALE_DAYS = 200
# Bump when ANY engine internal changes. The sweep cache is keyed on this, so a
# changed indicator definition can never silently reuse stale results (the
# harness review flagged exactly this hazard).
ENGINE_VERSION = "v2-postreview"


def buy_costs(t: float) -> float:
    e, s = t * EXCH_TXN, t * SEBI_FEE
    return t * STT + e + s + t * STAMP_BUY + GST_RATE * (BROKERAGE + e + s) + BROKERAGE


def sell_costs(t: float) -> float:
    e, s = t * EXCH_TXN, t * SEBI_FEE
    return t * STT + e + s + GST_RATE * (BROKERAGE + e + s) + BROKERAGE + DP_SELL


@dataclass(frozen=True)
class Config:
    exit: str = "E1"          # E1..E7
    stop: str = "8"           # "5" | "8" | "atr"
    c_growth: float = 1.25    # 1.25 | 1.30
    base_floor: float = 0.0   # 0 | p25 | p50 (absolute Rs)
    rs_min: float = 80.0      # 70 | 80 | 90
    mfilter: str = "dma_entry"   # dma_entry | dma_force | ema10m
    volume: str = "none"      # none | violation
    slippage: float = 0.0005

    def key(self) -> str:
        return (f"{ENGINE_VERSION}|{self.exit}|{self.stop}|{self.c_growth}|"
                f"{self.base_floor:.4f}|{self.rs_min}|{self.mfilter}|{self.volume}|{self.slippage}")


# ---------------------------------------------------------------- market load
def load_market(root: Path, max_date: pd.Timestamp | None = None) -> dict:
    scan = pd.read_parquet(root / "daily_scan.parquet")
    nifty = pd.read_parquet(root / "nifty_daily.parquet")
    eps = pd.read_parquet(root / "eps_quarterly.parquet")
    if max_date is not None:
        assert scan["date"].max() <= max_date, f"SEALED LEAK: scan {scan['date'].max()}"
        assert nifty.index.max() <= max_date, f"SEALED LEAK: nifty {nifty.index.max()}"
        assert eps["announce_ts"].max() <= max_date + pd.Timedelta(days=1), "SEALED LEAK: eps"

    universe = sorted(scan["symbol"].unique())
    px = {}
    for sym in universe:
        d = pd.read_parquet(root / "daily" / f"{sym}.parquet").sort_index()
        if max_date is not None:
            assert d.index.max() <= max_date, f"SEALED LEAK: {sym} {d.index.max()}"
        c, h, l = d["close"], d["high"], d["low"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        px[sym] = {
            "idx": d.index, "pos": {dt: i for i, dt in enumerate(d.index)},
            "o": d["open"].to_numpy(float), "h": h.to_numpy(float),
            "l": l.to_numpy(float), "c": c.to_numpy(float),
            "sma50": c.rolling(50).mean().to_numpy(float),
            "ema21": c.ewm(span=21, adjust=False).mean().to_numpy(float),
            "atr20": tr.rolling(20).mean().shift(1).to_numpy(float),  # prior-day ATR
            "low20": l.rolling(20).min().shift(1).to_numpy(float),   # prior 20 sessions
            "vol": d["volume"].to_numpy(float),
            "vol50": d["volume"].rolling(50).mean().shift(1).to_numpy(float),
        }

    # market filters
    non = (nifty["close"] > nifty["sma200"])
    m_close = nifty["close"].resample("ME").last()
    ema10 = m_close.ewm(span=10, adjust=False).mean()
    # point-in-time: day D uses the EMA through the PREVIOUS completed month
    prev_me = (nifty.index.to_period("M") - 1).to_timestamp("M")
    ema_daily = pd.Series(ema10.reindex(prev_me).to_numpy(), index=nifty.index)
    n_ema = (nifty["close"] > ema_daily)
    return {"scan": scan, "px": px, "universe": universe,
            "nifty_dma": non, "nifty_ema10m": n_ema, "eps": eps}


def eps_base_table(mkt: dict) -> pd.DataFrame:
    """Per (symbol, day) latest/base quarterly EPS as known that day.

    Recomputed here (not read from M3) because the sweep needs the BASE EPS VALUE
    for the base-floor dimension, which the M3 scan does not store. Same rules as
    M3: canonical rows of the symbol's chosen series, cumulative-max period_end
    over announcement order, 4-quarters-back match by (year, month), staleness.
    """
    eps, scan = mkt["eps"], mkt["scan"]
    canon = eps[~eps["is_revision"]]
    rows = []
    for sym, sc in scan.groupby("symbol"):
        s = canon[canon["symbol"] == sym]
        n_c = s[(s["variant"] == "cons") & (s["eps_basic_cons"].notna()
                                            | s["eps_dil_cons"].notna())]["period_end"].nunique()
        n_s = s[(s["variant"] == "stand") & (s["eps_basic_stand"].notna()
                                             | s["eps_dil_stand"].notna())]["period_end"].nunique()
        series = "cons" if n_c >= n_s else "stand"
        bcol, dcol = (("eps_basic_cons", "eps_dil_cons") if series == "cons"
                      else ("eps_basic_stand", "eps_dil_stand"))
        t = s[s["variant"] == series].copy()
        t = t[t["announce_ts"].notna()]
        t["eps"] = t[bcol].where(t[bcol].notna(), t[dcol])
        t = t[t["eps"].notna()].sort_values("announce_ts").drop_duplicates("period_end", keep="first")
        days = np.sort(sc["date"].unique())
        if t.empty:
            for d in days:
                rows.append((sym, d, np.nan, np.nan))
            continue
        ann = t["announce_ts"].to_numpy("datetime64[ns]")
        pe = t["period_end"].to_numpy("datetime64[ns]")
        known = np.maximum.accumulate(pe)
        eps_by_pe = dict(zip(t["period_end"], t["eps"]))
        idx = np.searchsorted(ann, (pd.DatetimeIndex(days) + pd.Timedelta(days=1)).to_numpy(
            "datetime64[ns]"), side="left") - 1
        for i, d in enumerate(days):
            j = idx[i]
            if j < 0:
                rows.append((sym, d, np.nan, np.nan))
                continue
            lpe = pd.Timestamp(known[j])
            if (pd.Timestamp(d) - lpe).days > STALE_DAYS:
                rows.append((sym, d, np.nan, np.nan))
                continue
            bpe = lpe - pd.DateOffset(years=1)
            bkey = next((p for p in eps_by_pe if p.year == bpe.year and p.month == bpe.month), None)
            rows.append((sym, d, eps_by_pe[lpe], eps_by_pe[bkey] if bkey is not None else np.nan))
    return pd.DataFrame(rows, columns=["symbol", "date", "eps_latest", "eps_base"])


def build_candidate_frame(mkt: dict, eps_tab: pd.DataFrame) -> pd.DataFrame:
    """Scan rows + base EPS, with the config-independent gates precomputed."""
    s = mkt["scan"].merge(eps_tab, on=["symbol", "date"], how="left")
    s["t1_7"] = s[["t1", "t2", "t3", "t4", "t5", "t6", "t7"]].all(axis=1)
    s["dma_on"] = s["date"].map(mkt["nifty_dma"]).fillna(False).astype(bool)
    s["ema10m_on"] = s["date"].map(mkt["nifty_ema10m"]).fillna(False).astype(bool)
    return s[["date", "symbol", "pivot", "rs_pct", "t1_7", "base_pass",
              "eps_latest", "eps_base", "dma_on", "ema10m_on"]]


# ---------------------------------------------------------------- simulation
def simulate(cfg: Config, cf: pd.DataFrame, px: dict, calendar, warm=None) -> dict:
    """Run one config. Returns trades + equity curve."""
    growth_ok = (cf["eps_latest"] >= cfg.c_growth * cf["eps_base"]) & (cf["eps_base"] > 0)
    floor_ok = cf["eps_base"] >= cfg.base_floor if cfg.base_floor > 0 else True
    mcol = {"dma_entry": "dma_on", "dma_force": "dma_on", "ema10m": "ema10m_on"}[cfg.mfilter]
    live = cf[cf["t1_7"] & cf["base_pass"] & growth_ok & floor_ok
              & (cf["rs_pct"] >= cfg.rs_min) & cf[mcol]]
    cand_by_day = {d: g.sort_values("rs_pct", ascending=False)
                   for d, g in live.groupby("date")}
    mkt_on = (cf.drop_duplicates("date").set_index("date")[mcol]
              if cfg.mfilter == "dma_force" else None)

    cash = START_EQUITY if warm is None else warm["cash"]
    positions = {k: dict(v) for k, v in warm["positions"].items()} if warm else {}
    trades, eq_rows, pending = [], [], []
    slip = cfg.slippage
    prev_day = None

    for day in calendar:
        force_close = bool(mkt_on is not None and prev_day is not None
                           and not bool(mkt_on.get(prev_day, True)))
        # ---- exits
        for sym in list(positions):
            p = positions[sym]
            P = px[sym]
            i = P["pos"].get(day)
            if i is None:
                continue
            o, h, l, c = P["o"][i], P["h"][i], P["l"][i], P["c"][i]
            price = reason = None
            qty_frac = 1.0
            if force_close:
                price, reason = o, "mkt_force"
            elif p["armed"]:
                price, reason = o, p["armed"]
                qty_frac = p["armed_frac"]
            elif o <= p["stop"]:
                price, reason = o, "stop"
            elif l <= p["stop"]:
                price, reason = p["stop"], "stop"
            elif p["target"] and o >= p["target"]:
                price, reason = o, "target"
            elif p["target"] and h >= p["target"]:
                price, reason = p["target"], "target"
            if price is not None:
                cash += _close(trades, p, sym, day, price, reason, slip, qty_frac, positions)
                if qty_frac >= 1.0 or p["qty"] <= 0:
                    positions.pop(sym, None)
                    continue
                # PARTIAL fill only: the retained shares are still exposed today,
                # so they must face the stop/target in this same session rather
                # than being skipped until tomorrow.
                p["armed"] = None
                if o <= p["stop"] or l <= p["stop"]:
                    px_ = o if o <= p["stop"] else p["stop"]
                    cash += _close(trades, p, sym, day, px_, "stop", slip, 1.0, positions)
                    positions.pop(sym, None)
                    continue
                if p["target"] and (o >= p["target"] or h >= p["target"]):
                    px_ = o if o >= p["target"] else p["target"]
                    cash += _close(trades, p, sym, day, px_, "target", slip, 1.0, positions)
                    positions.pop(sym, None)
                continue
            # E5 free-roll: +2R -> sell half, stop to breakeven. The stop check
            # above already ran (pessimistic ordering), so the moved breakeven
            # stop becomes live from the NEXT session — the day's low may predate
            # the +2R touch and we do not assume an intraday path.
            if cfg.exit == "E5" and not p["half"] and h >= p["r2_price"]:
                cash += _close(trades, p, sym, day, p["r2_price"], "half_2R", slip, 0.5, positions)
                p["half"] = True
                p["stop"] = p["entry"]
                if p["qty"] <= 0:
                    positions.pop(sym, None)

        # ---- entries
        if pending:
            mtm_prev = 0.0
            for s2, p2 in positions.items():
                mtm_prev += p2["qty"] * p2.get("last_close", p2["entry"])
            equity_ref = cash + mtm_prev
            for od in pending:
                sym = od["symbol"]
                P = px[sym]
                i = P["pos"].get(day)
                if i is None:
                    continue
                o, h = P["o"][i], P["h"][i]
                trig, piv = od["trigger"], od["pivot"]
                if o >= trig:
                    if o > piv * CHASE_CAP:
                        continue
                    raw = o
                elif h >= trig:
                    raw = trig
                else:
                    continue
                if len(positions) >= MAX_POSITIONS or sym in positions:
                    continue
                entry = raw * (1 + slip)
                atr = P["atr20"][i]
                if cfg.stop == "5":
                    stop = entry * 0.95
                elif cfg.stop == "8":
                    stop = entry * 0.92
                else:
                    d_atr = 2 * atr if not math.isnan(atr) else entry * 0.08
                    stop = entry - min(d_atr, entry * 0.10)
                if stop >= entry:
                    continue
                risk_amt = RISK_PER_TRADE * equity_ref
                qty = int(math.floor(risk_amt / (entry - stop)))
                qty = min(qty, int(math.floor(MAX_POSITION_PCT * equity_ref / entry)))
                while qty >= 1 and qty * entry + buy_costs(qty * entry) > cash:
                    qty -= 1
                if qty < 1:
                    continue
                turn = qty * entry
                cost = buy_costs(turn)
                cash -= turn + cost
                v50 = P["vol50"][i]
                vr = (P["vol"][i] / v50) if (v50 and not math.isnan(v50) and v50 > 0) else np.nan
                target = entry * 1.25 if cfg.exit in ("E1", "E2", "E7") else None
                positions[sym] = {
                    "qty": qty, "entry": entry, "stop": stop, "target": target,
                    "entry_date": day, "entry_i": i, "entry_cost": cost, "risk_amt": risk_amt,
                    "rs_at_entry": od["rs_pct"], "equity_before": equity_ref, "vol_ratio": vr,
                    "armed": None, "armed_frac": 1.0, "half": False, "peak": P["c"][i],
                    "pivot": piv, "r2_price": entry + 2 * (entry - stop),
                    "t_suspend": False, "last_close": P["c"][i], "ryan_done": False,
                    "pid": f"{sym}|{day:%Y%m%d}", "qty0": qty,
                }
                # fill-day stop/target (M4 lesson: the day's exit sweep ran before
                # this position existed, so it must be checked here)
                p = positions[sym]
                lo, hi = P["l"][i], P["h"][i]
                if lo <= p["stop"]:
                    cash += _close(trades, p, sym, day, p["stop"], "stop", slip, 1.0, positions)
                    positions.pop(sym, None)
                elif p["target"] and hi >= p["target"]:
                    cash += _close(trades, p, sym, day, p["target"], "target", slip, 1.0, positions)
                    positions.pop(sym, None)
        pending = []

        # ---- close: arm next-day exits
        mtm = 0.0
        for sym, p in positions.items():
            P = px[sym]
            i = P["pos"].get(day)
            if i is not None:
                c = P["c"][i]
                p["last_close"] = c
                p["peak"] = max(p["peak"], c)
                held = i - p["entry_i"]
                sma50, ema21, atr, low20 = P["sma50"][i], P["ema21"][i], P["atr20"][i], P["low20"][i]
                arm, frac = None, 1.0
                if cfg.volume == "violation" and held == 0 and not math.isnan(p["vol_ratio"] or np.nan) \
                        and (p["vol_ratio"] or 0) < 1.5:
                    arm = "vol_violation"
                elif cfg.exit == "E2":
                    if not p["t_suspend"] and held <= 15 and c >= p["entry"] * 1.20:
                        p["t_suspend"] = True
                        p["target"] = None          # 8-week rule: hold through +25%
                    if p["t_suspend"] and held >= 40 and not math.isnan(sma50) and c < sma50:
                        arm = "sma50_break"
                    elif not p["t_suspend"] and not math.isnan(sma50) and c < sma50:
                        arm = "sma50_break"
                elif cfg.exit == "E3":
                    trail = p["peak"] - 3 * atr if not math.isnan(atr) else None
                    if trail is not None and c < trail:
                        arm = "chandelier"
                elif cfg.exit == "E4":
                    if not math.isnan(low20) and c < low20:
                        arm = "turtle_low20"
                elif cfg.exit == "E6":
                    if not math.isnan(ema21) and c < ema21:
                        arm = "ema21_break"
                elif cfg.exit in ("E1", "E7"):
                    if not math.isnan(sma50) and c < sma50:
                        arm = "sma50_break"          # full exit dominates
                    elif cfg.exit == "E7" and not p["ryan_done"] and held <= 5 and c < p["pivot"]:
                        arm, frac = "ryan_half", 0.5
                        p["ryan_done"] = True
                elif cfg.exit == "E5":
                    # free-roll: before +2R the STOP is the only exit; the SMA50
                    # trail governs the remainder only after the half is sold.
                    if p["half"] and not math.isnan(sma50) and c < sma50:
                        arm = "sma50_break"
                p["armed"], p["armed_frac"] = arm, frac
            mtm += p["qty"] * p.get("last_close", p["entry"])
        eq_rows.append((day, cash + mtm, cash, mtm, len(positions)))

        # ---- tomorrow's working orders
        g = cand_by_day.get(day)
        pending = ([{"symbol": r.symbol, "pivot": float(r.pivot),
                     "trigger": float(r.pivot) * TRIGGER_MULT, "rs_pct": float(r.rs_pct)}
                    for r in g.itertuples()] if g is not None else [])
        prev_day = day

    last = calendar[-1]
    for sym in list(positions):
        p = positions[sym]
        P = px[sym]
        i = P["pos"].get(last)
        if i is None:
            i = len(P["c"]) - 1
        cash += _close(trades, p, sym, last, P["c"][i], "end-of-data", slip, 1.0, positions)
        positions.pop(sym, None)

    tdf = pd.DataFrame(trades)
    edf = pd.DataFrame(eq_rows, columns=["date", "equity", "cash", "deployed", "n_pos"]).set_index("date")
    return {"trades": tdf, "equity": edf}


def _close(trades, p, sym, day, raw, reason, slip, frac, positions) -> float:
    q = p["qty"] if frac >= 1.0 else max(1, int(p["qty"] * frac))
    price = raw * (1 - slip)
    turn = q * price
    cost = sell_costs(turn)
    entry_cost_share = p["entry_cost"] * (q / p["qty"]) if p["qty"] else 0.0
    gross = q * (price - p["entry"])
    net = gross - entry_cost_share - cost
    trades.append({
        "pid": p["pid"], "symbol": sym, "entry_date": p["entry_date"], "exit_date": day,
        "entry_price": p["entry"], "exit_price": price, "qty": q,
        "gross_pnl": gross, "net_pnl": net,
        "r_multiple": net / p["risk_amt"] if p["risk_amt"] else np.nan,
        "exit_reason": reason, "vol_ratio": p["vol_ratio"], "rs_at_entry": p["rs_at_entry"],
        "days_held": int(np.busday_count(p["entry_date"].date(), day.date())),
        "pct_return": 100 * (price / p["entry"] - 1), "equity_before": p["equity_before"],
        "risk_amt": p["risk_amt"],
    })
    p["qty"] -= q
    p["entry_cost"] -= entry_cost_share
    return turn - cost


def positionize(t: pd.DataFrame) -> pd.DataFrame:
    """Collapse partial-exit LEGS into one row per POSITION.

    Load-bearing for selection: E5/E7 exit in two legs, and scoring each leg as an
    independent trade against the FULL 1%-risk denominator both double-counts the
    trade count and roughly halves expectancy-R — the statistic the pre-registered
    selection rule maximises. R must be (total net PnL of the position) / (the 1%
    risk intended at entry), exactly as for a single-leg trade.
    """
    if t is None or t.empty:
        return t
    g = t.groupby("pid", sort=False)
    out = pd.DataFrame({
        "symbol": g["symbol"].first(), "entry_date": g["entry_date"].first(),
        "exit_date": g["exit_date"].max(), "entry_price": g["entry_price"].first(),
        "qty": g["qty"].sum(), "net_pnl": g["net_pnl"].sum(),
        "gross_pnl": g["gross_pnl"].sum(),
        "risk_amt": g["risk_amt"].first(),
        "exit_reason": g["exit_reason"].last(), "n_legs": g.size(),
        "vol_ratio": g["vol_ratio"].first(), "rs_at_entry": g["rs_at_entry"].first(),
        "days_held": g["days_held"].max(), "equity_before": g["equity_before"].first(),
    }).reset_index(drop=True)
    out["r_multiple"] = out["net_pnl"] / out["risk_amt"].replace(0, np.nan)
    out["pct_return"] = 100 * out["net_pnl"] / (out["entry_price"] * out["qty"]).replace(0, np.nan)
    return out


def metrics(t: pd.DataFrame, e: pd.DataFrame) -> dict:
    """Metrics are computed on POSITIONS, never on legs."""
    t = positionize(t)
    if t is None or t.empty:
        return {"trades": 0, "exp_r": np.nan, "pf": np.nan, "maxdd": np.nan,
                "win": np.nan, "net": 0.0, "cagr": np.nan, "expectancy_rs": np.nan}
    w, l = t[t["net_pnl"] > 0], t[t["net_pnl"] <= 0]
    gp, gl = w["net_pnl"].sum(), -l["net_pnl"].sum()
    eq = e["equity"]
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    return {
        "trades": len(t), "exp_r": t["r_multiple"].mean(),
        "expectancy_rs": t["net_pnl"].mean(),
        "pf": (gp / gl) if gl > 0 else np.inf, "win": 100 * len(w) / len(t),
        "maxdd": float((eq / eq.cummax() - 1).min()), "net": float(t["net_pnl"].sum()),
        "cagr": float((eq.iloc[-1] / eq.iloc[0]) ** (365.25 / days) - 1),
    }
