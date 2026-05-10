"""Live-vs-Backtest Deviation Monitor — locked behaviour pinned by 12 cases.

Synthetic backtest + live stats are tuned so each test isolates one
metric or one decision rule. The 12 cases mirror the spec one-for-one
(see ``prompts/master-plan-final.md`` "Live vs Backtest Deviation
Monitor") so anyone reading the test list immediately sees what
behaviour is locked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.strategy_engine.deviation import (
    DeviationReport,
    evaluate_deviation,
)
from tests.strategy_engine.deviation.conftest import (
    make_backtest,
    make_live_stats,
)


def _named_severities(report: DeviationReport) -> dict[str, str]:
    return {m.metric_name: m.severity for m in report.deviations}


# ─── 1. Insufficient trades → status="normal" ──────────────────────────


def test_insufficient_trades_returns_normal_with_message() -> None:
    """Below the 10-trade gate the monitor declines to evaluate.

    The report still surfaces — UI has something to render — but
    ``deviations`` is empty, the status is ``normal``, and the
    Hinglish summary explains *why* the analysis was skipped.
    """
    backtest = make_backtest(total_trades=50)
    live = make_live_stats(total_trades=5, sessions=2)
    report = evaluate_deviation(backtest, live)
    assert report.status == "normal"
    assert report.deviations == ()
    assert report.auto_kill_switch_signal is False
    assert "Insufficient" in report.hinglish_summary
    assert report.deviation_score == 0.0


# ─── 2. Perfect match → status="normal", score < 5 ─────────────────────


def test_perfect_match_returns_normal() -> None:
    """When live exactly mirrors the backtest, every metric is in the
    ``normal`` band → score is ``0.0`` and the kill-switch advisory
    stays low."""
    backtest = make_backtest()
    live = make_live_stats()
    report = evaluate_deviation(backtest, live)
    assert report.status == "normal"
    assert report.deviation_score < 5
    assert report.auto_kill_switch_signal is False
    severities = _named_severities(report)
    assert severities["win_rate"] == "normal"
    assert severities["drawdown"] == "normal"
    assert severities["profit_factor"] == "normal"
    assert severities["trade_frequency"] == "normal"


# ─── 3. Win rate 25% below expected → warning ──────────────────────────


def test_win_rate_25_pct_below_is_warning() -> None:
    backtest = make_backtest(win_rate=0.6)
    live = make_live_stats(win_rate=0.35)  # diff 0.25 → warning band
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["win_rate"] == "warning"
    assert report.status in ("warning", "critical")


# ─── 4. Win rate 35% below expected → critical ────────────────────────


def test_win_rate_35_pct_below_is_critical() -> None:
    backtest = make_backtest(win_rate=0.6)
    live = make_live_stats(win_rate=0.25)  # diff 0.35 → critical band
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["win_rate"] == "critical"
    assert report.status == "critical"
    assert report.auto_kill_switch_signal is True


# ─── 5. Drawdown 1.8x expected → warning ──────────────────────────────


def test_drawdown_1_8x_expected_is_warning() -> None:
    backtest = make_backtest(max_drawdown=0.10)
    live = make_live_stats(max_drawdown=0.18)  # 1.8x → warning band
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["drawdown"] == "warning"
    assert report.status in ("warning", "critical")


# ─── 6. Drawdown 2.5x expected → critical, kill-switch True ───────────


def test_drawdown_2_5x_expected_is_critical_with_killswitch_signal() -> None:
    backtest = make_backtest(max_drawdown=0.10)
    live = make_live_stats(max_drawdown=0.25)  # 2.5x → critical band
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["drawdown"] == "critical"
    assert report.status == "critical"
    assert report.auto_kill_switch_signal is True


# ─── 7. Profit factor 60% drop → critical ─────────────────────────────


def test_profit_factor_60_pct_drop_is_critical() -> None:
    backtest = make_backtest(profit_factor=2.0)
    live = make_live_stats(profit_factor=0.8)  # drop 60% → critical band
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["profit_factor"] == "critical"
    assert report.status == "critical"


# ─── 8. Trade frequency 60% lower → warning ───────────────────────────


def test_trade_frequency_60_pct_lower_is_warning() -> None:
    """Backtest = 50 trades over 10 days = 5/day; live = 20/10 = 2/session.
    diff = (5 - 2) / 5 = 60% → warning band (50-75%)."""
    backtest = make_backtest(total_trades=50, period_days=10.0)
    live = make_live_stats(total_trades=20, sessions=10)
    report = evaluate_deviation(backtest, live)
    assert _named_severities(report)["trade_frequency"] == "warning"


# ─── 9. should_pause=True only when status==critical ──────────────────


def test_should_pause_is_true_only_when_status_critical() -> None:
    """Sweep all four severities and assert the decision flags follow
    the locked map."""
    # critical (via win-rate)
    crit = evaluate_deviation(
        make_backtest(win_rate=0.7),
        make_live_stats(win_rate=0.3),  # diff 0.4
    )
    assert crit.status == "critical"
    assert crit.should_pause is True
    assert crit.should_reduce_size is True
    assert crit.should_switch_to_paper is True

    # warning (via win-rate diff 0.25)
    warn = evaluate_deviation(
        make_backtest(win_rate=0.6),
        make_live_stats(win_rate=0.35),
    )
    assert warn.status == "warning"
    assert warn.should_pause is False
    assert warn.should_reduce_size is True
    assert warn.should_switch_to_paper is True

    # watch (via win-rate diff 0.15)
    watch = evaluate_deviation(
        make_backtest(win_rate=0.6),
        make_live_stats(win_rate=0.45),
    )
    assert watch.status == "watch"
    assert watch.should_pause is False
    assert watch.should_reduce_size is False
    assert watch.should_switch_to_paper is False

    # normal (perfect match) — already pinned by test_perfect_match.


# ─── 10. should_switch_to_paper=True for warning AND critical ─────────


def test_paper_switch_fires_for_warning_and_critical() -> None:
    """Same locked rule as test 9, but pinned independently so renaming
    the flag still trips this assertion."""
    warn = evaluate_deviation(
        make_backtest(win_rate=0.6),
        make_live_stats(win_rate=0.35),
    )
    crit = evaluate_deviation(
        make_backtest(win_rate=0.7),
        make_live_stats(win_rate=0.3),
    )
    assert warn.should_switch_to_paper is True
    assert crit.should_switch_to_paper is True


# ─── 11. Determinism — running twice gives equal reports ──────────────


def test_evaluation_is_deterministic_across_runs() -> None:
    """Two identical calls must produce equal reports (frozen Pydantic
    structural equality). Catches accidental ``set`` ordering, ``dict``
    iteration drift, or hidden randomness."""
    backtest = make_backtest()
    live = make_live_stats(win_rate=0.4, max_drawdown=0.16)
    first = evaluate_deviation(backtest, live)
    second = evaluate_deviation(backtest, live)
    assert first == second
    assert first.deviation_score == second.deviation_score
    assert first.status == second.status


# ─── 12. AST inspection — no broker / kill-switch / AI imports ────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "app.services.fyers",
    "app.services.dhan",
    "app.services.broker",
    "app.brokers",
    "app.services.kill_switch",
    "app.services.algomitra_ai",
    "app.services.ai_validator",
)
_FORBIDDEN_SUFFIX_HINTS: tuple[str, ...] = (
    "kill_switch",
    "fyers_",
    "dhan_",
    "broker_",
    "algomitra_ai",
    "ai_validator",
)


def _deviation_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "deviation"
    return sorted(p for p in pkg_root.glob("*.py"))


@pytest.mark.parametrize("source_file", _deviation_python_files())
def test_deviation_module_does_not_import_broker_killswitch_or_ai(
    source_file: Path,
) -> None:
    """Walk every import in every deviation *.py file and assert it
    does not pull in a broker adapter, the kill-switch implementation,
    or any LLM/AI validator service.

    The monitor is, by design, isolated from execution-side modules — it
    consumes only structured outputs of upstream phases and emits
    advisory signals. This test pins that isolation so a future
    contributor can't quietly couple the monitor to a side-effecting
    service.
    """
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    if any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES):
        return True
    last_segment = name.rsplit(".", 1)[-1]
    return any(hint in last_segment for hint in _FORBIDDEN_SUFFIX_HINTS)
