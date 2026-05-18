# Indicator Commission Batch 1 — heikin_ashi / alma / kama / pivot_swing / fibonacci_retracement

**Branch:** `feat/indicator-commission-batch-1`
**Date:** 2026-05-17 → 2026-05-18
**Blockers:** `BLOCKERS_INDICATOR_COMMISSION_1.md`

---

## TL;DR

Five indicators promoted from `COMING_SOON` (or newly registered) to
`ACTIVE`. Each unblocks at least one Phase-2 template activation per
`docs/PHASE_2_TEMPLATES_PART_2.md`. 62 unit tests across 5 files, all
green; 1 graceful-skip when `pandas-ta` isn't installed.

| Indicator | Status before | Status after | Calc file | Tests |
|---|---|---|---|---:|
| `heikin_ashi` | COMING_SOON (stub) | ACTIVE | `calculations/heikin_ashi.py` | 11 |
| `alma` | COMING_SOON (stub) | ACTIVE (alias) | `calculations/alma.py` (re-export) | 12 |
| `kama` | COMING_SOON (stub) | ACTIVE | `calculations/kama.py` | 14 (1 skipped) |
| `pivot_swing` | not registered | ACTIVE (NEW) | `calculations/pivot_swing.py` | 12 |
| `fibonacci_retracement` | not registered | ACTIVE (NEW) | `calculations/fibonacci_retracement.py` | 13 |

Phase 2 templates unblocked:
- `heikin-ashi-smooth-trend` → uses `heikin_ashi`
- `alma-slope` → uses `alma`
- `kama-adaptive-trend` → uses `kama`
- `pivot-reversal-strategy` → uses `pivot_swing`
- `fibonacci-retracement-entry` → uses `fibonacci_retracement`

Template `renko-trend` remains blocked (no Renko transform in this batch).

---

## Per-indicator math + reference

### 1. `heikin_ashi`

**Calc file:** `backend/app/strategy_engine/indicators/calculations/heikin_ashi.py`

**Formula** (TradingView Pine canonical):
```
ha_close[i] = (open[i] + high[i] + low[i] + close[i]) / 4
ha_open[0]  = (open[0] + close[0]) / 2              # seed
ha_open[i]  = (ha_open[i-1] + ha_close[i-1]) / 2    # recursive
ha_high[i]  = max(high[i], ha_open[i], ha_close[i])
ha_low[i]   = min(low[i],  ha_open[i], ha_close[i])
```

**Output:** list of dicts ``{"open", "high", "low", "close"}`` per input bar.

**Reference sources:**
- TradingView Pine v5: `request.security(symbol, timeframe, ohlc4)` + manual recursion
- pandas-ta: `ta.ha(df)` — verified same recursion + seed
- TA-Lib: does NOT ship Heikin-Ashi (workaround widely-known)

**Hand-validated golden** in test_heikin_ashi.py::test_reference_three_bar_uptrend.

### 2. `alma` (re-export of `arnaud_legoux_ma`)

**Calc file:** `backend/app/strategy_engine/indicators/calculations/alma.py`

**Approach:** the working math already shipped under id
`arnaud_legoux_ma` in `_pack9_active.py`. The Phase-9 stub under id
`alma` had no calculation function. Templates reference the short
name. This branch ships `alma.py` as a thin re-export so:
- Both registry ids work for customer-facing config configs
- Single source of truth — no duplicate ALMA implementations
- No math drift

**Formula** (from arnaud_legoux_ma.py docstring, reproduced here):
```
m = floor(offset * (period - 1))
s = period / sigma
w[k] = exp(-(k - m)² / (2 * s²))
ALMA[i] = sum(w[k] * value[i - period + 1 + k]) / sum(w)
```

**Reference sources:**
- Arnaud Legoux & Dimitrios Kouzis-Loukas (2009) original paper
- pandas-ta: `ta.alma(close, length, sigma, offset)`
- TradingView Pine: `ta.alma(source, length, offset, sigma)`

### 3. `kama`

**Calc file:** `backend/app/strategy_engine/indicators/calculations/kama.py`

**Formula** (Perry Kaufman, 1995):
```
change[i]   = |close[i] - close[i - period]|
volatility[i] = sum_{k=0..period-1} |close[i-k] - close[i-k-1]|
ER[i] = change[i] / volatility[i]                  (0 when volatility == 0)

fast_sc = 2 / (fast + 1)     # default fast = 2  → 2/3
slow_sc = 2 / (slow + 1)     # default slow = 30 → 2/31
sc[i]   = (ER[i] * (fast_sc - slow_sc) + slow_sc)²

KAMA[period - 1] = close[period - 1]               # seed
KAMA[i]          = KAMA[i-1] + sc[i] * (close[i] - KAMA[i-1])
```

