"""Confluence components (Module R6).

Each is a pure function (ctx, cfg, side) -> activation in [0, 1]. Contribution to
the score is activation * weight (applied by the scorer). Missing inputs (None) ->
0 activation. ``side`` is "long" or "short"; short reads the sell-side mirror.

book_ofi and queue_imbalance are STUB-fed (ctx value None) until Monday's R1 depth
data — they return 0 (neutral) now; the interface is wired for calibration.
"""

from __future__ import annotations

from signals.painmap import trapped_pressure


def _sign(side: str) -> int:
    return 1 if side == "long" else -1


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _per_instrument(v, instrument: str, default: float) -> float:
    """Resolve a scalar-or-per-instrument-dict knob for ``instrument``."""
    if isinstance(v, dict):
        return float(v.get(instrument, v.get("_default", default)))
    return float(v if v is not None else default)


def book_ofi(ctx, cfg, side: str) -> float:
    """GRADED book-OFI (2026-07-15 fix). Was a binary 0/25 gate: _clamp01(signed-0)
    saturated to 1.0 on OFI SIGN alone (re-expressing the day's drift). Now: a
    magnitude FLOOR (ofi_min) filters noise, and the activation is scaled by a typical
    per-BAR OFI magnitude (ofi_scale) so a strong OFI -> ~1.0 and a weak one -> ~0.3.
    Scales are per-instrument, seeded from the MEASURED per-bar distribution (NIFTY med
    ~8.8k, BANKNIFTY ~4.1k) — NOT the per-increment std, which would re-saturate.
    STARTING HYPOTHESIS from 1 day (07-15); to be refined by the 15-day leak-proof test."""
    if ctx.book_ofi is None:                 # depth OFI off / no data -> neutral
        return 0.0
    signed = ctx.book_ofi * _sign(side)
    floor = _per_instrument(cfg.param("ofi_min", 0.0), ctx.instrument, 0.0)
    scale = _per_instrument(cfg.param("ofi_scale", 10000.0), ctx.instrument, 10000.0)
    if signed <= floor or scale <= 0:        # wrong side / below the noise floor
        return 0.0
    return _clamp01((signed - floor) / scale)


def big_print(ctx, cfg, side: str) -> float:
    """GRADED (2026-07-17): a recent big print aligned with ``side`` contributes its tail
    STRENGTH in [0,1] (a p99.9 print scores ~1, a print at the p99 cut ~0), not a flat 1.0 —
    OFI's lesson. In FIXED mode strength is 1.0 (binary, backward-compatible). INERT while
    bigprint.mode='fixed' + threshold 0: no events -> side None -> 0."""
    if ctx.recent_big_print_side != _sign(side):
        return 0.0
    return _clamp01(ctx.recent_big_print_strength)


def queue_imbalance(ctx, cfg, side: str) -> float:
    if ctx.queue_imbalance is None:          # STUB until R1 depth
        return 0.0
    signed = ctx.queue_imbalance * _sign(side)
    thr = float(cfg.param("queue_imbalance_min", 0.0))
    return _clamp01(signed - thr) if signed > thr else 0.0


def vwap_value_location(ctx, cfg, side: str) -> float:
    """Long: price at/below the VWAP lower band AND near support (VAL / IB_LOW).
    Short: price at/above the VWAP upper band AND near resistance (VAH / IB_HIGH)."""
    if ctx.vwap is None:
        return 0.0
    k = int(float(cfg.param("vwap_band_k", 1.0)))
    ticks = float(cfg.param("level_zone_ticks", 5.0))
    score = 0.0
    if side == "long":
        band = ctx.vwap_bands.get(f"lower_{k}")
        if band is not None and ctx.price <= band:
            score += 0.5
        supports = [x for x in (ctx.val, ctx.ib_low) if x is not None]
        if supports and min(abs(ctx.price - s) for s in supports) <= ticks:
            score += 0.5
    else:
        band = ctx.vwap_bands.get(f"upper_{k}")
        if band is not None and ctx.price >= band:
            score += 0.5
        resist = [x for x in (ctx.vah, ctx.ib_high) if x is not None]
        if resist and min(abs(ctx.price - r) for r in resist) <= ticks:
            score += 0.5
    return score


def cvd_confirm(ctx, cfg, side: str) -> float:
    thr = float(cfg.param("cvd_slope_min", 0.0))
    return 1.0 if ctx.cvd_slope * _sign(side) > thr else 0.0


def level_zone(ctx, cfg, side: str) -> float:
    """Proximity to the nearest key level (graded by closeness within a band)."""
    if ctx.registry is None:
        return 0.0
    near = ctx.registry.distance_to_nearest(ctx.price)
    if near is None:
        return 0.0
    ticks = float(cfg.param("level_zone_ticks", 5.0))
    if ticks <= 0 or near["abs_distance"] > ticks:
        return 0.0
    return _clamp01(1.0 - near["abs_distance"] / ticks)


def tape_velocity(ctx, cfg, side: str) -> float:
    """A velocity spike aligned with the side's direction (bar delta)."""
    if not ctx.velocity_spike:
        return 0.0
    return 1.0 if ctx.bar_delta * _sign(side) >= 0 else 0.0


def regime(ctx, cfg, side: str) -> float:
    want = "bull" if side == "long" else "bear"
    return 1.0 if ctx.regime_direction == want else 0.0


def pain_map(ctx, cfg, side: str) -> float:
    return trapped_pressure(ctx, side)


COMPONENTS = {
    "book_ofi": book_ofi,
    "big_print": big_print,
    "queue_imbalance": queue_imbalance,
    "vwap_value_location": vwap_value_location,
    "cvd_confirm": cvd_confirm,
    "level_zone": level_zone,
    "tape_velocity": tape_velocity,
    "regime": regime,
    "pain_map": pain_map,
}
