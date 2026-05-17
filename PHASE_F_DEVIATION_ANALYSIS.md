# Phase F — Deviation Analysis

**Date:** 2026-05-17 (1 day before May-18 launch)
**Branch:** `feat/phase-f-indicator-audit`
**Analyst:** Claude Code (Opus 4.7, 1M ctx), reviewed by Jayesh
**Scope:** Quantitative verification of the two Pine/TradingView deviations flagged in Phase A audit (`PHASE_F_COMPONENT_1_AUDIT.md`, §3-4).
**Evidence:** `backend/tests/services/indicators/fixtures/_deviation_analysis.py` (script, reproducible) + `backend/tests/services/indicators/fixtures/_deviation_analysis_output.csv` (per-bar values, 100 rows × 17 cols).

---

## Executive summary

- **EMA verdict: CONVENTION (non-deviation)** — empirical post-warmup % diff is exactly 0.0; TA-Lib and Pine both seed with `SMA(close[0..N-1])` at index N-1, so the `ema.py` module docstring's claim of a Pine seeding deviation is **factually incorrect** (the docstring describes a divergence that does not exist).
- **BB verdict: BUG** — TRADETRI's `bb.py:67-72` post-processing correction makes BB bands **+2.60% wider than Pine** at length=20, exactly equal to `sqrt(20/19) - 1`. Pine's `ta.stdev` defaults to biased (÷N), TA-Lib's `BBANDS` uses biased internally, so the "Pine-compat correction" goes the wrong way and inflates bands by ~2.6%. Existing fixture-CSV tests are self-referential against TRADETRI's own (wrong) output, so the bug is invisible to the current test suite.
- **Pre-launch recommendation: FIX BB BEFORE LAUNCH; no action on EMA.** BB fix is a one-line removal of the correction in `bb.py:67-72` + regeneration of `bb_expected.csv`. Per the new-files-only doctrine this is an authorized-exception fix; Jayesh decides whether to authorize.

---

## Deviation 1: EMA seeding

### What

The `ema.py` module docstring at `backend/app/services/indicators/ema.py:1-15` claims:

> *"TA-Lib's EMA seeds the recursion with `SMA(close[0..length-1])` and emits NaN for the first `length - 1` positions. Pine Script's `ta.ema(close, length)` seeds with the first close value and emits a non-NaN value at position 0."*

In reality, **Pine Script's `ta.ema` ALSO seeds with `SMA(close[0..length-1])` at index `length-1`** and emits no value before that index. The "deviation" the docstring describes does not exist.

### Where (file:line)

`backend/app/services/indicators/ema.py:1-15` (module docstring) — the factually incorrect claim.

`backend/app/services/indicators/ema.py:33-42` — the actual code, which is `talib.EMA(closes, timeperiod=params.length)` and is correct.

### Why (from code or audit)

The module docstring justifies the (non-existent) deviation as *"For v1 we ship the TA-Lib seeding (locked architecture: TA-Lib defaults are industry-standard). Operators comparing chart overlays to a Pine indicator will see a small leading-edge discrepancy that decays into the chart history."*

This is rationalizing a phantom problem. There is no chart-overlay discrepancy with Pine because TA-Lib's seeding IS Pine's seeding.

### Pine reference

Pine Script v5 documentation for `ta.ema(source, length)`:

```
alpha = 2 / (length + 1)
EMA[i] = NaN                              for i < length - 1
EMA[length - 1] = SMA(source[0..length-1])
EMA[i] = alpha * source[i] + (1 - alpha) * EMA[i - 1]   for i >= length
```

Identical to TA-Lib's `talib.EMA` (which is exactly what `ema.py` wraps).

### Divergence numbers

Source: 100-bar synthetic NIFTY series, length=20, post-warmup (81 bars compared).

| Metric | Value |
|---|---|
| Max abs %diff | **0.00e+00** (literal zero) |
| Mean abs %diff | 0.00e+00 |
| Bars with %diff > 0.1% | 0 |
| Bars with %diff > 1% | 0 |
| Bars with %diff > 5% | 0 |
| Persistence | n/a (no divergence to characterize) |

There is no divergence to measure. TRADETRI EMA and Pine EMA produce bit-identical output on every post-warmup bar.

### Threshold-flip impact

On the 100-bar synthetic series, comparing TRADETRI EMA(20) and Pine EMA(20) for the canonical "close crossed EMA" signal:

| Signal | TRADETRI flips | Pine flips | Disagreements |
|---|---:|---:|---:|
| close > ema(20) crossovers | (identity) | (identity) | **0** |

No signals would fire differently between TRADETRI and TradingView for the synthetic series. (Trivially true: the value arrays are equal.)

### Verdict

**CONVENTION** — but specifically: a **non-deviation that is documented as a deviation**. The math is right. The docstring is wrong. No customer-visible problem. The action item is a docstring fix in a future cleanup sprint, not a code fix.

---

