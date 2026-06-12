# Queue EEE — Smoke-Test Chain Final Report

**Branch:** `feat/queue-eee-indicator-smoketests` (worktree `../trading-bridge-smoketests`)
**Mission completed:** All 137 SKIPPED indicators from Sprint 6b have been smoke-tested.
**Scope reminder:** **Execution-quality testing only** — no reference math verification. SMOKE_PASS means the implementation is robust, NOT that the math is right.

---

## 1. Headline classification

| Class | Count | % |
|---|---:|---:|
| **SMOKE_PASS** | **127** | **93%** |
| SMOKE_WARN | 6 | 4% |
| SMOKE_FAIL | 0 | 0% |
| MOVED_OUT_OF_SCOPE | 3 | 2% |
| REMOVED_FROM_CODEBASE | 1 | 1% |
| **Total** | **137** | **100%** |

**Zero hard execution failures across all 137 indicators.** The 6 WARNs are "no signal under synthetic data" not crashes. The 4 reclassifications retire false-positive FAILs from the original session 1 run.

---

## 2. Per-skip-category breakdown (6b §4 categories)

| Category | Total | PASS | WARN | MOVED | REMOVED |
|---|---:|---:|---:|---:|---:|
| 4a Composite scores (TRADETRI-custom) | 13 | 9 | 0 | 3 | 1 |
| 4b Custom oscillators | 3 | 3 | 0 | 0 | 0 |
| 4c Risk-adjusted ratios | 8 | 8 | 0 | 0 | 0 |
| 4d Multi-timeframe / composites | 9 | 9 | 0 | 0 | 0 |
| 4e Options / F&O-specific | 5 | 5 | 0 | 0 | 0 |
| 4f Regression + statistical | 7 | 7 | 0 | 0 | 0 |
| 4g Advanced cycle / Hilbert | 4 | 4 | 0 | 0 | 0 |
| 4h Divergence variants | 3 | 3 | 0 | 0 | 0 |
| 4i Candlestick patterns | 8 | 8 | 0 | 0 | 0 |
| 4j Other (catch-all) | 77 | 71 | 6 | 0 | 0 |

Notable: every category except 4a and 4j is **100% PASS**. The PASS rate would be higher in 4a if we removed the 4 non-indicator entries (trust/truth/regime/rule_adherence_score) from the skip log.

---

## 3. Full non-PASS list with founder decision menu

### A. Reclassified out of indicator scope (4)

