"""AI signal validator — faithful port of the AWS bot's scoring engine.

This module replaces the Anthropic SDK stub from the strategy-engine
branch with the production-tested decision logic from the AWS bot
(``server_final30mar.py:evaluate_directional_ai``).

Why faithful port (not LLM):
    * The bot has been live in production with this exact algorithm.
    * Score weights, thresholds, and per-indicator pass rules are the
      result of months of backtesting + self-learning on real trades.
    * Deterministic logic is easier to audit, test, and roll back than
      a remote LLM call. We can layer LLM oversight on top later.

What is ported (verbatim or near-verbatim):
    * 17-indicator weighted scoring for LONG and SHORT (separate maps).
    * Per-indicator PASS rules: PASS earns full weight, FAIL earns 30%.
    * Score-to-lots tiers:
        - LONG  >= 85% -> 4 lots; >= 51% -> 2 lots; else REJECTED.
        - SHORT >= 55% -> 2 lots; else REJECTED.
    * VIX modulation: VIX < 11.5 OR > 20.0 -> halve qty; else full.
    * ``ENTRY_QTY_MAX`` cap (default 10).
    * Hardcoded ``AVG_VALUES`` reference table for normalised pass tests.

What is NOT ported (deliberate):
    * Self-learning weight optimisation (TRADETRI's first cut runs on
      the hardcoded defaults; learning lands on a future branch).
    * Regime detection beyond the VIX qty rule (the bot's
      ``_detect_regime`` adjusts thresholds; we keep thresholds fixed
      for now to make this auditable).
    * Time-of-day / daily-loss / conflict-direction gates - the bot
      doesn't enforce these at the validator level, and the strategy
      webhook receiver already enforces market hours upstream.
    * Anthropic SDK calls (entirely removed; the schema bypass-on-no-key
      branch is gone too).

The signature is unchanged for callers - :func:`validate_signal`
returns an :class:`AIDecision`. New field ``recommended_lots`` carries
the AI's tier; the executor honours it (capped by strategy.entry_lots).
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.schemas.ai_decision import AIDecision, AIDecisionStatus

_logger = get_logger("services.ai_validator")


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS — straight port from server_final30mar.py
# ═══════════════════════════════════════════════════════════════════════

#: Score thresholds (0-100 scale, bot's native units).
LONG_THRESHOLD: float = 51.0
LONG_THRESHOLD_4LOT: float = 85.0
SHORT_THRESHOLD: float = 55.0

#: Per-tier lot counts.
QTY_LONG_2LOT: int = 2
QTY_LONG_4LOT: int = 4
QTY_SHORT_2LOT: int = 2

#: Hard ceiling on entry quantity, applied after VIX modulation.
ENTRY_QTY_MAX: int = 10

#: VIX modulation band — outside this, halve qty. Inside, full qty.
VIX_THRESH_LOW: float = 11.5
VIX_THRESH_HIGH: float = 20.0
VIX_HALF_MULT: float = 0.5

#: LONG-side weights (17 indicators) — bot's hardcoded defaults.
LONG_W: dict[str, float] = {
    "PriceSpd": 15.67,
    "ATR": 12.82,
    "LongMA": 9.34,
    "GaussL": 8.94,
    "SlowMA": 8.90,
    "GaussS": 8.90,
    "FastMA": 8.89,
    "VWAPDist": 6.62,
    "BullGap": 5.39,
    "Squeeze": 4.21,
    "BodyPct": 3.76,
    "Vol": 1.84,
    "DeltaPwr": 1.62,
    "BearGap": 1.35,
    "RVOL": 0.97,
    "OFInten": 0.56,
    "RSI": 0.22,
}

#: SHORT-side weights (17 indicators) — bot's hardcoded defaults.
SHORT_W: dict[str, float] = {
    "PriceSpd": 10.86,
    "ATR": 10.19,
    "GaussL": 9.16,
    "LongMA": 9.15,
    "SlowMA": 9.14,
    "GaussS": 9.14,
    "FastMA": 9.12,
    "BearGap": 5.37,
    "Vol": 4.59,
    "Squeeze": 4.55,
    "VWAPDist": 4.42,
    "RSI": 3.55,
    "BullGap": 3.32,
    "RVOL": 2.76,
    "OFInten": 2.38,
    "DeltaPwr": 1.33,
    "BodyPct": 0.97,
}

#: Reference values used to test "did this indicator print strongly?".
AVG_VALUES: dict[str, float] = {
    "PriceSpd": 4.72,
    "ATR": 5.0,
    "LongMA": 736.49,
    "GaussL": 743.17,
    "SlowMA": 743.79,
    "GaussS": 743.82,
    "FastMA": 744.45,
    "VWAPDist": 0.77,
    "BullGap": 179.0,
    "Squeeze": 5.5,
    "BodyPct": 64.2,
    "Vol": 332669.68,
    "DeltaPwr": 33.61,
    "BearGap": 106.05,
    "RVOL": 1.66,
    "OFInten": 1.6,
    "RSI": 54.82,
}

#: Default IndiaVIX used when the signal payload omits one. Mid-band
#: value -> VIX rule passes through full qty. Wed evening swap-in for
#: a real Fyers / NSE feed is tracked separately.
DEFAULT_VIX: float = 15.0


# ─── Regime detection (faithful port of bot's _detect_regime) ─────────────
#
# Multiplies the side-specific threshold before the tier check.
# Mult > 1.0 = stricter (less likely to approve); = 1.0 = unchanged.
# Master toggle defaults OFF, matching the bot's USE_REGIME_DETECTION="0".

#: VIX above this -> volatile regime.
REGIME_VIX_HIGH: float = 22.0

#: ADX at or above this -> trending regime.
REGIME_ADX_TREND: float = 25.0

#: ADX at or below this -> ranging regime.
REGIME_ADX_RANGE: float = 15.0

#: Threshold multipliers per regime. Volatile and ranging both raise
#: the bar; trending leaves it unchanged.
REGIME_SCORE_VOLATILE_MULT: float = 1.10
REGIME_SCORE_TREND_MULT: float = 1.0
REGIME_SCORE_RANGE_MULT: float = 1.15


def _use_regime_detection() -> bool:
    """Read the regime master toggle live from env. Defaults OFF (bot parity).

    Read on every call (not module-load) so tests can flip it via
    ``monkeypatch.setenv`` without re-importing the module.
    """
    return os.environ.get("USE_REGIME_DETECTION", "0").lower() in ("1", "true", "yes")


def detect_regime(indicators: dict[str, Any]) -> tuple[str, float]:
    """Classify market regime and return its threshold multiplier.

    Faithful port of ``server_final30mar.py:_detect_regime``. Returns
    ``("off", 1.0)`` when ``USE_REGIME_DETECTION`` is off (bot default).

    Decision order:
        1. ``vix > REGIME_VIX_HIGH`` -> "volatile" (1.10)
        2. ``adx >= REGIME_ADX_TREND`` -> "trending" (1.00)
        3. ``adx <= REGIME_ADX_RANGE`` -> "ranging" (1.15)
        4. otherwise -> "normal" (1.00)

    Same ``IndiaVIX`` value is used here as in :func:`vix_adjust_qty` so
    the two layers stay coherent. Missing / malformed indicators fall
    back to 0, which routes to the normal branch.
    """
    if not _use_regime_detection():
        return "off", 1.0

    try:
        adx = float(indicators.get("ADX", 0) or 0)
    except (TypeError, ValueError):
        adx = 0.0
    try:
        vix = float(indicators.get("IndiaVIX", 0) or 0)
    except (TypeError, ValueError):
        vix = 0.0

    if vix > REGIME_VIX_HIGH:
        return "volatile", REGIME_SCORE_VOLATILE_MULT
    if adx >= REGIME_ADX_TREND:
        return "trending", REGIME_SCORE_TREND_MULT
    if adx <= REGIME_ADX_RANGE:
        return "ranging", REGIME_SCORE_RANGE_MULT
    return "normal", 1.0


def _long_passed(name: str, val: float, target: float) -> bool:
    """Per-indicator PASS test for the LONG side. Mirrors bot lines 1402-1419."""
    if name == "DeltaPwr":
        return val > 3.0
    if name == "ADX":
        return val >= 20.0
    if name == "MFI":
        return 40.0 <= val <= 80.0
    if name == "STDir":
        return val > 0
    if name == "OIBuild":
        return val >= 1.0
    if name == "MACDH":
        return val > 0
    if name in ("PriceSpd", "ATR", "RVOL", "BodyPct", "Squeeze", "VWAPDist", "RSI"):
        return val >= (target * 0.8)
    return abs(val) >= (target * 0.85)


def _short_passed(name: str, val: float, target: float) -> bool:
    """Per-indicator PASS test for the SHORT side. Mirrors bot lines 1420-1439."""
    if name == "DeltaPwr":
        return val < -3.0
    if name == "ADX":
        return val >= 20.0
    if name == "MFI":
        return 20.0 <= val <= 60.0
    if name == "STDir":
        return val < 0
    if name == "OIBuild":
        return val <= -1.0
    if name == "MACDH":
        return val < 0
    if name == "RSI":
        return val <= (target * 0.8)
    if name in ("PriceSpd", "ATR", "RVOL", "BodyPct", "Squeeze", "VWAPDist"):
        return abs(val) >= (target * 0.8)
    return abs(val) >= (target * 0.85)


# ═══════════════════════════════════════════════════════════════════════
# Core scoring
# ═══════════════════════════════════════════════════════════════════════


def compute_score(indicators: dict[str, Any], side: str) -> float:
    """Weighted-sum score on the bot's 0-100 scale.

    For each indicator: PASS earns full weight, FAIL earns 30% of the
    weight. Total of all earned weights is the score.

    Args:
        indicators: Free-form dict from the TradingView payload. Missing
            indicators score as 0 (their pass test will fail; FAIL still
            earns 30% so a stripped payload yields a baseline score).
        side: "LONG" or "SHORT" (case-insensitive).

    Returns:
        Score in [0, 100]. Caller decides what threshold to apply.
    """
    side_upper = side.upper()
    weights = LONG_W if side_upper == "LONG" else SHORT_W
    pass_fn = _long_passed if side_upper == "LONG" else _short_passed

    total = 0.0
    for name, weight in weights.items():
        try:
            val = float(indicators.get(name, 0))
        except (TypeError, ValueError):
            val = 0.0
        target = AVG_VALUES.get(name, 0.0)
        passed = pass_fn(name, val, target)
        total += weight if passed else (weight * 0.3)

    return round(total, 2)


def vix_adjust_qty(qty: int, vix: float | None) -> tuple[int, str]:
    """Apply the bot's VIX qty rule. Returns ``(adjusted_qty, tag)``.

    * vix is None  -> "vix_missing", qty unchanged.
    * vix outside [LOW, HIGH] -> halve qty (x0.5, rounded), tag "vix_half".
    * vix inside band -> full qty, tag "vix_full".
    """
    if qty <= 0:
        return 0, "qty_zero"
    if vix is None:
        return max(1, qty), "vix_missing"
    if vix < VIX_THRESH_LOW or vix > VIX_THRESH_HIGH:
        return max(1, int(round(qty * VIX_HALF_MULT))), "vix_half"
    return max(1, qty), "vix_full"


def _resolve_tier(
    score: float, side: str, *, regime_mult: float = 1.0
) -> tuple[bool, int, str]:
    """Map (score, side) -> (approved, base_qty, tier_tag).

    Faithful port: 4-lot heavy tier exists for LONG only. SHORT has a
    single 2-lot tier. Below the side's threshold, REJECTED with qty=0.

    ``regime_mult`` raises the effective threshold (mult > 1 = stricter).
    Mirrors the bot's ``eff_long_thresh = base_long * combined_mult``.
    Default 1.0 keeps the existing behaviour when the caller doesn't
    plumb regime through.
    """
    side_upper = side.upper()
    if side_upper == "LONG":
        eff_4lot = LONG_THRESHOLD_4LOT * regime_mult
        eff_2lot = LONG_THRESHOLD * regime_mult
        if score >= eff_4lot:
            return True, QTY_LONG_4LOT, "long_4lot"
        if score >= eff_2lot:
            return True, QTY_LONG_2LOT, "long_2lot"
        return False, 0, "long_rejected"
    eff_short = SHORT_THRESHOLD * regime_mult
    if score >= eff_short:
        return True, QTY_SHORT_2LOT, "short_2lot"
    return False, 0, "short_rejected"


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


async def validate_signal(
    signal: StrategySignal,
    strategy: Strategy,
    *,
    indicators: dict[str, Any] | None = None,
    vix: float | None = None,
) -> AIDecision:
    """Run the AWS bot's scoring algorithm against an inbound signal.

    Args:
        signal: The persisted ``StrategySignal``. ``signal.action`` (BUY
            /SELL) determines the side; ``signal.raw_payload['indicators']``
            (or the explicit ``indicators`` kwarg) provides the values.
        strategy: Owning strategy. Honours
            ``strategy.ai_validation_enabled`` — if False, returns a
            stub APPROVED with the strategy's configured ``entry_lots``
            so paper testing of the executor can flow without firing
            the validator.
        indicators: Override for the indicator dict. When None, we pull
            ``signal.raw_payload['indicators']`` (default empty dict).
        vix: IndiaVIX value. When None we fall through to the indicator
            payload's ``IndiaVIX`` field, then ``DEFAULT_VIX``. The Wed
            evening real-feed integration replaces this layer cleanly.

    Returns:
        :class:`AIDecision`. ``recommended_lots`` is post-VIX, post-cap.
        Confidence is ``score / 100`` clamped to [0, 1] so the field
        stays comparable across decision sources.
    """
    if not strategy.ai_validation_enabled:
        bypass_lots = max(0, min(strategy.entry_lots or 0, ENTRY_QTY_MAX))
        return AIDecision(
            decision=AIDecisionStatus.APPROVED,
            reasoning="AI validation disabled for this strategy.",
            confidence=Decimal("1.000"),
            recommended_lots=bypass_lots,
        )

    side = _signal_side(signal)
    if side is None:
        return AIDecision(
            decision=AIDecisionStatus.REJECTED,
            reasoning=f"Unsupported signal action for entry: {signal.action!r}",
            confidence=Decimal("0.000"),
            recommended_lots=0,
        )

    indicator_dict = indicators if indicators is not None else _extract_indicators(signal)
    score = compute_score(indicator_dict, side)
    regime_name, regime_mult = detect_regime(indicator_dict)
    approved, base_qty, tier_tag = _resolve_tier(
        score, side, regime_mult=regime_mult
    )

    if not approved:
        _logger.info(
            "ai_validator.rejected",
            signal_id=str(signal.id),
            side=side,
            score=score,
            tier=tier_tag,
            regime=regime_name,
            regime_mult=regime_mult,
        )
        return AIDecision(
            decision=AIDecisionStatus.REJECTED,
            reasoning=(
                f"Score {score:.2f} below {tier_tag} threshold "
                f"(LONG>={LONG_THRESHOLD}, SHORT>={SHORT_THRESHOLD}, "
                f"regime={regime_name} x{regime_mult:.2f})."
            ),
            confidence=_score_to_confidence(score),
            recommended_lots=0,
        )

    resolved_vix = vix if vix is not None else _vix_from_indicators(indicator_dict)
    adjusted_qty, vix_tag = vix_adjust_qty(base_qty, resolved_vix)
    capped_qty = min(adjusted_qty, ENTRY_QTY_MAX)

    _logger.info(
        "ai_validator.approved",
        signal_id=str(signal.id),
        side=side,
        score=score,
        tier=tier_tag,
        regime=regime_name,
        regime_mult=regime_mult,
        vix=resolved_vix,
        vix_tag=vix_tag,
        base_qty=base_qty,
        adjusted_qty=adjusted_qty,
        capped_qty=capped_qty,
    )

    reasoning = (
        f"Score {score:.2f} ({tier_tag}, regime={regime_name} x{regime_mult:.2f}, "
        f"VIX {resolved_vix:.2f} -> {vix_tag}, "
        f"{capped_qty} lot{'s' if capped_qty != 1 else ''})"
    )

    return AIDecision(
        decision=AIDecisionStatus.APPROVED,
        reasoning=reasoning,
        confidence=_score_to_confidence(score),
        recommended_lots=capped_qty,
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _signal_side(signal: StrategySignal) -> str | None:
    """Map signal.action -> bot vocab ('LONG'/'SHORT') or None for unsupported."""
    action = (signal.action or "").upper()
    if action == "BUY":
        return "LONG"
    if action == "SELL":
        return "SHORT"
    return None


def _extract_indicators(signal: StrategySignal) -> dict[str, Any]:
    """Pull the indicators dict from the raw payload. Missing -> empty dict."""
    payload = signal.raw_payload or {}
    indicators = payload.get("indicators")
    if isinstance(indicators, dict):
        return indicators
    return {}


def _vix_from_indicators(indicators: dict[str, Any]) -> float:
    """IndiaVIX from payload, or DEFAULT_VIX if absent / malformed."""
    raw = indicators.get("IndiaVIX")
    if raw is None:
        return DEFAULT_VIX
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_VIX
    return v if v > 0 else DEFAULT_VIX


def _score_to_confidence(score: float) -> Decimal:
    """Map 0-100 score to AIDecision's 0-1 confidence, clamped + rounded."""
    clamped = max(0.0, min(100.0, score))
    return Decimal(str(round(clamped / 100.0, 3)))


__all__ = [
    "AVG_VALUES",
    "DEFAULT_VIX",
    "ENTRY_QTY_MAX",
    "LONG_THRESHOLD",
    "LONG_THRESHOLD_4LOT",
    "LONG_W",
    "QTY_LONG_2LOT",
    "QTY_LONG_4LOT",
    "QTY_SHORT_2LOT",
    "REGIME_ADX_RANGE",
    "REGIME_ADX_TREND",
    "REGIME_SCORE_RANGE_MULT",
    "REGIME_SCORE_TREND_MULT",
    "REGIME_SCORE_VOLATILE_MULT",
    "REGIME_VIX_HIGH",
    "SHORT_THRESHOLD",
    "SHORT_W",
    "VIX_HALF_MULT",
    "VIX_THRESH_HIGH",
    "VIX_THRESH_LOW",
    "compute_score",
    "detect_regime",
    "validate_signal",
    "vix_adjust_qty",
]