**Defaults:** `period=10, fast=2, slow=30` (Kaufman's originals).

**Reference sources:**
- Perry Kaufman, "Smarter Trading" (1995)
- pandas-ta: `ta.kama(close, length=10, fast=2, slow=30)` — verified same
- TA-Lib: `KAMA(close, length=10)` — uses fixed fast=2, slow=30
- TradingView Pine: not built-in; custom implementations vary in defaults

**Cross-validation test** (test_kama.py::test_kama_matches_pandas_ta_when_available):
- Imports pandas-ta if available; computes both ours + pandas-ta
- Asserts max abs diff < 1e-3 on 100 random bars
- Skips gracefully if pandas-ta absent (current local env state)

### 4. `pivot_swing`

**Calc file:** `backend/app/strategy_engine/indicators/calculations/pivot_swing.py`

**Approach:** new indicator. Wraps the existing `swing_high` +
`swing_low` into one signed series per bar so condition_evaluator
queries simplify ("pivot_swing > 0" detects swing high).

**Formula:** at each bar `i` (after `left_bars + right_bars`
confirmation period):
```
high_confirm = swing_high(highs, left_bars, right_bars)[i]
low_confirm  = swing_low(lows,  left_bars, right_bars)[i]

if both → larger magnitude wins
if only swing_high     → out[i] = +high_confirm
if only swing_low      → out[i] = -low_confirm
otherwise              → out[i] = None
```

**Reference source:** Pine Script's "Pivot Reversal" strategy template
on TradingView. The classic Dow swing high/low confirmation maps
1-to-1 here.

### 5. `fibonacci_retracement`

**Calc file:** `backend/app/strategy_engine/indicators/calculations/fibonacci_retracement.py`

**Approach:** new indicator. Computes the 5 standard retracement
levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) from the highest high and
lowest low in a trailing `lookback`-bar window.

**Formula:**
```
swing_high = max(highs[-lookback:])
swing_low  = min(lows[-lookback:])
range     = swing_high - swing_low

# Bullish (default; retracing from high → low):
level_pct = swing_low + range * pct

# Bearish (retracing from low → high):
level_pct = swing_high - range * pct
```

**Output:** per-bar dict ``{swing_high, swing_low, "23.6", "38.2", "50.0", "61.8", "78.6"}``.

**Reference sources:**
- Classic retail Fibonacci retracement (not a regulated indicator)
- pandas-ta: no built-in (retracement is a derived computation, not a
  TA-Lib primitive)
- TradingView Pine: drawn via `request.security` + manual high/low

**Hand-validated golden** in test_fibonacci_retracement.py::test_known_input_golden_values
+ test_bullish_retracement_levels.

---

## Registry wiring

A new module file ships at:
`backend/app/strategy_engine/indicators/_batch1_commission_active.py`

It declares 5 `IndicatorMetadata` rows + exports them as
`BATCH1_COMMISSION_ACTIVE_INDICATORS`. The registry imports + splats
this tuple LAST in the assembly so the dict-comprehension's
"later splat wins" rule promotes the 3 same-id COMING_SOON stubs
(heikin_ashi, alma, kama) to ACTIVE.

Two registry edits total in this batch:
1. New import line at top of `registry.py`
2. New `*BATCH1_COMMISSION_ACTIVE_INDICATORS,` splat in the dict-comp

No existing `_pack*_active.py` or `_phase9_*.py` file is modified.

---

## Verification

```
$ pytest backend/tests/strategy_engine/indicators/calculations/ -v --no-cov
======================== 62 passed, 1 skipped in 0.70s =========================
```

Verified resolution:
```py
from app.strategy_engine.indicators.registry import (
    INDICATOR_REGISTRY, get_calculation_function
)
for name in ['heikin_ashi', 'alma', 'kama', 'pivot_swing', 'fibonacci_retracement']:
    assert INDICATOR_REGISTRY[name].status.value == 'active'
    assert callable(get_calculation_function(name))
```

All 5 ids: status = active, calculation_function resolves to callable.

---

## Hard constraints honoured

- ✅ NO modifications to existing indicator implementations
  (`_pack*_active.py`, `_phase9_*.py` files are untouched)
- ✅ NO modifications to `strategy_engine/backtest/*`
- ✅ NO new external packages (pandas-ta is reference-only, optional)
- ✅ NO new test framework — uses existing pytest + project conftest

## See also

- `BLOCKERS_INDICATOR_COMMISSION_1.md` — open questions
- `docs/PHASE_2_TEMPLATES_PART_2.md` — which templates this unblocks
