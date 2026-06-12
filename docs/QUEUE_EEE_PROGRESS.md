# Queue EEE — Smoke-test Progress

**CHAIN COMPLETE.** See `QUEUE_EEE_FINAL_REPORT.md` for the full founder report.

## Snapshot

| Metric | Count |
|---|---:|
| Total indicators in scope | 137 |
| Completed | **137** |
| Progress | **100%** |

## Final classification

| Class | Count | % |
|---|---:|---:|
| **SMOKE_PASS** | **127** | **93%** |
| SMOKE_WARN | 6 | 4% |
| MOVED_OUT_OF_SCOPE | 3 | 2% |
| REMOVED_FROM_CODEBASE | 1 | 1% |
| SMOKE_FAIL | **0** | 0% |

**Zero hard execution failures** across all 137 TRADETRI-custom indicators.

## What "SMOKE_PASS" means here

The indicator ran cleanly on all 6 synthetic regimes (uptrend, downtrend, flat, gappy, minimal-bars, zero-volume), produced output of expected length, didn't return `inf`, was deterministic between two runs, and didn't crash on the edge regimes. **It does NOT mean the math is correct** — these are TRADETRI-custom indicators with no external golden truth (per Sprint 6b spec). It means the implementation is robust under execution.

## Non-PASS items (10 total, all addressed in FINAL_REPORT)

### MOVED_OUT_OF_SCOPE (3) — found in codebase under non-indicator subsystems

- `trust_score` → `reliability/trust_score.py` (backtest scoring engine)
- `truth_score` → `truth/truth_score.py` (fake-backtest detector)
- `rule_adherence_score` → `paper_trading/engine.py` (runtime metric `rule_adherence_percent`)

### REMOVED_FROM_CODEBASE (1)

- `regime_score` — no match anywhere

### SMOKE_WARN (6) — all-NaN-tail under single-symbol synthetic data

- `fibonacci_retracement` — sparse pivot output by design
- `nifty_50_relative_position`, `nifty_correlation`, `nse_bse_arbitrage_proxy`, `relative_strength_vs_benchmark`, `vix_correlation` — need a second-symbol time-series the harness doesn't ship

See `QUEUE_EEE_FINAL_REPORT.md` §3 for the founder decision menu per item.

## Sessions

| Session | Batches | Pass | Warn | Fail | Reclassified |
|---:|---|---:|---:|---:|---:|
| 1 | 1, 2, 3 | 64 | 3 | 8 | — |
| 2 | 4, 5, 6 + harness extension | 57 | 5 | 0 | 8 (4 MOVED/REMOVED + 4 lookback-fix → PASS) |
| **Total** | **all 6** | **127** | **6** | **0** | **+3 MOVED, +1 REMOVED** |

## Status

**No further sessions needed.** See `QUEUE_EEE_FINAL_REPORT.md` for the founder review.
