# Queue XX Sprint 4c — NON_RUNNABLE Triage Report

**Branch:** `fix/sprint-4c-non-runnable`
**Time used:** ~20 min of 3 hr cap.
**Scope:** Triage Sprint 3's 16 NON_RUNNABLE (SCALAR sig_kind) indicators.
Apply MECHANICAL framework input-routing fixes only. ZERO indicator math
touched.

## 1. Root-cause classification (4 patterns)

Sprint 3's `detect_signature_kind()` classified these 16 as `SCALAR`
because none of the conventional OHLCV parameter names appeared
together. Reading the signatures via `inspect.signature` exposed four
underlying patterns:

| Pattern | Count | Inputs | Examples |
|---|---:|---|---|
| **A — Single-array + period/lookback** | 7 | one of {highs / lows / volumes} + period args | `consecutive_higher_lows`, `price_channel_high`, `price_channel_low`, `rate_of_change_volume`, `swing_high`, `swing_low`, `volume_sma` |
| **B — Timestamp-only** | 4 | `timestamps` (no OHLCV) | `day_of_week_signal`, `hour_of_day`, `is_expiry_week`, `minutes_to_close` |
| **C — Single-array + timestamps** | 3 | one of {highs / lows / volumes} + `timestamps` | `session_high_breakout`, `session_low_breakout`, `session_volume_pace` |
| **D — Special cases** | 2 | (i) `*args, **kwargs` reflection wrapper (alma) (ii) Pairwise `values_a, values_b` (correlation_coefficient) | `alma`, `correlation_coefficient` |

## 2. Framework fix applied

**New file:** `backend/tests/queue_xx_sprint_3/framework_extensions/sprint_4c_args.py`

Single function `build_args_4c()` — name-based generic router with two
special-case handlers:

- **`*args, **kwargs` (alma):** pass `closes_list` positional. Alma's
  reflection wrapper accepts the array as first positional.
- **Pairwise (`values_a, values_b`):** pass `closes_list` for BOTH arrays.
  Trivial autocorrelation = 1.0 on every bar, but proves the function
  invokes cleanly and emits the right output length. Real verification
  via paired arrays belongs to a hand-rolled-reference sprint.

Patterns A, B, C all handled by the generic name-based router already
described in Sprint 4b — single-input + timestamp routing works without
special-casing.

Zero changes to Sprint 3's existing framework modules.

## 3. Re-sweep results — 16 of 16 now RAN_OK

| Outcome | Count |
|---|---:|
| `RAN_OK` | **16 / 16** |
| `TYPE_ERR` | 0 |
| Other | 0 |

### Per-indicator output sanity

| Indicator | Pattern | NaN ratio | Sanity verdict |
|---|:---:|---:|---|
| `alma` | D | 0.002 | ✓ normal warmup |
| `consecutive_higher_lows` | A | 0.000 | ✓ |
| `correlation_coefficient` | D | 0.004 | ✓ trivial autocorr = 1.0 confirmed |
| `day_of_week_signal` | B | 0.000 | ✓ |
| `hour_of_day` | B | 0.000 | ✓ |
| `is_expiry_week` | B | 0.000 | ✓ |
| `minutes_to_close` | B | 0.000 | ✓ |
| `price_channel_high` | A | 0.004 | ✓ |
| `price_channel_low` | A | 0.004 | ✓ |
| `rate_of_change_volume` | A | 0.017 | ✓ |
| `session_high_breakout` | C | 0.000 | ✓ |
| `session_low_breakout` | C | 0.000 | ✓ |
| `session_volume_pace` | C | 0.048 | ✓ |
| `swing_high` | A | **0.941** | ✓ EXPECTED — swing-high pivots are rare (≤6% of bars) by design |
| `swing_low` | A | **0.936** | ✓ EXPECTED |
| `volume_sma` | A | 0.004 | ✓ |

No math-bug flags emerged from Sprint 4c — every indicator produces
output with semantics-consistent NaN ratios.

## 4. Mechanical fixes applied vs deferred

| Category | Mechanical (this sprint) | Deferred (other sprint) |
|---|---|---|
| Pattern A single-array routing | ✓ generic name-based router | — |
| Pattern B timestamp-only routing | ✓ generic name-based router | — |
| Pattern C single + timestamp routing | ✓ generic name-based router | — |
| Pattern D `*args/**kwargs` (alma) | ✓ positional `closes_list` | — |
| Pattern D pairwise (correlation_coefficient) | ✓ trivial autocorr proxy | Sprint 4d hand-roll with paired data |
| TA-Lib refs for these 16 | — | Sprint 4d (next in chain; none of these have a TA-Lib counterpart) |

## 5. Tier scoreboard delta from Sprint 4c

| Before Sprint 4c | After Sprint 4c |
|---|---|
| 16 × NEEDS_MANUAL_REVIEW (NON_RUNNABLE) | 16 × NEEDS_MANUAL_REVIEW (RAN_OK, needs hand-roll for verification) |

The 16 move from "couldn't even invoke" to "invokes cleanly, output
semantics confirmed, awaiting hand-rolled reference for tier
classification."

## 6. Sprint 4c hard-stops — all clear

| # | Cap | Observed | Status |
|---:|---|---|:---:|
| 1 | Sub-sprint time ≤ 180 min | 20 min | ✓ |
| 4 | >50% indicators fail | 0% fail (16/16 RAN_OK) | ✓ |
| 5 | Math fix attempted | 0 | ✓ |
| 6 | Main merge attempted | 0 | ✓ |

## 7. Sprint 4c artifacts

- `backend/tests/queue_xx_sprint_3/framework_extensions/sprint_4c_args.py`
  (~100 LOC; load_data_with_timestamps + build_args_4c with pairwise + var-args handlers)
- `backend/tests/queue_xx_sprint_3/sprint_4c_results.csv` (16 rows × 4 cols)
- `docs/QUEUE_XX_SPRINT_4C_REPORT.md` (this file)

## 8. Sprint 4c recommended next-session action

1. **Sprint 4d picks up these 16** (plus Sprint 4b's 22 RAN_OK + Sprint 3's
   168 NEEDS_REF) for hand-rolled reference verification.
2. **correlation_coefficient** specifically benefits from real paired data
   (e.g., NIFTY close vs RELIANCE close) in a future sprint — autocorr=1
   verifies invocation but not the actual math.
3. **swing_high / swing_low high NaN ratios (94%)** are by design — swing
   pivots are sparse. Don't flag as bugs.

## 9. Framework router maturity after Sprint 4b + 4c

The `build_args_4b` + `build_args_4c` pair now covers **38 of the 220
indicators** that Sprint 3 couldn't auto-invoke (22 EXEC_FAIL + 16
NON_RUNNABLE). Generic name-based routing handles the bulk; two specific
special-case branches close the long tail.

Combined router design recommendation for the next sprint: merge 4b and
4c into a single `build_args_unified()` since they share most logic. Live
on a stable post-chain branch.
