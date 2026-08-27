"""Baseline signal: price vs session VWAP.

Deliberately trivial — this is the pipeline smoke-test rung, NOT an edge. RVOL /
regime / structure filters are later ablation rungs, not here.

Both variants are causal: session VWAP at bar t uses only bars ≤ t within the
same day, and the harness executes the resulting position at t+1's open.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Cumulative VWAP that RESETS each trading day."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    day = pd.Index(df.index.date)
    cum_pv = (typical * df["volume"]).groupby(day).cumsum()
    cum_v = df["volume"].groupby(day).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    # Early-session bars with zero cumulative volume → fall back to typical price.
    return pd.Series(np.where(cum_v.to_numpy() > 0, vwap.to_numpy(), typical.to_numpy()),
                     index=df.index)


def vwap_long_only(df: pd.DataFrame) -> pd.Series:
    """+1 (long) when close > session VWAP, else 0 (flat)."""
    v = session_vwap(df)
    return (df["close"] > v).astype(int)


def vwap_long_short(df: pd.DataFrame) -> pd.Series:
    """+1 above VWAP, -1 below, 0 exactly on it."""
    v = session_vwap(df)
    pos = pd.Series(0, index=df.index, dtype=int)
    pos[df["close"] > v] = 1
    pos[df["close"] < v] = -1
    return pos
