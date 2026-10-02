"""Regime filter (ablation rung 1) — CAUSAL rolling indicators.

Three trailing-window indicators, each using PAST bars only (window ends at the
current bar t, never reaches past it). They gate the decision formed at bar t,
which the harness executes at t+1's open — so there is no future leakage.

Regime == "trending" iff  Hurst > H_THRESH  AND  ER > ER_THRESH  AND  ATR_pct > ATR_THRESH.
Thresholds + lookback are fixed in config (NOT tuned here).

NOTE on Hurst: on 5-min intraday it is noisy / low-confidence (short windows,
microstructure). We keep it in the AND-gate for now, but expect the Efficiency
Ratio and ATR-percentile to carry most of the discriminating power; Hurst is the
first thing to reconsider on a later rung.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import Config


def _rolling_hurst(close: np.ndarray, window: int) -> np.ndarray:
    """Rolling Hurst via the variance-of-lagged-differences estimator.

    For a random walk H≈0.5; H>0.5 trending/persistent, H<0.5 mean-reverting.
    Uses only the trailing `window` closes at each t — strictly causal.
    """
    n = len(close)
    out = np.full(n, np.nan)
    max_lag = max(3, min(20, window // 2))
    lags = np.arange(2, max_lag)
    log_lags = np.log(lags)
    for t in range(window - 1, n):
        w = close[t - window + 1 : t + 1]
        tau = np.empty(len(lags))
        for j, lag in enumerate(lags):
            d = w[lag:] - w[:-lag]
            tau[j] = np.sqrt(np.std(d)) if d.size > 1 else np.nan
        mask = tau > 0
        if mask.sum() < 2:
            continue
        # slope of log(sqrt(std(diff))) vs log(lag), ×2  →  Hurst exponent
        out[t] = np.polyfit(log_lags[mask], np.log(tau[mask]), 1)[0] * 2.0
    return out


def _efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    """Kaufman ER = |net move over window| / sum(|bar-to-bar move|) over window.

    1.0 = perfectly directional, →0 = pure chop. Fully vectorized + causal.
    """
    net_move = close.diff(window).abs()
    path = close.diff().abs().rolling(window).sum()
    return net_move / path.replace(0, np.nan)


def _atr_percentile(df: pd.DataFrame, atr_period: int, window: int) -> pd.Series:
    """Percentile rank (0–100) of the current ATR within the trailing window."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]).abs(),
         (df["high"] - prev_close).abs(),
         (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    # raw=True → x is a numpy window ending at the current bar; x[-1] is "now".
    return atr.rolling(window).apply(lambda x: (x <= x[-1]).mean() * 100.0, raw=True)


def compute_regime(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    lb = config.regime_lookback
    hurst = _rolling_hurst(df["close"].to_numpy(dtype=float), lb)
    er = _efficiency_ratio(df["close"], lb)
    atr_pct = _atr_percentile(df, config.atr_period, lb)

    out = pd.DataFrame(
        {"hurst": hurst, "er": er.to_numpy(), "atr_pct": atr_pct.to_numpy()},
        index=df.index,
    )
    out["trending"] = (
        (out["hurst"] > config.hurst_thresh)
        & (out["er"] > config.er_thresh)
        & (out["atr_pct"] > config.atr_pct_thresh)
    ).fillna(False)
    return out


def _rolling_pctrank(s: pd.Series, window: int) -> pd.Series:
    """Trailing percentile rank in [0,1] of the current value within its own
    rolling window (past bars only; window ends at t). Self-calibrating."""
    return s.rolling(window).apply(lambda x: (x <= x[-1]).mean(), raw=True)


def regime_score(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Continuous, causal, SELF-CALIBRATING regime score in [0,1].

    Each raw indicator (Hurst, ER, ATR) is converted to its trailing percentile
    rank within its own rolling lookback — so there are no absolute magic
    thresholds; "high" is defined relative to the instrument's own recent
    history/era. regime_score = mean of the three sub-ranks.

    ER is expected to dominate the signal; Hurst is low-confidence on 5-min
    (median Hurst ≈ 0.38 here) and mostly adds noise to the average — its rank
    is kept for transparency, not because we trust it.
    """
    lb = config.regime_lookback
    hurst = pd.Series(_rolling_hurst(df["close"].to_numpy(dtype=float), lb), index=df.index)
    er = _efficiency_ratio(df["close"], lb)

    hurst_rank = _rolling_pctrank(hurst, lb)
    er_rank = _rolling_pctrank(er, lb)
    atr_rank = _atr_percentile(df, config.atr_period, lb) / 100.0  # already a trailing rank

    ranks = pd.concat({"hurst_rank": hurst_rank, "er_rank": er_rank, "atr_rank": atr_rank}, axis=1)
    score = ranks.mean(axis=1)
    score[ranks.isna().any(axis=1)] = float("nan")  # require all three valid
    ranks["regime_score"] = score
    return ranks


def make_regime_signal(base_fn, config: Config):
    """Wrap a baseline signal_fn: keep its position only when regime is trending,
    otherwise flat. Both long-only and long/short bases work unchanged."""

    def _signal(df: pd.DataFrame) -> pd.Series:
        trending = compute_regime(df, config)["trending"]
        base = base_fn(df)
        return base.where(trending, 0).astype(int)

    return _signal
