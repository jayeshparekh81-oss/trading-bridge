"""Tests for :mod:`app.services.probability_engine`.

Pure-function service — no Redis, no DB, no async. We construct
``DNAResult`` / ``AnomalyResult`` fixtures directly and assert the
formula output across the design-proposal paths:

* default OFF short-circuits to ``DISABLED``
* missing / cold-start DNA → ``INSUFFICIENT_INPUTS``
* high DNA + no anomaly → strong_entry, very_high band
* high DNA + heavy anomaly penalty → reco demoted
* low DNA → skip
* mid DNA → cautious / entry depending on confidence
* recommendation thresholds at boundary
* clamp [5, 95] respected
* anomaly None handled (penalty=0)
* expected_rr derivation (legacy formula)
* `block` is NOT a possible recommendation (RULE 1 audit)
"""

from __future__ import annotations

import pytest

from app.core import config as app_config
from app.services import probability_engine as svc
from app.services.anomaly_shield_service import AnomalyResult
from app.services.trade_dna_service import DNAResult


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    app_config.get_settings.cache_clear()
    yield
    app_config.get_settings.cache_clear()


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBABILITY_ENGINE_ENABLED", "true")
    app_config.get_settings.cache_clear()


def _dna(
    *,
    win_prob: float | None = 75.0,
    confidence: float | None = 70.0,
    note: str = "OK",
    enabled: bool = True,
) -> DNAResult:
    """Build a usable DNAResult fixture."""
    return DNAResult(
        enabled=enabled,
        score=(win_prob - 50.0) * 2.0 if win_prob is not None else None,
        win_prob=win_prob,
        confidence=confidence,
        winners=8 if (win_prob or 0) > 50 else 2,
        losers=2 if (win_prob or 0) > 50 else 8,
        sample_size=20,
        note=note,
    )


def _anomaly(*, composite: float = 0.0, tripped: bool = False) -> AnomalyResult:
    return AnomalyResult(
        tripped=tripped,
        composite_score=composite,
        reason="tripped" if tripped else "normal",
        bars_collected=200,
    )


# ═══════════════════════════════════════════════════════════════════════
# Default OFF
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultOff:
    def test_is_enabled_false_by_default(self) -> None:
        assert svc.is_enabled() is False

    def test_compute_short_circuits_when_disabled(self) -> None:
        result = svc.compute(_dna(), _anomaly())
        assert result.enabled is False
        assert result.note == "DISABLED"
        assert result.win_probability is None
        assert result.recommendation == "n/a"


# ═══════════════════════════════════════════════════════════════════════
# Cold start / missing DNA
# ═══════════════════════════════════════════════════════════════════════


class TestColdStart:
    def test_dna_none_yields_insufficient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        result = svc.compute(None, _anomaly())
        assert result.enabled is True
        assert result.note == "INSUFFICIENT_INPUTS"
        assert result.win_probability is None
        assert result.recommendation == "n/a"

    def test_dna_insufficient_history_yields_insufficient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        cold_dna = _dna(win_prob=None, confidence=None, note="INSUFFICIENT_HISTORY:7/20")
        result = svc.compute(cold_dna, _anomaly())
        assert result.note.startswith("INSUFFICIENT_INPUTS")
        assert "INSUFFICIENT_HISTORY" in result.note
        assert result.win_probability is None

    def test_dna_disabled_yields_insufficient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        disabled_dna = _dna(win_prob=None, confidence=None, note="DISABLED", enabled=False)
        result = svc.compute(disabled_dna, _anomaly())
        assert result.note.startswith("INSUFFICIENT_INPUTS")
        assert result.recommendation == "n/a"


# ═══════════════════════════════════════════════════════════════════════
# Scoring math — happy path
# ═══════════════════════════════════════════════════════════════════════


