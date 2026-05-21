# Existing backtest engine audit — `app.strategy_engine.backtest`

**Branch:** `feat/backtest-engine-week2-prep`
**Date:** 2026-05-17
**Scope:** structural map of the production backtest engine that ships behind `POST /api/strategies/{strategy_id}/backtest` (Phase D Strategy Tester). This audit informs the Week 2 extension plan (`docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`) — what to extend, what to call as-is, what to never touch.

---

## TL;DR

The engine at `backend/app/strategy_engine/backtest/` is 2617 LOC across 8 files, **synchronous + in-process + non-persistent**, and ships behind the Phase D Strategy Tester. It is **deterministic, pure-Python, no AI/DB/network in the hot path** — the explicit master-prompt guarantee.

The Week 2 extension keeps `run_backtest()` as the canonical execution primitive. We wrap it with three new layers and ship them as a sibling package `backend/app/backtest_extension/` so the existing engine never has to change:

1. **Persistence** — write the Pydantic `BacktestResult` (plus the input request hash + engine version) into three new tables: `backtest_runs`, `backtest_trades`, `backtest_metrics`.
2. **Async dispatch** — a Celery `@shared_task` that takes a `BacktestEnqueueRequest`, computes the idempotency hash, looks up cached runs, and either returns the cached result or queues `run_backtest()` on a worker.
3. **Idempotency** — a deterministic hash over `(strategy_config_canonical_json + date_range + engine_version)` so identical re-runs return the existing `backtest_runs.id` without re-executing.

These three layers are the entire Week 2 supervised-work surface area. The engine itself stays frozen on this branch.

---

## File inventory + ownership

| File | LOC | Responsibility | Extension surface |
|---|---:|---|---|
| `__init__.py` | 37 | Public boundary — `AmbiguityMode`, `BacktestInput`, `BacktestResult`, `CostSettings`, `EquityPoint`, `Trade`, `run_backtest()` | **Re-exported by `backtest_extension.__init__`**; do not modify |
| `runner.py` | 149 | `run_backtest(payload) -> BacktestResult` — glues normalizer + indicator_runner + simulator + metrics | **Called by `backtest_extension.celery_tasks`**; do not modify |
| `normalizer.py` | 75 | Sort/validate/dedupe candle list | Not called directly by extension |
| `indicator_runner.py` | 1492 | Pre-compute every strategy indicator series once per run | Not called directly by extension; see §Indicator-runner deep dive |
| `simulator.py` | 568 | Candle-by-candle position/exit/risk loop | Not called directly by extension |
| `metrics.py` | 154 | Pure metric functions (sharpe via expectancy approx, max DD, profit factor, etc.) | **Imported by `backtest_extension.persistence`** for any post-hoc metric the migration writes (e.g. profit factor → `backtest_metrics.profit_factor`) |
| `costs.py` | 89 | `CostSettings` + `leg_cost` + `adjust_for_slippage` | Re-exported, not modified |
| `trade_log.py` | 53 | `Trade` + `EquityPoint` Pydantic rows | Read-only — extension persists these into `backtest_trades` rows |

---

## Public boundary contract (frozen for Week 2)

```py
from app.strategy_engine.backtest import (
    AmbiguityMode,       # StrEnum: conservative | optimistic | accurate_placeholder
    BacktestInput,       # Pydantic, frozen, extra="forbid"
    BacktestResult,      # Pydantic, frozen, extra="forbid"
    CostSettings,        # Pydantic, frozen, extra="forbid"
    EquityPoint,         # Pydantic row in BacktestResult.equity_curve
    Trade,               # Pydantic row in BacktestResult.trades
    run_backtest,        # (BacktestInput) -> BacktestResult, sync
)
```

`run_backtest(input)` invariants:
- **Determinism** — identical input → identical output, byte-for-byte
- **No clock reads, no randomness, no LLM calls, no DB, no network**
- **O(N) memory** in candle count; one full sweep of `indicator_runner.precompute_indicators` per call

