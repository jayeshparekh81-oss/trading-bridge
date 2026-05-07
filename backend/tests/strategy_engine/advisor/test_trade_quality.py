"""Trade Quality scorer tests.

Pure-function coverage for the five-component trade-quality engine.
Each test fabricates a :class:`BacktestResult` directly (no candles,
no simulator) so the assertions hit precise metric inputs.
"""

from __future__ import annotations

import ast
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.strategy_engine.advisor import (
    TradeQualityComponent,
    TradeQualityReport,
    compute_trade_quality,
)
from app.strategy_engine.advisor.trade_quality import (
    COMPONENT_WEIGHTS,
    GRADE_BOUNDS,
    MIN_TRADES_FOR_QUALITY,
)
from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.backtest.trade_log import Trade
from app.strategy_engine.schema.strategy import Side

# ─── Builders ──────────────────────────────────────────────────────────


_BASE_TS = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)


def _make_trade(
    *,
    pnl: float,
    exit_reason: str = "target",
    side: Side = Side.BUY,
    offset_minutes: int = 0,
) -> Trade:
    """Build a real :class:`Trade`. Prices are fixtures — only ``pnl``
    and ``exit_reason`` matter to the trade-quality scorer."""
    return Trade(
        entry_time=_BASE_TS + timedelta(minutes=offset_minutes),
        exit_time=_BASE_TS + timedelta(minutes=offset_minutes + 5),
        side=side,
        entry_price=100.0,
        exit_price=101.0,
        quantity=1.0,
        pnl=pnl,
        exit_reason=exit_reason,
    )


def _make_backtest(
    *,
    total_pnl: float = 1000.0,
    total_return_percent: float = 10.0,
    win_rate: float = 0.55,
    total_trades: int | None = None,
    average_win: float = 200.0,
    average_loss: float = 100.0,
    max_drawdown: float = 0.08,
    profit_factor: float = 2.0,
    expectancy: float = 20.0,
    trades: list[Trade] | None = None,
) -> BacktestResult:
    """Synthesise a :class:`BacktestResult` with caller-controlled trades."""
    trade_list = list(trades) if trades is not None else []
    # When the caller passes a trade list, default ``total_trades`` to
    # its length so the per-trade denominators (consistency, exit-
    # discipline) line up with the trades the report actually inspects.
    if total_trades is not None:
        n = total_trades
    elif trade_list:
        n = len(trade_list)
    else:
        n = 50
    return BacktestResult(
        total_pnl=total_pnl,
        total_return_percent=total_return_percent,
        win_rate=win_rate,
        loss_rate=max(0.0, 1.0 - win_rate),
        total_trades=n,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=average_win * 2,
        largest_loss=average_loss * 2,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=expectancy,
        equity_curve=[],
        trades=trade_list,
        warnings=[],
    )


def _excellent_trades(n: int = 20) -> list[Trade]:
    """``n`` target-exit trades with tight, positive pnls — drives
    excellent scores on consistency and exit-discipline."""
    return [
        _make_trade(pnl=110.0 + (i % 3), exit_reason="target", offset_minutes=i * 5)
        for i in range(n)
    ]


# ─── 1. Excellent strategy → grade A, all components high ─────────────


def test_excellent_strategy_lands_in_grade_a() -> None:
    backtest = _make_backtest(
        average_win=300.0,
        average_loss=100.0,  # RR = 3.0 → 100
        max_drawdown=0.04,  # → 100
        trades=_excellent_trades(20),  # consistency + exits → 100 each
    )
    # Pass gross_pnl such that the survival ratio is excellent (1.0 → 100).
    report = compute_trade_quality(backtest, gross_pnl=backtest.total_pnl)

    assert isinstance(report, TradeQualityReport)
    assert report.grade == "A"
    assert report.overall_score >= GRADE_BOUNDS["A"]
    assert len(report.components) == 5
    # Every component lands in the strengths bucket (≥ 80).
    component_names = {c.component_name for c in report.components}
    assert component_names == {
        "risk_reward",
        "consistency",
        "drawdown",
        "cost_survival",
        "exit_discipline",
    }
    assert all(c.score >= 80.0 for c in report.components)
    assert "Strong risk-reward ratio" in report.strengths
    assert report.weaknesses == ()


# ─── 2. Bad RR → component 1 low ──────────────────────────────────────


