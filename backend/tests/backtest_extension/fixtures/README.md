# Backtest extension test fixtures

Skeleton-stage fixtures for the Week 2 supervised sprint. The JSON
files in this directory are placeholders — Day 1 of Week 2 materialises
real content after migration 028 applies.

## Files

| File | Used by | Shape |
|---|---|---|
| `sample_enqueue_request.json` | Day 2 idempotency tests, Day 4 API contract tests | `BacktestEnqueueRequest` payload — owned-strategy variant |
| `sample_anon_config_request.json` | Day 6 anonymous-config tests | `BacktestEnqueueRequest` with strategy_config but no strategy_id |
| `sample_strategy_config.json` | Referenced by sample_anon_config_request.json | Phase-1 active template config_json (`parabolic-sar-reversal`) |
| `expected_request_hash.txt` | Day 2 hash determinism test | Pinned SHA-256 hex of `compute_request_hash(sample_enqueue_request.json)` |
| `determinism_pin.json` | Day 7 engine-determinism test | `(BacktestInput, expected BacktestResult)` pair from running engine 1.0 against a fixed candle sequence |

## How fixtures get refreshed

1. Day 1 — populate `sample_enqueue_request.json` with realistic
   payload (NIFTY 5m, 60-day window, default cost settings)
2. Day 2 — implement `compute_request_hash`, run it against
   `sample_enqueue_request.json`, write the result into
   `expected_request_hash.txt`
3. Day 7 — run the existing engine against a fixed candle sequence,
   write `(BacktestInput JSON, BacktestResult JSON)` into
   `determinism_pin.json`. From this point onwards, any engine change
   that breaks the pin must either revert OR bump `__engine_version__`.

## Why JSON files, not Python factories

Future-proofing: the Day-7 determinism test must be portable across
language clients (e.g. a Rust rewrite of the engine for a perf
breakthrough would still need to produce byte-identical output). JSON
fixtures travel cleanly across language boundaries; Python factory
objects don't.