## Deviation 2: BB stddev

### What

`backend/app/services/indicators/bb.py:67-72` applies a post-processing correction to TA-Lib's `BBANDS` output:

```python
correction = math.sqrt(params.length / (params.length - 1))
upper = middle + (upper - middle) * correction
lower = middle - (middle - lower) * correction
```

The docstring claims this converts TA-Lib's biased (÷N) stddev bands to Pine's sample (÷N-1) stddev bands, "matching Pine `ta.bb()` exactly."

In reality, **Pine `ta.stdev` defaults to `biased=true` (÷N, population stddev)** — the same convention TA-Lib uses internally. The correction is therefore unnecessary AND backwards: it scales bands UP by `sqrt(N/(N-1))` when they should be left alone, making TRADETRI's bands **~2.6% wider than Pine's at length=20**.

### Where (file:line)

`backend/app/services/indicators/bb.py:1-26` (module docstring): contains the factual error about Pine's stddev default.

`backend/app/services/indicators/bb.py:67-72` (the correction code): the lines that need to be removed.

### Why (from code or audit)

The module docstring claims:

> *"TA-Lib's `talib.BBANDS` computes the band's standard deviation using the **biased (population)** formula — divides the sum of squared deviations by N. TradingView's Pine `ta.stdev(src, length)` uses **sample** stddev — divides by N-1."*

The first sentence is correct. The second is wrong. Pine's `ta.stdev(src, length)` accepts a `biased` parameter that **defaults to `true`** — divisor = N, same as TA-Lib. The docstring's "Pine uses sample" premise is the source of the bug.

### Pine reference

Pine Script v5 documentation for `ta.stdev(source, length, biased)`:

> *"If the biased argument is set to true, the function will compute using a biased estimate of the entire population. If set to false, it will use an unbiased estimate of a sample. By default, biased is true."*

Pine `ta.bb(close, length, mult)` is implemented as:

```
basis = ta.sma(close, length)
dev   = mult * ta.stdev(close, length)   // biased=true default
[basis + dev, basis, basis - dev]
```

i.e. biased stddev, no correction factor. Same convention as raw TA-Lib `BBANDS`. The corrective scaling in `bb.py:67-72` has no Pine-side counterpart.

