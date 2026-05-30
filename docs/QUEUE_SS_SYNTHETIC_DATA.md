# Queue SS — Richer Synthetic Backtest Data

**Branch:** `feat/synthetic-data-richer` (base `origin/main` `4da606a`, contains
A2+C2+D2+E2). **Status:** Implemented + validated; full suite green. **Not merged.**

**One-line:** the production backtest placeholder was a pure sine (zero
divergence/trend/candle structure → divergence & swing templates fired 0 trades,
per Queue RR). It is now a deterministic, structurally-rich **single continuous
1-minute intraday session** that makes all 12 newly-unlocked templates fire while
keeping the 8 baselines firing.

---

## ⚠️ Intentional behavioural change (read first)

- **Bar count and spacing changed on purpose:** old = **120 × 1-min pure sine**;
  new = **720 × 1-min structured**. Backtests run on the synthetic fallback will
  therefore look **quantitatively different** from any older ones (different
  equity curve length, trade counts, P&L). This is expected and desired.
- **No migration concern.** Synthetic data is generated fresh per request and is
  **never persisted**. Existing stored backtest results are untouched and remain
  valid as historical records. Nothing in the DB changes; no migration runs.
- **Live-trading risk: ZERO.** The synthetic generator is used only by the
  backtest endpoints (`/api/strategies/{id}/backtest`, compare-fix). It never
  touches the live order path, brokers, or persisted strategy state.

---

## Phase 1 — Discovery findings

### Generator location (prompt path corrected)
- The prompt cited `backtest_extension/backtest.py:628` — **does not exist.** Real
  generator: **`backend/app/strategy_engine/api/backtest.py`**, `_synthetic_candles`.
- **Two consumers**, both kept working: `backtest.py` `_resolve_candles()` (the
  production endpoint) and `compare_fix.py` (compare endpoint).
- Output contract is **`list[Candle]`** (frozen Pydantic, OHLC-invariant,
  tz-aware, no dup timestamps, ≥2 bars) — NOT a pandas DataFrame.

### The three binding constraints
1. **Time gate.** Every override carries an intraday `time between 09:30/09:15 …
   15:00/15:15` AND-clause; the engine compares the candle's **raw time-of-day**
   (no tz conversion). Entry bars must sit inside the window.
