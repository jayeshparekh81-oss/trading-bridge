# Phase F — Deviation Analysis PART 2

**Date:** 2026-05-17 (1 day before May-18 launch)
**Branch:** `feat/phase-f-indicator-audit`
**Analyst:** Claude Code (Opus 4.7, 1M ctx), reviewed by Jayesh
**Scope:** Extension of the deviation sub-audit to cover the remaining MVP indicators — RSI(14), SMA(20), MACD(12,26,9) — against Pine Script conventions, using the same deterministic synthetic 100-bar NIFTY dataset as Part 1.
**Evidence:** `backend/tests/services/indicators/fixtures/_deviation_analysis.py` (extended in place; runs both parts in one invocation) + new `backend/tests/services/indicators/fixtures/_deviation_analysis_part2_output.csv` (100 rows × 19 cols).
**Part 1 reference:** `PHASE_F_DEVIATION_ANALYSIS.md` (committed at `680479b`).

---

## Executive summary

- **RSI(14) verdict: CONVENTION (non-deviation)** — Wilder smoothing is identical in TA-Lib and Pine `ta.rsi`; max %diff on the synthetic series is literal 0.00e+00 over 86 post-warmup bars; oversold/overbought counts match exactly (4/4 <30, 2/2 >70).
- **SMA(20) verdict: AMBIGUOUS** — clean inputs produce identity (max %diff = 3.3e-14, float-epsilon); on NaN-poisoned inputs, TA-Lib's sliding-sum design propagates NaN forever (50 bars vs Pine which recovers as the NaN clears the trailing window). Documented in `test_sma.py:127-141`; customer impact only matters if upstream candle data can legitimately have NaN closes.
- **MACD(12,26,9) verdict: CONVENTION (non-deviation)** — all three components (macd line, signal line, histogram) max %diff = 0.00e+00; signal-line crossover counts match exactly (5/5). MACD inherits SMA-seeded EMA, which Part 1 already verified matches Pine.
- **Pre-launch recommendation:** No new fixes required from Part 2. The BB fix recommended in Part 1 still stands; nothing in Part 2 changes the calculus. SMA's NaN-poisoning warrants a one-line customer-docs footnote if (and only if) upstream data sources can produce NaN closes.

---

## Why hand-rolled Pine references and not pandas-ta

Same rationale as Part 1: hand-rolled implementations of Pine's textbook RSI / SMA / MACD math are auditable by inspection (each function is ~10 lines), deterministic, and free of install / wheel-availability risk on Python 3.14. The user's original spec authorized hand-implementation as an explicit fallback. RSI Wilder smoothing, plain rolling SMA, and 3-EMA MACD have unambiguous public-domain formulas — no library wrapper is required to establish ground truth.

A reader who wants pandas-ta cross-validation can run the embedded snippet in `_deviation_analysis.py`'s module docstring in any venv that has pandas-ta installed; the script's Pine reference functions are byte-exact transcriptions of Pine's documented recurrences.

---

## Deviation 3: RSI(14)

### What

`backend/app/services/indicators/rsi.py:1-7` correctly identifies that TA-Lib's RSI uses Wilder's smoothing (`alpha = 1/length`, NOT the EMA alpha `2/(length+1)`) and that this matches Pine `ta.rsi`'s default. The module ships zero modifications to TA-Lib's output. **No deviation is claimed in the source; there is also no deviation in fact.**

### Where (file:line)

`backend/app/services/indicators/rsi.py:25-34` — the `RsiIndicator.compute()` method. One TA-Lib call, no post-processing.

### Why (from code or audit)

The module docstring's justification: *"TA-Lib's RSI uses Wilder's smoothing internally (alpha = 1/length, not the EMA alpha 2/(length+1)). This is precisely what TradingView's default `ta.rsi(close, length)` Pine Script implementation produces, so no divergence flag is required for RSI."*

This claim is correct.

### Pine reference

Pine Script v5 `ta.rsi(source, length)` definition:

```
deltas[i] = source[i] - source[i-1]
gain[i]   = max(deltas[i], 0)
loss[i]   = max(-deltas[i], 0)

avg_gain[length] = mean(gain[0..length-1])     # Wilder seed (SMA)
avg_loss[length] = mean(loss[0..length-1])

avg_gain[i] = (avg_gain[i-1] * (length-1) + gain[i-1]) / length
avg_loss[i] = (avg_loss[i-1] * (length-1) + loss[i-1]) / length

rsi[i] = 100 - 100 / (1 + avg_gain[i] / avg_loss[i])
```

Source: TradingView Pine v5 reference (https://www.tradingview.com/pine-script-reference/v5/#fun_ta.rsi). TA-Lib's `talib.RSI` implements this recurrence bit-for-bit (`talib/ta_func/ta_RSI.c` in upstream).

### Divergence numbers

Source: 100-bar synthetic NIFTY series, length=14, post-warmup (86 bars compared).

| Metric | Value |
|---|---|
| Max abs %diff | **0.00e+00** (literal float identity) |
| Mean abs %diff | 0.00e+00 |
| Bars with %diff > 0.1% | 0 |
| Bars with %diff > 1% | 0 |
| Bars with %diff > 5% | 0 |
| Persistence | n/a (no divergence to characterize) |

### Threshold-flip impact

Counts of bars where the indicator triggered the canonical RSI signal boundaries:

| Signal | TRADETRI | Pine | Disagreements |
|---|---:|---:|---:|
| RSI < 30 (oversold) | 4 | 4 | **0** |
| RSI > 70 (overbought) | 2 | 2 | **0** |

Zero disagreements — same threshold flips on the same bars.

### Verdict

**CONVENTION** — specifically, a non-deviation. Math and threshold behaviour are bit-identical. No code change, no docstring change, no customer impact.

---

## Deviation 4: SMA(20)

### What

`backend/app/services/indicators/sma.py:13-19` describes SMA as a trivial `mean(close[t-length+1 : t+1])` that "trivially matches TradingView's `ta.sma` — no smoothing-convention divergence to flag." This claim holds **for clean inputs**.

For **NaN-poisoned inputs**, the two implementations diverge in a documented and intentional way. TA-Lib's `SMA` implementation maintains a rolling sum accumulator (`sum += close[t]; sum -= close[t-length]`). Once a NaN enters the accumulator, subsequent additions and subtractions all involve NaN, and the accumulator stays NaN forever — even after the offending NaN has rolled off the trailing window. Pine's `ta.sma` evaluates each window independently per bar, so once the NaN drops out of the trailing window the SMA recovers.

This behavioural gap is already documented in `backend/tests/services/indicators/test_sma.py:127-141`:

> *"TA-Lib's SMA implementation maintains a rolling sum. Once NaN enters the accumulator, it persists indefinitely. So the output remains NaN for every position from the NaN-input bar through the end of the input series, not just for `length` positions. Pine Script's `ta.sma` recovers after the smoothing window clears. The Day-6 brief specified Pine-style recovery; we ship TA-Lib's behaviour per the locked architecture."*

### Where (file:line)

`backend/app/services/indicators/sma.py:24-36` — the `SmaIndicator.compute()` method, one `talib.SMA` call, no post-processing. The behaviour comes from TA-Lib's internal sliding-sum design.

The deviation is also acknowledged at `backend/tests/services/indicators/test_sma.py:127-161` (test asserts the propagation, with a docstring explaining the gap vs Pine).

### Why (from code or audit)

Code-comment justification: locked architecture defaults to TA-Lib's behaviour; the Day-6 brief asked for Pine-style recovery but the operator shipped TA-Lib's anyway and flagged the deviation.

### Pine reference

```
sma[i] = mean(source[i-length+1..i])
       = NaN if any value in the trailing window is NaN
       = arithmetic mean of the window otherwise
```

Once the NaN exits the trailing window (i.e. for all bars `i > nan_index + length - 1`), the SMA returns to valid output.

### Divergence numbers

#### On clean inputs (no NaN injection)

| Metric | Value |
|---|---|
| Max abs %diff | **3.30e-14** (float-epsilon — implementations agree to machine precision) |
| Mean abs %diff | ~1e-15 |
| Bars with %diff > 0.1% | 0 |
| Crossovers (close vs SMA) — TRADETRI vs Pine | 13 vs 13 → **0 disagreements** |

#### On NaN-poisoned input (NaN injected at close[30])

Source: same 100-bar synthetic series, with `close[30]` overwritten to NaN. Post-warmup region is bars `[19, 99]` = 81 bars.

| Metric | Value |
|---|---|
| Bars where TRADETRI=NaN and Pine=valid | **50** (bars 50–99: NaN has cleared Pine's trailing window but TA-Lib's accumulator stays poisoned) |
| Bars where TRADETRI=valid and Pine=NaN | 0 (sanity: TA-Lib is a strict superset of Pine's NaN outputs) |
| Bars where both are NaN | 19 (warmup) + 20 (positions 30–49, where the trailing window legitimately includes the NaN) = 39 |
| Bars where both are valid and equal | 31 (positions 19–29, pre-NaN region) |

50 bars of post-NaN divergence is significant — TRADETRI emits NaN for every single bar from position 30 to 99 (70 consecutive NaN bars) while Pine emits NaN only for positions 30–49 (the 20 bars where NaN is in the trailing window) and recovers from position 50 onwards.

### Threshold-flip impact

#### Clean inputs

| Signal | TRADETRI | Pine | Disagreements |
|---|---:|---:|---:|
| close vs SMA(20) crossover | 13 | 13 | **0** |

#### NaN-poisoned inputs

| Signal | TRADETRI | Pine | Disagreements |
|---|---:|---:|---:|
| close vs SMA(20) signal-eligible bars (where SMA is finite) | 31 | 81 | **50 bars** with no TRADETRI signal but a valid Pine signal |

On poisoned data, a customer's strategy on TRADETRI would be **fully silent for 50/100 bars** (50% of the post-warmup window) while the same strategy on TradingView would continue firing signals.

### Verdict

**AMBIGUOUS.**

- On the **clean inputs** that 99%+ of customer use cases produce, TRADETRI is bit-identical to Pine. No customer-visible problem.
- On the rare **NaN-poisoned inputs** (which would come from gaps in upstream tick data, missing-bar interpolation failures, or broker outages), TRADETRI silently goes dark for the rest of the series. The deviation is from a defensible-but-unusual choice (TA-Lib's sliding-sum design); the Day-6 brief preferred Pine recovery but operator shipped TA-Lib anyway.

Pre-existing test (`test_sma_nan_in_input_poisons_subsequent_output`) demonstrates the team is aware of this and consciously shipping it.

Customer impact depends on whether the chart-history feed and backtest engine can ever produce NaN closes:
- Live tick data: NaN unlikely (broker would simply not emit a bar; gap-fill logic upstream may or may not insert NaN).
- Backtest data: NaN possible if a strategy mid-run encounters a missing bar (depending on the candle-source's contract).

This is a "Jayesh decides" item — the data provided here is the basis for that decision.

---

## Deviation 5: MACD(12,26,9)

### What

`backend/app/services/indicators/macd.py` is a one-shot wrapper around `talib.MACD`, which computes three SMA-seeded EMAs internally:

```
ema_fast    = EMA(close, fast=12)
ema_slow    = EMA(close, slow=26)
macd_line   = ema_fast - ema_slow
signal_line = EMA(macd_line, signal=9)         # seeded with SMA of first `signal` valid macd_line values
histogram   = macd_line - signal_line
```

The module docstring flags an EMA-seeding nuance inherited from `ema.py:2-15`, but Part 1 of this sub-audit established that **the documented EMA seeding deviation does not actually exist** (Pine `ta.ema` and TA-Lib `EMA` both seed with `SMA(close[0..N-1])` at index `N-1`). So MACD, which is just three EMAs combined, also has **no actual deviation from Pine `ta.macd`**.

### Where (file:line)

`backend/app/services/indicators/macd.py:28-50` — the `MacdIndicator.compute()` method, one `talib.MACD` call, returns three components.

### Why (from code or audit)

Module docstring claims MACD "produces the same field set modulo the same EMA-seeding nuance flagged in `app.services.indicators.ema` — practical chart values are within float-32 epsilon after the first few bars." Per Part 1 finding, the "EMA-seeding nuance" itself is a non-existent deviation; therefore so is MACD's.

### Pine reference

Pine Script v5 `ta.macd(source, fast, slow, signal)`:

```
[macd, signal, histogram] = ta.macd(close, fast=12, slow=26, signal=9)

where:
  fast_ma = ta.ema(close, fast)
  slow_ma = ta.ema(close, slow)
  macd    = fast_ma - slow_ma
  signal  = ta.ema(macd, signal)
  hist    = macd - signal
```

All three EMAs use SMA seeding at index `length - 1`. Identical to TA-Lib's `MACD`.

### Divergence numbers

Source: 100-bar synthetic NIFTY series, fast=12, slow=26, signal=9. Post-warmup region for the signal line begins at index `slow + signal - 2 = 33`.

| Component | Max abs %diff | Mean abs %diff | n>0.1% |
|---|---|---|---:|
| MACD line | **0.00e+00** | 0.00e+00 | 0 |
| Signal line | **0.00e+00** | 0.00e+00 | 0 |
| Histogram | **0.00e+00** | 0.00e+00 | 0 |

Float identity across all three components.

### Threshold-flip impact

| Signal | TRADETRI | Pine | Disagreements |
|---|---:|---:|---:|
| MACD line crosses signal line | 5 | 5 | **0** |

Same signal counts on the same bars.

### Verdict

**CONVENTION** — non-deviation. The "inherited EMA-seeding nuance" claimed in the docstring traces back to a non-existent deviation in EMA. No code change needed; the inheritance chain of incorrect docstrings (ema.py → macd.py) is cleaned up in the same docstring-fix sprint flagged in Part 1.

---

## Recommendation

**No new fixes required from Part 2.** The pre-launch action items remain exactly what Part 1 established:

1. **FIX `bb.py`** (Part 1 BB BUG): 6-line removal of `bb.py:67-72` correction + regenerate `bb_expected.csv`. Authorize the existing-file edit as a one-time doctrine override.
2. **Docstring cleanup** (Part 1 EMA + Part 2 MACD): factually wrong claims about Pine seeding in `ema.py:1-15` and the inherited reference in `macd.py:1-15`. Cosmetic; safe for post-launch.
3. **OPTIONAL — SMA NaN-poisoning footnote** (Part 2 SMA AMBIGUOUS): one paragraph in customer-facing chart docs, only if upstream data sources are known to occasionally produce NaN closes. If the candle-source contract guarantees no-NaN, skip the footnote.

RSI and MACD require **zero action**.

### Net pre-launch checklist

| Item | Action | Risk if skipped |
|---|---|---|
| BB fix | Authorize edit + regen fixture | Customer-credibility hit: TRADETRI BB visibly different from TradingView BB |
| EMA + MACD docstring cleanup | Post-launch sprint | None to customers; readers will be confused but not misled |
| SMA NaN-poisoning footnote | Decide based on data-source guarantees | Silent strategy failure if data has NaN; zero impact otherwise |

---

## Reproducing this analysis

```bash
git checkout feat/phase-f-indicator-audit
python3 backend/tests/services/indicators/fixtures/_deviation_analysis.py
```

Output is deterministic across runs. Two CSV evidence files now exist (one per part):

- `backend/tests/services/indicators/fixtures/_deviation_analysis_output.csv` — Part 1 (EMA + BB per-bar values)
- `backend/tests/services/indicators/fixtures/_deviation_analysis_part2_output.csv` — Part 2 (RSI + SMA clean + SMA dirty + MACD per-bar values)

## Hard constraints respected

| Guardrail | Status |
|---|---|
| Zero edits to files in `backend/app/services/indicators/` | ✓ All edits to my own prior-turn script (new file) + new doc |
| Zero edits to `indicator_service.py`, admin route, `pyproject.toml`, existing test files | ✓ |
| New files only | ✓ New Part 2 doc + new Part 2 CSV; the analysis script (created by me last turn) was extended in place |
| Did not auto-fix bug | ✓ Bugs surfaced in Part 1 + Part 2 docs; no code-fix attempted |
| No push | ✓ Local commit only |
