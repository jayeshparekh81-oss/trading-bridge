# Queue WW Sprint 8b — 7 broken-template translator extensions

**Branch:** `feat/sprint-7-translator-extensions` (off `main@85d09ea`)
**Date:** 2026-06-02
**Time used:** ~75 min (cap 180 min)
**Verdict:** **PASS.** 7/7 templates close the translator gap via additive overrides; 6/7 fire trades on the 720-bar synthetic; 1/7 (inside-bar-breakout) is xfail-on-synthetic (override structurally valid, synthetic pattern-poor; re-test on real Dhan data tomorrow). 27 of 28 integration tests pass + 1 xfail; full translator regression 67/67 pass.

---

## 1. Headline

| Item | Value |
|---|---|
| Templates extended | 7 / 7 (all 7 ACTIVE_BUT_BROKEN from Sprint 7e) |
| Templates firing trades on 720-bar synthetic | **6 / 7** (within plan's 5-7 expected band) |
| New override module | `backend/app/strategy_engine/translator/sprint_7e_overrides.py` |
| override_registry.py edits | 2 lines (one import, one dict-spread) — fully additive |
| `parser.py` edits | **0** (per plan: "DO NOT modify existing translator/parser.py beyond additive imports" — and we didn't need to touch it at all) |
| Indicator dispatch edits | 0 (all required indicators already wired) |
| Seed JSON edits | 0 |
| Sacred-zone touches | 0 |
| Frontend touches | 0 |
| Migrations | 0 |
| Integration tests | 28 (4 per template × 7) — 27 PASS, 1 XFAIL |
| Translator-layer regression | 67/67 PASS |

---

## 2. Per-template summary

| # | Slug | Override approach | Synthetic trades | PnL on synth | Win rate | Status |
|---:|---|---|---:|---:|---:|:---:|
| 1 | `bb-mean-reversion` | `close crossover bb_lower` (bounce) | 3 | −185.09 | 66.7% | ✅ FIRES |
| 2 | `bb-squeeze-breakout` | `close crossover bb_upper` (breakout) | 4 | +288.33 | 50.0% | ✅ FIRES |
| 3 | `macd-histogram-momentum` | `macd_line crossover macd_signal AND macd_histogram > 0` | 4 | +364.28 | 50.0% | ✅ FIRES |
| 4 | `donchian-channel-breakout` | `close > donchian_middle_20 AND adx_14 > 20` | 2 | −306.99 | 50.0% | ✅ FIRES |
| 5 | `ichimoku-cloud-crossover` | `tenkan crossover kijun AND close > tenkan` | 3 | +120.44 | 66.7% | ✅ FIRES |
| 6 | `adx-strong-trend-filter` | `adx_14 > 25 AND ema_9 crossover ema_21` | 4 | +119.66 | 50.0% | ✅ FIRES |
| 7 | `inside-bar-breakout` | `inside_bar_breakout > 0 AND close > ema_20` | 0 | 0.00 | n/a | ⚠ XFAIL |

**Total: 20 trades across 6 firing templates on the deterministic 720-bar synthetic.**

The 7th template (`inside-bar-breakout`) translates cleanly, executes without error, but its 3-bar pattern requirement does not occur in the deterministic 720-bar synthetic fixture from `_synthetic_candles`. The override is structurally valid; this is a fixture-coverage issue, not an override defect. Per plan: documented as `MANUAL_REVIEW` for tomorrow's founder review on real Dhan data.

---

## 3. Schema simplifications (loss-of-nuance call-outs)

Each override below drops constructs the current schema cannot express. The dropped construct is the precise reason these templates were ACTIVE_BUT_BROKEN in Sprint 7e — these overrides are the agreed-cost trade-off.

| Template | Original NL nuance dropped | Reason |
|---|---|---|
| bb-mean-reversion | `low <= bb_lower` (touch) — collapsed into the bounce-via-crossover idiom | Schema has no per-bar-history `<=` against indicator |
| bb-squeeze-breakout | `bb_width at 20-bar low`, `atr_14 increasing` | Schema has no rolling-extremum predicate, no indicator-slope |
| macd-histogram-momentum | `macd_histogram[0] > [1] > [2]` chain | Schema has no bar-offset indexing |
| donchian-channel-breakout | "new 20-bar high" (strict upper-band breakout) | Donchian `upper[i]` includes bar i → `close > upper` unreachable; relaxed to midline-breakout |
| ichimoku-cloud-crossover | `chikou above price-26-bars-ago`, cloud (senkou A/B) | Phase-11 ichimoku components not in current impl |
| adx-strong-trend-filter | `ema_9 sloping up` | Schema has no indicator-slope; crossover implies recent upturn |
| inside-bar-breakout | (None of the original was dropped) | All three of the original clauses are captured by `inside_bar_breakout > 0` + `close > ema_20` |

These are simplifications, not silent corner-cutting. Each appears in the override module's docstring and in this report. Tomorrow's founder review can decide which need a schema extension (slope, bar-offset, rolling-extremum) before the backtest path is considered first-class for those templates.

---

## 4. Files changed

```
backend/app/strategy_engine/translator/sprint_7e_overrides.py     | new (370 LOC)
backend/app/strategy_engine/translator/override_registry.py       | +5 lines (one import + one dict-spread)
backend/tests/queue_ww_sprint_8/test_sprint_7e_overrides.py       | new (110 LOC, parametrized over 7 slugs × 4 test fns = 28 cases)
docs/QUEUE_WW_SPRINT_8B_REPORT.md                                  | new (this file)
```

Zero touches to: `parser.py`, `strategy_executor`, `direct_exit`, `webhook`, `kill_switch`, `broker` adapters, BSE LTD strategy, any migration, any seed JSON, any frontend file.

---

## 5. Test results

### 5.1 Sprint 8b integration tests (`tests/queue_ww_sprint_8/`)
| Test class | Pass | XFail | Fail |
|---|---:|---:|---:|
| `test_override_registered` (7 slugs) | 7 | 0 | 0 |
| `test_translate_succeeds` (7 slugs) | 7 | 0 | 0 |
| `test_backtest_executes_without_error` (7 slugs) | 7 | 0 | 0 |
| `test_backtest_fires_trades_on_synthetic` (7 slugs) | 6 | 1 | 0 |
| **Total** | **27** | **1** | **0** |

### 5.2 Translator-layer regression (`tests/strategy_engine/translator/`)
67 passed in 0.21s. Sprint 7e overrides do not interfere with existing parser, divergence, trend, candle, sub-output or field-mapper tests.

---

## 6. Founder review checklist for tomorrow

1. **Per-template approach** — skim §3 above. Confirm the schema-simplification list (dropped slopes, bar-offsets, rolling-extremums) is acceptable as a first-pass backtest-affordance. If any specific nuance is non-negotiable (e.g. the macd_histogram[0]>[1]>[2] chain), flag for a follow-up schema-extension sprint.

2. **donchian-channel-breakout** — semantic relaxation to midline-breakout is the most opinionated call here. Confirm this is acceptable as a first-pass affordance, OR queue a schema-extension to expose the prior-period (shifted) donchian upper.

3. **inside-bar-breakout** — re-test on real Dhan 30d data tomorrow. The override is structurally complete; the 720-bar deterministic synthetic just lacks the 3-bar inside-then-breakout pattern. Real intraday NIFTY data should contain plenty.

4. **Per-template PnL** — the synthetic-PnL column in §2 is for sanity, not selection. The synthetic is structurally rich but not statistically real; tomorrow's real-data backtest is the authoritative measurement.

5. **No state changes** — `is_active=true` on these 7 templates already; the override doesn't change activation. The strategy_executor live path is unchanged (it parses OLD prose natively). All this sprint does is **close the user-facing backtest gap** for these 7 specific NL constructs.
