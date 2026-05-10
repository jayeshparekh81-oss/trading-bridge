"""Compliance evaluator unit tests.

Pure logic — no FastAPI, no DB. Uses the real indicator registry
where convenient and monkeypatches a synthetic EXPERIMENTAL entry
where coverage requires it (the registry has zero EXPERIMENTAL
indicators today, so we'd otherwise skip that branch).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.strategy_engine.compliance.evaluator import (
    BLOCKED_RISK,
    SAFE_RISK,
    WARNING_RISK,
    evaluate_indicator,
    evaluate_strategy_compliance,
    summarise_strategy,
)
from app.strategy_engine.indicators import registry as registry_mod
from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
)

# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def synthetic_experimental(
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """Inject one EXPERIMENTAL indicator into the registry for the
    duration of the test. The registry has zero experimental
    entries today; without this fixture the experimental branch in
    the evaluator would go untested."""
    test_id = "compliance_test_xp"
    meta = IndicatorMetadata(
        id=test_id,
        name="ComplianceTestXP",
        category="Test",
        description="Synthetic experimental indicator for compliance tests.",
        inputs=[],
        outputs=["line"],
        chartType=IndicatorChartType.OVERLAY,
        pineAliases=[],
        difficulty=IndicatorDifficulty.EXPERT,
        status=IndicatorStatus.EXPERIMENTAL,
        aiExplanation="N/A — test fixture only.",
        tags=["test"],
        calculationFunction=None,
    )
    # The runtime type of INDICATOR_REGISTRY is dict (the typing
    # annotation Mapping is just for read-side correctness).
    patched = dict(registry_mod.INDICATOR_REGISTRY)
    patched[test_id] = meta
    monkeypatch.setattr(registry_mod, "INDICATOR_REGISTRY", patched)
    return test_id


def _strategy_json(*indicators: dict[str, Any]) -> dict[str, Any]:
    """Wrap a list of indicator dicts into the minimal strategy
    JSON shape the evaluator inspects. Real strategies have many
    more keys — the evaluator only reads ``indicators[*]``."""
    return {"indicators": list(indicators)}


# ─── evaluate_indicator ───────────────────────────────────────────────


def test_active_indicator_is_safe_and_live_eligible() -> None:
    info = evaluate_indicator(indicator_id="ema", instance_id="ema_20")
    assert info.status == "active"
    assert info.risk_level == SAFE_RISK
    assert info.can_use_live is True
    assert info.can_use_paper is True
    assert info.can_use_backtest is True


def test_coming_soon_indicator_is_warning_paper_only() -> None:
    info = evaluate_indicator(indicator_id="kama", instance_id="kama_a")
    assert info.status == "coming_soon"
    assert info.risk_level == WARNING_RISK
    assert info.can_use_live is False  # SafetyChain blocks live
    assert info.can_use_paper is True
    assert info.can_use_backtest is True


def test_experimental_indicator_is_warning_paper_only(
    synthetic_experimental: str,
) -> None:
    info = evaluate_indicator(
        indicator_id=synthetic_experimental, instance_id="xp_a"
    )
    assert info.status == "experimental"
    assert info.risk_level == WARNING_RISK
    assert info.can_use_live is False
    assert info.can_use_paper is True
    assert info.can_use_backtest is True


def test_unknown_indicator_is_blocked_everywhere() -> None:
    """An indicator id that isn't in the registry — the strategy
    references something that no longer exists. Block from every
    execution path so the strategy can't silently misbehave."""
    info = evaluate_indicator(
        indicator_id="totally_made_up_xyz_v999", instance_id="ghost"
    )
    assert info.status == "unknown"
    assert info.risk_level == BLOCKED_RISK
    assert info.can_use_live is False
    assert info.can_use_paper is False
    assert info.can_use_backtest is False


def test_hinglish_messages_mention_indicator_name() -> None:
    """The Hinglish copy is what the user sees in the dashboard
    chip. It must reference the indicator name so the user knows
    *which* indicator the line is about — not a generic
    placeholder."""
    info = evaluate_indicator(indicator_id="ema", instance_id="ema_20")
    assert "EMA" in info.user_facing_message_hinglish
    info2 = evaluate_indicator(
        indicator_id="kama", instance_id="kama_a"
    )
    # KAMA's display name from the registry is what we expect.
    assert "kama" in info2.user_facing_message_hinglish.lower()


