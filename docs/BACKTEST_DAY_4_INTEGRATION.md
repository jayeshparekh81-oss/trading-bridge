# Backtest Engine Day 4 — Engine Integration Contract

**Branch:** `feat/backtest-engine-day-4`
**Builds on:** Day 1-3 (`feat/backtest-engine-day-1-3`)

---

## TL;DR

Day 1-3 wired the Celery task plumbing — state machine, persistence,
idempotency, API. Day 4 verifies the engine invocation end-to-end with
9 integration tests that run the REAL
`app.strategy_engine.backtest.run_backtest` (no mocking).

Day 1-3's `test_celery_tasks.py` mocked the engine to isolate the
state machine. Day 4's `test_engine_integration.py` removes the mock
and runs the engine against synthetic 500-bar candles.

The only celery_tasks.py change in Day 4 is upgrading the synthetic
candle generator from 60 monotonic bars → 500 sinusoidal bars that
actually exercise crossover-style entries and SL/TP triggers.

---

## Engine ↔ extension contract

The `backtest_extension/celery_tasks._run_backtest_async` function
calls `run_backtest(BacktestInput)` from `strategy_engine.backtest`.
The contract:

### Input shape (`BacktestInput`)

```py
class BacktestInput(BaseModel):
    candles: list[Candle]              # ≥ 2 entries, monotonic time
    strategy: StrategyJSON             # full validated DSL
    initial_capital: float             # > 0
    quantity: float                    # > 0
    cost_settings: CostSettings        # default zero-cost
    ambiguity_mode: AmbiguityMode      # conservative | optimistic | accurate_placeholder
```

Day 4 always constructs this from:
- `candles`: synthetic generator (Day 6 work replaces with Dhan)
- `strategy`: from `backtest_runs.request_payload` → resolve `strategy_id` →
  `Strategy.strategy_json` → `StrategyJSON.model_validate(...)`
- `initial_capital` / `quantity`: from request payload (defaults 100k / 1.0)
- `cost_settings`: from request payload (default zero-cost)
- `ambiguity_mode`: from request payload (default conservative)

### Output shape (`BacktestResult`)

```py
class BacktestResult(BaseModel):
    total_pnl: float
    total_return_percent: float
    win_rate: float           # [0, 1]
    loss_rate: float          # [0, 1]
    total_trades: int         # ≥ 0
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    max_drawdown: float       # [0, 1]
    profit_factor: float      # math.inf when wins-only
    expectancy: float
    equity_curve: list[EquityPoint]
    trades: list[Trade]
    warnings: list[str]
```

Day 4 persists:
- Each `Trade` → `backtest_trades` row (preserving order via `trade_index`)
- Summary metrics → `backtest_metrics` row (`profit_factor=math.inf` → DB NULL)
- `equity_curve` is NOT persisted (per Day 1-3 decision Q6 — too large to materialise)
- `warnings` lands in `backtest_metrics.warnings` JSONB column

### Failure modes

Any uncaught exception during steps 3-5 of `_run_backtest_async`:
- `BaseException` is captured → `_build_error_payload(exc)` →
  `error_json = {type, message[:1024], traceback_first_line[:512]}`
- `update_status(FAILED)` transitions the row
- No trades or metrics are persisted on the FAILED path

Specific Day-4-validated failure scenarios:
- `strategy_id` references a non-existent Strategy →
  `StrategyPayloadResolutionError("Strategy {id} not found")`
- Strategy row has `strategy_json=null` →
  `StrategyPayloadResolutionError("Strategy {id} has no DSL")`
- Strategy row has malformed `strategy_json` (e.g. missing required
  `execution` block) →
  `pydantic_core.ValidationError` from `StrategyJSON.model_validate`

---

## Synthetic candle generator (Day 4 upgrade)

`_build_synthetic_candles_payload` now produces 500 deterministic bars:

```py
# Long-wave drift (peak-to-peak ~3%) + short wave (peak-to-peak ~0.5%)
long_wave = math.sin(2 * math.pi * i / 80) * 300.0
short_wave = math.sin(2 * math.pi * i / 12) * 50.0
shock = 30.0 if i % 50 == 0 and i > 0 else 0.0
c = 22000.0 + long_wave + short_wave + shock
```

Properties:
- **Deterministic** — identical seed (none used), reproducible per run
- **OHLC invariant satisfied** — `low <= open/close <= high`
- **Exercises crossover indicators** — EMA fast/slow cross ~every 60 bars
- **Triggers SL/TP** — short-wave peaks ~0.5% give tight-SL strategies hits
- **Exceeds warmup window** — 500 bars >> any active indicator's lookback
- **Volume varies** — `1000 + (i % 100) * 10` so volume-conditioned
  indicators see realistic flow

Replaced in Day 6 supervised work with
`app.strategy_engine.data_provider.fetch_historical_candles`.

---

## Test inventory (9 tests, all passing in 0.46s)

| Test | Verifies |
|---|---|
| `test_engine_integration_happy_path_succeeds` | EMA crossover strategy → SUCCEEDED with > 0 trades |
| `test_engine_integration_trades_persisted_in_order` | `trade_index` monotonic, contiguous from 0 |
| `test_engine_integration_zero_trades_strategy` | Never-fires strategy → SUCCEEDED, 0 trades, 0 P&L |
| `test_engine_integration_tight_stop_produces_mixed_results` | Sanity bounds on metrics in legal Pydantic ranges |
| `test_engine_integration_malformed_strategy_json_fails` | Missing execution block → FAILED, ValidationError |
| `test_engine_integration_strategy_with_null_dsl_fails` | strategy_json=null → FAILED, "no DSL" message |
| `test_synthetic_candles_are_deterministic` | Same payload → same candles |
| `test_synthetic_candles_respect_ohlc_invariant` | Engine acceptance test |
| `test_engine_module_untouched` | Day 4 didn't change engine surface |

---

## Hard constraints honoured

- ✅ NO modifications to `strategy_engine/backtest/*` internals
  (only read-only imports; `git diff origin/feat/backtest-engine-day-1-3 -- strategy_engine/backtest/` empty)
- ✅ NO real Dhan API calls — synthetic generator only
- ✅ NO router registration in `main.py` (still dormant per Day 1-3)
- ✅ NO migration changes — 028 still apply-ready but unchanged
- ✅ NO new external packages
- ✅ NO modifications to Day 1-3 tests (test_celery_tasks.py untouched;
  test_persistence.py untouched; test_idempotency.py untouched;
  test_api.py untouched). Day 4 added `test_engine_integration.py` as
  a brand-new test file.

---

## What's NEXT (Day 5)

Rate-limiting middleware on `POST /api/backtest` per spec Q1 in
`BLOCKERS_BACKTEST_WEEK2.md`. Token-bucket pattern with per-user
caps. Out of scope for Day 4.

---

## See also

- `docs/EXISTING_BACKTEST_ENGINE_AUDIT.md` — engine internals
- `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` — 7-day plan
- `BLOCKERS_DAY_1_3.md` — Day 1-3 founder-review items
