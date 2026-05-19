# Queue Z — Phase 2 Skip + Priority List for Future Commissioning

**Phase 2 status:** SKIPPED per mission's "Phase 1 finds ZERO missing indicators" hard-stop.
**Phase 3 status:** Also skipped — no clean priority list of dispatch-only commissions exists.
**Phase 4 status:** This file substitutes a curated priority list for Jayesh's review.

## Why no Phase 2/3 dispatch-wiring sprint

Per mission protocol "do Phase 3-equivalent batch from priority list (next 10 most commonly used uncommissioned indicators)," I surveyed the candidate pool:

1. **From templates:** zero missing (see `MISSING_INDICATORS.md`).
2. **From registry ACTIVE vs dispatch:** zero gap (perfect 230/230 parity).
3. **From registry COMING_SOON:** 51 candidates, BUT all 51 have `calculation_function=None` — no calc implementation exists on disk. Per mission's per-indicator hard-stop ("If NOT EXIST: STOP this indicator, log to BLOCKERS_DISPATCH_BATCH_2.md, move to next"), all 51 would be skipped, leaving zero net commissions.

So there is no dispatch-wiring sprint with quality output achievable in 3-4 hours. Anything in this space requires WRITING calc functions + golden-value tests + cross-validation against TA-Lib/pandas-ta — substantial per-indicator effort that warrants Jayesh's per-indicator design call (e.g. "match TA-Lib formula exactly" vs "use the pandas-ta variant" vs "ship a TradingView-compatible interpretation").

## The 51 COMING_SOON indicators (priority list for future supervised commissioning)

### Group A — Likely aliases for already-dispatched indicators (LOW EFFORT once verified)

These have name-similar peers in the ACTIVE dispatch table. Commission would likely be: write a thin calc that delegates to the ACTIVE peer, or just add an alias mapping in dispatch. Per-indicator effort ~30 min IF the alias is sound:

