"""Donchian-channel breakout — a genuinely TREND-FOLLOWING entry.

Diagnostic partner to the VWAP-cross baseline: if the regime-score tercile test
stays null even here, the null is about the score; if it turns monotone, the
earlier null was about the (reversion-flavoured) baseline.

Causality: the channel at bar t is the highest-high / lowest-low of the N bars
*up to t-1* (``.shift(1)`` excludes the current bar). The position formed at
bar t is then executed at t+1's open by the harness — no look-ahead.

State: classic breakout hold — go/stay long after an upper break, flip short
(long/short) or flat (long-only) after a lower break, hold otherwise. The
harness still enforces intraday square-off + no overnight carry on top.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_donchian(n: int, long_short: bool):
    """Return a causal signal_fn(df) -> positions in {-1,0,+1}."""

    def _signal(df: pd.DataFrame) -> pd.Series:
        upper = df["high"].rolling(n).max().shift(1)   # channel excludes current bar
        lower = df["low"].rolling(n).min().shift(1)
        raw = pd.Series(np.nan, index=df.index)
        raw[df["close"] > upper] = 1.0                 # upper break → long
        raw[df["close"] < lower] = -1.0 if long_short else 0.0  # lower break → short / flat
        state = raw.ffill().fillna(0.0)                # hold until an opposite break
        return state.astype(int)

    return _signal
