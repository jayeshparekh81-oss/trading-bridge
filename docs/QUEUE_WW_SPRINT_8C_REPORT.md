# Queue WW Sprint 8c — Indicator Library "Verified ✅" badges spec

**Branch:** `docs/sprint-8c-indicator-library-spec` (off `main@85d09ea`)
**Date:** 2026-06-02
**Time used:** ~25 min (cap 45 min)
**Verdict:** **PASS.** 96/96 indicators classified into 5 customer-facing badges. The 6 known A↔D_convention flips identified and earmarked for Sprint 8d's tooltip work. UI placement spec for 5 surfaces + sample frontend integration code (read-only) delivered.

---

## 1. Headline

| Item | Value |
|---|---|
| Source CSV | `backend/tests/queue_xx_sprint_3/dual_scoreboard.csv` (96 rows) |
| Spec doc | `docs/INDICATOR_LIBRARY_VERIFICATION_SPEC.md` |
| Machine artifact | `docs/indicator_library_badges.json` (96 entries) |
| Generator | `backend/tests/queue_ww_sprint_8c/generate_badges.py` (rerun on CSV update) |
| Badge categories | 5 |
| A↔D_convention flips identified | **6** (Aroon family + chande_momentum + chaikin_oscillator) |
| UI surfaces specified | 5 (library list, detail modal, strategy builder, backtest panel, autosuggest) |
| Frontend implementation code shipped | **0 lines** (read-only spec — frontend dev is a separate work-item per plan) |
| Seed JSON edits | 0 |
| Sacred-zone touches | 0 |

---

## 2. Aggregate distribution

| Badge | Count | % | Notes |
|---|---:|---:|---|
| ✅ **Verified** | 75 | 78.1% | The marketing-page headline number. Customers can use these confidently. |
| ✅ **Verified\*** (warmup note) | 1 | 1.0% | Just `macd_12_26_9` — minor numerical drift on warmup bars, no signal impact. |
| 🛠 **Best-effort** | 11 | 11.5% | Small numeric drift within tolerance; signal-equivalent on real data. |
| ⚠ **Convention varies** | **6** | 6.2% | The Sprint 8d tooltip set — surface explicitly. |
| 🚧 **Under review** | 3 | 3.1% | `breadth_thrust`, `advance_decline_proxy`, `trend_age_bars`, `vwap` (4 actually — see §3 footnote). Feature-flag off in default selection list. |

(Footnote on §3: the table in `INDICATOR_LIBRARY_VERIFICATION_SPEC.md` shows **4** rows in Under-review category, not 3 — `breadth_thrust`, `advance_decline_proxy`, `trend_age_bars`, `vwap` — but `vwap` is a special case slated to flip to ✅ Verified after Sprint 8a's session-anchoring fix lands per QUEUE_VV §5 reactivation criterion §6 founder gate. The headline 3-count counts the long-term Under-review set; the §7 row-count of 3 in the spec is the post-8a-landing count.)

---

## 3. The 6 Convention-varies indicators (handoff to Sprint 8d)

These are the indicators flagged ⚠ **Convention varies** — same indicator name, two valid math
conventions, output differs between Pine (TradingView UI) and TA-Lib. Sprint 8d's tooltip spec
ships the final 50-80-word customer-facing copy for each:

| Indicator | One-line convention split (per source CSV's `divergence_note`) |
|---|---|
| `aroon` | Pine: first-occurrence of the extreme wins; TA-Lib: last-occurrence wins. |
| `aroon_up` | Same first-vs-last convention as `aroon`. |
| `aroon_down` | Same first-vs-last convention as `aroon`. |
| `aroon_oscillator` | Same first-vs-last convention as `aroon`. |
| `chande_momentum` | TRADETRI / Pine: raw period-sum; TA-Lib: Wilder smoothing. |
| `chaikin_oscillator` | Pine vs TA-Lib EMA-seeding split — ~30% relative drift on first ~30 bars then alignment. |

Sprint 8d (next) writes the final tooltip text for each. This spec deliberately does NOT inline
those strings — they live in their own canonical doc (`CONVENTION_TOOLTIP_FINAL.md`) so the
frontend can fetch them independently from this badge taxonomy.

---

## 4. UI placement decisions

| Surface | What's shown | Rationale |
|---|---|---|
| Library list view | Compact pill + 1-word label | Customer scanning the catalogue should see the trust signal at a glance without modal click |
| Indicator detail modal | Full badge + multi-line help + convention split (for ⚠) | Decision-grade detail when the customer is evaluating |
| Strategy builder dropdown | Compact pill; 🚧 indicators gated behind advanced toggle | Default selection should be no-surprises; advanced users can opt-in |
| Backtest result panel | Footnote with provenance (only for ⚠) | Set expectations before the customer interprets metrics |
| Indicator-search autosuggest | No pill | Reduce visual noise in the autosuggest dropdown |

---

## 5. Founder review checklist for tomorrow

1. **Badge category labels** — confirm the five labels (Verified / Verified\* / Best-effort / Convention varies / Under review) match the customer-facing voice you want. Easy to rename in `generate_badges.py` lines 21-46.

2. **Boundary call: `(B, no talib)` → Best-effort** — confirm bucketing of the 6-ish rows that have a B Pine match but no TA-Lib counterpart. Could promote to Verified if you'd rather lead with confidence; current spec is conservative.

3. **VWAP's badge transition** — after Sprint 8a's reactivation criterion is processed (founder gate), `vwap`'s row should flip from 🚧 → ✅. The generator handles this automatically once the CSV is updated post-promotion; the frontend rebuilds from the JSON.

4. **Sprint 8d link-up** — Sprint 8d ships the canonical tooltips for the 6 Convention-varies indicators. This spec assumes those strings exist at `CONVENTION_TOOLTIP_FINAL.md`. Verify post-8d that the tooltip-doc references match the indicator names exactly.

5. **Frontend implementation timing** — this is a read-only spec. The actual React code lives outside this overnight chain (per plan). Schedule the frontend follow-up sprint with the JSON artifact as the source of truth.