Source: TradingView Pine v5 reference (https://www.tradingview.com/pine-script-reference/v5/). Cross-checked against the parallel implementation at `backend/app/strategy_engine/indicators/calculations/bollinger_bands.py` whose docstring correctly states *"population (n denominator) to match Pine's `ta.stdev`"* — i.e. the strategy_engine codebase already documents the correct Pine convention; only `app.services.indicators.bb` got it wrong.

### Divergence numbers

Source: 100-bar synthetic NIFTY series, length=20, mult=2.0, post-warmup (81 bars compared).

| Metric | Upper band | Lower band | Middle band |
|---|---:|---:|---:|
| Max abs %diff | 0.0098% | 0.0099% | 0.00e+00 (sanity) |
| Mean abs %diff | 0.0052% | 0.0052% | 0.00e+00 |
| Bars with %diff > 0.1% | 0 | 0 | 0 |
| Bars with %diff > 1% | 0 | 0 | 0 |
| Persistence | transient | transient | n/a |

Per-bar % diffs look small (~0.005-0.01%) because the **synthetic series has low volatility** (calibrated to NIFTY 5m, ~0.09% per-bar log-vol). The right metric is **band-width inflation**:

| Metric | TRADETRI | Pine | Delta |
|---|---:|---:|---:|
| Mean band-width % of middle | **0.4084%** | **0.3981%** | **+2.60%** |

**+2.60% matches exactly the predicted `sqrt(20/19) - 1 ≈ 0.0260`.** This is the smoking gun — the deviation is a clean, persistent, multiplicative scaling artifact of the wrong-direction correction, NOT a numerical drift or floating-point issue. On a higher-vol instrument (e.g. crypto or single-stock options), the absolute % diffs scale linearly with stddev and the same +2.60% band-width inflation holds — independent of vol regime.

### Threshold-flip impact

On the 100-bar synthetic series, counting "any-touch" events:

| Signal | TRADETRI | Pine | Disagreements |
|---|---:|---:|---:|
| low ≤ lower_band ("price touches lower band") | 13 | 14 | **+1** (Pine more) |
| high ≥ upper_band ("price touches upper band") | 17 | 19 | **+2** (Pine more) |
| close > middle_band (crossover, sanity) | 49 | 49 | 0 (passes) |

**Total signal disagreements: 3 on 100 bars = 3%.** Pine sees MORE band touches because its bands are tighter (no inflation). A customer whose strategy is "BUY when price touches lower band" will see 14 entry signals on TradingView and only 13 on TRADETRI for the same instrument over the same period. The 1-signal gap might be the difference between a winning and losing backtest run.

On longer / higher-vol series the disagreement count scales roughly with `length / total_bars × bw_inflation_pct` — for a 5000-bar backtest at 2.6% inflation, expect ~50-150 signal disagreements.

### Verdict

**BUG.**

Not "convention" because Pine and TRADETRI are not implementing two valid alternatives of the same concept — TRADETRI implements a math operation (scale bands by sqrt(N/(N-1))) that has no counterpart in either Pine's reference or TA-Lib's reference. It's a no-op compensation for a misdescribed problem.

Not "ambiguous" because the band-width inflation is exact, persistent, and reproducible. There is no defensible interpretation under which `sqrt(N/(N-1))` scaling matches Pine's biased-stddev default.

---

## Recommendation

**STOP and fix BB before May 18 launch.** Specifically:

1. **Authorize an existing-file edit** to `backend/app/services/indicators/bb.py:67-72` — remove the post-processing correction. This is a 6-line deletion. Net code change:

   ```diff
   -    correction = math.sqrt(params.length / (params.length - 1))
   -    upper = middle + (upper - middle) * correction
   -    lower = middle - (middle - lower) * correction
        return {"upper": upper, "middle": middle, "lower": lower}
   ```

   Plus delete the now-stale module docstring section (`bb.py:1-26`) about the "correction".

2. **Regenerate `bb_expected.csv`** from the corrected output. The existing fixture was generated from TRADETRI's wrong output, so the existing `test_tradingview_result_match` test would fail post-fix until the fixture is refreshed. Regeneration is a one-line `pytest --regenerate-fixtures` or equivalent ops command, depending on how Day-6 sprint structured fixture refresh.

3. **Add an independent ground-truth test** (separate from the fixture-match test) to prevent recurrence — same idea as the Phase F Component 1 Option C plan from `PHASE_F_COMPONENT_1_AUDIT.md`. Pine-formula hand-computation OR `pandas-ta` as ground truth.

4. **Update `ema.py:1-15` docstring** in the same authorized-edit window (since we're already touching files in the indicators package): remove the false claim about Pine seeding from `close[0]`. The code itself is correct; only the prose is wrong. No code change needed for EMA.

**Why fix-before-launch and not defer:**

- 2 LIVE paper-mode customers are currently rendering BB on the chart. Any customer who validates their strategy by comparing TRADETRI's BB to TradingView's BB will see numerically different bands and reasonably conclude TRADETRI is computing the indicator wrong. This is a credibility-level issue, not just a numbers issue.
- A 6-line fix on launch-day-eve is a contained change. Test suite needs one fixture refresh. No schema changes, no migrations, no router changes, no API contract changes.
- The fix has **zero risk of breaking strategy_engine consumers** because `app.services.indicators.bb` is only consumed by the chart HTTP route (`/api/chart/indicator`) — confirmed in `PHASE_F_COMPONENT_1_AUDIT.md` §4 consumer set. The 17 strategy_engine pack tests use `app.strategy_engine.indicators` (a separate parallel system that already gets Pine's stddev convention right).

**Defer alternative (if launch-day risk aversion outweighs correctness):**

Ship as-is and add a footnote to customer-facing docs: *"TRADETRI's Bollinger Bands are calibrated for sample-stddev (÷N-1) convention; TradingView's defaults to population-stddev (÷N). Bands will appear ~2.6% wider on TRADETRI at length=20. To compare like-for-like, set Pine's `biased` argument to `false` (or use `ta.stdev(close, 20, false)` directly)."* Then fix in a post-launch Phase G sprint.

Jayesh decides which path. Both are acceptable; my recommendation is **fix-before-launch** for the credibility argument above.

---

## Hard constraints respected

| Guardrail | Status |
|---|---|
| Zero edits to files in `backend/app/services/indicators/` | ✓ Audit + script only |
| Zero edits to `indicator_service.py`, admin route, pyproject.toml, existing tests | ✓ |
| New files only | ✓ Two new files; one new generated CSV |
| Did not auto-fix bug | ✓ Bug surfaced in this doc; fix authorization request escalated to Jayesh |
| No push | ✓ Local commit only |
| Bug escalated to BLOCKERS.md if "found during analysis" | The BB bug IS the analysis's deliverable, not a side-finding; documented here in the verdict slot rather than duplicating into BLOCKERS.md. No NEW unexpected findings emerged from the script run that would warrant a BLOCKERS write. |

## Reproducing this analysis

Deterministic and stateless:

```bash
git checkout feat/phase-f-indicator-audit
python3 backend/tests/services/indicators/fixtures/_deviation_analysis.py
```

Output is bit-identical across runs (np.random.default_rng seeded). Per-bar CSV at `backend/tests/services/indicators/fixtures/_deviation_analysis_output.csv`.

Optional cross-check against deployed TA-Lib (requires a venv with project deps + ta-lib): see the 3-line snippet in the script's module docstring. Float-epsilon match expected because both sides are calling `talib.BBANDS` then applying the same `sqrt(N/(N-1))` post-processing.
