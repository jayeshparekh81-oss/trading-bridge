"""Sanity tests for the locked Phase 4 constants.

The values are product-locked — these tests only enforce shape/contiguity
invariants so a future edit to ``constants.py`` can't accidentally introduce
overlap or holes in the grade ranges.
"""

from __future__ import annotations

from app.strategy_engine.reliability.constants import (
    GRADE_VERDICTS,
    HIGH_WIN_RATE_WARNING_THRESHOLD,
    OOS_DEGRADATION_WARNING_THRESHOLD,
    PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD,
    PARAMETER_SENSITIVITY_VARIATION,
    TRUST_SCORE_GRADES,
    WALK_FORWARD_WINDOWS,
)


def test_locked_thresholds_match_approval_message() -> None:
    """The four headline thresholds must match the Phase 4 approval message."""
    assert HIGH_WIN_RATE_WARNING_THRESHOLD == 0.85
    assert OOS_DEGRADATION_WARNING_THRESHOLD == 0.25
    assert WALK_FORWARD_WINDOWS == 5
    assert PARAMETER_SENSITIVITY_VARIATION == 0.20
    assert PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD == 0.30


def test_grade_ranges_are_contiguous_and_non_overlapping() -> None:
    """A→B→C→D→F must tile [0, 100] without gaps or overlaps."""
    expected = {
        "A": (85, 100),
        "B": (70, 84),
        "C": (55, 69),
        "D": (40, 54),
        "F": (0, 39),
    }
    assert expected == TRUST_SCORE_GRADES


def test_each_grade_has_a_verdict() -> None:
    """Every grade key must have a non-empty human-readable verdict."""
    assert set(GRADE_VERDICTS.keys()) == set(TRUST_SCORE_GRADES.keys())
    for grade, verdict in GRADE_VERDICTS.items():
        assert isinstance(verdict, str)
        assert len(verdict) > 0, f"Grade {grade} has empty verdict"


def test_grade_ranges_cover_zero_to_hundred() -> None:
    """Union of ranges spans [0, 100] exactly."""
    covered: set[int] = set()
    for low, high in TRUST_SCORE_GRADES.values():
        covered.update(range(low, high + 1))
    assert covered == set(range(0, 101))
