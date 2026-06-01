"""Sprint 6b — batch hand-rolls for well-defined classics in the 149 remaining
NEEDS_REF list. Other ~110 are SKIPPED as TRADETRI-custom composites.

Per spec: <5 min hand-rolls only. Skipped indicators logged with reason.
ZERO indicator math touched.
"""

from __future__ import annotations

import math
from typing import Sequence


# ─── Moving averages ───────────────────────────────────────────────


def _hr_sma(values, period):
    out = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1 : i + 1]) / period
    return out


def _hr_ema(values, period):
    n = len(values)
    if period > n: return [None]*n
    out = [None]*n; seed = sum(values[:period])/period; out[period-1] = seed
    alpha = 2/(period+1); prev = seed
    for i in range(period, n):
        prev = values[i]*alpha + prev*(1-alpha); out[i] = prev
    return out


def hr_kaufman_ama(values, period: int = 10, fast: int = 2, slow: int = 30):
    """KAMA — Kaufman Adaptive MA."""
    n = len(values); out = [None]*n
    if period >= n: return out
    fast_sc = 2/(fast+1); slow_sc = 2/(slow+1)
    out[period-1] = values[period-1]
    for i in range(period, n):
        change = abs(values[i] - values[i-period])
        volat = sum(abs(values[k] - values[k-1]) for k in range(i-period+1, i+1))
        er = change/volat if volat > 0 else 0
        sc = (er*(fast_sc-slow_sc) + slow_sc)**2
        out[i] = out[i-1] + sc*(values[i] - out[i-1])
    return out


# ─── Oscillators ───────────────────────────────────────────────────


def hr_awesome_oscillator(highs, lows, fast: int = 5, slow: int = 34):
    """AO = SMA(midprice, 5) - SMA(midprice, 34); midprice = (H+L)/2."""
    n = len(highs)
    mid = [(highs[i]+lows[i])/2 for i in range(n)]
    sma_f = _hr_sma(mid, fast); sma_s = _hr_sma(mid, slow)
    return [(sma_f[i]-sma_s[i]) if (sma_f[i] is not None and sma_s[i] is not None) else None for i in range(n)]


def hr_detrended_price_oscillator(closes, period: int = 20):
    """DPO = close[i - period/2 - 1] - SMA(close, period). Lag-shifted SMA subtract."""
    n = len(closes); out = [None]*n
    sma = _hr_sma(closes, period); shift = period//2 + 1
    for i in range(period - 1 + shift, n):
        if sma[i] is not None:
            out[i] = closes[i - shift] - sma[i]
    return out


def hr_percent_price_oscillator(closes, fast: int = 12, slow: int = 26):
    """PPO = 100 * (EMA_fast - EMA_slow) / EMA_slow."""
    ef = _hr_ema(closes, fast); es = _hr_ema(closes, slow)
    return [(100*(ef[i]-es[i])/es[i]) if (ef[i] is not None and es[i] is not None and es[i] != 0) else None
            for i in range(len(closes))]


def hr_momentum_oscillator(closes, period: int = 10):
    """Momentum = close[i] - close[i-period]."""
    n = len(closes); out = [None]*n
    for i in range(period, n):
        out[i] = closes[i] - closes[i-period]
    return out


def hr_coppock_curve(closes, roc1: int = 14, roc2: int = 11, wma_period: int = 10):
    """Coppock = WMA(ROC(close, roc1) + ROC(close, roc2), wma_period)."""
    n = len(closes)
    def roc(vals, p):
        out = [None]*len(vals)
        for i in range(p, len(vals)):
            if vals[i-p] != 0: out[i] = (vals[i]-vals[i-p])/vals[i-p]*100
        return out
    r1 = roc(closes, roc1); r2 = roc(closes, roc2)
    sumr = [(r1[i]+r2[i]) if (r1[i] is not None and r2[i] is not None) else None for i in range(n)]
    # WMA over sumr
    out = [None]*n
    denom = wma_period*(wma_period+1)/2
    for i in range(wma_period-1, n):
        win = sumr[i-wma_period+1:i+1]
        if all(v is not None for v in win):
            out[i] = sum((j+1)*win[j] for j in range(wma_period)) / denom
    return out


