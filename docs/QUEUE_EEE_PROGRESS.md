# Queue EEE — Smoke-test Progress

**Reusable founder-readable snapshot. Updated at end of every session.**

## Snapshot

| Metric | Count |
|---|---:|
| Total indicators in scope | 137 |
| Completed | **75** |
| Remaining | 62 |
| Progress | **55%** |

## Classification so far

| Class | Count | % of completed |
|---|---:|---:|
| SMOKE_PASS | 64 | 85% |
| SMOKE_WARN | 3 | 4% |
| SMOKE_FAIL | 8 | 11% |

## What "SMOKE_PASS" means here

The indicator ran cleanly on all 6 synthetic regimes (uptrend, downtrend, flat, gappy, minimal-bars, zero-volume), produced output of expected length, didn't return `inf`, was deterministic between two runs, and didn't crash on the edge regimes (R5 minimal_bars / R6 zero_volume). **It does NOT mean the math is correct** — these are TRADETRI-custom indicators with no external golden truth (per Sprint 6b spec). It means the implementation is robust under execution.

## Notable SMOKE_FAILs (8 so far)

### Group A — Missing modules (4, expected)

These names appear in the 6b skip log but the corresponding `.py` file is absent in `app/strategy_engine/indicators/calculations/`. Likely renamed or never landed.

| Indicator | Reason |
|---|---|
| `trust_score` | No module in calculations/ |
| `truth_score` | No module in calculations/ |
| `regime_score` | No module in calculations/ |
| `rule_adherence_score` | No module in calculations/ |

**Founder decision menu:** for each of these — **(a) deprecate** from skip log (file is gone), or **(b) fix** by reinstating the module, or **(c) accept** as a known orphan in the 6b classification.

### Group B — Returns empty / zero-length output (4)

These run without exception but return a 0-length series, which fails S2 (length mismatch with input). They probably need *returns* (per-bar return series) as input, not raw closes — same issue Sprint 6b flagged for risk-adjusted ratios.

| Indicator | Reason |
|---|---|
| `calmar_ratio` | Empty output; needs equity-curve/returns input |
| `omega_ratio` | Empty output; needs returns input |
| `iv_percentile` | Empty output; likely needs IV time-series input |
| `iv_rank` | Empty output; likely needs IV time-series input |

**Founder decision menu:** **(a) fix** by extending the smoke-test data loader to provide returns + IV proxy series, or **(b) accept-as-custom-with-disclaimer** because these inputs are outside the OHLCV contract.

## Notable SMOKE_WARNs (3)

All three are "all-NaN tail" — the indicator ran cleanly but the trailing 30% of output had no finite values. Not a crash, but no usable signal at the end of the synthetic series. Possible causes: long warmup period, or upstream NaN propagation from a composed indicator.

| Indicator | Note |
|---|---|
| `negative_volume_index_signal` | all_nan_tail (probably long warmup + threshold lookback) |
| `positive_volume_index_signal` | all_nan_tail (same family) |
| `fibonacci_retracement` | all_nan_tail (likely returns pivots-only, sparse output) |

**Founder decision menu:** likely **(c) accept** — these are not crashes, just "no signal" under synthetic data; would be re-checked on real NIFTY data before being flagged in production.

## Sessions complete

| Session | Batches | Pass | Warn | Fail |
|---:|---|---:|---:|---:|
| 1 | 1, 2, 3 | 64 | 3 | 8 |

## What's next

- **Session 2** picks up **NEXT_BATCH = 4** (rows 76-100 of the skip CSV: `logarithmic_regression` → `relative_vigor_index`)
- Per spec, each session hard-caps at 3 batches (~75 indicators)
- After batch 6 (12 indicators), the chain completes — final report goes to `docs/QUEUE_EEE_FINAL_REPORT.md`
