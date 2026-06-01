# Queue ZZ Sprint 7c — Backtest execution audit

**Branch:** `verify/sprint-7c-backtest-execution` (off 7b)
**Date:** 2026-06-01
**Time used:** ~40 min (cap 2.5 hr)
**Verdict:** **PASS.** 20/27 active templates (74%) translate + backtest end-to-end against the 720-bar synthetic series. 7 actives blocked by translator NL-parse gaps. 0 EXECUTION_ERROR, 0 ZERO_TRADES.

---

## Headline

### Active (27)

| Bucket | Count | % |
|---|---:|---:|
| **FIRES_CLEAN** | **15** | 55.6% |
| FIRES_WITH_WARNINGS (all benign Phase-9 note) | 5 | 18.5% |
| ZERO_TRADES | 0 | 0% |
| EXECUTION_ERROR | 0 | 0% |
| TRANSLATION_FAILED (NL-parse gap) | 7 | 25.9% |

→ **0 EXECUTION_ERROR. 0 ZERO_TRADES. 20/27 fully exercised.**

### Inactive spot-check (first 10 with populated config)

| Bucket | Count |
|---|---:|
| TRANSLATION_FAILED | 10/10 |

9 fail on `UnknownIndicatorError` (translator registry doesn't yet know `pdh`, `banknifty_pdh`, `parabolic_sar_*`, `heikin_ashi`, `keltner_channel_*`, `stochastic_slow_*`, `pivot_points_standard`, `pre_market_gap_pct`); 1 on `UnparseableConditionError` (vwap-bounce, NL prior-bar reference). Pattern confirmed in 10 → did not extend spot-check to remaining 8 populated inactives.

### Hard-stop status

| # | Threshold | Current | Status |
|---|---|---|---|
| 4 | >50% failures in sub-sprint | Active 25.9% / combined 45.9% | **Under** — chain continues |
| 9 | Backtest API unreachable | All invocations succeeded | **Pass** |

---

## 1. Method

For each of the 27 active templates + first 10 populated inactives:

1. **Translate** OLD-format `config_json` → `StrategyJSON` via `app.strategy_engine.translator.parser.translate_template(template_dict)` — the same translator the user-clone flow uses (`backend/app/templates/clone_service.py:185`).
2. **Backtest** the translated `StrategyJSON` against `_synthetic_candles(720)` — the deterministic 720-bar series used by the HTTP backtest endpoint when no real candles are supplied (`backend/app/strategy_engine/api/backtest.py:_synthetic_candles`).
3. **Capture** `total_trades`, `total_pnl`, `win_rate`, `warning_count`, `runtime_ms`, and an error tail.

**No template modifications. No seed JSON writes. No DB. No HTTP. Pure-Python pipeline through the existing engine.**

Confirmed: the prompt's "RC1 synthetic data (720 bars)" is exactly `_synthetic_candles(720)` — a 1-min intraday session (09:15 IST anchor) with 6 engineered regimes packed in the first 330 bars (≤14:45 IST) so every template family fires inside its intraday gate. Documented in `backend/app/strategy_engine/api/backtest.py:620-760` and the (no-longer-checked-in) `QUEUE_RR_ZERO_TRADES_DIAGNOSIS.md` / `QUEUE_SS_SYNTHETIC_DATA.md` references.

Framework: `backend/tests/queue_zz_sprint_7/framework_extensions/backtest_execution.py`
Output: `backend/tests/queue_zz_sprint_7/backtest_execution.csv` (37 rows × 11 cols).

---

## 2. Active FIRES_CLEAN — 15 templates

| Slug | Trades | PnL | Win rate | Runtime |
|---|---:|---:|---:|---:|
| `ema-crossover-9-21` | 4 | +527.81 | 0.500 | 8.5ms |
| `ema-crossover-20-50` | 3 | −1020.87 | 0.000 | 8.0ms |
| `rsi-oversold-bounce` | 117 | −144.59 | 0.641 | 9.4ms |
| `triple-ema-crossover` | 1 | +323.84 | 1.000 | 8.7ms |
| `williams-pct-r-reversal` | 20 | +790.47 | 0.550 | 8.8ms |
| `cci-momentum` | 13 | +891.98 | 0.615 | 9.0ms |
| `aroon-crossover` | 6 | +867.70 | 0.667 | 10.4ms |
| `engulfing-candle-reversal` | 1 | −37.01 | 0.000 | 8.3ms |
| `doji-reversal` | 2 | +357.35 | 0.500 | 9.6ms |
| `obv-divergence` | 4 | +238.79 | 0.500 | 10.5ms |
| `cmf-confirmation` | 2 | −297.07 | 0.000 | 9.1ms |
| `mfi-overbought-oversold` | 38 | +1008.91 | 0.737 | 9.0ms |
| `rsi-divergence` | 3 | +607.83 | 0.667 | 9.7ms |
| `macd-divergence` | 2 | +1315.72 | 1.000 | 10.2ms |
| `hull-ma-trend` | 7 | +494.49 | 0.429 | 10.4ms |

PnL on synthetic data isn't a real performance signal (the series is engineered to trigger fires, not to model market microstructure). What this tells us: **every one of these 15 templates produces measurable trade flow with zero warnings under the canonical synthetic harness.** That's the gate 7c is meant to assess.

---

## 3. Active FIRES_WITH_WARNINGS — 5 templates (all benign)

| Slug | Trades | PnL | Warning |
|---|---:|---:|---|
| `macd-trend-signal` | 5 | +169.48 | macd multi-output Phase-9 note |
| `supertrend-rider` | 4 | +141.16 | supertrend multi-output Phase-9 note |
| `orb-15min` | 1 | −65.78 | opening_range_breakout multi-output Phase-9 note |
| `rsi-macd-confluence` | 4 | +566.04 | macd multi-output Phase-9 note |
| `bb-rsi-oversold` | 3 | −123.71 | bollinger_bands multi-output Phase-9 note |

**Single warning class across all 5:**
> "Indicator 'X' (type='Y') is multi-output; only the primary line is referenced by name. Phase 9 will add dotted-notation access (e.g. {cfg.id}.signal)."

This is a **known, documented Phase-9 deferral** — the indicator emits multiple series (e.g. MACD line + signal + histogram) but the strategy references only the primary line by base name. Backtest still proceeds and produces trades; the warning is informational, not corrective. These 5 are operationally equivalent to FIRES_CLEAN for production purposes.

---

## 4. Active TRANSLATION_FAILED — 7 templates (NL parse gap)

| Slug | Failure mode | Construct that the prose parser doesn't yet handle |
|---|---|---|
| `bb-mean-reversion` | `UnparseableConditionError` | `low <= bb_lower AND previous close > bb_lower` — `previous close` cross-time reference |
| `bb-squeeze-breakout` | `UnparseableConditionError` | `bb_width at 20-bar low AND close > bb_upper AND atr_14 increasing` — `at N-bar low/high` rolling-extremum + derivative `atr_14 increasing` |
| `macd-histogram-momentum` | `UnparseableConditionError` | `macd_histogram[0] > macd_histogram[1] > macd_histogram[2]` — bar-offset chain `[k]` |
| `donchian-channel-breakout` | `UnparseableConditionError` | `close > 20-bar donchian upper band (new 20-bar high)` — parameterized component reference w/ NL gloss |
| `ichimoku-cloud-crossover` | `UnparseableConditionError` | `chikou above price-26-bars-ago AND tenkan > kijun` — cross-time + multi-component composite |
| `adx-strong-trend-filter` | `UnparseableConditionError` | `adx_14 > 25 AND ema_9 crosses above ema_21 AND ema_9 sloping up` — `sloping up` slope derivative |
| `inside-bar-breakout` | `UnparseableConditionError` | `previous bar fully inside the bar before it (inside-bar pattern)` — multi-bar pattern recognition |

**These are translator-parser gaps, not template defects.** The templates carry valid OLD-format `config_json` (7a v2 confirmed PARSE_OK for all 7) and reference verified A/B indicators (7b confirmed INDIRECT_DEPENDENCY clean). What's missing is the prose-parser's coverage of:

1. **Cross-time references** (`previous close`, `price-26-bars-ago`)
2. **Bar-offset indexing** (`x[0] > x[1] > x[2]`)
3. **Rolling-extremum predicates** (`at 20-bar low`)
4. **Indicator-derivative predicates** (`atr_14 increasing`, `ema_9 sloping up`)
5. **Multi-component composite references** (`chikou`, `tenkan`, `kijun`, `bb_lower`, `bb_upper`, `bb_width`)
6. **Multi-bar pattern phrases** (`inside-bar pattern`)

All six categories are plausible Phase-2 / Phase-9 translator expansions; none implicate the underlying indicators (which are all verified) or the backtest engine itself (which executes successfully when given a well-formed StrategyJSON).

---

## 5. Inactive spot-check — 10/10 TRANSLATION_FAILED

| Slug | Failure | Detail |
|---|---|---|
| `pdh-pdl-breakout` | UnknownIndicatorError | `pdh` |
| `vwap-bounce` | UnparseableConditionError | `prior bars > vwap AND current low touches vwap` (cross-time + multi-condition) |
| `banknifty-weekly-equity` | UnknownIndicatorError | `banknifty_pdh` |
| `premarket-gap` | UnknownIndicatorError | `pre_market_gap_pct` |
| `heikin-ashi-trend` | UnknownIndicatorError | `heikin_ashi` |
| `keltner-channel-bounce` | UnknownIndicatorError | `keltner_channel_20_2_atr14` |
| `parabolic-sar-reversal` | UnknownIndicatorError | `parabolic_sar_0.02_0.2` |
| `stochastic-oscillator` | UnknownIndicatorError | `stochastic_slow_14_3_3` |
| `psar-ema-combo` | UnknownIndicatorError | `parabolic_sar_0.02_0.2` |
| `pivot-point-bounce` | UnknownIndicatorError | `pivot_points_standard` |

→ Same pattern as 7b's HAS_UNKNOWN bucket. **9 of 10 are blocked by translator's indicator-registry not knowing about composite-parameterized indicator IDs** (the translator expects to find `parabolic_sar_0.02_0.2` as a known indicator type; the actual registry has only the base `parabolic_sar` or no entry at all).

Per the founder's spot-check guidance ("skip rest if pattern clear"), did not invoke the remaining 8 populated inactives — the failure cause is uniform: missing indicator-registry coverage for the composite-named OLD-format references and a few NL conditions the prose-parser doesn't support.

---

## 6. Cross-validation against Sprint 7b

| 7b bucket | Active count | 7c outcome |
|---|---:|---|
| ALL_VERIFIED (macd-trend-signal, macd-histogram-momentum, macd-divergence) | 3 | 1 FIRES_WITH_WARNINGS (multi-output Phase-9 note) + 1 FIRES_CLEAN + 1 TRANSLATION_FAILED (macd-histogram-momentum: `[k]` bar-offset chain) |
| INDIRECT_DEPENDENCY | 22 | 13 FIRES_CLEAN + 3 FIRES_WITH_WARNINGS + 6 TRANSLATION_FAILED |
| PARTIAL_VERIFIED (rsi-macd-confluence, obv-divergence) | 2 | 1 FIRES_WITH_WARNINGS + 1 FIRES_CLEAN |

7b's dependency-clean verdict ✓ aligns with 7c's executability. The 7 TRANSLATION_FAILED actives all reside in 7b-verified buckets; the failure cause is parser coverage, not indicator dependency.

---

## 7. Performance / runtime characteristics

| Metric | Value |
|---|---|
| Max per-template runtime (active) | 12.7 ms |
| Median per-template runtime (active) | ~9 ms |
| Total wall time, 37 invocations | <0.5 s |
| Memory pressure | negligible — deterministic single-pass indicator precompute |

→ Production-grade backtest performance, even when batched. 7d (performance sanity) can safely run on the 20 FIRES_* templates without runtime concerns.

---

## 8. Hard-stops re-evaluated

| # | Hard-stop | Status |
|---|---|---|
| 1 | Sub-sprint time cap | ~40 min vs 2.5-hr cap — well under |
| 2 | Total elapsed >10 hr | Cumulative 7a (45m) + 7b (35m) + 7c (40m) ≈ 2 hr |
| 3 | Sacred-zone path write | All writes inside `backend/tests/queue_zz_sprint_7/` + `docs/QUEUE_ZZ_*` |
| 4 | >50% template failures | Active 25.9% — well under |
| 5 | Seed JSON modification attempted | Zero |
| 6 | Template math/logic edit | Zero — observation only |
| 7 | Wanted to merge to main | Branch-only |
| 8 | Strategic decision required | None |
| 9 | Backtest API unreachable | All invocations succeeded (translate may fail, but the engine is reachable + functional) |

---

## 9. Deliverables

- `backend/tests/queue_zz_sprint_7/framework_extensions/backtest_execution.py` (new)
- `backend/tests/queue_zz_sprint_7/backtest_execution.csv` (37 rows × 11 cols)
- `docs/QUEUE_ZZ_SPRINT_7C_REPORT.md` (this file)

No modifications to seed JSON, schemas, sacred zone, or any production path. Pure-Python in-process invocation of pre-existing read-only engine modules.

---

## 10. Handoff to 7d

Inputs ready for 7d (performance sanity check):

- **20 active templates** produced trade flow (15 FIRES_CLEAN + 5 FIRES_WITH_WARNINGS).
- For each: `total_trades`, `total_pnl`, `win_rate`, `warning_count` already captured in `backtest_execution.csv`.
- 7d should additionally surface: profit_factor, max_drawdown, expectancy (available from `BacktestResult` but not exported in this CSV — 7d framework can re-run and capture).
- Sanity flags to apply per founder direction: win_rate ∈ [0, 100], profit_factor finite, max_drawdown reasonable, watch for 100% win rate on >5 trades and infinite profit_factor.
- 7d should NOT re-attempt the 7 active TRANSLATION_FAILED templates (no metrics to sanity-check there).

Sprint 7c is **complete**. Continuing chain to 7d.