# ─── evaluate_strategy_compliance — scoring ───────────────────────────


def test_all_active_strategy_scores_100() -> None:
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {"id": "ema_a", "type": "ema", "params": {}},
        {"id": "sma_a", "type": "sma", "params": {}},
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid, strategy_name="all-active", strategy_json=json_blob
    )
    assert report.compliance_score == 100
    assert report.blocking_issues == []
    assert report.warnings == []
    assert report.recommendations == []
    assert len(report.indicators_used) == 2


def test_one_coming_soon_strategy_scores_90() -> None:
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {"id": "ema_a", "type": "ema", "params": {}},
        {"id": "kama_a", "type": "kama", "params": {}},
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="one-cs",
        strategy_json=json_blob,
    )
    assert report.compliance_score == 90
    assert report.blocking_issues == []
    assert len(report.warnings) == 1
    assert "kama" in report.warnings[0].lower()


def test_two_coming_soon_strategy_scores_80() -> None:
    """Per-instance deductions — two coming_soon = -20, not -10
    (we don't dedupe by registry id)."""
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {"id": "kama_a", "type": "kama", "params": {}},
        {"id": "kama_b", "type": "kama", "params": {}},
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="two-cs",
        strategy_json=json_blob,
    )
    assert report.compliance_score == 80


def test_one_experimental_strategy_scores_75(
    synthetic_experimental: str,
) -> None:
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {
            "id": "xp_a",
            "type": synthetic_experimental,
            "params": {},
        },
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid, strategy_name="one-xp", strategy_json=json_blob
    )
    assert report.compliance_score == 75
    assert len(report.warnings) == 1
    assert "experimental" in report.warnings[0].lower()


def test_one_blocked_strategy_scores_50() -> None:
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {
            "id": "ghost_inst",
            "type": "totally_made_up_xyz_v999",
            "params": {},
        },
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="one-blocked",
        strategy_json=json_blob,
    )
    assert report.compliance_score == 50
    assert len(report.blocking_issues) == 1
    assert len(report.recommendations) == 1
    assert "ghost_inst" in report.blocking_issues[0]


def test_score_clamps_at_zero_no_negative() -> None:
    """Six unknown indicators would compute to -200 raw — must
    clamp to 0, not go negative."""
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        *[
            {"id": f"ghost_{i}", "type": f"unknown_{i}_xyz", "params": {}}
            for i in range(6)
        ]
    )
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="all-blocked",
        strategy_json=json_blob,
    )
    assert report.compliance_score == 0


def test_empty_indicators_scores_100() -> None:
    """A strategy with no indicators (degenerate but valid) is
    fully compliant — there's nothing to be non-compliant about."""
    sid = uuid.uuid4()
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="empty",
        strategy_json={"indicators": []},
    )
    assert report.compliance_score == 100
    assert report.indicators_used == []


def test_malformed_strategy_json_is_silent() -> None:
    """Strategies with weird JSON shape (missing ``indicators``,
    non-list, dicts without ``type``) must not raise — the
    dashboard should always render. The evaluator silently skips
    malformed entries."""
    sid = uuid.uuid4()
    report = evaluate_strategy_compliance(
        strategy_id=sid,
        strategy_name="weird",
        strategy_json={
            "indicators": [
                "not-a-dict",
                {},  # missing type
                {"type": 123},  # type is not a string
                {"id": "ok", "type": "ema"},
            ],
        },
    )
    # Only the well-formed ema entry counts.
    assert len(report.indicators_used) == 1
    assert report.compliance_score == 100


# ─── summarise_strategy ───────────────────────────────────────────────


def test_summarise_keeps_counts_only() -> None:
    sid = uuid.uuid4()
    json_blob = _strategy_json(
        {"id": "ema_a", "type": "ema", "params": {}},
        {"id": "kama_a", "type": "kama", "params": {}},
        {"id": "ghost", "type": "missing_xyz", "params": {}},
    )
    full = evaluate_strategy_compliance(
        strategy_id=sid, strategy_name="mix", strategy_json=json_blob
    )
    summary = summarise_strategy(full)
    assert summary.strategy_id == full.strategy_id
    assert summary.strategy_name == full.strategy_name
    assert summary.compliance_score == full.compliance_score
    assert summary.indicator_count == 3
    assert summary.warning_count == 1
    assert summary.blocking_issue_count == 1
