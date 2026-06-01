# Queue XX Sprint 5e — Calculations Inventory Hygiene Report

**Branch:** `docs/sprint-5e-inventory`
**Time used:** ~10 min of 30 min cap.
**Scope:** Resolve the 7 names that Sprint 4d's hand-roll list said
"TRADETRI doesn't ship". Classify each as typo / stub / planned-not-built
/ exists-under-different-name.

## 1. Resolution per missing name

| Sprint 4d candidate | Status | TRADETRI module (if exists) |
|---|---|---|
| `hanging_man` | **NOT SHIPPED** | None — TRADETRI ships `hammer.py`; hanging-man = same shape but at uptrend tops, typically combined with `hammer` detector + trend context |
| `spinning_top` | **NOT SHIPPED** | None — small body + wicks on both sides; TRADETRI ships `doji.py` + `marubozu.py` (extreme cases) but not the middle "small body, two wicks" pattern |
| `classic_pivots` | **EXISTS, name mismatch** | `pivot_points.py` ✓ (docstring line 1: *"Classic Pivot Points — daily PP plus R1/R2 and S1/S2"*) |
| `fibonacci_pivots` | **NOT SHIPPED** | None — TRADETRI ships `fibonacci_retracement.py` (which uses Fib ratios on swing high/low, different formula) |
| `central_pivot_range` | **NOT SHIPPED** | None — common TradingView CPR indicator, would need new module |
| `money_flow_volume` | **NOT SHIPPED** | None — but TRADETRI ships `cmf.py` (Chaikin Money Flow), `mfi.py` (Money Flow Index), `twiggs_money_flow.py`. The per-bar MFM × volume calc is internal to `accumulation_distribution.py` (a related cumulative line) |
| `woodies_pivots` | **EXISTS, typo** | `woodie_pivots.py` ✓ (singular "woodie") |

## 2. Summary breakdown

| Outcome | Count | Names |
|---|---:|---|
| **Typo / name mismatch (EXISTS)** | **2** | `classic_pivots` → `pivot_points`, `woodies_pivots` → `woodie_pivots` |
| **Genuinely not shipped** | **5** | `hanging_man`, `spinning_top`, `fibonacci_pivots`, `central_pivot_range`, `money_flow_volume` |

## 3. Re-verification opportunity (Tier A candidates)

The 2 typo/name-mismatch indicators can be Sprint 5d-style verified with
existing Sprint 4d hand-rolls re-pointed at the correct module:

- **`pivot_points`** (the actual TRADETRI module for "classic" pivots) —
  hand-roll `hr_classic_pivot` already exists in
  `sprint_4d_handrolls.py`. Re-test should yield Tier A.
- **`woodie_pivots`** (the actual TRADETRI module) — hand-roll
  `hr_woodies_pivot` already exists. Re-test should yield Tier A.

**Estimated cumulative scoreboard gain: +2 Tier A.** Defer to Sprint 6
(or fold into the founder-approved sweep_v2 work).

## 4. What does TRADETRI's calculations/ ship for the "not shipped" 5?

Each of the 5 missing has either no equivalent or a related-but-different module:

- **hanging_man:** TRADETRI's `hammer.py` covers the body+wick shape;
  context (uptrend vs downtrend) determines whether it's "hammer" or
  "hanging man." TRADETRI may have decided to ship shape-only detection
  and leave context to the strategy layer. **Design call, not gap.**
- **spinning_top:** Plausibly missing — could be added as ~10 LOC, fills
  a gap between doji (zero body) and marubozu (full body).
  **Backlog candidate.**
- **fibonacci_pivots:** Not a common Indian-market indicator; the
  related `fibonacci_retracement.py` covers most strategy needs.
  **Design call, low priority.**
- **central_pivot_range:** Popular in Indian intraday trading;
  noteworthy gap. **Backlog candidate** if customers ask.
- **money_flow_volume:** The per-bar money-flow-volume value is computed
  internally inside `accumulation_distribution.py`. Could be exposed as
  its own indicator with ~5 LOC. **Backlog candidate** for completeness.

## 5. Recommended inventory follow-up

For the next non-mechanical sprint:

1. **Re-test the 2 typo-renamed** in Sprint 5d's framework (`pivot_points`,
   `woodie_pivots`). Expected: +2 Tier A.
2. **Decide on the 5 truly-missing.** Two are noteworthy (spinning_top,
   central_pivot_range); three are design calls (hanging_man,
   fibonacci_pivots, money_flow_volume).
3. **Catalog the calculations/ directory** more rigorously — Sprint 5e's
   investigation found that 234 modules' naming conventions are not always
   consistent (singular vs plural; "classic" vs explicit "_classic"
   prefix). A future sprint could rename for consistency or add aliases.

## 6. Tier scoreboard delta from Sprint 5e

ZERO net delta — Sprint 5e is hygiene/documentation only.

If the 2 typo-renamed get re-tested in a future sprint and confirm Tier A:
- 81 → 83 cumulative classified
- 54 → 56 A

## 7. Sprint 5e hard-stops — all clear

| # | Cap | Observed | Status |
|---:|---|---|:---:|
| 1 | Sub-sprint time ≤ 30 min | 10 min | ✓ |
| 4 | Math fix attempted | 0 | ✓ |
| 5 | Math fix beyond mechanical | 0 (documentation only) | ✓ |
| 6 | Main merge attempted | 0 | ✓ |

## 8. Sprint 5e artifacts

- `docs/QUEUE_XX_SPRINT_5E_REPORT.md` (this file)
- No code changes — Sprint 5e is documentation only.

## 9. Sprint 5e lesson (lesson #12 for the chain)

**Sprint 4d's "module not found" list contained 2 typos — `_pivots` vs
`_pivot`, plural vs singular.** Catching these via a quick `ls` sweep is
a 5-min check that future hand-roll sprints should do upfront before
deciding an indicator doesn't ship.

For Sprint 6+: when a Sprint hand-roll lookup fails, fall through to a
fuzzy match (Levenshtein distance ≤ 2 OR singular/plural toggle) before
flagging as missing. ~30 LOC in the framework would auto-resolve these.