`BacktestResult` shape (Pydantic `frozen=True`, all field names by_alias-compatible):

```
total_pnl                : float
total_return_percent     : float
win_rate                 : float  ∈ [0, 1]
loss_rate                : float  ∈ [0, 1]
total_trades             : int    ≥ 0
average_win              : float
average_loss             : float  (magnitude, positive)
largest_win              : float
largest_loss             : float  (signed, negative)
max_drawdown             : float  ∈ [0, 1]  positive fraction of peak
profit_factor            : float  (math.inf when wins-only)
expectancy               : float
equity_curve             : list[EquityPoint]   # one per input candle
trades                   : list[Trade]
warnings                 : list[str]
```

`Trade` (frozen):

```
entry_time, exit_time : datetime
side                  : Side  (BUY | SELL)
entry_price           : float, > 0
exit_price            : float, > 0
quantity              : float, > 0
pnl                   : float
exit_reason           : str, len 1..128
entry_reasons         : tuple[str, ...]
```

---

## Existing API call paths (read-only reference)

### `POST /api/strategies/{strategy_id}/backtest`

`backend/app/strategy_engine/api/backtest.py` — Phase 5B Part 3.

Flow:
1. Load owned `Strategy` row (404 on miss; 422 if `strategy_json` is null — see `STRATEGY_JSON_DEPENDENCY_MAP.md`)
2. Validate `strategy_row.strategy_json` against `StrategyJSON` schema
3. Fetch historical candles (Dhan or synthetic fallback) via `app.strategy_engine.data_provider.fetch_historical_candles`
4. Build `BacktestInput`, call `run_backtest()` synchronously
5. Layer on:
   - reliability via `build_reliability_report`
   - walk-forward via `run_walk_forward`
   - truth via `evaluate_strategy_truth`
   - regime via `detect_regime`
   - deviation via `evaluate_deviation`
   - coach via `generate_health_card`
   - trade quality via `compute_trade_quality`
   - manifest via `capture_manifest`
6. Audit log via `log_backtest_run`

The whole thing runs **in the request thread** — Phase D's UX accepts the ~5-15s wait. This is the cost model the Week 2 async extension is designed to fix for **anonymous-config preview** (template card "preview backtest" before clone, future Phase 5 Strategy Builder "run before save", etc.).

### Other callers of `run_backtest()` directly

- `app.strategy_engine.reliability.parameter_sensitivity`
- `app.strategy_engine.reliability.out_of_sample`
- `app.strategy_engine.reliability.reliability_report`
- `app.strategy_engine.reliability.walk_forward`
- `app.strategy_engine.api.compare_fix` (the version-compare endpoint)

All synchronous, all in-process. The Week 2 extension does **not** rewrite any of these — they continue to call `run_backtest()` directly. Async is opt-in via the new endpoints.

---

## Indicator-runner deep dive — the 1492-LOC monster

`indicator_runner.precompute_indicators(candles, strategy)` is **the bottleneck**. It's a flat dispatch table — one `if cfg.type == "X":` block per indicator type. Counted: **165 indicator dispatch branches** across 18 indicator "packs":

