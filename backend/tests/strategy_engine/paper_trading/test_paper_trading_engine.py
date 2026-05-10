"""Paper Trading Engine — 11 tests covering the spec matrix + safety.

The 10 tests called out in the spec, plus an AST-inspection test that
locks "no real broker order placement" by asserting nothing in the
``paper_trading`` package imports from ``app.brokers``.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.strategy_engine.paper_trading import (
    PaperReadinessReport,
    PaperSession,
    clear_paper_state,
    compute_readiness,
    end_session,
    get_session_trades,
    process_candle,
    start_session,
)
from app.strategy_engine.paper_trading.engine import (
    MIN_COMPLETED_SESSIONS,
)
from app.strategy_engine.schema.strategy import Side
from tests.strategy_engine.paper_trading.conftest import (
    fixed_user_id,
    make_candle,
    make_strategy,
)

# ─── 1. start_session shape ───────────────────────────────────────────


def test_start_session_returns_valid_paper_session() -> None:
    strategy = make_strategy()

    session = start_session(strategy, user_id=fixed_user_id())

    assert isinstance(session, PaperSession)
    assert session.strategy_id == strategy.id
    assert session.user_id == fixed_user_id()
    assert session.ended_at is None
    assert session.candles_processed == 0


# ─── 2. Phase 2 reuse — engine module imports the right primitives ────


def test_engine_reuses_phase2_entry_exit_and_position_primitives() -> None:
    """AST-inspect engine.py for the canonical Phase 2 imports.

    Re-implementing entry / exit / position transitions inside paper
    trading would cause double-maintenance and divergence with Phase 3.
    The spec is "reuse, don't reimplement" — this test pins it.
    """
    engine_path = (
        pathlib.Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "paper_trading"
        / "engine.py"
    )
    tree = ast.parse(engine_path.read_text(encoding="utf-8"))
    imports_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "app.strategy_engine.engines.entry" in imports_from
    assert "app.strategy_engine.engines.exit" in imports_from
    assert "app.strategy_engine.engines.position" in imports_from


# ─── 3. Next-bar entry contract ───────────────────────────────────────


def test_entry_signal_opens_position_at_next_bar_open_price() -> None:
    """Phase 3 contract: signal-on-close, fill-on-next-open."""
    strategy = make_strategy()  # condition: price > 99.5

    session = start_session(strategy, user_id=fixed_user_id())
    # Bar 0: condition fires (100 > 99.5) → entry queued for bar 1.
    process_candle(session, make_candle(minutes=0, open_=100.0), {})
    # Bar 1: position opens at this bar's open (100.0).
    process_candle(session, make_candle(minutes=1, open_=100.0), {})

    trades = get_session_trades(session)
    assert trades == []  # no exit yet — position still open.

    # Bar 2: target 102 hits intra-bar.
    closed = process_candle(
        session,
        make_candle(minutes=2, open_=100.5, high=102.0, low=100.0, close=101.0),
        {},
    )
    assert len(closed) == 1
    trade = closed[0]
    assert trade.entry_price == 100.0  # bar 1's open, NOT bar 0's close.


# ─── 4. Trade closes on target hit ────────────────────────────────────


def test_trade_closes_on_target_with_correct_pnl() -> None:
    strategy = make_strategy(
        exit_block={"targetPercent": 2.0, "stopLossPercent": 1.0},
    )

    session = start_session(strategy, user_id=fixed_user_id())
    process_candle(session, make_candle(minutes=0, open_=100.0), {})
    process_candle(session, make_candle(minutes=1, open_=100.0), {})
    closed = process_candle(
        session,
        make_candle(minutes=2, open_=100.0, high=102.0, low=100.0, close=101.0),
        {},
    )

    assert len(closed) == 1
    trade = closed[0]
    assert trade.side is Side.BUY
    assert trade.entry_price == 100.0
    assert trade.exit_price == 102.0  # target = entry * 1.02
    assert trade.pnl == pytest.approx(2.0)  # qty=1
    assert trade.exit_reason == "target"


# ─── 5. Trade closes on stop loss hit ─────────────────────────────────


def test_trade_closes_on_stop_loss_with_correct_pnl() -> None:
    strategy = make_strategy(
        exit_block={"targetPercent": 5.0, "stopLossPercent": 1.0},
    )

    session = start_session(strategy, user_id=fixed_user_id())
    process_candle(session, make_candle(minutes=0, open_=100.0), {})
    process_candle(session, make_candle(minutes=1, open_=100.0), {})
    closed = process_candle(
        session,
        make_candle(minutes=2, open_=100.0, high=100.5, low=99.0, close=99.5),
        {},
    )

    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_price == 99.0  # stop = entry * 0.99
    assert trade.pnl == pytest.approx(-1.0)
    assert trade.exit_reason == "stop_loss"


# ─── 6. Readiness: 7 winning sessions → live_ready=True ───────────────


def _winning_session() -> PaperSession:
    """Run a tiny 3-bar sequence that opens at 100 and closes at the 2 % target."""
    strategy = make_strategy()
    session = start_session(strategy, user_id=fixed_user_id())
    process_candle(session, make_candle(minutes=0, open_=100.0), {})
    process_candle(session, make_candle(minutes=1, open_=100.0), {})
    process_candle(
        session,
        make_candle(minutes=2, open_=100.0, high=102.0, low=100.0, close=101.0),
        {},
    )
    return end_session(session)


def test_seven_winning_sessions_yield_live_ready_true() -> None:
    sessions = [_winning_session() for _ in range(MIN_COMPLETED_SESSIONS)]

    report = compute_readiness(make_strategy(), sessions)

    assert isinstance(report, PaperReadinessReport)
    assert report.completed_sessions == MIN_COMPLETED_SESSIONS
    assert report.paper_pnl > 0
    assert report.paper_win_rate == 1.0
    assert report.rule_adherence_percent == 100.0
    assert report.live_ready is True
    assert report.blocked_reasons == ()


# ─── 7. Readiness: 6 sessions → blocked on count ──────────────────────


def test_six_winning_sessions_blocked_on_insufficient_count() -> None:
    sessions = [_winning_session() for _ in range(6)]

    report = compute_readiness(make_strategy(), sessions)

    assert report.completed_sessions == 6
    assert report.live_ready is False
    assert any("Insufficient completed sessions" in r for r in report.blocked_reasons)


# ─── 8. Readiness: 7 sessions but losing → blocked on PnL ─────────────


def _losing_session() -> PaperSession:
    """Open at 100, hit the 1 % stop loss for a -1 PnL."""
    strategy = make_strategy(
        exit_block={"targetPercent": 5.0, "stopLossPercent": 1.0},
    )
    session = start_session(strategy, user_id=fixed_user_id())
    process_candle(session, make_candle(minutes=0, open_=100.0), {})
    process_candle(session, make_candle(minutes=1, open_=100.0), {})
    process_candle(
        session,
        make_candle(minutes=2, open_=100.0, high=100.2, low=99.0, close=99.0),
        {},
    )
    return end_session(session)


def test_seven_losing_sessions_blocked_on_negative_pnl() -> None:
    sessions = [_losing_session() for _ in range(MIN_COMPLETED_SESSIONS)]

    report = compute_readiness(make_strategy(), sessions)

    assert report.completed_sessions == MIN_COMPLETED_SESSIONS
    assert report.paper_pnl < 0
    assert report.live_ready is False
    assert any("not positive" in r for r in report.blocked_reasons)


# ─── 9. Readiness: missing stop loss → blocked ────────────────────────


def test_missing_stop_loss_blocks_live_ready_even_with_winning_sessions() -> None:
    """Strategy has only a target — no SL means no live-ready, ever."""
    strategy = make_strategy(exit_block={"targetPercent": 2.0})  # no stopLossPercent
    sessions = [_winning_session() for _ in range(MIN_COMPLETED_SESSIONS)]

    report = compute_readiness(strategy, sessions)

    assert report.live_ready is False
    assert any("no stop loss" in r.lower() for r in report.blocked_reasons)


# ─── 10. Determinism — same input twice yields identical trades ───────


def test_two_runs_produce_identical_closed_trades() -> None:
    """Run a fixed sequence twice; closed trade dumps must be equal.

    Session timestamps (started_at / ended_at use datetime.now) differ
    between runs by design — we compare *trade* outputs, which are
    sourced from the supplied candle timestamps and so are deterministic.
    """

    def run() -> list[dict[str, object]]:
        clear_paper_state()
        strategy = make_strategy()
        session = start_session(strategy, user_id=fixed_user_id())
        process_candle(session, make_candle(minutes=0, open_=100.0), {})
        process_candle(session, make_candle(minutes=1, open_=100.0), {})
        process_candle(
            session,
            make_candle(minutes=2, open_=100.0, high=102.0, low=100.0, close=101.0),
            {},
        )
        end_session(session)
        return [
            t.model_dump(mode="json", exclude={"session_id"})
            for t in get_session_trades(session)
        ]

    first = run()
    second = run()
    assert first == second
    assert len(first) == 1


# ─── 11. Safety — no broker imports anywhere in the package ───────────


def test_paper_trading_package_does_not_import_any_broker_module() -> None:
    """AST-walk every .py under app/strategy_engine/paper_trading/.

    Asserts none of them import from ``app.brokers`` or
    ``app.services.broker_*`` — paper trading must remain broker-free.
    """
    pkg_root = (
        pathlib.Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "paper_trading"
    )
    offenders: list[str] = []
    for py_file in pkg_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app.brokers") or alias.name.startswith(
                        "app.services.broker"
                    ):
                        offenders.append(
                            f"{py_file.name}:{node.lineno} imports {alias.name}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module.startswith("app.brokers")
                    or node.module.startswith("app.services.broker")
                )
            ):
                offenders.append(
                    f"{py_file.name}:{node.lineno} imports from {node.module}"
                )
    assert not offenders, "Paper-trading must stay broker-free; found:\n  - " + "\n  - ".join(
        offenders
    )
