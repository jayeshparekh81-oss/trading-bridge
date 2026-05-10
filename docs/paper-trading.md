# Paper Trading Engine

> Status: Production-ready
> Engine introduced: Commit `9bd8245`
> DB persistence (Migration 010): Commit `74e3e3d`
> SafetyChain integration: Commit `9c5b811`
> Last updated: 2026-05-09

## Overview

The Paper Trading Engine is a deterministic, broker-free,
LLM-free, candle-driven simulator that runs the same Phase 2
entry / exit / position primitives the batch backtest uses,
just one candle at a time. It exists for one load-bearing
reason: **before any user can place real money on a strategy,
they must demonstrate at least 7 completed paper-trading
sessions on it.** That 7-session requirement is the
strategy-maturity gate of the live-orders SafetyChain.

The engine itself is in-memory + deterministic; the
`paper_sessions` + `paper_trades` tables (Migration 010) carry
the durable record across process restarts so the SafetyChain's
`get_completed_sessions_count` query keeps working.

## Why It Exists

Backtests describe "what would have happened on historical
candles". Paper-trading sessions describe "what actually
happened tick by tick on data the user explicitly walked
through". The distinction matters because:

- **Strategies look great in a backtest, then bleed live.** The
  engine surfaces the gap before real money touches it.
- **Users underestimate slippage + execution lag.** Paper trading
  doesn't perfectly model these but it does force the user to
  experience the strategy bar-by-bar for at least 7 days.
- **The SafetyChain needs a maturity proof.** Live trading is
  gated on `get_completed_sessions_count >= 7`; without the
  paper-trading record there's nothing to count.

## Public API

```python
from app.strategy_engine.paper_trading import (
    start_session,
    process_candle,
    end_session,
    get_session_trades,
    compute_readiness,
    clear_paper_state,
)

# 1. Start a session.
session = start_session(strategy=strategy_json, user_id=user.id)
# session is a frozen PaperSession Pydantic model.

# 2. Drive the simulation candle-by-candle.
closed_trades = process_candle(session, candle, indicator_values)
# closed_trades is the list of trades that closed on this candle
# (target hit / stop loss / time-based exit / etc.).

# 3. End the session when the user / cron stops it.
ended = end_session(session)
# ended.ended_at is now non-None.

# 4. Read the trades it produced.
trades = get_session_trades(session.id)

# 5. Once the user has multiple sessions, check live-readiness.
readiness = compute_readiness(strategy=strategy_json, sessions=user_sessions)
# readiness.is_ready          → bool
# readiness.completed_sessions → int (must be >= 7 for live)
# readiness.warnings           → tuple[str]
```

Source: `backend/app/strategy_engine/paper_trading/engine.py`.

## Lifecycle

```
start_session(strategy, user_id)         → PaperSession (frozen)
process_candle(session, candle, ivals)   → list[PaperTrade] closed
process_candle(session, candle, ivals)   → ...
end_session(session)                     → PaperSession (with ended_at)
compute_readiness(strategy, sessions)    → PaperReadinessReport
```

The engine holds its mutable state in a module-level
`_RECORDS: dict[UUID, _SessionRecord]` map. Every snapshot the
caller receives is **immutable** — `_RECORDS` is the single
source of truth for live state and it's never exposed
directly. `get_session_trades` is the canonical way to fetch
trades; `clear_paper_state()` resets the dict (tests use it
for isolation).

## Conservative Exit Prioritisation

When multiple exit conditions trigger in the same candle, the
engine resolves them in **locked priority order**:

```
stop_loss > trailing_stop > square_off > time > reverse_signal >
indicator-based-exit > target
```

The intuition: a stop loss is the loudest signal "I want out at
any cost"; honoring it before a profit target avoids falsely
counting a stop-loss day as a winner because the candle also
hit the target. The order is pinned by tests so a refactor that
reshuffles trips a regression.

## DB Persistence (Migration 010)

The engine itself is in-process. The `paper_sessions` +
`paper_trades` tables (Migration 010, commit `74e3e3d`) are
the durable record:

- `paper_sessions` — one row per (user, strategy, day). Carries
  `is_complete`, `total_trades`, `total_pnl`,
  `engine_strategy_id`, `started_at`, `completed_at`. Unique
  on `(user_id, strategy_id, session_date)` so the 7-session
  count query counts distinct days, not session restarts.
- `paper_trades` — one row per closed trade. CASCADE-deleted
  with the parent session.