def test_bad_risk_reward_marks_component_low() -> None:
    backtest = _make_backtest(
        average_win=80.0,
        average_loss=200.0,  # RR = 0.4 → score 10
        trades=_excellent_trades(20),
    )
    report = compute_trade_quality(backtest)
    rr = next(c for c in report.components if c.component_name == "risk_reward")
    assert rr.score == 10.0
    assert "Risk-reward ratio too low" in report.weaknesses
    # The tip references the actual ratio in ₹ form.
    assert "₹0.40" in rr.hinglish_tip


# ─── 3. Wild variance → component 2 low ───────────────────────────────


def test_wild_variance_trades_marks_consistency_low() -> None:
    """Mix one giant winner with many tiny losers so the cv is huge."""
    wild = [
        _make_trade(pnl=10_000.0, exit_reason="target", offset_minutes=0),
        *[
            _make_trade(pnl=-50.0, exit_reason="stop_loss", offset_minutes=i * 5)
            for i in range(1, 20)
        ],
    ]
    backtest = _make_backtest(trades=wild)
    report = compute_trade_quality(backtest)
    consistency = next(c for c in report.components if c.component_name == "consistency")
    assert consistency.score <= 40.0
    assert "Trade outcomes too variable" in report.weaknesses


# ─── 4. High drawdown → component 3 low ───────────────────────────────


def test_high_drawdown_marks_component_low() -> None:
    backtest = _make_backtest(
        max_drawdown=0.30,  # 30 % → score 25
        trades=_excellent_trades(20),
    )
    report = compute_trade_quality(backtest)
    dd = next(c for c in report.components if c.component_name == "drawdown")
    assert dd.score == 25.0
    assert "Drawdown too high" in report.weaknesses
    # Tip carries the actual drawdown percentage.
    assert "30.0%" in dd.hinglish_tip


# ─── 5. Cost destroys profit → component 4 low ────────────────────────


def test_cost_destroys_profit_marks_component_low() -> None:
    backtest = _make_backtest(
        total_pnl=50.0,  # Net survives at only 5 % of gross.
        trades=_excellent_trades(20),
    )
    report = compute_trade_quality(backtest, gross_pnl=1000.0)
    cost = next(c for c in report.components if c.component_name == "cost_survival")
    assert cost.score == 10.0  # ratio 0.05 → bottom band
    assert "Costs erode profit" in report.weaknesses
    # Hinglish tip mentions a percentage.
    assert "%" in cost.hinglish_tip


def test_cost_survival_falls_back_to_unknown_sentinel_when_gross_omitted() -> None:
    backtest = _make_backtest(trades=_excellent_trades(20))
    report = compute_trade_quality(backtest)  # no gross_pnl
    cost = next(c for c in report.components if c.component_name == "cost_survival")
    assert cost.score == 50.0
    assert "Cost data uplabdh nahi hai" in cost.hinglish_tip


# ─── 6. Many indicator exits → component 5 low ────────────────────────


def test_many_indicator_exits_marks_exit_discipline_low() -> None:
    """20 trades — only 4 are structured exits, the rest are indicator
    or time exits. fraction = 0.20 → score 30 (bottom band)."""
    structured = [
        _make_trade(pnl=100.0, exit_reason="target", offset_minutes=i * 5) for i in range(2)
    ]
    structured += [
        _make_trade(pnl=-50.0, exit_reason="stop_loss", offset_minutes=(i + 2) * 5)
        for i in range(2)
    ]
    unstructured = [
        _make_trade(pnl=20.0, exit_reason="indicator", offset_minutes=(i + 4) * 5) for i in range(8)
    ] + [_make_trade(pnl=10.0, exit_reason="time", offset_minutes=(i + 12) * 5) for i in range(8)]
    backtest = _make_backtest(trades=structured + unstructured)
    report = compute_trade_quality(backtest)
    exits = next(c for c in report.components if c.component_name == "exit_discipline")
    assert exits.score == 30.0
    assert "Weak exit discipline" in report.weaknesses
    assert "20% trades structured exits se band hue" in exits.hinglish_tip


# ─── 7. Insufficient trades → grade F + empty components ──────────────


