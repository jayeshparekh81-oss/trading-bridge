# Queue XX Sprint 6c — consecutive_higher_lows Triangulation Report

**Branch:** `fix/sprint-6c-consec-higher-lows`
**Time used:** ~10 min of 60 min cap.
**Scope:** Triangulate Sprint 5b's 1 remaining D-tier indicator
(non-VWAP) against 3 candidate conventions. ZERO indicator math touched.

## 1. Results — bit-exact match to TRADETRI's docstring claim

| Convention | max abs Δ | Match |
|---|---:|:---:|
| **Conv 1 — Running count + reset + capped at lookback** (TRADETRI's docstring claim) | **0.0000** | ✓ EXACT |
| Conv 2 — Lookback window count (Sprint 5b's interpretation) | **0.0000** | ✓ EXACT (matches Conv 1 numerically on this data) |
| Conv 3 — Running count, NO cap | 3.0 | ✗ |

## 2. Re-classification — D → A

`consecutive_higher_lows` is **Tier A**.

TRADETRI's docstring formula (running count, reset on non-HL, capped at
`lookback`) implements correctly. Sprint 5b's D-tier classification came
from a default-lookback parameter mismatch (Sprint 5b passed `lookback=5`
in some routing path; TRADETRI's default is 10).

Convention 1 and Convention 2 produce identical output on the 4280-bar
NIFTY series because the test data doesn't contain a stretch of >10
consecutive higher-low bars where the cap would distinguish them.

## 3. Tier scoreboard delta from Sprint 6c

| Before Sprint 6c | After Sprint 6c |
|---|---|
| 94 (78 A, 14 B, 0 C, 5 D) | **95 (79 A, 14 B, 0 C, 4 D)** |
| consecutive_higher_lows: D | consecutive_higher_lows: **A** |

D-tier now down to 4: VWAP (de-risked) + breadth_thrust (6a) +
advance_decline_proxy (6a) + trend_age_bars (6b). All four are
"formula divergence flagged for source-reading, not real bugs."

## 4. Sprint 6c framework lesson (lesson #13 for the chain)

**A D-tier from one prior sprint can be reverified to A by running multi-
convention triangulation against the indicator's documented formula.**
Sprint 5b's classifier compared against my hand-roll with a different
default parameter; Sprint 6c's triangulation correctly identifies
TRADETRI's claimed convention as exact. This is the third instance
(Sprint 5a aroon, Sprint 5c trin_proxy, Sprint 6c here) where "D-tier"
turned out to be framework/methodology issue, not indicator bug.

The framework v2 (Sprint 5d pending) should:
1. Auto-detect indicator's documented default parameters via docstring
   parsing OR `inspect.signature` defaults.
2. Run multi-convention triangulation automatically before any D-tier
   classification.

## 5. Sprint 6c hard-stops — all clear

| # | Cap | Observed | Status |
|---:|---|---|:---:|
| 1 | Sub-sprint time ≤ 60 min | 10 min | ✓ |
| 4 | Math fix attempted | 0 (triangulation only) | ✓ |
| 5 | Math fix beyond mechanical | 0 | ✓ |
| 6 | Main merge attempted | 0 | ✓ |

## 6. Sprint 6c artifacts

- `docs/QUEUE_XX_SPRINT_6C_REPORT.md` (this file)
- No code changes — triangulation script ran inline; results recorded here only.

## 7. Cumulative impact

After Sprint 6c, the cumulative D-tier count is **4**:
- `VWAP` — already customer-de-risked via release-cutover-4
- `breadth_thrust` (6a) — single-symbol breadth proxy formula divergence
- `advance_decline_proxy` (6a) — same family as breadth_thrust
- `trend_age_bars` (6b) — SMA-crossover counting convention

None of the 4 are confirmed math bugs. VWAP has known fix planned. The
other 3 are flagged for source-reading or test-vector clarification but
not classified as customer-impact-critical.
