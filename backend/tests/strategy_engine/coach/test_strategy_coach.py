"""Strategy Coach — Hinglish health-card tests.

Coverage matrix:

    1.  Excellent strategy → A grade, every metric EXCELLENT.
    2.  90 % win rate + bad RR → win rate CONCERNING, overall F or D.
    3.  15 trades → trade count CONCERNING.
    4.  30 % drawdown → CONCERNING with ₹ in tip.
    5.  Negative expectancy → CONCERNING.
    6.  Reliability supplied vs absent — both code paths build a card.
    7.  Hinglish tips contain ₹ for monetary metrics.
    8.  Determinism — two runs of the same input produce identical card.
    9.  Pydantic round-trip via ``model_dump`` → ``model_validate``.
    10. AST-inspect coach package — no LLM / network imports.
"""

from __future__ import annotations

import ast
import pathlib

from app.strategy_engine.coach import (
    StrategyHealthCard,
    generate_health_card,
)
from tests.strategy_engine.coach.conftest import (
    make_backtest_result,
    make_reliability_with_trust,
)

# ─── 1. Excellent strategy → A ────────────────────────────────────────


def test_excellent_strategy_lands_in_grade_a_with_all_metrics_excellent() -> None:
    backtest = make_backtest_result(
        total_pnl=15_000.0,
        total_return_percent=120.0,
        win_rate=0.55,            # excellent (50-65%)
        total_trades=150,         # excellent (>100)
        average_win=300.0,
        average_loss=120.0,       # RR = 2.5x → excellent
        profit_factor=3.0,        # >2.0 → excellent
        max_drawdown=0.05,        # 5% → excellent
        expectancy=80.0,
    )

    card = generate_health_card(backtest)

    assert card.overall_grade == "A"
    grades = {m.metric_name: m.your_grade for m in card.metric_grades}
    assert all(g == "EXCELLENT" for g in grades.values()), grades


# ─── 2. Win-rate trap → CONCERNING + low overall grade ────────────────


def test_high_win_rate_with_bad_risk_reward_concerns_win_rate_and_drops_grade() -> None:
    """90 % win + tiny avg win, huge avg loss = classic over-fit shape."""
    backtest = make_backtest_result(
        total_pnl=-500.0,
        total_return_percent=-2.0,
        win_rate=0.90,            # > 85 → CONCERNING
        total_trades=60,
        average_win=50.0,
        average_loss=400.0,       # RR = 0.125 → CONCERNING
        profit_factor=0.95,       # < 1.2 → CONCERNING
        max_drawdown=0.20,
        expectancy=-8.3,
    )

    card = generate_health_card(backtest)

    by_name = {m.metric_name: m for m in card.metric_grades}
    assert by_name["Win Rate"].your_grade == "CONCERNING"
    assert by_name["Risk-Reward"].your_grade == "CONCERNING"
    assert "suspicious" in by_name["Win Rate"].hinglish_tip.lower() or "overfitting" in by_name["Win Rate"].hinglish_tip.lower()
    # Multiple concerning metrics should drop the overall grade into D or F.
    assert card.overall_grade in {"D", "F"}


# ─── 3. Low trade count → CONCERNING ──────────────────────────────────


def test_fifteen_trades_marks_total_trades_concerning() -> None:
    backtest = make_backtest_result(total_trades=15)

    card = generate_health_card(backtest)

    by_name = {m.metric_name: m for m in card.metric_grades}
    assert by_name["Total Trades"].your_grade == "CONCERNING"
    assert "15" in by_name["Total Trades"].hinglish_tip
    assert "luck" in by_name["Total Trades"].hinglish_tip.lower()


# ─── 4. 30 % drawdown → CONCERNING with ₹ in tip ──────────────────────


def test_thirty_percent_drawdown_concerning_with_rupee_example_in_tip() -> None:
    backtest = make_backtest_result(max_drawdown=0.30)

    card = generate_health_card(backtest)

    by_name = {m.metric_name: m for m in card.metric_grades}
    dd_row = by_name["Max Drawdown"]
    assert dd_row.your_grade == "CONCERNING"
    assert dd_row.your_value == 30.0
    # Concrete-rupee example for the operator.
    assert "₹" in dd_row.hinglish_tip
    assert "₹100" in dd_row.hinglish_tip


# ─── 5. Negative expectancy → CONCERNING ──────────────────────────────


