# Broker Execution Guard

> Status: Production-ready (advisory verdict; live-order wiring uses a slim subset)
> Introduced: Commit `7520680`
> Live-orders SafetyChain integration: Commit `620e0d4`
> Last updated: 2026-05-09

## Overview

The Broker Execution Guard composes 6 safety checks into a
single `GuardDecision` the caller can act on before placing a
live order. It's a pure decision function: no network, no DB,
no clock reads, no mutation of inputs. The guard intentionally
imports nothing from any broker adapter and nothing from the
kill-switch implementation — these properties are pinned by
AST-inspection tests in `tests/strategy_engine/broker_guard/`.

The live-orders path (Phase 8B-2) doesn't call the full guard.
It calls a slim subset via the SafetyChain — see [Why the live
path uses a slim subset](#why-the-live-path-uses-a-slim-subset)
below.

## Why It Exists

Live order placement has many ways to go wrong, and each
"correctness" check is a separate concern:

- Is the user's broker connection healthy?
- Is the kill switch tripped?
- Has the strategy got a stop loss?
- Did the strategy's recent paper / live drawdown breach a
  threshold?
- Has the user opted into live trading?
- Have they completed the 7-session paper-trading minimum?

Bundling these into one composable decision lets the test
surface lock in the contract: changing the guard's verdict for
any input combination requires updating the matrix test, which
is far harder to do silently than tweaking 6 separate
if-statements scattered across the codebase.

## 6 Safety Check Categories

```
1. broker_connected         ← does the user have a healthy broker link?
2. kill_switch_inactive     ← is the user's kill switch in a clean state?
3. has_stop_loss            ← does the strategy have a stop_loss_percent set?
4. high_drawdown            ← is the strategy's recent drawdown below the cap?
5. paper_sessions_minimum   ← has the user completed the 7-session gate?
6. live_trading_enabled     ← global + per-user opt-in?
```

Source: `backend/app/strategy_engine/broker_guard/checks.py`. Each
check is a small pure function returning a `(passed: bool,
reason: str)` tuple.

## Public API

```python
from app.strategy_engine.broker_guard import evaluate_guard

decision = evaluate_guard(
    strategy=strategy_json,
    backtest=backtest_result,
    paper_completed_sessions=count,
    broker_connected=is_connected,
    kill_switch_active=is_tripped,
    live_trading_enabled=is_enabled,
)
# decision.passed → bool
# decision.failed_checks → tuple[(name, reason)]
# decision.passed_checks → tuple[name]
```

Source: `backend/app/strategy_engine/broker_guard/guard.py`.

## AST Isolation Enforcement

The guard's docstring states the isolation contract verbatim:

> Wiring this verdict into actual order placement is a *separate*
> future phase. The guard intentionally:
>
>     * Imports nothing from any broker adapter.
>     * Imports nothing from the kill-switch implementation.
>     * Performs no I/O (no HTTP, no DB, no clock reads).
>     * Mutates none of its inputs (frozen Pydantic models).

Two AST-inspection tests pin this:

```
tests/strategy_engine/broker_guard/test_isolation.py::
  test_no_broker_imports
  test_no_kill_switch_imports
```

Both walk the package's AST and reject any `import` /
`from-import` that names a broker or kill-switch module. **Don't
loosen these tests.** A real-world incident would route through
the guard; if the guard could itself touch a broker, an exception
in the broker adapter could mask a safety verdict.

## Live-Orders SafetyChain Integration

The Phase 8B-2 SafetyChain (`live_orders/safety_chain.py`,
commit `620e0d4`) does NOT call `evaluate_guard` directly. The
SafetyChain's 7 checks are:

```
1. auto_kill_switch
2. paper_sessions
3. trust_score
4. truth_score
5. live_trading_enabled
6. broker_connection
7. risk_engine_precheck (deferred)
```

The overlap with the broker guard is intentional but the
SafetyChain consumes a **slim subset** — Trust + Truth scores
come from `last_trust_score` / `last_truth_score` columns
cached on the strategy row (Migration 012), NOT from running
the full reliability + truth pipeline on every live order.

### Why the live path uses a slim subset

The full broker guard expects a `BacktestResult` to evaluate
the `high_drawdown` check. Computing `BacktestResult` requires
the full backtest pipeline — for every live order this is
unacceptable latency. The Phase 8B-2 design instead:

1. Caches Trust + Truth scores at backtest time
   (Migration 012).
2. The SafetyChain's `trust_score` + `truth_score` checks read
   the cached columns (microseconds, not seconds).
3. The full broker guard remains the **advisory verdict** the
   frontend backtest panel surfaces and the AI Advisor's rules
   consult.

The split is documented in the live-orders DESIGN.md
(`backend/app/strategy_engine/live_orders/DESIGN.md`).

## Configuration

Thresholds in `broker_guard/constants.py`:

- `MIN_PAPER_SESSIONS = 7` (mirrors paper-trading constant).
- `MAX_DRAWDOWN_PCT_FOR_LIVE = 25` — strategies with worse
  drawdowns can't ship to live.

These are constants, not env vars, for the same load-bearing
safety reason as the rest of the engine — a deploy-time tweak
shouldn't silently weaken the gate.

## Edge Cases & Limitations

- **The guard doesn't see live deviation.** Today the Deviation
  Monitor's `auto_kill_switch_signal` is read-only and not
  consulted by the guard. A future phase wires the signal into
  a 7th check.
- **No instrument-specific gating.** The guard treats NIFTY +
  BANKNIFTY identically; an instrument-specific drawdown cap
  would let aggressive strategies on volatile instruments
  pass while keeping the floor strict on calmer ones.
- **`high_drawdown` reads from `BacktestResult` only.** The
  check doesn't see actual live drawdown — that's the
  Deviation Monitor's job.
- **The guard says yes/no, not why-this-many.** A strategy that
  fails 4 checks and one that fails 1 both get
  `decision.passed = False`. The `failed_checks` tuple lets
  callers render specifics; the underlying scoring is binary.

## Testing

- `tests/strategy_engine/broker_guard/test_checks_*.py` — per-check
  positive + negative case matrix.
- `tests/strategy_engine/broker_guard/test_guard_decision.py` —
  the 6-check combination matrix (representative subset, not
  full 2⁶).
- `tests/strategy_engine/broker_guard/test_isolation.py` —
  AST-pinned import isolation. The tests pass on commit `7520680`
  with 17 tests total in the broker_guard suite.

## Future Work

- **Wire the Deviation Monitor signal as a 7th check.** Adds a
  `live_deviation_clean` check that reads
  `DeviationReport.auto_kill_switch_signal`; the guard's verdict
  flips to `False` when deviation is critical.
- **Per-instrument thresholds.** Replace `broker_guard/constants.py`
  with a per-instrument lookup the guard reads from the
  strategy row.
- **Gradient verdict.** Today the guard is binary. A gradient
  verdict (`risk_score: 0.0-1.0`) would let the frontend show
  "your strategy is 80% ready" instead of just yes/no.

## References

- Module source: `backend/app/strategy_engine/broker_guard/`
- Live-orders SafetyChain: `backend/app/strategy_engine/live_orders/safety_chain.py`
- Live-orders DESIGN: `backend/app/strategy_engine/live_orders/DESIGN.md`
- Tests: `backend/tests/strategy_engine/broker_guard/`
- Sister doc: [`/docs/auto-kill-switch-integration.md`](./auto-kill-switch-integration.md)
- Sister doc: [`/docs/paper-trading.md`](./paper-trading.md)
- Sister doc: [`/docs/feature-flags.md`](./feature-flags.md)
