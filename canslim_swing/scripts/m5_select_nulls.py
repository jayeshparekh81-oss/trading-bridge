#!/usr/bin/env python3
"""M5 STAGE C (selection) + STAGE D (null battery). BUILD HALF ONLY.

Selection rule was pre-registered and is applied mechanically:
  eligible  : build trades >= 50 AND build maxDD <= 15%
  champion  : highest build expectancy-R among eligible configs whose one-step
              neighbours (every single-notch move in ANY dimension) are >= 60%
              positive-expectancy. If none clears 60%, take the highest-expectancy
              config with the greatest positive-neighbour share AND SAY SO.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_engine as E  # noqa: E402
import m5_sweep as S  # noqa: E402

TRACK = Path(__file__).resolve().parents[1]
OUT = TRACK / "data" / "m5"
MIN_TRADES, MAX_DD = 50, -0.15
NEIGHBOUR_BAR = 0.60

DIMS = {"exit": S.EXITS, "stop": S.STOPS, "c_growth": S.GROWTH,
        "floor": ["none", "p25", "p50"], "rs": S.RS,
        "mfilter": S.MFILTER, "volume": S.VOLUME}


def neighbours(row: pd.Series, df: pd.DataFrame) -> pd.DataFrame:
    """Every config one single notch away in exactly one dimension."""
    masks = []
    for dim, levels in DIMS.items():
        cur = row[dim]
        try:
            i = levels.index(cur)
        except ValueError:
            i = levels.index(type(levels[0])(cur))
        for j in (i - 1, i + 1):
            if 0 <= j < len(levels):
                m = pd.Series(True, index=df.index)
                for d2 in DIMS:
                    m &= (df[d2] == (levels[j] if d2 == dim else row[d2]))
                masks.append(m)
    if not masks:
        return df.iloc[:0]
    return df[np.logical_or.reduce([m.to_numpy() for m in masks])]


def select(df: pd.DataFrame) -> dict:
    elig = df[(df["trades"] >= MIN_TRADES) & (df["maxdd"] >= MAX_DD)].copy()
    out = {"n_all": len(df), "n_elig": len(elig),
           "pct_positive_all": 100 * (df["exp_r"] > 0).mean(),
           "pct_positive_elig": 100 * (elig["exp_r"] > 0).mean() if len(elig) else np.nan}
    if elig.empty:
        out["champion"] = None
        return out
    elig = elig.sort_values("exp_r", ascending=False)
    shares = {}
    for idx, row in elig.iterrows():
        nb = neighbours(row, df)
        shares[idx] = ((nb["exp_r"] > 0).mean() if len(nb) else 0.0, len(nb))
    elig["nb_share"] = [shares[i][0] for i in elig.index]
    elig["nb_n"] = [shares[i][1] for i in elig.index]
    clear = elig[elig["nb_share"] >= NEIGHBOUR_BAR]
    if len(clear):
        champ = clear.iloc[0]
        out["rule_relaxed"] = False
    else:
        best = elig["nb_share"].max()
        champ = elig[elig["nb_share"] == best].iloc[0]
        out["rule_relaxed"] = True
        out["best_nb_share"] = float(best)
    out["champion"] = champ
    out["eligible"] = elig
    return out


# ------------------------------------------------------------------ STAGE D
def random_entry_null(champ_trades: pd.DataFrame, cf: pd.DataFrame, px: dict,
                      calendar, stop_rule="8", n_iter=500, seed=20260802) -> dict:
    """Same universe, same trade count, same hold-duration distribution, entries
    on RANDOM days that were NOT candidate days. Costs and slippage identical."""
    rng = np.random.default_rng(seed)
    n = len(champ_trades)
    holds = champ_trades["days_held"].to_numpy()
    cand_pairs = set(zip(cf["date"], cf["symbol"]))
    syms = sorted({s for s in px})
    cal = list(calendar)
    exps = []
    for _ in range(n_iter):
        rs = []
        for k in range(n):
            for _try in range(40):
                sym = syms[rng.integers(len(syms))]
                P = px[sym]
                if len(P["idx"]) < 60:
                    continue
                i = int(rng.integers(50, len(P["idx"]) - 1))
                day = P["idx"][i]
                if (day, sym) in cand_pairs:
                    continue
                hold = int(holds[rng.integers(len(holds))])
                j = min(i + max(hold, 1), len(P["c"]) - 1)
                entry = P["o"][i] * (1 + 0.0005)
                exitp = P["c"][j] * (1 - 0.0005)
                # R basis must match the CHAMPION's stop rule, not a hardcoded 8%,
                # or the null is scored on a different denominator than the ledger.
                if stop_rule == "5":
                    frac = 0.05
                elif stop_rule == "8":
                    frac = 0.08
                else:
                    a = P["atr20"][i]
                    frac = (min(2 * a, entry * 0.10) / entry) if (a == a and a > 0) else 0.08
                rs.append((exitp / entry - 1.0) / frac)
                break
        if rs:
            exps.append(float(np.mean(rs)))
    return {"dist": np.array(exps), "n_iter": len(exps)}


def mc_drawdown(champ_trades: pd.DataFrame, n_iter=10000, seed=20260802) -> np.ndarray:
    """Resample the champion's own trade sequence to get a DD distribution."""
    rng = np.random.default_rng(seed)
    r = champ_trades["r_multiple"].to_numpy()
    n = len(r)
    dds = np.empty(n_iter)
    for k in range(n_iter):
        s = r[rng.integers(0, n, n)]
        eq = np.cumsum(s)
        peak = np.maximum.accumulate(np.maximum(eq, 0))
        dds[k] = float((eq - peak).min())
    return dds