2. **Data quality.** `_resolve_candles` runs `_candle_warnings` →
   `validate_candles`. `check_time_gaps` flags any inter-bar gap > **2× the
   timeframe** as a **`missing_candle` CRITICAL** ("backtest will not be
   reliable"). So the series must be **gap-free continuous**.
3. **Structure.** Each template family needs a specific shape; the stack's own
   override tests contain the proven motifs (decelerating decline → divergence;
   band-crossing sine → supertrend/hull; uptrend+pullbacks → triple-ema; periodic
   dojis; engulfing reversal).

---

## Phase 2 — Design: the 5-minute attempt and why it failed

**Approved at sign-off:** 720 bars, **5-min**, multi-session (72 bars/day across
10 IST sessions).

**Why it failed (implementation-time discovery):** multi-session data has
**overnight gaps** between sessions. `check_time_gaps` flagged each gap as a
`missing_candle` **critical** → every synthetic backtest returned 9 warnings.
That (a) broke `test_backtest_endpoint` (asserts `warnings == []`) and (b) would
show users "backtest will not be reliable" on every run. The fix could not be a
test edit — the warnings are real, user-visible, and degrade the quality verdict.

**Root conflict:** `warnings == []` ⇒ data must be **gap-free continuous**; the
**time gate** ⇒ entry bars must be **in-window**; **720 × 5-min** = 60 h ⇒ cannot
fit one ~5.75 h intraday window. Gap-free 5-min puts only ~69 bars in-window per
288, so the six regimes can't all land in-window within 720 bars (~6/12 fire).
The three constraints are mutually unsatisfiable at 5-min. **Stopped at the gate
for a parameter decision rather than ship gappy data or a weakened test.**

## Phase 2 (revised) — the 1-minute resolution (founder-approved)

**Switch spacing 5-min → 1-min**, keep 720 bars, **single continuous intraday
session** (one calendar day, 09:15 IST anchor). At 1-min the in-window stretch
09:15→15:00 holds **345 consecutive bars** — enough to pack all six regimes
(~50–86 bars each, ≥ divergence `lookback=20` + RSI/MACD warmup) inside one
gap-free, in-window stretch. Why it satisfies all three:

| Constraint | How 1-min satisfies it |
|---|---|
| Time gate | Structure packed in bars 0…329 (09:15→14:45 IST) — inside every gate; entries fire, square-off (15:00) leaves a buffer. |
| Data quality | Continuous 1-min ⇒ every inter-bar gap = 60 s ≤ 1.5× tolerance ⇒ **zero** gap warnings. `expected_minutes` reverts to **1** (net-zero vs old). |
| Structure | All six proven motifs retained; price formulas are per-bar so spacing-independent. |

The only deviation from the original sign-off is spacing **(b) 5-min → 1-min**
(approved). `(a)` stays **720**; `(c)` `expected_minutes` reverts to **1**.

### Future-proofing note
If 5-minute spacing is ever desired, it would require **either** a richer
**multi-day continuous-timestamp model** (regimes spread across several in-window
days with gap-free continuation, ≈1500+ bars) **or** a **data-quality validator
change** to treat overnight session gaps as expected (not `missing_candle`
critical). Either path is a deliberate change needing **explicit founder
approval** — do not silently reintroduce session gaps.

---

## New generator architecture (`_synthetic_candles`)

- **Anchor:** `2026-01-05 09:15 IST`; 720 × 1-min bars on one day (09:15→21:14).
- **Structural span:** first `_SYNTH_STRUCT_BARS = 330` bars (09:15→14:45),
  carrying six regimes by weight `(0.26, 0.12, 0.16, 0.16, 0.15, 0.15)` —
  divergence gets the largest slice (warmup + lookback):
  1. **R1** decelerating decline → bullish rsi/macd divergence
  2. **R2** down-drift + up-weighted volume → bullish OBV divergence
  3. **R3** band-crossing sine → supertrend/hull + macd/bb/orb sub-output crosses
  4. **R4** uptrend with pullbacks → triple-ema stack + trend baselines
  5. **R5a** oversold decline + periodic zero-body dojis → doji-reversal + oversold baselines
  6. **R5b** decline→pause→bullish-engulf → engulfing-reversal
- **Filler:** remaining bars (~390) = neutral bounded oscillation, **out-of-window
  (after 15:00)** so it never produces entries — purely to reach the bar count.
- **Determinism:** pure closed-form (sin/exp); no RNG → byte-identical reruns.
- **Output:** `list[Candle]`, contract unchanged.

Motifs are lifted from the stack's own override tests
(`tests/strategy_engine/translator/test_{divergence,trend,candle,sub_outputs}_overrides.py`).

---

## Phase 4 & 5 — validation (trade counts, all 20 templates)

Run via the real `run_backtest` engine. `old` = prior pure-sine (120 bars);
`NEW` = this generator (720 bars).

### 12 newly-unlocked — ALL > 0 ✅
| Template | family | old | NEW |
|---|---|---:|---:|
| macd-trend-signal | A2 | 2 | 5 |
| rsi-macd-confluence | A2 | 5 | 4 |
| bb-rsi-oversold | A2 | 3 | 3 |
| orb-15min | A2 | 0 | **1** |
| rsi-divergence | C2 | 0 | **3** |
| macd-divergence | C2 | 0 | **2** |
| obv-divergence | C2 | 0 | **4** |
| supertrend-rider | D2 | 2 | 4 |
| hull-ma-trend | D2 | 2 | 7 |
| triple-ema-crossover | D2 | 0 | **1** |
| doji-reversal | E2 | 3 | 2 |
| engulfing-candle-reversal | E2 | 0 | **1** |

The six that were 0 on the old sine (orb, rsi/macd/obv-divergence, triple-ema,
engulfing) now all fire. orb/triple-ema/engulfing sit at exactly 1 — `>0` and
**deterministic** (stable, not flaky), though a thin margin (see Known limits).

### 8 baselines (pre-A2) — zero regressions ✅
| Template | old | NEW |
|---|---:|---:|
| ema-crossover-9-21 | 2 | 4 |
| ema-crossover-20-50 | 2 | 3 |
| rsi-oversold-bounce | 59 | 117 |
| williams-pct-r-reversal | 11 | 20 |
| cci-momentum | 4 | 13 |
| aroon-crossover | 2 | 6 |
| mfi-overbought-oversold | 14 | 38 |
| cmf-confirmation | 0 | 2 |

(The other active seed templates — bb-mean-reversion, vwap-bounce, ichimoku, etc.
— raise `UnparseableConditionError` at **translate time** on BOTH old and new
identically; they are pre-existing parser gaps, out of scope for Queue SS, not a
regression.)

### Determinism & contract
- **Determinism:** two calls → byte-identical candles ✅
- **Contract:** `list[Candle]`, len 720, tz-aware, sorted, unique timestamps ✅
- **Data-quality warnings:** `[]` (gap-free) ✅

### Full test suite
`44 failed, 4189 passed` — **exactly the documented baseline, zero new
failures.** Two stale synthetic-count assertions (`== 120`) updated to `720`
(`test_real_data_backtest.py`, `test_backtest_endpoint.py`) — the direct
corollary of the approved bar-count change; both are synthetic-fallback
assertions. (Two other `== 120` assertions left untouched — they use a local
`_build_candles(120)` fixture / the explicit-120-bar dhan path, not the
generator.)

---

## Sign-off record
- Original design sign-off: (a) 720, (b) 5-min, (c) `expected_minutes` 1→5.
- Revised after implementation-time discovery (gap-warning validator conflict):
  (a) 720 ✅, **(b) 1-min** ✅, (c) `expected_minutes` reverts to 1 (net-zero).
  Founder explicitly approved the revision.

## Known limits
- orb-15min / triple-ema-crossover / engulfing-candle-reversal fire exactly **1**
  trade — deterministic and `>0`, but a thin margin. If these templates' params
  drift, revisit the regime sizing (give R3/R4/R5b a few more bars). Not changed
  now to avoid perturbing the green baseline.

## Scope honoured
- Touched: `_synthetic_candles` (+ helpers) in `backtest.py`, the coupled
  `expected_minutes` literal (reverted to 1), and **two stale test assertions**
  (synthetic candle count 120→720). No engine/translator/schema edits; A2 stack
  byte-identical; forbidden files (executor, direct_exit, webhook, kill_switch,
  brokers, alembic) untouched; live paths unaffected.
