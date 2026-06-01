# Queue ZZ Sprint 7 — Chain Summary

**Mission:** Verify all 113 strategy templates across 5 dimensions — parse, indicator dependencies, backtest execution, performance sanity, final categorization. Pure observation. NO template/seed/main modifications.

**Scope:** 5 sub-sprints (7a → 7e), each on its own branch, additive test+docs only.

**Status:** ✅ All 5 sub-sprints complete. No hard-stops fired except the two expected ones (7a #4/#8: schema gap discovery → resolved by founder Option A). 0 sacred-zone touches. 0 production code touches. 0 main pushes.

---

## 1. Per-sub-sprint outcomes

| Sub-sprint | Branch | HEAD | Time used | Cap | Outcome |
|---|---|---|---:|---:|---|
| **7a** | `verify/sprint-7a-template-parse` | `c425344` | ~45 min | 1.5 hr | v1: 0/113 against StrategyJSON (forward schema, expected) → founder Option A → v2: 45/113 PARSE_OK against OLD format. 68 PHASE_2_PLACEHOLDER. 0 errors / 0 drift. |
| **7b** | `verify/sprint-7b-indicator-deps` | `ee065f3` | ~35 min | 1.5 hr | 0/27 active templates depend on unknown or D-tier indicators. 26.7% failure rate on populated 45 (10 HAS_UNKNOWN + 2 HAS_D_TIER, all inactive). Cross-validated against founder's commit `7ca0830` (vwap-bounce, camarilla-pivots-intraday). |
| **7c** | `verify/sprint-7c-backtest-execution` | `c5ead19` | ~40 min | 2.5 hr | 20/27 active fire trades end-to-end (15 FIRES_CLEAN + 5 FIRES_WITH_WARNINGS — all benign Phase-9 multi-output notes). 7 active TRANSLATION_FAILED (NL-parse gaps, not template defects). 0 EXECUTION_ERROR / 0 ZERO_TRADES. 10/10 inactive spot-checks failed translation (uniform pattern). |
| **7d** | `verify/sprint-7d-performance-sanity` | `19738ef` | ~20 min | 1 hr | 18/20 PASS_SANITY. 2 SUSPICIOUS_INF_PROFIT_FACTOR (small-sample artifacts, 1-trade and 2-trade samples with no losing trades). 0 other flags. |
| **7e** | `verify/sprint-7e-scorecard` | `aa67773` | ~30 min | 1 hr | Composite: 20 PRODUCTION_READY + 7 ACTIVE_BUT_BROKEN + 12 NEEDS_FIX + 74 INACTIVE_OK + 0 UNKNOWN = 113. |

**Cumulative time: ≈170 min (~2.8 hr) of 10 hr global budget. ~73% budget unused.**

---

## 2. 113 templates classified across all 5 dimensions

| Dimension | Bucket distribution (of 113) |
|---|---|
| **7a (OLD-format parse)** | 45 PARSE_OK · 68 PHASE_2_PLACEHOLDER · 0 VALIDATION_ERROR · 0 SCHEMA_DRIFT |
| **7b (indicator deps)** | 3 ALL_VERIFIED · 27 INDIRECT_DEPENDENCY · 3 PARTIAL_VERIFIED · 2 HAS_D_TIER · 10 HAS_UNKNOWN · 68 PHASE_2_PLACEHOLDER · 0 MISSING |
| **7c (backtest exec)** | 15 FIRES_CLEAN · 5 FIRES_WITH_WARNINGS · 0 ZERO_TRADES · 0 EXECUTION_ERROR · 17 TRANSLATION_FAILED · 76 NOT_TESTED (incl. 68 placeholders + 8 of the 12 NEEDS_FIX inactives, per spot-check policy) |
| **7d (perf sanity)** | 18 PASS_SANITY · 2 SUSPICIOUS_INF_PROFIT_FACTOR · 93 NOT_TESTED (only run on 20 trade-firing) |
| **7e (composite)** | 20 PRODUCTION_READY · 7 ACTIVE_BUT_BROKEN · 12 NEEDS_FIX · 74 INACTIVE_OK · 0 UNKNOWN |

---

## 3. Headline metrics

| Metric | Value |
|---|---|
| Templates parse cleanly (against OLD format, the live schema) | **45 / 113** (39.8%) — remaining 68 are by-design Phase 2-3 placeholders |
| All-verified indicator deps (no D-tier, no unknown) | **101 / 113** — including all 27 active (incl. 22 INDIRECT, 3 ALL_VERIFIED, 2 PARTIAL) + all 68 placeholders (vacuous) + 6 dep-clean populated inactives |
| Active templates firing trades (on 720-bar synthetic) | **20 / 27** (74%) — 15 clean + 5 with benign Phase-9 multi-output warnings |
| Active templates broken on backtest path | **7 / 27** (26%) — all due to translator NL-parse gaps, NOT template defects |
| Production-ready (composite from 7e) | **20 / 113** (17.7%); equivalently **20 / 27** active (74%) |
| Sacred-zone touches | **0** |
| Production-code touches | **0** |
| Seed JSON modifications | **0** |
| Template math/logic edits | **0** |
| Main-branch pushes | **0** |

---

## 4. Top concerns — 7 templates needing immediate attention

These are the **7 active templates** flagged `ACTIVE_BUT_BROKEN` in 7e. They run LIVE today (`strategy_executor` reads OLD format natively) — production capital is not at risk. What's blocked is the **backtest** path through the OLD→StrategyJSON translator's prose parser. Listed in order of concept density / likely Phase-2 priority:

| # | Slug | Translator-parse gap |
|---|---|---|
| 1 | `bb-mean-reversion` | `previous close` — bar-offset reference (`previous` / `[N]`) |
| 2 | `bb-squeeze-breakout` | `at 20-bar low`, `atr_14 increasing` — rolling-extremum + indicator-derivative |
| 3 | `macd-histogram-momentum` | `macd_histogram[0] > [1] > [2]` — bar-offset indexing chain |
| 4 | `donchian-channel-breakout` | parameterized component reference + rolling-extremum |
| 5 | `ichimoku-cloud-crossover` | multi-component composite (`tenkan`/`kijun`/`chikou`) + cross-time |
| 6 | `adx-strong-trend-filter` | `ema_9 sloping up` — indicator-slope derivative |
| 7 | `inside-bar-breakout` | multi-bar pattern phrase recognition (or a named pattern indicator) |

Six distinct translator-extension categories cover all 7. Extending each in turn closes the gap; this is Phase-2 translator work (`backend/app/strategy_engine/translator/`), not template or sacred-zone work.

**Why "immediate attention":** these are the templates that today have a *backtest-vs-live mismatch* — a user clicking "backtest this strategy" in the UI on these 7 hits a 422 / opaque error today. Live trades still work; backtest UX is the gap.

---

## 5. Secondary concerns — 12 inactive NEEDS_FIX templates

Lower urgency (all `is_active=false`, none on production capital):

| Bucket | Count | Recommendation |
|---|---:|---|
| HAS_D_TIER (vwap-bounce, camarilla-pivots-intraday) | 2 | Wait for VWAP D-tier fix (per `release-cutover-4`). Already founder-deactivated. |
| HAS_UNKNOWN (PSAR, Fibonacci, auto-S/R, PDH primitives, raw `volume`, etc.) | 10 | Queue against indicator-verification work; OR rewrite individual templates to use already-verified indicators. |

---

## 6. Recommended founder review order

1. **PRODUCTION_READY (20)** — no action; this is the live trading set, behaving as designed.
2. **ACTIVE_BUT_BROKEN (7)** — schedule translator NL-parse extensions for the 6 distinct construct categories listed in §4. Highest ratio of "templates unblocked per LOC of translator work."
3. **NEEDS_FIX HAS_D_TIER (2)** — already addressed by founder deactivation. Re-evaluate after VWAP fix.
4. **NEEDS_FIX HAS_UNKNOWN (10)** — long tail; queue case-by-case alongside the indicator-verification stream.
5. **INACTIVE_OK Phase-2-3 placeholders (68)** — addressed when Phase 2-3 schedules each.
6. **INACTIVE_OK dep-clean populated (6)** — re-test on demand if activation is contemplated; 4 will need the translator extensions from #2 to backtest.

No deactivations recommended at this time. No new activations recommended at this time. Everything is either already in its right state or already correctly deactivated.

---

## 7. Strategic decisions encountered + parked

### 7.1 [RESOLVED] Two coexisting strategy schemas

7a v1 surfaced that the seed JSON's `config_json` and the Phase-1-shipped `StrategyJSON` Pydantic schema have **zero overlap on required fields**. The seed is in the OLD format (the format `strategy_executor` reads live); StrategyJSON is forward-looking, downstream phases will adopt it.

**Resolution:** Founder picked Option A (re-target Sprint 7 to OLD format). v2 of 7a wrote the sibling `OldFormatConfig` validator and re-ran cleanly (45 PARSE_OK / 68 placeholders / 0 errors). Chain continued on this anchor. The OLD→StrategyJSON migration itself is **not** Queue ZZ scope; it's separate Phase-2 work the schema docstring already anticipates.

**Artifact:** `docs/QUEUE_ZZ_SPRINT_7A_REPORT.md` §3 + §10-15.

### 7.2 [PARKED] Translator's indicator-id registry < dual_scoreboard coverage

7c surfaced that the OLD→StrategyJSON translator's internal indicator-id registry has tighter coverage than Sprint 6e's dual-scoreboard. Several templates that are 7b dep-clean (against the scoreboard) still fail 7c because the translator doesn't recognize their composite-parameterized IDs (`heikin_ashi`, `keltner_channel_20_2_atr14`, `stochastic_slow_14_3_3`, `pivot_points_standard`, `parabolic_sar_0.02_0.2`).

**Status:** Parked. This is a translator-coverage concern (Phase 2). The chain documented it; no scope to fix in this queue.

**Artifact:** `docs/QUEUE_ZZ_SPRINT_7C_REPORT.md` §5.

### 7.3 [PARKED] Six translator NL-parse extensions for ACTIVE_BUT_BROKEN templates

Closing the backtest-vs-live mismatch for the 7 ACTIVE_BUT_BROKEN templates requires extending the prose parser in 6 distinct ways (§4 above). Each is a Phase-2 translator concern.

**Status:** Parked with concrete recommendations.

**Artifact:** `docs/QUEUE_ZZ_SPRINT_7E_REPORT.md` §3.

---

## 8. Hard-stops fired across the chain

| # | Hard-stop | When | Disposition |
|---|---|---|---|
| 4 | >50% failures in sub-sprint | 7a v1 (100% → 0 PARSE_OK against StrategyJSON) | Resolved — investigated, not a script bug; founder Option A redirected the chain. v2 cleared. |
| 8 | Strategic decision required | 7a v1 (schema gap) | Resolved — founder picked Option A and the chain continued under OLD-format anchor. |

No other hard-stops fired. Specifically:
- 4 (>50%) — 7b 26.7%, 7c 25.9% on active, 7d 0%, 7e 0%.
- 9 (backtest API unreachable) — every invocation succeeded; `translate_template` failures are gating filters, not API outages.
- 3 (sacred-zone write) — zero writes outside `backend/tests/queue_zz_sprint_7/` and `docs/QUEUE_ZZ_*`.
- 5 (seed JSON modification) — zero.
- 6 (template math/logic edit) — zero.
- 7 (wanted main merge) — zero pushes to main.

---

## 9. Branches + deliverables (all pushed to origin, none merged)

| Branch | HEAD | Purpose |
|---|---|---|
| `verify/sprint-7a-template-parse` | `c425344` | parse_audit.py + old_format_audit.py + parse_results.csv + parse_results_old_format.csv + 7A_REPORT |
| `verify/sprint-7b-indicator-deps` | `ee065f3` | dependency_audit.py + dependency_audit.csv + 7B_REPORT |
| `verify/sprint-7c-backtest-execution` | `c5ead19` | backtest_execution.py + backtest_execution.csv + 7C_REPORT |
| `verify/sprint-7d-performance-sanity` | `19738ef` | performance_sanity.py + performance_sanity.csv + 7D_REPORT |
| `verify/sprint-7e-scorecard` | `aa67773` (+chain summary commit) | scorecard.py + template_scorecard.csv + 7E_REPORT + this chain summary |

All branches sequential off the previous (7a off main; 7b off 7a; ...; 7e off 7d) — the same chained pattern Queue XX used, ready for Queue YY-style squash-merge at founder's discretion. All branches additive; zero modifications to existing files outside the queue's own dirs.

---

## 10. Founder gate

Per Queue ZZ Sprint 7 prompt: **"Founder gate at chain end."**

The chain is checkpointed at:
- `verify/sprint-7e-scorecard` @ post-chain-summary commit (this doc)

Awaiting founder review. No follow-on action initiated. Production unchanged.

**Recommendations if you want to merge any of this into main:** the 5 branches form a clean linear chain. A future "Queue ZZ Phase B" could squash-merge them in order (4a→4e style), mirroring Queue YY's mechanic. No conflicts expected — everything is additive under `backend/tests/queue_zz_sprint_7/` and `docs/QUEUE_ZZ_*`.

**Reminder:** Production stays at `release-cutover-4` / `7ca0830`. Queue ZZ touched zero production paths. No EC2 deploy implications.
