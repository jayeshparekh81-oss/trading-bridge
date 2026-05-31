# Queue XX Sprint 4a — Framework Artifact Fixes Report

**Branch:** `fix/sprint-4a-framework-artifacts`
**Time used:** ~30 min of 90 min cap.
**Scope:** Re-run Sprint 3's 9 D-tier indicators with corrected framework
(column-routing + parameter overrides). MECHANICAL FIXES ONLY — no
indicator math touched.

## Results — 4 of 9 promoted from D

| Indicator | Sprint 3 tier | Sprint 4a tier | Fix applied |
|---|:---:|:---:|---|
| `chaikin_oscillator` | D (3505 sign-flips) | **A** (PASS, bit-exact) | Pass `fastperiod=3, slowperiod=10` explicitly to `talib.ADOSC` (Sprint 3 passed single positional 14 → fastperiod=14 mismatch) |
| `trix` | D (109 sign-flips, 6591% drift) | **A** (PASS, 2.7e-14) | Pass `timeperiod=15` to `talib.TRIX` (TRADETRI default = 15, talib default = 30) |
| `ultimate_oscillator` | D (746 threshold-flips, 79% drift) | **A** (PASS, 1.4e-14) | Pass `timeperiod1=7, timeperiod2=14, timeperiod3=28` to `talib.ULTOSC` (Sprint 3 passed single positional 14 → only first period set) |
| `variance` | D (31568% drift) | **B** (MINOR, 1.5e-6 max abs) | Pass `timeperiod=20, nbdev=1` to `talib.VAR` (TRADETRI default = 20, talib default = 5) |

## Results — 5 remaining D (require math investigation, deferred)

| Indicator | max abs Δ | sign-flips | thresh-flips | Likely root cause |
|---|---:|---:|---:|---|
| `aroon` | 8.0 | 0 | 0 | Convention divergence: TRADETRI's window = `period + 1` bars vs talib's window length. 0 thresh-flips suggests signal-equivalent for canonical thresholds — could be Tier B after deeper inspection. |
| `aroon_up` | 14.3 | 0 | 3 | Same window-convention question; 14.3 = 100×(2/14) suggests a 2-bar offset between TRADETRI and talib lookback windows |
| `aroon_down` | 21.4 | 0 | 4 | Same; 21.4 = 100×(3/14) suggests a 3-bar offset |
| `aroon_oscillator` | 21.4 | 0 | 1 | Inherited from aroon_up/aroon_down arithmetic |
| `chande_momentum` | 97.8 | 659 | 661 | Still ~15% sign-flip rate even with matched period=9. Not a parameter mismatch — possibly TRADETRI uses different up/down accumulation window semantics, OR talib uses Wilder-smoothed up/down (TRADETRI docstring says raw sums). Requires per-bar math triangulation to disambiguate. |

## Framework changes (Sprint 4a deliverable)

**New file:** `backend/tests/queue_xx_sprint_3/framework_extensions/sprint_4a_refs.py`

Two corrections vs Sprint 3's `references.py`:

1. **`TALIB_PARAM_OVERRIDES` dict** — per-indicator kwargs to pass into the
   talib reference call. Sprint 3 passed a single `default_period=14`
   positional which broke any talib function with multiple period args
   (ADOSC fast/slow, ULTOSC three periods, VAR + nbdev).

2. **`TALIB_TUPLE_COLUMN` + `TRADETRI_TUPLE_COLUMN` dicts** — when talib
   or TRADETRI returns a tuple, select the right column for the comparison.
   Sprint 3 took `[0]` blindly which paired TRADETRI's `aroon_up` against
   talib's `aroon_down` (talib.AROON returns `(down, up)` not `(up, down)`).

Zero changes to Sprint 3's `references.py` / `discover.py` / `sweep.py` —
the corrections live in a sibling module so the original Sprint 3 sweep
remains reproducible.

## Tier scoreboard delta from Sprint 4a

| Before Sprint 4a | After Sprint 4a |
|---|---|
| A: 1 (`obv`) | A: **4** (+chaikin_oscillator, +trix, +ultimate_oscillator) |
| B: 4 (`dema`, `kama`, `tema`, `wma`) | B: **5** (+variance) |
| D: 9 | D: **5** (Aroon family + chande_momentum) |
| Verified surface: 5 / 220 | Verified surface: **9 / 220** |

## Cumulative tier scoreboard (after Sprint 4a)

Across Queue UU + VV + Sprint 1 + Sprint 3 + Sprint 4a:

| Source | A | B | C | D |
|---|---:|---:|---:|---:|
| Queue UU (MACD) | 1 | 0 | 0 | 0 |
| Queue VV (SMA/EMA/RSI/BB/ATR/+VWAP) | 6 | 0 | 0 | 1 |
| Sprint 1 (top 7) | 6 | 1 | 0 | 0 |
| Sprint 3 (220 shallow) | 1 | 4 | 0 | 9 (initial) |
| Sprint 4a (re-classify 9) | +3 | +1 | — | -4 |
| **Cumulative** | **17** | **6** | **0** | **6** |

29 indicators now have confidence-tier classification (was 25 after Sprint 3).
The 6 remaining D-tier: VWAP (already de-risked) + 5 Sprint 4a-unresolved
(Aroon family + chande_momentum, all requiring math-level investigation).

## What I deliberately did NOT do

- ❌ No indicator math changes (hard-stop #5 holds)
- ❌ No fixes to `chande_momentum` despite confirming it's not a parameter
  issue — math investigation belongs in a future deep sprint
- ❌ No Aroon window-convention "fix" — that's a math decision (which
  window length matches Pine docs?), not a framework decision
- ❌ No main merge
- ❌ No EC2 deploy

## Sprint 4a hard-stops — all clear

| # | Cap | Observed | Status |
|---:|---|---|:---:|
| 1 | Sub-sprint time ≤ 90 min | 30 min | ✓ |
| 5 | Math fix attempted | 0 | ✓ |
| 6 | Main merge attempted | 0 | ✓ |

## Sprint 4a recommended next-session action

For the 5 remaining D-tier:
- **Aroon family (4 of 5):** read TRADETRI's aroon.py window-iteration logic
  line-by-line, compare against TA-Lib's C source (`ta_AROON.c`). Decide
  whether to (a) accept the convention difference and re-tier to B, (b)
  document a footnote, or (c) align TRADETRI to talib's window. This is a
  ~1 hr investigation, not a framework fix.
- **chande_momentum (1 of 5):** triangulate against pandas-ta-classic
  `ta.cmo` on the same data; per-bar inspection at 5 flip events.
  ~30 min investigation.

Total: ~1.5 hr in a future sprint can likely close out the last 5 D-tier
(or formally document them as accepted convention differences).