| Section | Line range | Indicator pack |
|---|---|---|
| Phase 1 active | 106-152 | EMA, SMA, WMA, RSI, TRIX, Linear Regression, Volume SMA, MACD, Bollinger, ATR, VWAP, OBV |
| Phase 9 active | 154-224 | ADX, DMI, Aroon, Ultimate Oscillator, CMF, Force Index, Pivot Points, Ichimoku… |
| Pack 2 | 225-297 | additional Phase-9 active set |
| Pack 3 | 298-362 | candlestick pattern detectors |
| Pack 4 | 363-436 | S/R + statistical + volatility/range |
| Pack 5 | 437-498 | advanced statistical / risk / performance |
| Pack 6 | 499-576 | volume flow + advanced volatility |
| Pack 7 | 577-642 | trend strength + advanced momentum |
| Pack 8 | 643-723 | multi-timeframe + specialty + India-specific |
| Pack 9 | 724-786 | bands + envelopes + advanced MAs |
| Pack 10 | 787-864 | volume profile + microstructure + order flow |
| Pack 11 | 865-935 | cycle + divergence + advanced patterns |
| Pack 12 | 936-1002 | volatility regime + risk-adjusted + bands |
| Pack 13 | 1003-1090 | sentiment + breadth + cross-asset |
| Pack 14 | 1091-1128 | statistical + regression + advanced math |
| Pack 15 | 1129-1200 | time-based + session + intraday |
| Pack 16 | 1201-1276 | options-aware + Greeks-proxy |
| Pack 17 | 1277-1354 | composite signals + ML-style features |
| Pack 18 | 1355-1449 | final 15: trend / momentum / volume / India |

**Complexity hotspot**: any indicator that emits multi-output series (MACD, Bollinger, Aroon, Ichimoku, DMI, Pivot Points…) stores the **primary line** under `cfg.id` and **sub-outputs** under `cfg.id.suffix`. The simulator's `values_at` lookup is dotted-notation-aware; the Phase-1 StrategyJSON validator currently REJECTS dotted references (Phase 9 expansion item, called out in `indicator_runner.py:14-25`).

**Implication for Week 2**: the extension does NOT need to touch this dispatch. It calls `run_backtest()` which calls `precompute_indicators()` internally. The only knowledge the extension needs:

- Each indicator's `cfg.type` is read off `IndicatorConfig.type` (registered in `app.strategy_engine.indicators.registry`)
- 165 dispatch branches = 165 supported indicator types
- Multi-output indicators emit a warning that lands in `BacktestResult.warnings`

---

## Determinism notes (what Week 2 hash must capture)

For the idempotency hash to be safe, it must include every input that changes the output. Per the engine's determinism contract:

| Input | Hash member |
|---|---|
| `BacktestInput.candles` | Yes — full series. Practical: hash `(symbol, timeframe, start_ts, end_ts)` instead of the candles themselves, since candles are fetched deterministically from Dhan/synthetic |
| `BacktestInput.strategy` | Yes — canonical JSON of `StrategyJSON.model_dump()` |
| `BacktestInput.initial_capital` | Yes |
| `BacktestInput.quantity` | Yes |
| `BacktestInput.cost_settings` | Yes — all 4 fields |
| `BacktestInput.ambiguity_mode` | Yes |
| `engine_version` | Yes — a string the extension bumps when any of: `runner.py`, `simulator.py`, `indicator_runner.py`, `metrics.py`, `normalizer.py`, `costs.py`, `trade_log.py` ships a behavioural change |

Hash is computed over a canonical JSON serialisation (sorted keys, no whitespace) so trivial dict-order changes don't bust the cache.

---

## What Week 2 will NOT touch

- Any file in `backend/app/strategy_engine/backtest/`
- `app/strategy_engine/api/backtest.py` (the Phase D Strategy Tester endpoint — separate, synchronous path)
- The reliability/truth/coach helpers — they continue to consume `run_backtest()` synchronously
- The `Strategy` table — no schema change, no FK from `backtest_runs` (use nullable `strategy_id` so anonymous-config runs work)
- The Phase D Strategy Tester UI — Week 2 is a NEW endpoint family

## What Week 2 WILL add (additive, in `backtest_extension/`)

- 3 new tables via migration 028 (DRAFT, not applied this branch)
- 1 new Pydantic schema module
- 1 new Celery task module
- 1 new persistence helper module
- 1 new idempotency-hash module
- 1 new FastAPI router (NOT registered in `app.main` this branch — supervised activation)
- 1 new package `__init__.py` re-exporting `run_backtest` from `strategy_engine.backtest` so callers don't need to import from two packages
- Test fixtures (NO test logic — that's Week 2 day-by-day)

See `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` for the day-by-day rollout.
