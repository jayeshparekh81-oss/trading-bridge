# Phase 2 Templates Part 2 — selection rationale + status report

**Branch:** `feat/phase-2-templates-part-2`
**Date:** 2026-05-17
**Audit data:** snapshot of `backend/data/strategy_templates_seed.json` at branch cut

---

## TL;DR — surprise finding

The Queue II Task 2 spec asked for "the next 20 inactive equity templates." The current state of `main`:

```
TOTAL templates:        113
active equity:           45   ← was 15 at Queue I start
inactive equity:          5   ← was 35 at Queue I start
options pending:         63
```

**The 20 not-picked from Queue I's first round are nearly all active.** Only 5 inactive equity slugs remain — all of them blocked on **missing indicator implementations** (registry metadata exists, but `calculation_function` is None). They cannot be config'd until the underlying indicators are commissioned.

This branch documents the gap and proposes the indicator commission backlog.

---

## The 5 remaining inactive equity templates

| Slug | Category | Complexity | Required indicator | Indicator status |
|---|---|---|---|---|
| `renko-trend` | Trend Following | advanced | `renko` | metadata only (COMING_SOON, no calculation_function) |
| `heikin-ashi-smooth-trend` | Trend Following | intermediate | `heikin_ashi` | metadata only (COMING_SOON, no calculation_function) |
| `alma-slope` | Trend Following | intermediate | `alma` | metadata only (COMING_SOON, no calculation_function) |
| `kama-adaptive-trend` | Trend Following | advanced | `kama` | metadata only (COMING_SOON, no calculation_function) |
| `pivot-reversal-strategy` | Mean Reversion | intermediate | `pivot_swing` | **not in registry at all** |

For comparison, the registry currently holds **281 indicator entries** of which:
- 230 are `ACTIVE` (have working `calculation_function`)
- 51 are `COMING_SOON` (metadata-only, calculation_function = None)

The 4 indicators above are members of the 51 `COMING_SOON` set. The 5th (`pivot_swing`) is missing entirely — the closest registered candidates are `swing_high`, `swing_low`, `pivot_points`, but those have different semantics and would change the template's character.

---

## What this branch ships

Three artifacts. No config_json — the indicators don't exist, so a config that references them would fail the registry-membership validator at strategy-creation time.

### 1. `docs/PHASE_2_TEMPLATES_PART_2.md` — this file

Selection rationale + indicator-gap analysis.

### 2. `backend/data/phase_2_part_2_template_configs.json`

Empty configs array. Carries `_meta.status = "BLOCKED — needs indicator commission"` so any future automation that picks this file up sees the blocker explicitly.

### 3. `BLOCKERS_PHASE_2_PART_2.md`