def test_negative_expectancy_marks_concerning_and_mentions_loss_in_tip() -> None:
    """Negative total_return / total_trades drives the expectancy gate."""
    backtest = make_backtest_result(
        total_return_percent=-30.0,  # losing strategy overall
        total_trades=50,
    )

    card = generate_health_card(backtest)

    by_name = {m.metric_name: m for m in card.metric_grades}
    exp_row = by_name["Expectancy"]
    assert exp_row.your_grade == "CONCERNING"
    assert exp_row.your_value < 0
    assert "loss" in exp_row.hinglish_tip.lower()
    assert "₹" in exp_row.hinglish_tip


# ─── 6. Reliability supplied vs absent ────────────────────────────────


def test_card_produced_with_reliability_includes_trust_learning_tip() -> None:
    backtest = make_backtest_result()
    reliability = make_reliability_with_trust(backtest, trust_score=55, grade="C")

    card = generate_health_card(backtest, reliability=reliability)

    assert any("trust score" in t.lower() for t in card.learning_tips)
    assert any("55" in t for t in card.learning_tips)


def test_card_produced_without_reliability_still_has_learning_tips() -> None:
    backtest = make_backtest_result()

    card = generate_health_card(backtest)

    assert isinstance(card, StrategyHealthCard)
    assert card.learning_tips  # non-empty
    # No reliability-flavoured tip when reliability is None.
    assert not any("trust score" in t.lower() for t in card.learning_tips)


# ─── 7. ₹ presence on monetary tips ───────────────────────────────────


def test_profit_factor_and_drawdown_tips_use_rupee_for_monetary_examples() -> None:
    """Profit factor (good) and drawdown (concerning) anchor money to ₹."""
    backtest = make_backtest_result(
        profit_factor=1.7,        # GOOD
        max_drawdown=0.30,        # CONCERNING
    )

    card = generate_health_card(backtest)

    by_name = {m.metric_name: m for m in card.metric_grades}
    assert "₹" in by_name["Profit Factor"].hinglish_tip
    assert "₹" in by_name["Max Drawdown"].hinglish_tip


# ─── 8. Determinism — two runs equal ─────────────────────────────────


def test_two_runs_produce_identical_cards() -> None:
    backtest = make_backtest_result(
        total_pnl=4_200.0,
        total_return_percent=42.0,
        win_rate=0.58,
        total_trades=80,
        average_win=210.0,
        average_loss=140.0,
        profit_factor=1.7,
        max_drawdown=0.12,
        expectancy=52.5,
    )

    first = generate_health_card(backtest)
    second = generate_health_card(backtest)

    assert first.model_dump() == second.model_dump()


# ─── 9. Pydantic round-trip ──────────────────────────────────────────


def test_health_card_round_trips_through_pydantic_validation() -> None:
    backtest = make_backtest_result()
    card = generate_health_card(backtest)

    dumped = card.model_dump(mode="json")
    rebuilt = StrategyHealthCard.model_validate(dumped)

    assert rebuilt == card


# ─── 10. AST inspection — no LLM / network imports ───────────────────


_FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {"anthropic", "openai", "httpx", "requests", "aiohttp", "urllib"}
)


def test_no_llm_or_network_imports_in_coach_package() -> None:
    pkg_root = (
        pathlib.Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "coach"
    )
    offenders: list[str] = []
    for py_file in pkg_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _FORBIDDEN_MODULES:
                        offenders.append(
                            f"{py_file.name}:{node.lineno} imports {alias.name}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.split(".")[0] in _FORBIDDEN_MODULES
            ):
                offenders.append(
                    f"{py_file.name}:{node.lineno} imports from {node.module}"
                )
    assert not offenders, "Coach must remain LLM/network-free; found:\n  - " + "\n  - ".join(
        offenders
    )


# ─── 11. ASCII safety — only %, ₹ allowed beyond ASCII ────────────────


def test_all_card_strings_are_ascii_plus_rupee_and_percent() -> None:
    backtest = make_backtest_result(max_drawdown=0.30, total_trades=15)
    card = generate_health_card(backtest)

    allowed_extra = {"₹", "%"}

    def _check(text: str, where: str) -> list[str]:
        out: list[str] = []
        for ch in text:
            if ord(ch) < 128 or ch in allowed_extra:
                continue
            out.append(f"{where}: non-ASCII char {ch!r} (U+{ord(ch):04X})")
        return out

    offenders: list[str] = []
    offenders.extend(_check(card.overall_summary_hinglish, "summary"))
    for tip in card.learning_tips:
        offenders.extend(_check(tip, "learning_tip"))
    for step in card.next_steps_hinglish:
        offenders.extend(_check(step, "next_step"))
    for m in card.metric_grades:
        offenders.extend(_check(m.hinglish_tip, f"{m.metric_name} tip"))

    assert not offenders, "ASCII-safety violation:\n  - " + "\n  - ".join(offenders)