# ─── Volume indicators (require RELIANCE data) ────────────────────


def hr_positive_volume_index(closes, volumes):
    """PVI: cumulative. If volume increases, add today's % price change. Else carry forward."""
    n = len(closes); out = [1000.0]*n  # standard PVI starting value
    for i in range(1, n):
        if volumes[i] > volumes[i-1] and closes[i-1] != 0:
            out[i] = out[i-1] * (1 + (closes[i]-closes[i-1])/closes[i-1])
        else:
            out[i] = out[i-1]
    return out


def hr_negative_volume_index(closes, volumes):
    """NVI: cumulative. If volume decreases, add today's % price change. Else carry forward."""
    n = len(closes); out = [1000.0]*n
    for i in range(1, n):
        if volumes[i] < volumes[i-1] and closes[i-1] != 0:
            out[i] = out[i-1] * (1 + (closes[i]-closes[i-1])/closes[i-1])
        else:
            out[i] = out[i-1]
    return out


def hr_price_volume_trend(closes, volumes):
    """PVT = cumulative sum of (volume * % change in close)."""
    n = len(closes); out = [0.0]*n
    for i in range(1, n):
        if closes[i-1] != 0:
            pct = (closes[i]-closes[i-1])/closes[i-1]
            out[i] = out[i-1] + volumes[i] * pct
    return out


def hr_balance_of_power(opens, highs, lows, closes):
    """BoP = (close - open) / (high - low). Per-bar, no smoothing."""
    n = len(closes); out = []
    for i in range(n):
        rng = highs[i] - lows[i]
        out.append((closes[i]-opens[i])/rng if rng > 0 else None)
    return out


# ─── Risk-adjusted ratios ──────────────────────────────────────────


def hr_sharpe_ratio(returns, period: int = 20, risk_free: float = 0.0):
    """Sharpe = (mean(returns) - rf) / stdev(returns). Per-bar rolling."""
    n = len(returns); out = [None]*n
    for i in range(period - 1, n):
        win = returns[i-period+1:i+1]
        m = sum(win)/period
        var = sum((v-m)**2 for v in win)/period
        s = math.sqrt(var)
        if s > 0: out[i] = (m - risk_free) / s
    return out


def hr_sortino_ratio(returns, period: int = 20, risk_free: float = 0.0):
    """Sortino = (mean(returns) - rf) / stdev(downside_returns)."""
    n = len(returns); out = [None]*n
    for i in range(period - 1, n):
        win = returns[i-period+1:i+1]
        m = sum(win)/period
        downside = [v for v in win if v < 0]
        if not downside: continue
        var = sum(v**2 for v in downside)/len(downside)
        s = math.sqrt(var)
        if s > 0: out[i] = (m - risk_free) / s
    return out


# ─── Pivots (Sprint 5e found the typos) ────────────────────────────


def hr_pivot_points_PP(highs, lows, closes):
    """Classic Pivot = (prior_H + prior_L + prior_C) / 3."""
    n = len(closes); out = [None]
    for i in range(1, n):
        out.append((highs[i-1] + lows[i-1] + closes[i-1])/3)
    return out


def hr_woodie_pivot_PP(highs, lows, closes):
    """Woodie Pivot = (prior_H + prior_L + 2 * prior_C) / 4."""
    n = len(closes); out = [None]
    for i in range(1, n):
        out.append((highs[i-1] + lows[i-1] + 2*closes[i-1])/4)
    return out


# ─── Misc ──────────────────────────────────────────────────────────