Persistence is the bridge between the in-memory engine and the
SafetyChain's DB query. The bridge module
(`paper_trading/persistence.py`) writes `PaperSession` snapshots
into the table on `end_session`.

## Readiness Check Algorithm

`compute_readiness(strategy, sessions)` walks the user's
sessions for that strategy and returns:

- `completed_sessions: int` — count of `PaperSession` rows
  where `is_complete is True`.
- `is_ready: bool` — `completed_sessions >= 7` AND no warning
  conditions trip.
- `warnings: tuple[str]` — Hinglish hints when sessions are
  short, all on the same day, missing trades, etc.

The 7-session minimum is a constant in
`paper_trading/constants.py::REQUIRED_COMPLETED_SESSIONS`. It's
a constant (not env var) for the same reason advisor thresholds
are constants — letting an operator silently lower the bar
weakens safety.

## SafetyChain Integration

The live-orders SafetyChain (commit `9c5b811`) consults the
paper-trading record as its **second** safety check, right
after the kill switch:

```
1. auto_kill_switch     ← platform safety
2. paper_sessions       ← THIS — strategy maturity gate
3. trust_score
4. truth_score
5. live_trading_enabled
6. broker_connection
7. risk_engine_precheck (deferred)
```

The check calls a small slim function (not the full
`compute_readiness`) — see
[`/docs/broker-execution-guard.md`](./broker-execution-guard.md)
for why the SafetyChain consumes a slim subset of the full
guard pipeline.

## Configuration

Constants in `paper_trading/constants.py`:

- `REQUIRED_COMPLETED_SESSIONS = 7` — the gate.
- `STRATEGY_PAPER_LTP_VOLATILITY` — per-tick volatility for the
  paper LTP random walk (env-overridable for tuning).
- `STRATEGY_PAPER_LTP_DRIFT_BIAS` — `up` / `down` / `neutral`
  drift bias used when testing exit primitives.

## Edge Cases & Limitations

- **In-process state is not multi-process-safe.** Two app
  instances running paper sessions for the same user will
  diverge in their in-memory `_RECORDS` dict. Production
  deploys behind a load balancer must pin paper-trading sessions
  to the same instance via session affinity, OR run the
  paper-trading engine as a single dedicated worker.
- **No real broker order routing.** Paper trades never touch a
  broker. A "filled" paper trade isn't necessarily a price the
  broker would have given on a live order.
- **The 7-session minimum doesn't validate quality.** A user
  can satisfy the gate with 7 short sessions of 1 trade each.
  The SafetyChain layers Trust + Truth checks on top to catch
  shallow histories.
- **Session day boundary is the user's local-time day.** A
  session started Sunday 11:55 PM IST and ended Monday 12:05
  AM IST counts as Sunday (when it started). Pinned by the
  unique index on `(user_id, strategy_id, session_date)`.

## Testing

- `tests/strategy_engine/paper_trading/test_engine_*.py` —
  per-primitive entry/exit, exit-prioritisation, readiness
  matrix.
- `tests/strategy_engine/paper_trading/test_persistence.py` —
  DB round-trip + the unique-day constraint.
- `tests/strategy_engine/live_orders/test_safety_chain.py` —
  the safety-check ordering test pins paper-sessions as the
  second gate.

## Future Work

- **Multi-tenant paper-trading workers.** Move `_RECORDS` from
  in-process to Redis-backed shared state so the engine scales
  past one instance.
- **Realistic slippage modelling.** Today paper fills are at
  the candle close. A slippage model that conditions on
  spread + volume would narrow the gap to live.
- **Paper-mode broker adapters.** Today the engine is
  broker-free; a "paper Dhan" adapter that mimics Dhan's
  order-routing latency + reject behaviour would let users
  validate against the *broker* shape they'll use live.

## References

- Engine source: `backend/app/strategy_engine/paper_trading/engine.py`
- Persistence bridge: `backend/app/strategy_engine/paper_trading/persistence.py`
- Migration: `backend/migrations/versions/010_paper_sessions_persistence.py`
- SafetyChain consumer: `backend/app/strategy_engine/live_orders/safety_checks.py`
- Tests: `backend/tests/strategy_engine/paper_trading/`
- Sister doc: [`/docs/auto-kill-switch-integration.md`](./auto-kill-switch-integration.md)
- Sister doc: [`/docs/broker-execution-guard.md`](./broker-execution-guard.md)