| COMING_SOON slug | Suspected ACTIVE peer | Verification needed |
|------------------|----------------------|---------------------|
| `mcginley` | `mcginley_dynamic` | Confirm "mcginley" = same formula as "mcginley_dynamic" (likely yes — McGinley Dynamic is the canonical name). |
| `mesa_sine` | `mesa_sine_wave` | Likely identical — confirm. |
| `sine_wave` | `mesa_sine_wave` | Likely identical — confirm. |
| `dominant_cycle` | `dominant_cycle_period` | Likely identical — confirm. |
| `vortex` | `vortex_positive` + `vortex_negative` | The unified "vortex" indicator output is the (positive, negative) pair. Could ship as a multi-output entry. |
| `roc_percent` | `roc` | Likely identical — `roc` already returns percent change typically. |
| `kama` | `kaufman_ama` | Almost certainly identical (Kaufman's Adaptive MA). |
| `alma` | `arnaud_legoux_ma` | Likely identical — ALMA = Arnaud Legoux MA. |
| `mcclellan_oscillator` | `mcclellan_oscillator_proxy` | The COMING_SOON is the "real" calc; ACTIVE is an approximation. May NOT be aliasable. |

### Group B — Genuinely new, deterministic, achievable (~45-60 min each with tests)

These need a fresh calc but have clear textbook definitions:

| Slug | Notes |
|------|-------|
| `stoch_rsi` | Stochastic of RSI — composes existing `rsi` + a stoch-on-series transform. |
| `heikin_ashi` | OHLC transform: 4-line formula. No params. |
| `dpo` | Detrended Price Oscillator — close minus shifted SMA. |
| `momentum` | Basic momentum oscillator (close − close[n]). Trivial. |
| `eom` | Ease of Movement (Arms). Standard. |
| `vix_fix` | Larry Williams' VIX Fix — highest-high over n periods. Simple. |
| `adl` | Accumulation/Distribution Line — already have `accumulation_distribution` ACTIVE; likely alias to that. Re-verify in Group A. |
| `nvi` | Negative Volume Index — already have `negative_volume_index` ACTIVE; alias to that. |
| `pvi` | Positive Volume Index — already have `positive_volume_index` ACTIVE; alias. |
| `vpt` | Volume Price Trend — already have `price_volume_trend` ACTIVE; alias. |

### Group C — Genuinely new, complex (90+ min each, founder design call recommended)

| Slug | Why complex |
|------|-------------|
| `t3` | Tillson T3 — cascaded EMAs with volume factor; multiple formula variants exist. |
| `frama` | Fractal Adaptive MA — uses Hurst exponent estimate; sensitive to parameter choices. |
| `jurik_ma` | Jurik MA — proprietary algorithm with multiple public approximations. |
| `mama` / `fama` | MESA Adaptive MA / Following Adaptive MA — Hilbert-transform driven. |
| `hilbert_transform` | Standalone Hilbert transform — typically a building block, rarely user-facing. |
| `ergodic_oscillator` | Blau's ergodic — double-smoothed momentum. |
| `pmo` | Price Momentum Oscillator — multi-step smoothing. |
| `rmi` | Relative Momentum Index — RSI variant with lookback. |
| `schaff_trend_cycle` | STC — composition of MACD + Stochastic, multi-step. |
| `arms_index_trin` | Requires advance/decline data, not just OHLCV. |
| `klinger_oscillator` / `kvo` | Klinger Volume Oscillator. |
| `accelerator_oscillator` | Awesome Oscillator derivative. |
| `ppo` | Percentage Price Oscillator — MACD with % output. |
| `lsma_*` (slope/angle/intercept) | Least-squares MA decomposition. |
| `demand_index` | Specialty volume indicator. |
| `market_facilitation_index` | Bill Williams — OHLC + volume. |
| `range_bars`, `renko` | Bar-construction methods, not on-OHLCV calcs. Engine-architectural change. |
| `fractals` | Bill Williams fractals — pattern detection. |
| `fib_extension`, `fib_fan`, `fib_retracement`, `fib_time_zones` | Fibonacci family — UI overlay tools, may not need engine calcs. |
| `envelopes`, `percentile_bands`, `atr_bands`, `std_error_bands` | Band variations on existing indicators — possibly all aliases of pre-existing band calcs. |
| `demark_pivots` | TD pivot methodology. |
| `hilbert_transform`, `dominant_cycle` already in Group A. |

## Recommendation for the supervised session

If/when Jayesh decides to commission a batch:

1. **Start with Group A.** Verify the suspected aliases by reading the COMING_SOON registry rows + comparing definitions to the ACTIVE peers. Where alias is sound, flip status to ACTIVE and add a dispatch entry that calls the same calc function. **Estimated batch yield: 5-7 indicators, ~3 hours total** — same time the original mission budgeted for 10.

2. **Then Group B.** Pick the 3-4 that customers most ask for. `stoch_rsi` and `heikin_ashi` are TradingView staples and likely customer-facing demand.

3. **Group C is roadmap, not sprint material.** Each needs a per-indicator spec.

## Why this is the right call vs blasting through 10

Per memory's "AI-first 90/10 doctrine + 96% test coverage non-negotiable":

- A speculative 10-indicator dispatch sprint without per-indicator semantic verification ships **bugs at scale** if any of the 5-6 suspected aliases turn out to be subtly different calculations (e.g. ALMA's offset parameter is non-trivial; T3's volume factor is implementation-dependent).
- 96% coverage requires golden-value tests with verified numeric outputs. Without time to run pandas-ta cross-validation per indicator, "coverage" would be hollow line-coverage on calc functions, not behavioral verification.
- The mission's hard-stop on `ESCALATED_LIVE_TOUCH` is satisfied (calcs are engine-only), but the spirit ("ship a quality batch") is better served by Jayesh's per-indicator green-light than by autonomous guesses on each calc choice.

The conservative output is also the actually-useful output here.