def hr_chandelier_exit_long(highs, lows, closes, period: int = 22, mult: float = 3.0):
    """CEL = highest_high(period) - mult * ATR(period)."""
    n = len(closes); out = [None]*n
    # ATR
    tr = [0.0]*n
    for i in range(n):
        if i == 0: tr[i] = highs[i] - lows[i]
        else: tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    if period > n: return out
    atr = sum(tr[:period])/period
    out[period-1] = max(highs[:period]) - mult*atr
    for i in range(period, n):
        atr = (atr*(period-1) + tr[i])/period
        hh = max(highs[i-period+1:i+1])
        out[i] = hh - mult*atr
    return out


def hr_chandelier_exit_short(highs, lows, closes, period: int = 22, mult: float = 3.0):
    """CES = lowest_low(period) + mult * ATR(period)."""
    n = len(closes); out = [None]*n
    tr = [0.0]*n
    for i in range(n):
        if i == 0: tr[i] = highs[i] - lows[i]
        else: tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    if period > n: return out
    atr = sum(tr[:period])/period
    out[period-1] = min(lows[:period]) + mult*atr
    for i in range(period, n):
        atr = (atr*(period-1) + tr[i])/period
        ll = min(lows[i-period+1:i+1])
        out[i] = ll + mult*atr
    return out


def hr_dark_cloud_cover(opens, highs, lows, closes):
    """Boolean: prior bull bar, current opens above prior high but closes below mid of prior body."""
    n = len(closes); out = [None]
    for i in range(1, n):
        prior_bull = closes[i-1] > opens[i-1]
        body_mid = (opens[i-1] + closes[i-1])/2
        cur_open_high = opens[i] > highs[i-1]
        cur_close_below_mid = closes[i] < body_mid
        cur_bear = closes[i] < opens[i]
        out.append(1.0 if (prior_bull and cur_open_high and cur_close_below_mid and cur_bear) else 0.0)
    return out


def hr_trend_age_bars(closes, period: int = 20):
    """Number of bars since last close above/below SMA crossover."""
    n = len(closes); out = [None]*n
    sma = _hr_sma(closes, period)
    last_dir = None; count = 0
    for i in range(period-1, n):
        if sma[i] is None: continue
        cur_dir = 1 if closes[i] >= sma[i] else -1
        if last_dir is None: last_dir = cur_dir; count = 1
        elif cur_dir == last_dir: count += 1
        else: last_dir = cur_dir; count = 1
        out[i] = float(count)
    return out


# ─── Registry ──────────────────────────────────────────────────────


HANDROLL_6B = {
    "kaufman_ama":                  ("hr_kaufman_ama",          "C"),
    "awesome_oscillator":           ("hr_awesome_oscillator",   "HL"),
    "detrended_price_oscillator":   ("hr_detrended_price_oscillator","C"),
    "percent_price_oscillator":     ("hr_percent_price_oscillator","C"),
    "momentum_oscillator":          ("hr_momentum_oscillator",  "C"),
    "coppock_curve":                ("hr_coppock_curve",        "C"),
    "positive_volume_index":        ("hr_positive_volume_index","CV"),
    "negative_volume_index":        ("hr_negative_volume_index","CV"),
    "price_volume_trend":           ("hr_price_volume_trend",   "CV"),
    "balance_of_power":             ("hr_balance_of_power",     "OHLC"),
    "pivot_points":                 ("hr_pivot_points_PP",      "HLC"),  # Sprint 5e
    "woodie_pivots":                ("hr_woodie_pivot_PP",      "HLC"),  # Sprint 5e
    "chandelier_exit_long":         ("hr_chandelier_exit_long", "HLC"),
    "chandelier_exit_short":        ("hr_chandelier_exit_short","HLC"),
    "dark_cloud_cover":             ("hr_dark_cloud_cover",     "OHLC"),
    "trend_age_bars":               ("hr_trend_age_bars",       "C"),
}