class TestScoring:
    def test_high_dna_no_anomaly_yields_entry_or_better(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """High-quality DNA + clean tape → at least 'entry' recommendation.

        Note on absolute ceiling: with cascade + mode stubbed at neutral 50,
        the base formula can't exceed 70 (=0.40*100 + 0.30*50 + 0.30*50).
        That's intentional — strong_entry is effectively unreachable until
        feature #14 (Cascade) lands and unstubs the 0.30 slot. When that
        happens the same DNA=90 input will push final into the 75+ range.
        """
        _enable(monkeypatch)
        # DNA 90 + stubs: base = 36 + 15 + 7.5 + 7.5 = 66
        # confidence: 80*0.5 + 50*0.3 + 100*0.2 = 75 → very_high
        result = svc.compute(_dna(win_prob=90.0, confidence=80.0), _anomaly(composite=0.0))
        assert result.note == "OK"
        assert result.win_probability == pytest.approx(66.0, abs=0.5)
        assert result.confidence_pct == pytest.approx(75.0, abs=0.5)
        assert result.confidence_band == "very_high"
        # strong_entry needs final ≥ 75 (unreachable while cascade stubbed),
        # so we land in `entry` band (final ≥ 65 AND conf ≥ 55).
        assert result.recommendation == "entry"

    def test_low_dna_yields_skip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        # DNA 20% + cascade 50 stub + neutrals = base 38
        result = svc.compute(_dna(win_prob=20.0, confidence=60.0), _anomaly())
        assert result.note == "OK"
        assert result.win_probability is not None and result.win_probability < 50.0
        assert result.recommendation == "skip"

    def test_anomaly_penalty_demotes_recommendation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """High DNA but heavy anomaly should knock down the final score."""
        _enable(monkeypatch)
        no_anom = svc.compute(_dna(win_prob=85.0, confidence=80.0), _anomaly(composite=0.0))
        with_anom = svc.compute(_dna(win_prob=85.0, confidence=80.0), _anomaly(composite=80.0))

        # Heavy anomaly knocks 80 * 0.3 = 24 percentage points off final.
        assert with_anom.win_probability is not None
        assert no_anom.win_probability is not None
        assert with_anom.win_probability < no_anom.win_probability
        # Anomaly penalty also drags confidence (max(0, 100-80)*0.2 = 4 vs 100*0.2=20).
        assert with_anom.confidence_pct is not None
        assert no_anom.confidence_pct is not None
        assert with_anom.confidence_pct < no_anom.confidence_pct

    def test_anomaly_none_treated_as_zero_penalty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        a = svc.compute(_dna(win_prob=70.0, confidence=70.0), None)
        b = svc.compute(_dna(win_prob=70.0, confidence=70.0), _anomaly(composite=0.0))
        # Both paths produce identical numbers — None == zero penalty.
        assert a.win_probability == b.win_probability
        assert a.confidence_pct == b.confidence_pct


# ═══════════════════════════════════════════════════════════════════════
# Clamp behaviour
# ═══════════════════════════════════════════════════════════════════════


class TestClamp:
    def test_lower_clamp_at_5(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        # DNA 5% + max anomaly drives below clamp.
        result = svc.compute(_dna(win_prob=5.0, confidence=10.0), _anomaly(composite=100.0))
        assert result.win_probability is not None
        assert result.win_probability >= 5.0

    def test_upper_clamp_at_95(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        result = svc.compute(_dna(win_prob=100.0, confidence=100.0), _anomaly(composite=0.0))
        assert result.win_probability is not None
        assert result.win_probability <= 95.0


# ═══════════════════════════════════════════════════════════════════════
# Confidence bands — boundary checks
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceBands:
    def test_very_high_band(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        # DNA confidence 90 → contrib 45; cascade contrib 15; anomaly contrib 20.
        # Total = 80 → very_high.
        result = svc.compute(_dna(win_prob=85.0, confidence=90.0), _anomaly(composite=0.0))
        assert result.confidence_band == "very_high"

    def test_low_band(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        # DNA conf 20 → 10. Cascade 15. Anomaly contrib (100-90)*0.2 = 2. Total = 27 → low.
        result = svc.compute(_dna(win_prob=50.0, confidence=20.0), _anomaly(composite=90.0))
        assert result.confidence_band == "low"


# ═══════════════════════════════════════════════════════════════════════
# Expected R:R
# ═══════════════════════════════════════════════════════════════════════


class TestExpectedRR:
    def test_high_dna_yields_rr_above_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        result = svc.compute(_dna(win_prob=80.0, confidence=70.0), None)
        # legacy: 1 + (80-50)/30 = 2.0
        assert result.expected_rr == pytest.approx(2.0, abs=0.05)

    def test_low_dna_yields_rr_below_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        result = svc.compute(_dna(win_prob=40.0, confidence=50.0), None)
        # legacy: max(0.3, 40/50) = 0.8
        assert result.expected_rr == pytest.approx(0.8, abs=0.05)

    def test_floor_at_03(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable(monkeypatch)
        result = svc.compute(_dna(win_prob=10.0, confidence=10.0), None)
        # legacy: max(0.3, 10/50) = max(0.3, 0.2) = 0.3
        assert result.expected_rr == pytest.approx(0.3, abs=0.05)


# ═══════════════════════════════════════════════════════════════════════
# RULE 1 — `block` recommendation is forbidden
# ═══════════════════════════════════════════════════════════════════════


class TestStateDivergenceRule1:
    """Anomaly-based blocking is Black-Swan Shield's lane. The Probability
    Engine is advisory-only and must NEVER produce a `block` recommendation,
    regardless of inputs."""

    @pytest.mark.parametrize(
        ("dna_prob", "anomaly_score"),
        [
            (90.0, 100.0),  # high DNA, max anomaly
            (10.0, 100.0),  # low DNA, max anomaly
            (50.0, 100.0),  # mid DNA, max anomaly
            (5.0, 95.0),    # everything bad
        ],
    )
    def test_no_block_recommendation_under_any_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
        dna_prob: float,
        anomaly_score: float,
    ) -> None:
        _enable(monkeypatch)
        result = svc.compute(
            _dna(win_prob=dna_prob, confidence=50.0),
            _anomaly(composite=anomaly_score, tripped=True),
        )
        assert result.recommendation != "block"
        assert result.recommendation in (
            "strong_entry", "entry", "cautious", "skip", "n/a"
        )


# ═══════════════════════════════════════════════════════════════════════
# Payload serialization
# ═══════════════════════════════════════════════════════════════════════


class TestPayload:
    def test_to_payload_dict_is_json_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable(monkeypatch)
        result = svc.compute(_dna(win_prob=70.0, confidence=60.0), _anomaly(composite=20.0))
        payload = result.to_payload_dict()

        import json
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["enabled"] is True
        assert "factors" in round_tripped
        assert "dna" in round_tripped["factors"]
        assert "cascade" in round_tripped["factors"]
        assert round_tripped["factors"]["cascade"]["stub"] is True
        assert "feature #14" in round_tripped["factors"]["cascade"]["stub_reason"]
