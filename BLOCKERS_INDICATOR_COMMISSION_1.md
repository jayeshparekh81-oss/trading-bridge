# BLOCKERS — Indicator Commission Batch 1

**Branch:** `feat/indicator-commission-batch-1`
**Date:** 2026-05-17 → 2026-05-18

---

## Founder-review items before merge

### Q1. `alma` and `arnaud_legoux_ma` are now two registry ids with the same calc

Both registry entries point at the **same calculation function**
(via `calculations/alma.py` re-exporting from
`calculations/arnaud_legoux_ma.py`). Three implications:

- Customer-facing template configs that reference `"alma"` now work
- Configs that reference `"arnaud_legoux_ma"` continue to work
- The `_pack9_active.py` row for `arnaud_legoux_ma` is unchanged

**Decision needed:** is the dual-id situation acceptable, or should
the `arnaud_legoux_ma` registry entry be marked DEPRECATED with a
follow-up sprint to migrate any reference in the catalog seed?

Recommendation: **accept dual-id**. `alma` is the customer-facing
canonical name (matches Pine + pandas-ta); `arnaud_legoux_ma` is the
historical id for backwards compatibility. No deprecation needed
until a template-naming-canonicalisation sprint.

### Q2. `pandas-ta` cross-validation skips when not installed

`test_kama.py::test_kama_matches_pandas_ta_when_available` skips
gracefully if pandas-ta isn't in the venv. The current local dev env
doesn't have it — test was skipped.

**Decision needed:** add `pandas-ta` to `[dev]` dependencies in
`pyproject.toml` so CI always runs the cross-validation? Or rely on
the skip-when-missing pattern?

Recommendation: add to **dev-only** deps. The library is widely
trusted; CI cross-validation against a real reference is exactly the
guard we want. Production runtime path doesn't import pandas-ta —
zero prod overhead.

### Q3. `renko` indicator NOT in this batch

The Phase 2 Part 2 BLOCKERS doc listed 5 indicators blocking template
activations. This batch ships 4 + 1 net-new (fibonacci) but does NOT
ship Renko.

**Rationale for skipping Renko this batch:**
- Renko is a chart-bar TRANSFORM, not a per-bar indicator
- Output cardinality differs from input (one input bar may emit 0/1/
  many bricks)
- The existing indicator framework assumes "one output value per
  input bar"
- Renko needs a separate path that emits a list of variable-cadence
  bricks rather than a same-length output series

**Decision needed:** is the Renko deferral acceptable for this batch?
Recommendation: yes — Renko goes in Batch 2 (separate sprint) with
its own variable-cadence output convention.

Templates still blocked: `renko-trend`.

### Q4. `fibonacci_retracement` lookback default = 50

The default lookback is 50 bars. This works well on intraday 5-min
data (~4 hours of context) but may be too short on daily data (50
days = ~10 weeks). Existing pattern templates typically pull a
swing from a 20-60 bar window.

**Decision needed:** is 50 the right default? Should the default
adapt based on timeframe? Recommendation: **keep at 50** — templates
that need different lookback explicitly pass it; advanced templates
that want timeframe-adaptive lookback are a Phase 5+ feature.

### Q5. Output dict shape vs flat list shape

This batch ships TWO indicators with non-scalar outputs:
- `heikin_ashi` → list of 4-key dicts (ha_open, ha_high, ha_low, ha_close)
- `fibonacci_retracement` → list of 7-key dicts (swing_high, swing_low, 5 levels)

The existing convention for multi-output indicators (MACD,
Bollinger) uses TUPLES of separate same-length lists — the
indicator_runner then exposes each sub-output under
`<config_id>.<suffix>` in the strategy DSL.

**Decision needed:** should heikin_ashi + fibonacci_retracement be
refactored to return tuples-of-lists to match the existing dispatch
pattern in `backtest/indicator_runner.py`?

Recommendation: **YES, but in a follow-up Batch 1B** — keep this
batch's calc files exactly as-is (the unit tests pass and the
math is correct), then in Batch 1B refactor the output shape to
tuples-of-lists + update `indicator_runner.py` dispatch.

Until then, anyone who tries to USE heikin_ashi or
fibonacci_retracement in a backtest will hit a dispatch gap in
`indicator_runner.py` (the indicator dispatch table doesn't know
about the new ids).

**This is a critical gap to surface before merge** — the
indicator IS registered ACTIVE but the backtest engine doesn't
know how to call it. The strategy_engine.backtest.indicator_runner
must learn the new ids before customers can backtest strategies
using them.

### Q6. `indicator_runner.py` dispatch table needs entries for the new ids

Per Q5, the backtest engine's `precompute_indicators` function
contains a 165-branch dispatch table mapping each registered
indicator id to its input-shape signature. The 5 new ids are NOT in
that dispatch. Calling `run_backtest` on a strategy that uses any
of the 5 new ids will hit the fallback
`raise IndicatorRunnerError("No backtest dispatch for indicator
type ...")`.

This is **outside the scope of Task 1** (hard constraint:
"NO modifications to backend/app/strategy_engine/backtest/*").

**Decision needed:** when does the dispatch wiring sprint land?
The 5 indicators are ACTIVE in the registry (UI shows them as
available), but the backtest engine can't simulate them yet.

Recommendation: ship a follow-up branch `feat/indicator-runner-batch-1-dispatch`
that ONLY touches `indicator_runner.py` to add the 5 dispatch
branches. That branch is explicitly out of this task's scope but
needs to ship before any Phase-2 template using these ids can be
activated.

---

## Files added/modified

```
backend/app/strategy_engine/indicators/calculations/heikin_ashi.py         NEW
backend/app/strategy_engine/indicators/calculations/alma.py                NEW (re-export)
backend/app/strategy_engine/indicators/calculations/kama.py                NEW
backend/app/strategy_engine/indicators/calculations/pivot_swing.py         NEW
backend/app/strategy_engine/indicators/calculations/fibonacci_retracement.py  NEW
backend/app/strategy_engine/indicators/_batch1_commission_active.py        NEW
backend/app/strategy_engine/indicators/registry.py                         2-line edit (import + splat)
backend/tests/strategy_engine/indicators/__init__.py                       NEW (empty)
backend/tests/strategy_engine/indicators/calculations/__init__.py          NEW (empty)
backend/tests/strategy_engine/indicators/calculations/test_heikin_ashi.py             NEW (11 tests)
backend/tests/strategy_engine/indicators/calculations/test_alma.py                    NEW (12 tests)
backend/tests/strategy_engine/indicators/calculations/test_kama.py                    NEW (14 tests, 1 skipped)
backend/tests/strategy_engine/indicators/calculations/test_pivot_swing.py             NEW (12 tests)
backend/tests/strategy_engine/indicators/calculations/test_fibonacci_retracement.py   NEW (13 tests)
docs/INDICATOR_COMMISSION_BATCH_1.md                                       NEW
BLOCKERS_INDICATOR_COMMISSION_1.md                                         NEW (this file)
```

NOT touched:
- Any file in `backend/app/strategy_engine/backtest/`
- Any existing `_pack*_active.py` (only `registry.py` for the splat)
- Any existing test
- `pyproject.toml` (no new packages)

## Test results

```
$ pytest backend/tests/strategy_engine/indicators/calculations/ --no-cov
======================== 62 passed, 1 skipped in 0.70s =========================
```

The 1 skip is `test_kama_matches_pandas_ta_when_available` — graceful
skip when pandas-ta isn't in the venv (decision Q2).