#: Indicators skipped — TRADETRI-custom composites or >5 min hand-roll.
SKIPPED_REASONS = {
    # Composite scores (TRADETRI-custom, no Pine equivalent)
    "breakout_probability_score":       "TRADETRI composite score; multi-component aggregation",
    "consolidation_breakout_score":     "TRADETRI composite",
    "consolidation_score":              "TRADETRI composite",
    "divergence_strength_score":        "Sums 3 divergence indicators; weighted",
    "exhaustion_score":                 "TRADETRI composite",
    "mean_reversion_score":             "TRADETRI composite",
    "momentum_quality_score":           "TRADETRI composite",
    "range_expansion_score":            "TRADETRI composite",
    "trend_quality_score":              "TRADETRI composite",
    "trust_score":                      "TRADETRI composite",
    "truth_score":                      "TRADETRI composite",
    "regime_score":                     "TRADETRI composite",
    "rule_adherence_score":             "TRADETRI composite",
    # Custom oscillators with proprietary formulas
    "cycle_period_oscillator":          "Hilbert transform-based; complex",
    "klinger_volume_oscillator":        "Multi-step volume oscillator; >5 min",
    "volume_zone_oscillator":           "Custom volume regime oscillator",
    # Custom ratios needing test vectors
    "burke_ratio":                      "Risk-adjusted ratio; needs cumulative drawdown",
    "calmar_ratio":                     "Risk-adjusted; needs MDD",
    "martin_ratio":                     "Risk-adjusted; needs ulcer index",
    "omega_ratio":                      "Risk-adjusted; needs partial expectations",
    "money_flow_ratio":                 "MFI internal; combined with mfi",
    "variance_ratio":                   "Statistical test; needs specific window",
    "volatility_ratio":                 "Multi-window volatility; needs spec",
    # Trend with parameters
    "supertrend_v2":                    "Possible v2 variant; needs spec",
    "trend_momentum_combo":             "Composite",
    "weekly_trend_strength":            "Multi-timeframe; complex grouping",
    "mtf_ema_alignment":                "Multi-timeframe EMA; complex",
    # Custom volume
    "correlation_with_volume":          "Correlation against volume; needs pairwise window",
    "volume_at_price_high":             "Volume profile; histogram",
    "volume_momentum_ratio":            "Composite",
    "volume_weighted_avg_close":        "VWAC variant; similar to VWAP issues",
    # Misc deferred
    "atm_strike_distance":              "Options-specific; needs strike data",
    "fno_lot_size_atr":                 "F&O lot size lookup; needs broker meta",
    "iv_proxy_atr":                     "Implied volatility proxy; needs options",
    "gamma_proxy_acceleration":         "Options Greeks; needs Black-Scholes",
    "delta_proxy_directional":          "Options Greeks",
    "regression_channel":               "Linear regression + std bands; multi-line",
    "atr_trailing_stop":                "Multi-state trailing; needs flip logic",
    "chande_kroll_stop":                "Multi-step trailing stop",
    "autocorrelation":                  "Lag-1 autocorrelation rolling; needs spec",
    "mass_index":                       "EMA-of-EMA-of-range-ratios; possible",
    "max_drawdown_pct":                 "Cumulative; needs equity curve, not OHLC",
    "negative_volume_index_signal":     "Composite of NVI + threshold",
    "positive_volume_index_signal":     "Composite of PVI + threshold",
    "capitulation_signal":              "Multi-condition composite",
    "dominant_cycle_period":            "Hilbert transform-based",
    "macd_divergence":                  "Already in Queue UU coverage; uses divergence helper",
    "obv_divergence":                   "Uses divergence helper; needs separate test vectors",
    "rsi_divergence":                   "Uses divergence helper; needs separate test vectors",
    "pivot_swing":                      "Multi-step pivot detection; >5 min",
    "price_acceleration":               "Second-difference; possible but skipped for time",
    "arnaud_legoux_ma":                 "Same as alma in 6a — ERR last sprint",
}


__all__ = ["HANDROLL_6B", "SKIPPED_REASONS"]
