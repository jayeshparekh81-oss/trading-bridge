"""Regime module (Module R6).

Inputs: India-VIX band (knobs), trend (MA-slope knob), participant-OI bias (manual
override until R5-nightly automation), and net-GEX sign + gamma-flip distance from
R5 (the GEX regime FLAG is inert until calibrated). Output: a regime_state
(direction bull/bear/neutral + vol_band low/normal/high) consumed by (a) the regime
score component and (b) the asymmetric gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_BIAS = {"long": "bull", "short": "bear", "bull": "bull", "bear": "bear", "neutral": "neutral"}


@dataclass
class RegimeState:
    direction: str            # bull | bear | neutral
    vol_band: str             # low | normal | high
    net_gex_sign: Optional[int] = None
    gamma_flip_distance: Optional[float] = None
    trend: str = "neutral"


def _vol_band(vix, low, high) -> str:
    if vix is None:
        return "normal"
    if vix < low:
        return "low"
    if vix > high:
        return "high"
    return "normal"


def _trend(ma_slope, slope_min) -> str:
    if ma_slope is None:
        return "neutral"
    if ma_slope > slope_min:
        return "bull"
    if ma_slope < -slope_min:
        return "bear"
    return "neutral"


def compute_regime(ctx, cfg) -> RegimeState:
    rc = cfg.regime
    vol = _vol_band(ctx.vix, float(rc["vix_low"]), float(rc["vix_high"]))
    td = _trend(ctx.ma_slope, float(rc["trend_slope_min"]))
    pb = _BIAS.get(str(rc.get("participant_oi_bias", "neutral")), "neutral")
    if pb == "neutral":
        direction = td
    elif pb == td or td == "neutral":
        direction = pb
    else:
        direction = "neutral"        # trend vs participant conflict
    gex_sign = None
    if rc.get("use_gex") and ctx.net_gex is not None:
        gex_sign = 1 if ctx.net_gex > 0 else (-1 if ctx.net_gex < 0 else 0)
    flip_dist = (ctx.gamma_flip - ctx.price) if (ctx.gamma_flip is not None and ctx.price) else None
    return RegimeState(direction=direction, vol_band=vol, net_gex_sign=gex_sign,
                       gamma_flip_distance=flip_dist, trend=td)


_DISABLED = 999_999.0


def apply_asymmetric(base: float, side: str, direction: str, ag: dict) -> float:
    """Escalate (or disable) the counter-trend side's threshold in a strong regime."""
    if not ag.get("enabled"):
        return base
    if side == "short" and direction == "bull":
        return _DISABLED if ag.get("disable_countertrend") \
            else base + float(ag.get("strong_bull_short_penalty", 0))
    if side == "long" and direction == "bear":
        return _DISABLED if ag.get("disable_countertrend") \
            else base + float(ag.get("strong_bear_long_penalty", 0))
    return base