The indicator-commission backlog: for each of the 5 templates, what indicator implementation is required, what TA-Lib equivalent exists (or doesn't), and which template should ship first when commissions land.

---

## Why each indicator is non-trivial

### `renko`

Renko is a **chart transform**, not an indicator. A Renko brick prints when price moves a fixed ATR distance from the previous brick — it's a re-sampling of OHLC data, not a per-bar value. Implementation needs:

- A brick-emit decision per OHLC bar (may emit zero, one, or multiple bricks)
- A separate output series shape (bricks ≠ candles)
- Indicator-runner dispatch logic to handle the variable-length output

This is several days of work, not a one-function port from TA-Lib (which doesn't have it either — it's a TradingView-native primitive).

### `heikin_ashi`

Heikin-Ashi is a **candle transform** — every input candle maps to one transformed candle:

```
ha_close  = (o + h + l + c) / 4
ha_open   = (prev_ha_open + prev_ha_close) / 2  (recursive)
ha_high   = max(h, ha_open, ha_close)
ha_low    = min(l, ha_open, ha_close)
```

Implementation is straightforward (~30 lines of Python) but the
indicator-runner dispatch needs to emit **four output series** under
one config id (`ha_open`, `ha_high`, `ha_low`, `ha_close`) rather than
the usual single primary line. The dotted-notation sub-output pattern
(used by MACD, Bollinger, etc.) handles this — no new dispatch shape
needed, just an `_compute_one` branch + a test fixture.

Estimated work: 1 day including tests.

### `alma`

Arnaud Legoux Moving Average — Gaussian-weighted smoothing:

```
alma(close, period, offset=0.85, sigma=6) =
    sum_i [ exp(-((i - m)^2) / (2 * s^2)) * close[-period + i] ]
    / normaliser
where  m = offset * (period - 1)
       s = period / sigma
```

Pure-Python implementation is ~15 lines. TA-Lib doesn't ship ALMA;
`pandas-ta` does. Two routes:
- (a) write the formula directly (no new dep)
- (b) vendor `pandas-ta` (new dep, surfaces in BLOCKERS_PHASE_2_PART_2.md)

Estimated work: half a day including tests + parameter validation
(period 5-200, offset 0-1, sigma 1-20).

### `kama`

Kaufman Adaptive Moving Average — variable-smoothing based on an
"efficiency ratio":

```
direction[n] = abs(close[n] - close[n-period])
volatility[n] = sum_i abs(close[n-i] - close[n-i-1])  for i in [0, period)
er[n] = direction[n] / volatility[n]                  # efficiency ratio
sc[n] = (er[n] * (fast_sc - slow_sc) + slow_sc) ^ 2   # smoothing constant
kama[n] = kama[n-1] + sc[n] * (close[n] - kama[n-1])
```

with `fast_sc = 2/(2+1) = 2/3` and `slow_sc = 2/(30+1) = 2/31` by
default. TA-Lib ships `KAMA` natively (`talib.KAMA`); the binding is
already installed (`pyproject.toml: ta-lib = ...`). Implementation =
one TA-Lib call + param validation + warmup region handling.

Estimated work: half a day including tests.

### `pivot_swing` (missing from registry entirely)

The slug `pivot-reversal-strategy` ports a TradingView built-in
"Pivot Reversal" strategy that detects classic Dow swing pivots
(higher-highs, lower-lows pattern) and trades the reversal.

Two ways to implement:
- (a) Add a new `pivot_swing` indicator whose calculation is a
  thin wrapper around the existing `swing_high` + `swing_low` pair,
  emitting a signed "swing direction" per bar.
- (b) Wire the template directly to `swing_high` + `swing_low` and let
  the condition_evaluator combine them.

Recommendation: **(a)** — keeps the template's `indicators_used` field
self-documenting (the customer-visible explanation is "pivot reversal,"
not "two swing detectors AND a custom join condition"). Also the
`pivot-reversal-strategy` slug exists in the seed; renaming would
require an `is_active` flip-flop migration.

Estimated work: half a day, including registering the new indicator.

---

## Recommended commission sequence

If founder approves the indicator commission, the lightest-first order is:

1. **`kama`** (half day; one TA-Lib call away from done)
2. **`alma`** (half day; ~15 lines pure-Python)
3. **`pivot_swing`** (half day; thin wrapper on existing swing_high/low)
4. **`heikin_ashi`** (one day; needs multi-output dispatch)
5. **`renko`** (~3 days; chart transform with variable output cadence)

Total: ~5 dev-days for all 5 templates to become shippable.

If priorities force a subset: ship items 1-3 (1.5 days) for **3 templates active** (kama-adaptive-trend, alma-slope, pivot-reversal-strategy). The Heikin-Ashi + Renko templates wait for a later sprint.

---

## What I did NOT do on this branch

- **No edits to `strategy_templates_seed.json`** — the live seed stays unchanged. The 5 templates remain `is_active=False`.
- **No new indicator implementations** — those are real engine work, not template-config work. They belong in a separate `feat/indicator-commission-renko-heikin-alma-kama-pivot-swing` branch (or split into 5 mini-branches).
- **No `phase_2_part_2_template_configs.json` configs** — proposing configs that reference non-functional indicators would just fail validation. The file ships with an empty `proposals` array + a status note.

---

## See also

- `BLOCKERS_PHASE_2_PART_2.md` — indicator-commission backlog
- `docs/PHASE_2_TEMPLATE_CONFIGS.md` — Queue I Task 2 (the 15 configs that were originally proposed; founder review pending)
- `backend/data/strategy_templates_seed.json` — live seed (45 active equity now)
- `backend/app/strategy_engine/indicators/registry.py` — 281-entry indicator registry
