"""Trust-score: A/B/C/D/F grade boundary tests."""

from __future__ import annotations

import pytest

from app.strategy_engine.reliability.constants import TRUST_SCORE_GRADES
from app.strategy_engine.reliability.trust_score import grade_for


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        (100, "A"),
        (90, "A"),
        (85, "A"),
        (84, "B"),
        (75, "B"),
        (70, "B"),
        (69, "C"),
        (60, "C"),
        (55, "C"),
        (54, "D"),
        (45, "D"),
        (40, "D"),
        (39, "F"),
        (20, "F"),
        (0, "F"),
    ],
)
def test_grade_for_returns_correct_letter(score: int, expected_grade: str) -> None:
    assert grade_for(score) == expected_grade


def test_grade_for_clamps_above_hundred_to_a() -> None:
    """Inputs above 100 should be treated as 100 (defensive)."""
    assert grade_for(150) == "A"


def test_grade_for_clamps_below_zero_to_f() -> None:
    """Negative scores should be treated as 0."""
    assert grade_for(-25) == "F"


def test_every_grade_letter_has_at_least_one_score() -> None:
    """Sanity: each grade is reachable for at least one valid 0-100 score."""
    seen = set()
    for s in range(0, 101):
        seen.add(grade_for(s))
    assert seen == set(TRUST_SCORE_GRADES.keys())