def test_insufficient_trades_returns_placeholder_report() -> None:
    backtest = _make_backtest(total_trades=5, trades=_excellent_trades(5))
    report = compute_trade_quality(backtest)
    assert report.grade == "F"
    assert report.overall_score == 0.0
    assert report.components == ()
    assert report.strengths == ()
    assert report.weaknesses == ()
    assert "5 trades" in report.overall_summary_hinglish
    # Boundary: exactly MIN_TRADES_FOR_QUALITY runs the full pipeline.
    boundary = _make_backtest(
        total_trades=MIN_TRADES_FOR_QUALITY,
        trades=_excellent_trades(MIN_TRADES_FOR_QUALITY),
    )
    assert len(compute_trade_quality(boundary).components) == 5


# ─── 8. Determinism: same input → same output ─────────────────────────


def test_compute_trade_quality_is_deterministic() -> None:
    backtest = _make_backtest(trades=_excellent_trades(20))
    a = compute_trade_quality(backtest, gross_pnl=backtest.total_pnl)
    b = compute_trade_quality(backtest, gross_pnl=backtest.total_pnl)
    assert a == b
    assert a.components == b.components
    assert a.overall_score == b.overall_score


# ─── 9. Weights sum to 1.0 (module-load + runtime check) ──────────────


def test_component_weights_sum_to_one() -> None:
    """The aggregator assumes weights sum to 1.0; the module-load
    assertion would have raised on import. Re-confirm at runtime so a
    silent edit on the constant tuple still trips a test."""
    assert math.isclose(sum(COMPONENT_WEIGHTS), 1.0, abs_tol=1e-9)
    # And each component on a real report carries its locked weight.
    backtest = _make_backtest(trades=_excellent_trades(20))
    report = compute_trade_quality(backtest)
    weights = [c.weight for c in report.components]
    assert math.isclose(sum(weights), 1.0, abs_tol=1e-9)


# ─── 10. Hinglish tips contain ₹ for currency-bearing components ──────


def test_hinglish_tips_contain_rupee_symbol_for_currency_metrics() -> None:
    """Risk-reward and drawdown tips both reference ``₹`` in their
    bands — the spec calls this out as a hard requirement."""
    backtest = _make_backtest(
        average_win=300.0,
        average_loss=100.0,
        max_drawdown=0.45,  # >40 % → bottom band → tip uses ₹/100 example
        trades=_excellent_trades(20),
    )
    report = compute_trade_quality(backtest)
    rr_tip = next(c.hinglish_tip for c in report.components if c.component_name == "risk_reward")
    dd_tip = next(c.hinglish_tip for c in report.components if c.component_name == "drawdown")
    assert "₹" in rr_tip
    assert "₹" in dd_tip


# ─── 11. AST inspection: no forbidden imports ─────────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "aiohttp",
    "websocket",
    "websockets",
    "socket",
    "app.services",
)


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


def test_trade_quality_module_has_no_llm_or_network_imports() -> None:
    source_file = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "advisor"
        / "trade_quality.py"
    )
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
    assert not offenders, f"trade_quality.py pulls in forbidden modules: {offenders}"


# ─── 12. ASCII safety: every string is ASCII or ₹/% ───────────────────


_ALLOWED_NON_ASCII: frozenset[str] = frozenset({"₹"})


def _is_safe(text: str) -> bool:
    for ch in text:
        if ord(ch) < 128:
            continue
        if ch in _ALLOWED_NON_ASCII:
            continue
        return False
    return True


def test_all_report_strings_are_ascii_plus_rupee_and_percent() -> None:
    """Every Hinglish-bearing string in the report is ASCII-safe save
    for ``₹`` (``%`` is plain ASCII)."""
    backtest = _make_backtest(trades=_excellent_trades(20))
    report = compute_trade_quality(backtest, gross_pnl=backtest.total_pnl)
    assert _is_safe(report.overall_summary_hinglish), report.overall_summary_hinglish
    for c in report.components:
        assert _is_safe(c.component_name), c.component_name
        assert _is_safe(c.hinglish_tip), c.hinglish_tip
    for s in [*report.strengths, *report.weaknesses]:
        assert _is_safe(s), s


# ─── 13. Pydantic round-trip via model_dump / model_validate ──────────


def test_trade_quality_report_round_trips_through_pydantic() -> None:
    backtest = _make_backtest(trades=_excellent_trades(20))
    original = compute_trade_quality(backtest, gross_pnl=backtest.total_pnl)
    raw = original.model_dump_json()
    restored = TradeQualityReport.model_validate_json(raw)
    assert restored == original
    # Every component round-trips too.
    for orig_c, new_c in zip(original.components, restored.components, strict=True):
        assert isinstance(new_c, TradeQualityComponent)
        assert orig_c == new_c
