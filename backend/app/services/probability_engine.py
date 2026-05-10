"""Predictive Probability Engine — meta-aggregator for advisory entry scoring.

Faithful port of the AWS bot's ``trade_brain._compute_probability``
(``/tmp/cowork_legacy/trade_brain.py:629``), reframed per
``state_divergence_rule.md``:

* **RULE 1** — *advisory only*. The result is attached to
  ``strategy_signals.raw_payload._probability`` and surfaced in logs.
  The ``recommendation`` field is metadata for the operator/UI; it
  **does not** enforce broker actions or override the AI validator.
  We deliberately do NOT port the legacy ``"block"`` recommendation —
  anomaly-based blocking belongs to the Black-Swan Shield's lane.
* **RULE 2** — pure function with no I/O. Triggered only inside the
  webhook handler (= confirmed bar close). No background poller, no
  scheduled task, no Redis writes.
* **Pine alignment** — purely additive. Pine drives every entry/exit;
  we just annotate the signal record so the operator can see "78% win
  probability with HIGH confidence".

Inputs
------
The engine consumes outputs from already-computed upstream services:

* ``DNAResult`` — from :mod:`app.services.trade_dna_service`. The
  dominant signal (40% weight). When ``None`` or
  ``note != "OK"``, the engine short-circuits to ``INSUFFICIENT_INPUTS``.
* ``AnomalyResult`` — from :mod:`app.services.anomaly_shield_service`.
  Contributes a penalty proportional to ``composite_score``. May be
  ``None`` (Black-Swan Shield disabled) — penalty defaults to 0.
* **Cascade** — STUBBED at neutral 50% until feature #14 is ported.
  The 30% weight slot stays so the formula slots in cleanly later.
* **Strategy Mode** — STUBBED at 0 adjustment until feature #16
  (adaptive morphing) is ported.

Output bands
------------
``confidence_band`` thresholds match the **tightened** Sun 2026-05-10
product call (post-Friday risk-aversion): ``very_high ≥ 75``,
``high ≥ 65``, ``medium ≥ 55``, else ``low``. Legacy bot used
75/55/35 — ours is stricter on the lower bands.

``recommendation`` thresholds (also tightened from legacy 72/60/50):

* ``strong_entry`` — final ≥ 75 AND confidence ≥ 65
* ``entry``       — final ≥ 65 AND confidence ≥ 55
* ``cautious``    — final ≥ 55
* ``skip``        — otherwise

(The legacy ``block`` reco is intentionally absent.)

Default OFF
-----------
``settings.probability_engine_enabled`` is False by default. When
False, :func:`is_enabled` returns False and :func:`compute` returns
a no-op result with ``note="DISABLED"``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.anomaly_shield_service import AnomalyResult
from app.services.trade_dna_service import DNAResult

logger = get_logger("app.services.probability_engine")


# ═══════════════════════════════════════════════════════════════════════
# Confidence-band thresholds (tightened from legacy per Sun 2026-05-10)
# ═══════════════════════════════════════════════════════════════════════

#: confidence_pct ≥ this → "very_high". Legacy: 75 (unchanged).
CONF_VERY_HIGH: float = 75.0

#: confidence_pct ≥ this → "high". Legacy: 55. Tightened to 65.
CONF_HIGH: float = 65.0

#: confidence_pct ≥ this → "medium". Legacy: 35. Tightened to 55.
CONF_MEDIUM: float = 55.0

# ═══════════════════════════════════════════════════════════════════════
# Recommendation thresholds (also tightened — post-Friday risk-aversion)
# ═══════════════════════════════════════════════════════════════════════

#: final_prob ≥ this AND confidence ≥ CONF_HIGH → "strong_entry". Legacy: 72.
RECO_STRONG_ENTRY_PROB: float = 75.0

#: final_prob ≥ this AND confidence ≥ CONF_MEDIUM → "entry". Legacy: 60.
RECO_ENTRY_PROB: float = 65.0

#: final_prob ≥ this → "cautious". Legacy: 50.
RECO_CAUTIOUS_PROB: float = 55.0


# ═══════════════════════════════════════════════════════════════════════
# Result dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ProbabilityResult:
    """Outcome of one probability evaluation.

    Attributes:
        enabled: True iff the service is on. False short-circuits everything.
        win_probability: Final clamped probability ∈ [clamp_min, clamp_max],
            or None when inputs are insufficient.
        confidence_pct: Composite confidence (0-100), or None on cold start.
        confidence_band: ``"very_high"`` | ``"high"`` | ``"medium"`` |
            ``"low"`` | ``"n/a"``.
        expected_rr: Expected reward:risk derived from DNA win_prob.
            None on cold start.
        recommendation: ``"strong_entry"`` | ``"entry"`` | ``"cautious"`` |
            ``"skip"`` | ``"n/a"``. **Advisory only** — never enforced.
            Note the absence of legacy's ``"block"`` reco (RULE 1).
        factors: Per-input breakdown for log/audit. Keys: ``dna``,
            ``cascade``, ``anomaly``, ``mode``.
        note: ``"OK"`` | ``"DISABLED"`` | ``"INSUFFICIENT_INPUTS"`` |
            ``"ERROR:<msg>"``.
    """

    enabled: bool
    win_probability: float | None
    confidence_pct: float | None
    confidence_band: str
    expected_rr: float | None
    recommendation: str
    note: str
    factors: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_payload_dict(self) -> dict[str, Any]:
        """JSON-safe dict for embedding in ``raw_payload._probability``."""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def is_enabled() -> bool:
    """Master toggle. False unless ``PROBABILITY_ENGINE_ENABLED`` is set."""
    return bool(get_settings().probability_engine_enabled)


def compute(
    dna_result: DNAResult | None,
    anomaly_result: AnomalyResult | None = None,
) -> ProbabilityResult:
    """Combine upstream signals into a single probability prediction.

    Pure function — no I/O, no side effects, no exceptions raised. The
    caller is responsible for attaching the result to the signal.

    Args:
        dna_result: From :func:`trade_dna_service.evaluate`. Required;
            ``None`` or ``note != "OK"`` short-circuits to
            ``INSUFFICIENT_INPUTS``.
        anomaly_result: From :func:`anomaly_shield_service.evaluate`.
            Optional — when ``None`` the anomaly-penalty defaults to 0.

    Returns:
        :class:`ProbabilityResult`. Always returns a dataclass; never
        raises (caller never has to wrap in try/except).
    """
    settings = get_settings()
    if not settings.probability_engine_enabled:
        return _no_op_result(enabled=False, note="DISABLED")

    # DNA is the dominant input — without a usable score, the rest of
    # the formula is meaningless (cascade is stubbed, mode is stubbed,
    # anomaly is a penalty not a signal).
    if dna_result is None or not dna_result.enabled or dna_result.note != "OK":
        dna_note_suffix = (
            f" (dna_note={dna_result.note})" if dna_result is not None else ""
        )
        return _no_op_result(
            enabled=True,
            note=f"INSUFFICIENT_INPUTS{dna_note_suffix}",
        )

    try:
        return _compute_inner(dna_result, anomaly_result, settings)
    except Exception as exc:  # noqa: BLE001 — pure fn, never propagate
        logger.warning(
            "probability_engine.compute_failed",
            error=str(exc),
            dna_score=dna_result.score if dna_result else None,
        )
        return _no_op_result(enabled=True, note=f"ERROR:{exc}")


# ═══════════════════════════════════════════════════════════════════════
# Internals
# ═══════════════════════════════════════════════════════════════════════

def _compute_inner(
    dna_result: DNAResult,
    anomaly_result: AnomalyResult | None,
    settings: Any,
) -> ProbabilityResult:
    """Hot path — no None checks, no exception handling. Called only after
    ``compute`` has validated inputs."""

    # Factor 1 — DNA (dominant, 40% weight).
    # win_prob is guaranteed non-None when note=="OK" (per DNAResult contract).
    assert dna_result.win_prob is not None  # noqa: S101 — contract
    dna_prob = float(dna_result.win_prob)
    dna_confidence = float(dna_result.confidence or 0.0)

    # Factor 2 — Cascade (STUBBED at neutral 50% until feature #14 ports).
    # Slot retained so the formula doesn't need rewiring later.
    cascade_prob = 50.0

    # Factor 3 — Anomaly (penalty, not a signal).
    if anomaly_result is not None and anomaly_result.composite_score > 0:
        anomaly_score = float(anomaly_result.composite_score)
    else:
        anomaly_score = 0.0
    anomaly_penalty = anomaly_score * float(settings.probability_anomaly_penalty_factor)

    # Factor 4 — Strategy Mode (STUBBED at 0 until feature #16 ports).
    mode_adj = 0.0

    # Base formula — weighted average. Cascade + Mode slots feed neutral
    # 50 right now; their weights still apply so the math is identical
    # to legacy once those modules land.
    base_prob = (
        dna_prob * float(settings.probability_dna_weight)
        + cascade_prob * float(settings.probability_cascade_weight)
        + 50.0 * 0.15  # anomaly slot — neutral baseline; penalty applied below
        + 50.0 * 0.15  # mode slot — neutral baseline; adjustment applied below
    )

    final_prob = base_prob - anomaly_penalty + mode_adj
    final_prob = max(
        float(settings.probability_clamp_min),
        min(float(settings.probability_clamp_max), final_prob),
    )

    # Composite confidence — DNA confidence dominates (50%), cascade
    # alignment next (30%), inverse-anomaly last (20%).
    cascade_conf_contrib = (cascade_prob / 100.0) * 100.0  # = cascade_prob
    confidence_pct = min(
        100.0,
        dna_confidence * 0.5
        + cascade_conf_contrib * 0.3
        + max(0.0, 100.0 - anomaly_score) * 0.2,
    )

    # Bucketed confidence band.
    if confidence_pct >= CONF_VERY_HIGH:
        confidence_band = "very_high"
    elif confidence_pct >= CONF_HIGH:
        confidence_band = "high"
    elif confidence_pct >= CONF_MEDIUM:
        confidence_band = "medium"
    else:
        confidence_band = "low"

    # Expected reward:risk — derived from DNA win_prob. Mirrors legacy.
    if dna_prob > 60.0:
        expected_rr = 1.0 + (dna_prob - 50.0) / 30.0
    else:
        expected_rr = max(0.3, dna_prob / 50.0)

    # Recommendation — tightened thresholds. NOTE: no "block" — that's
    # Black-Swan Shield's lane (RULE 1).
    if final_prob >= RECO_STRONG_ENTRY_PROB and confidence_pct >= CONF_HIGH:
        recommendation = "strong_entry"
    elif final_prob >= RECO_ENTRY_PROB and confidence_pct >= CONF_MEDIUM:
        recommendation = "entry"
    elif final_prob >= RECO_CAUTIOUS_PROB:
        recommendation = "cautious"
    else:
        recommendation = "skip"

    factors = {
        "dna": {
            "prob": round(dna_prob, 1),
            "confidence": round(dna_confidence, 1),
            "weight": float(settings.probability_dna_weight),
        },
        "cascade": {
            "prob": cascade_prob,
            "weight": float(settings.probability_cascade_weight),
            "stub": True,
            "stub_reason": "feature #14 not ported",
        },
        "anomaly": {
            "composite": round(anomaly_score, 2),
            "penalty": round(anomaly_penalty, 2),
            "factor": float(settings.probability_anomaly_penalty_factor),
        },
        "mode": {
            "adjustment": mode_adj,
            "stub": True,
            "stub_reason": "feature #16 not ported",
        },
    }

    return ProbabilityResult(
        enabled=True,
        win_probability=round(final_prob, 1),
        confidence_pct=round(confidence_pct, 1),
        confidence_band=confidence_band,
        expected_rr=round(expected_rr, 2),
        recommendation=recommendation,
        note="OK",
        factors=factors,
    )


def _no_op_result(*, enabled: bool, note: str) -> ProbabilityResult:
    """Build a dormant result for the disabled / cold-start / error paths.

    All numeric fields are ``None``; recommendation is ``"n/a"``;
    confidence band is ``"n/a"``. The caller can attach this to
    ``raw_payload._probability`` exactly like a real result.
    """
    return ProbabilityResult(
        enabled=enabled,
        win_probability=None,
        confidence_pct=None,
        confidence_band="n/a",
        expected_rr=None,
        recommendation="n/a",
        note=note,
    )


__all__ = [
    "CONF_HIGH",
    "CONF_MEDIUM",
    "CONF_VERY_HIGH",
    "ProbabilityResult",
    "RECO_CAUTIOUS_PROB",
    "RECO_ENTRY_PROB",
    "RECO_STRONG_ENTRY_PROB",
    "compute",
    "is_enabled",
]