| Indicator | Class | Where it actually lives | Founder decision menu |
|---|---|---|---|
| `trust_score` | MOVED_OUT_OF_SCOPE | `backend/app/strategy_engine/reliability/trust_score.py` — backtest reliability scoring engine | **(a) Remove from skip log** (recommended — it's not an indicator); **(b)** Leave as a known orphan |
| `truth_score` | MOVED_OUT_OF_SCOPE | `backend/app/strategy_engine/truth/truth_score.py` — fake-backtest detector consuming ReliabilityReport | **(a) Remove from skip log** (recommended); **(b)** Leave as known orphan |
| `rule_adherence_score` | MOVED_OUT_OF_SCOPE | Surfaces as `rule_adherence_percent` in `paper_trading/engine.py` — runtime paper-trading metric | **(a) Remove from skip log** (recommended); **(b)** Leave as known orphan |
| `regime_score` | REMOVED_FROM_CODEBASE | No match anywhere in `backend/app` | **(a) Remove from skip log** (recommended — genuinely gone); **(b)** Reinstate the module if intended |

### B. SMOKE_WARN — all-NaN-tail under single-symbol synthetic data (6)

| Indicator | Root cause | Founder decision menu |
|---|---|---|
| `fibonacci_retracement` | Returns sparse pivot-point output; trailing 30% is NaN-padded by design | **(a) Accept-as-custom** (recommended — not a crash, just sparse output); **(b)** Add pivot-aware S3 check to harness |
| `nifty_50_relative_position` | Needs a second symbol (NIFTY) time-series; harness only injects single-symbol OHLCV → all-NaN | **(a) Accept-as-custom-with-disclaimer** (recommended — works in prod where a benchmark feed exists); **(b)** Add benchmark-pair input route to harness (~30 min) |
| `nifty_correlation` | Same — needs benchmark series | Same menu as above |
| `nse_bse_arbitrage_proxy` | Same — needs second-exchange series | Same menu — note: this indicator may need real cross-exchange data even in prod |
| `relative_strength_vs_benchmark` | Same — needs benchmark series | Same menu |
| `vix_correlation` | Needs VIX series alongside primary OHLCV | Same menu — note: VIX feed availability is a prod question |

**All 6 WARNs cluster into 2 root causes:**
1. **Sparse output by design** (1 indicator: `fibonacci_retracement`) — accept.
2. **Single-symbol harness limitation** (5 indicators) — accept-as-custom, with a note that prod must verify the second-symbol feed is wired.

---

## 4. Session 1 → Session 2 delta (reclassification work)

Session 1 ended at **64P / 3W / 8F**. The 8 FAILs broke into two groups, both addressed in session 2:

### Group A — 4 missing-module FAILs (now reclassified)
Hunted in the codebase, found 3 under different subsystems (reliability, truth, paper_trading) and 1 genuinely gone. None are OHLCV indicators. Reclassified as MOVED_OUT_OF_SCOPE / REMOVED_FROM_CODEBASE.

### Group B — 4 empty-output FAILs (now PASS)
Root cause was a harness gap, not an indicator bug: `calmar_ratio`, `omega_ratio`, `iv_percentile`, `iv_rank` all default `period`/`lookback=252` (one trading year), but the harness only injected 200-bar synthetic data. Fixed `smoke_runner.build_call`:
- Detect `lookback` in addition to `period`/`length`/`window`
- Override large period-ish defaults (>50) to 30 — opens the lookback window while respecting indicator minimums (e.g., `hurst_exponent` requires period ≥ 16)

Side effect: 2 of session 1's WARNs (`negative_volume_index_signal`, `positive_volume_index_signal`) also flipped to PASS under the new harness.

Net: 64P/3W/8F → 70P/1W/0F + 3 MOVED + 1 REMOVED (on the original 75 indicators).

---

## 5. Framework lessons (continuation of Sprint 6 chain's #15)

**Lesson #16 (Queue EEE):** When the harness routes synthetic inputs by signature kind, it must also override large default lookbacks/periods. An indicator that "passes" in production with a 252-bar default needs a smaller window under 200-bar synthetic data. The right policy is: override period-ish kwargs whose defaults exceed `n_synthetic / 4` to a value `≥ 16` (covers known minimums).

**Lesson #17 (Queue EEE):** Single-symbol synthetic data hides "second-symbol" indicator dependencies. Five indicators in this batch quietly returned all-NaN because the harness only ships one OHLCV. Future harness v3 should accept either an explicit benchmark series or a sentinel flag that triggers BENCHMARK_REQUIRED classification instead of WARN.

**Lesson #18 (Queue EEE):** A skip list inherited from earlier sprints can be stale — the 4 MOVED/REMOVED entries above were in the 6b skip log but are not actually OHLCV indicators. Before a smoke chain, grep the skip list against `calculations/*.py` and flag mismatches as a first-class category.

---

## 6. Recommendation

**Ship as-is.** Queue EEE confirms that **127 of 137 TRADETRI-custom indicators run cleanly under execution-quality stress**:

- No crashes on uptrend / downtrend / flat / gappy / minimal-bars / zero-volume regimes
- No `inf` returns, no non-deterministic outputs, no S2 length mismatches
- The 6 WARNs are not blockers — they're known sparse-output or single-symbol limitations

**Action items for founder review:**

1. **Skip-log hygiene** — remove `trust_score`, `truth_score`, `rule_adherence_score`, `regime_score` from the Sprint 6b skip log (they're not OHLCV indicators). Cleans up the `41% coverage` denominator if you ever recompute it.
2. **Production verification of 5 benchmark-needing indicators** — before any of `nifty_50_relative_position`, `nifty_correlation`, `nse_bse_arbitrage_proxy`, `relative_strength_vs_benchmark`, `vix_correlation` ship in a customer-facing template, confirm the second-symbol feed is wired in prod.
3. **No production code changes recommended** from this chain — per spec, this was execution testing, not math verification. The 96-indicator verified surface from Sprint 6 (Pine-view) is unchanged.

---

## 7. Artifacts

| File | Description |
|---|---|
| `backend/tests/queue_eee_smoketests/smoke_runner.py` | The harness (≈360 LOC) |
| `backend/tests/queue_eee_smoketests/results.csv` | All 137 rows: indicator, S1-S5, classification, note |
| `docs/QUEUE_EEE_STATE.md` | Per-indicator state + session log |
| `docs/QUEUE_EEE_PROGRESS.md` | Founder-readable snapshot |
| `docs/QUEUE_EEE_FINAL_REPORT.md` | This file |

**Branch ready for review.** No merges to main. No production touched. No Docker touched.
