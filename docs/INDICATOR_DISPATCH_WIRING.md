# Indicator Dispatch Wiring — Batch 1

**Branch:** `feat/indicator-dispatch-batch-1`
**Builds on:** `feat/indicator-commission-batch-1` (registry-side)
**Closes:** `BLOCKERS_INDICATOR_COMMISSION_1.md` Q6

---

## TL;DR

The 5 Batch-1 commissioned indicators (heikin_ashi, alma, kama,
pivot_swing, fibonacci_retracement) are now in the backtest engine's
dispatch table at
`app/strategy_engine/backtest/indicator_runner.py:_compute_one`.

Single existing-file edit: 5 new `if cfg.type == "X"` branches inserted
before the fall-through `raise IndicatorRunnerError`. NO modifications
to existing branches.

Closes the "active in registry but not callable by backtest" gap from
Queue III Task 1 that left strategies referencing these indicators
unable to backtest.

---

## Per-indicator wiring

| Indicator | Inputs from candles | Params (with defaults) | Output shape |
|---|---|---|---|
| `heikin_ashi` | opens, highs, lows, closes | (none) | Multi-output: primary=`ha_close`, sub-outputs `ha_open` / `ha_high` / `ha_low` / `ha_close` |
| `alma` | values from `source` | period (required), sigma=6.0, offset=0.85, source="close" | Single series |
| `kama` | values from `source` | period (required), fast=2, slow=30, source="close" | Single series |
| `pivot_swing` | highs, lows | left_bars=5, right_bars=5 | Single signed series (+ swing high, - swing low) |
| `fibonacci_retracement` | highs, lows | lookback=50, direction="bull" | Multi-output: primary=`50.0`, sub-outputs `swing_high` / `swing_low` / `23.6` / `38.2` / `61.8` / `78.6` |

### Multi-output handling

Two of the five (heikin_ashi, fibonacci_retracement) return per-bar
dicts from their calc functions, not flat lists. The dispatch unpacks
these into separate same-length series and surfaces them via the
existing dotted-notation pattern that MACD and Bollinger use:

```py
# heikin_ashi example
return ha_close, {
    "ha_open": ha_open,
    "ha_high": ha_high,
    "ha_low": ha_low,
    "ha_close": ha_close,
}
```

The strategy DSL references sub-outputs as `<config_id>.<suffix>`:
- `ha.ha_close` (or just `ha` for the primary line)
- `fib.swing_high`, `fib.swing_low`, `fib.61.8`, etc.

A "multi-output limitation" warning is emitted (matches Phase 9
convention) so the operator sees the dotted-notation gap.

---

## Parameter validation

Default values propagate through `_coerce_int` / `_coerce_float` /
`_coerce_str` helpers. Sources are validated via the existing
`PriceSource` enum (open / high / low / close / volume / hl2 / hlc3 / ohlc4).

| Param | Range | Coercer |
|---|---|---|
| `period` (alma, kama) | int ≥ 2 | `_coerce_int` |
| `sigma` (alma) | float > 0 | `_coerce_float` |
| `offset` (alma) | float ∈ [0, 1] | `_coerce_float` |
| `fast` (kama) | int ≥ 1 | `_coerce_int` |
| `slow` (kama) | int > fast | `_coerce_int` |
| `left_bars` / `right_bars` (pivot_swing) | int ≥ 1 | `_coerce_int` |
| `lookback` (fibonacci_retracement) | int ≥ 2 | `_coerce_int` |
| `direction` (fibonacci_retracement) | "bull" or "bear" | `_coerce_str` |
| `source` | one of PriceSource | `_coerce_str` |

The calc functions themselves enforce range constraints; the dispatch
just shape-coerces. Validation errors raise `IndicatorRunnerError`
with the offending param name.

---

## Test inventory (11 tests, all passing in 0.08s)

| Test | Verifies |
|---|---|
| `test_dispatch_heikin_ashi_runs_without_error` | Smoke: precompute_indicators runs cleanly + emits sub-outputs |
| `test_dispatch_alma_runs_without_error` | Smoke + warmup pattern (period-1 None, rest defined) |
| `test_dispatch_kama_runs_without_error` | Smoke + seed at period-1 |
| `test_dispatch_pivot_swing_runs_without_error` | Smoke + output length match |
| `test_dispatch_fibonacci_retracement_runs_without_error` | Smoke + 5+ sub-outputs present |
| `test_heikin_ashi_close_lies_within_input_range` | HA close ∈ [min(low), max(high)], no NaN/Inf |
| `test_alma_warmup_then_defined` | Warmup respected, post-warmup all finite |
| `test_kama_constant_series_yields_constant_kama` | Flat candles → ER=0 → KAMA = seed |
| `test_pivot_swing_returns_some_pivots_on_oscillating_series` | Both signs present on sinusoidal input |
| `test_fibonacci_retracement_50_pct_is_midpoint` | 50% level = (swing_high + swing_low) / 2 |
| `test_unknown_indicator_type_raises_helpful_error` | Fall-through path preserved |

---

## Hard constraints honoured

- ✅ MINIMAL existing-file edit to `indicator_runner.py` — only 5 new
  dispatch branches inserted (~75 lines), no existing branches modified
- ✅ NO modifications to ANY other engine code
- ✅ NO modifications to existing tests
- ✅ Test path follows existing convention
  (`backend/tests/strategy_engine/backtest/`)

## What's NEXT

Phase 2 templates that reference these 5 indicators can now backtest.
The follow-up work is founder review of the 5 templates currently
blocked by these indicators (per `BLOCKERS_PHASE_2_PART_2.md`):
- `heikin-ashi-smooth-trend` → uses `heikin_ashi`
- `alma-slope` → uses `alma`
- `kama-adaptive-trend` → uses `kama`
- `pivot-reversal-strategy` → uses `pivot_swing`
- `fibonacci-retracement-entry` → uses `fibonacci_retracement`
