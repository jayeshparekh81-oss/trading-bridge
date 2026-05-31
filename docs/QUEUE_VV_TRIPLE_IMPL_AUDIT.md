# Queue VV — Triple-Impl Audit on Remaining Indicators

**Date:** 2026-05-31
**Branch:** `cleanup/queue-vv-indicator-consolidation` (commit 4)
**Scope:** Apply Queue UU's MACD triple-impl methodology to SMA, EMA,
RSI, BB, ATR, VWAP. For each: enumerate every impl, classify
customer-facing vs orphan, quantify convention agreement on real
NIFTY 4280 bars (yfinance `^NSEI` 5m, 60 days).
**Status:** Complete. Two findings, no customer-impact divergences.

---

## 1. Impl-per-indicator matrix

| Indicator | FE TS (`computeX` in `lib/chart/indicators.ts`) | strategy_engine (`indicators.calculations.X`) | services (`services/indicators/X.py`) | Customer-facing impl |
|---|:---:|:---:|:---:|---|
| SMA | ✓ `computeSMA` (l.38) | ✓ `sma()` | ✓ `SmaIndicator` (ORPHAN†) | FE TS (chart) + strategy_engine (backtest) |
| EMA | ✓ `computeEMA` (l.59) | ✓ `ema()` | ✓ `EmaIndicator` (ORPHAN†) | FE TS (chart) + strategy_engine (backtest) |
| RSI | ✓ `computeRSI` (l.89) | ✓ `rsi()` | ✓ `RsiIndicator` (ORPHAN†) | FE TS (chart) + strategy_engine (backtest) |
| MACD | ✓ `computeMACD` (l.138) | ✓ `macd()` | ~~`MacdIndicator`~~ DELETED (8d7b8a8) | FE TS + strategy_engine |
| BB | ✗ no FE TS impl | ✓ `bollinger_bands()` | ✓ `BollingerBandsIndicator` (ORPHAN†) | strategy_engine only |
| ATR | ✗ no FE TS impl | ✓ `atr()` | ✗ no services impl | strategy_engine only |
| VWAP | ✗ no FE TS impl | ✓ `vwap()` | ✗ no services impl | strategy_engine only |

† ORPHAN = the same dead-code pattern Queue VV Commit 2 (8d7b8a8) just
removed for `MacdIndicator`. The `services/indicators/` package's only
production consumer was `services/indicator_service.py`, which served
the unmounted `POST /api/chart/indicator` route. After Commit 2,
nothing in production reaches `REGISTRY[*]` for any indicator.

---

## 2. Convention agreement on real NIFTY (4280 bars 5m)

Pairwise max-absolute-diff between every impl pair, post-warmup
bars only:

### SMA(20)
| Pair | max abs Δ | mean abs Δ | Verdict |
|---|---|---|---|
| strategy_engine vs services (talib) | 5.82e-11 | 2.71e-11 | machine epsilon |
| strategy_engine vs FE TS replicate | 5.82e-11 | 2.61e-11 | machine epsilon |
| services (talib) vs FE TS replicate | 1.46e-11 | 4.07e-12 | machine epsilon |

### EMA(20)
| Pair | max abs Δ | mean abs Δ | Verdict |
|---|---|---|---|
| strategy_engine vs services (talib) | 1.46e-11 | 3.20e-12 | machine epsilon |
| **strategy_engine vs FE TS replicate** | **0.000e+00** | **0.000e+00** | **bit-identical** |
| services (talib) vs FE TS replicate | 1.46e-11 | 3.20e-12 | machine epsilon |

### RSI(14)
| Pair | max abs Δ | mean abs Δ | Verdict |
|---|---|---|---|
| strategy_engine vs services (talib) | 2.13e-14 | 4.22e-15 | sub-epsilon |
| strategy_engine vs talib direct (FE TS uses Wilder = talib) | 2.13e-14 | 4.22e-15 | sub-epsilon |
| services vs talib direct | 0.000e+00 | 0.000e+00 | bit-identical |

### Bollinger(20, 2.0) — no FE TS impl
| Pair | max abs Δ | mean abs Δ | Verdict |
|---|---|---|---|
| upper:  strategy_engine vs services | 1.30e-07 | 1.36e-08 | sub-epsilon (slight float-accumulation noise in stddev) |
| middle: strategy_engine vs services | 5.82e-11 | 2.71e-11 | machine epsilon |
| lower:  strategy_engine vs services | 1.30e-07 | 1.36e-08 | sub-epsilon |

### ATR(14), VWAP — single impl, no pair to diff
| Indicator | Output sanity (4280-bar real NIFTY) |
|---|---|
| ATR | 4267 finite bars, range `[12.82, 88.26]` ✓ reasonable for NIFTY 5m |
| VWAP | **0 finite bars** (all NaN) ⚠ separate finding — see §5 |

---

## 3. Verdict — no convention divergence on the surviving impls

**Every customer-facing pair agrees at machine epsilon or sub-epsilon.**
The Queue UU concern — that two impls of the same indicator could
disagree by signal-relevant amounts — does not materialize for
SMA/EMA/RSI/BB. The MACD seeding question was unique to MACD
(aligned-vs-independent fast EMA seeding inside `talib.MACD`); the
other talib functions don't have an analogous internal-seeding
asymmetry.

This is the strongest possible read of Queue UU's "load-bearing
finding was the architectural one, not the math fix" thesis. Now
that the orphan `MacdIndicator` is gone, the FE TS + strategy_engine
pair for MACD is the only surviving pair and they were already
machine-epsilon equal (Queue UU §6 confirmed at 2.55e-11).

---

## 4. Four remaining orphan files (Commit 5 candidates)

After Commit 2 (`8d7b8a8`) removed `services/indicators/macd.py`,
the `services/indicators/` package contains:

| File | LOC | Importers (prod) | Disposition |
|---|---:|---|---|
| `__init__.py` | 33 (edited) | 0 prod | REGISTRY consumer (`indicator_service.py`) deleted in Commit 2 → REGISTRY is dead |
| `_types.py` | 49 | 0 prod | `backtest_adapter.py` (sole importer) deleted in Commit 2 → orphan |
| `base.py` | 125 | 4 sibling files in same package | infra for the orphan classes |
| `sma.py` | 39 | 1 (`__init__.py`, orphan) | **same pattern as deleted macd.py** |
| `ema.py` | 45 | 1 (`__init__.py`, orphan) | **same pattern as deleted macd.py** |
| `rsi.py` | 37 | 1 (`__init__.py`, orphan) | **same pattern as deleted macd.py** |
| `bb.py` | 59 | 1 (`__init__.py`, orphan) | **same pattern as deleted macd.py** |
| `BACKTEST_USAGE.md` | n/a | doc file | refers to deleted `backtest_adapter` |
| `tests/services/indicators/test_*.py` (4 files) | ~600 LOC | exercise orphan code | tests of dead code |
| `tests/services/indicators/fixtures/*` (Phase F generators) | ~500 LOC | exercise orphan code | regenerators for fixtures that test dead code |

Total to-be-deleted scope for Commit 5: **~1,500 LOC** (4 indicator
classes + base + types + __init__ + tests + Phase F fixtures + the
BACKTEST_USAGE doc).

### Why these are dead

Exactly the same dependency-graph argument that justified deleting
`MacdIndicator`:

1. Each `XIndicator` class is consumed only by `__init__.py`'s
   `REGISTRY` assembly.
2. `REGISTRY` was consumed only by `services/indicator_service.py`
   (deleted in Commit 2).
3. Therefore each `XIndicator` class is now unreachable in
   production.

The remaining unit tests (`test_sma.py`, `test_ema.py`, etc.) exercise
behavior that no production code path ever reads. They are tests of
dead code.

### Why deleting was NOT in Commit 2's scope

Founder explicitly listed only `MacdIndicator` in Commit 2's scope.
The Queue UU context made MACD the focal point. Commit 5 was reserved
for "consolidate any duplicates found (if Phase 2 finds them)" — i.e.,
this very finding.

---

## 5. URGENT finding — VWAP impl is broken on multi-day data, used by 2 active shipped templates

`app.strategy_engine.indicators.calculations.vwap.vwap()` returned
NaN for every one of the 4280 bars on the test input (yfinance ^NSEI
5m, 60 days continuous).

### Root cause (read directly from the impl)

The function is **"anchored-at-start" cumulative VWAP** —
accumulates `cum_pv / cum_vol` from input bar 0 with no intraday
session reset. The docstring at
`backend/app/strategy_engine/indicators/calculations/vwap.py:12-13`
states verbatim: *"Phase 1 implements anchored-at-start VWAP.
Session-anchored (intraday reset) VWAP is a Phase 2/3 concern when
the backtest [engine grows session markers]."*

Two failure modes on real data:
1. **Multi-day input:** value drifts to the multi-day cumulative
   average, not today's intraday VWAP. Entries/exits fire on wrong
   reference levels.
2. **NaN-volume poisoning:** once a NaN volume enters `cum_vol`, it
   poisons all subsequent bars (same pattern as TA-Lib SMA's NaN
   accumulator). On the yfinance test stream where some bars have
   NaN volume, this produced the all-NaN result.

### Shipped templates affected — caller-grep on
`backend/data/strategy_templates_seed.json`

| Template slug | `is_active` | VWAP usage |
|---|:---:|---|
| `vwap-bounce` | **true** | Primary indicator. Entry: `prior bars > vwap AND current low touches vwap AND close > vwap`. Exit: `close > vwap * 1.01 OR close < vwap`. |
| `camarilla-pivots-intraday` | **true** | Confirmation filter. Entry condition: `close > H3 AND volume > 1.5x recent average AND close > vwap`. |

### Severity by surface

| Surface | Status | Why |
|---|---|---|
| RC1 720-bar synthetic backtest (paper-launch path) | **OK** | Single intraday session; no session boundaries to miss; no NaN volumes (synthetic is clean) |
| Real multi-day historical backtest via Dhan | **BROKEN** | Will drift to multi-day cumulative; entries/exits on wrong reference; the `vwap-bounce` template's whole thesis breaks |
| Live intraday trading via strategy_executor | **Likely OK** | Process starts at session open; no historical bulk pre-fill; cumulative-from-start ≡ today's VWAP for as long as the process runs uninterrupted |
| Chart panel | **N/A** | No `computeVWAP` in `frontend/src/lib/chart/indicators.ts`; chart doesn't display VWAP today |

### Action taken (2026-05-31, founder-approved Option B+broader)

After completing the live-execution-path trace below, founder selected
the broader customer-trust de-risk: both templates flipped to
`is_active=false` in `backend/data/strategy_templates_seed.json` on
branch `risk/deactivate-vwap-templates`. Counts pre-edit: 29 active /
84 inactive. Post-edit: 27 active / 86 inactive. Seed-loader DB-free
validation (113 rows, 0 errors, 0 duplicates) confirms the file
upserts cleanly on the next EC2 deploy.

**Reason for deactivation:** TRADETRI's backtest engine consumes
`calculations/vwap.py` over the FULL `BacktestInput.candles` window
without session resets. Customer backtests over multi-day Dhan
historical produce an equity curve based on a cumulative-from-bar-0
VWAP, not today's-session VWAP. The same template's live execution
fires correctly (TradingView computes VWAP server-side and the live
path never touches our `vwap()` function — see §5 caller-graph below).
Disabling the templates protects customers from selecting them based
on misleading backtest results.

**Live execution path is verifiably unaffected.** Caller-graph proof
(grep `vwap(` in `backend/app`, excluding tests + self):
- `strategy_engine/backtest/indicator_runner.py:165` — backtest only
- ZERO live callers (verified: `api/strategy_webhook.py`,
  `services/strategy_executor.py`, `services/direct_exit.py`,
  `app/workers/*`, `app/tasks/*` — all zero hits on vwap/indicator_runner)

So this is a backtest-fidelity de-risk, not a safety de-risk. The
live BSE LTD trading path and any other live TV-driven strategy that
internally uses VWAP remains correct.

### Reactivation criterion

Set `is_active=true` on both templates only when ALL of the following
hold:

1. `calculations/vwap.py` rewritten to support session-anchoring with
   intraday reset on each new IST trading day boundary (09:15 IST or
   first bar after midnight, whichever lands first in the input).
2. NaN-volume skip added (`if math.isnan(volumes[i]): continue` — do
   not poison `cum_vol`).
3. New unit tests in `tests/strategy_engine/indicators/calculations/`
   covering: single-session correctness, multi-day reset boundary,
   NaN-volume skip, empty-volume bar, zero-volume bar.
4. Cross-validation against pandas-ta-classic's `ta.vwap()` on the
   yfinance ^NSEI 60-day 5m dataset matches at machine epsilon
   per-session (same methodology as Queue UU MACD analysis).
5. End-to-end backtest of `vwap-bounce` on a 30-day real Dhan window
   produces a defensibly-sane equity curve (no NaN gaps,
   entries/exits fire on plausible bars, no obvious convention
   divergence vs TradingView's UI for the same symbol/window).
6. Founder reviews the new fixture + regenerated backtest output
   before flipping the flag back.

### Recommended next ticket — VWAP session-anchoring fix sprint

**Effort estimate:** 1 focused dev-day (4-6 hours of actual work).

| Task | Estimate |
|---|---|
| Rewrite `calculations/vwap.py` (session detect + NaN skip + signature accepting optional timestamps) | ~1 hour, ~50 LOC |
| Update single caller `backtest/indicator_runner.py:165` to pass timestamps | ~15 min, ~3 LOC |
| New unit tests covering 5 scenarios | ~1.5 hours, ~200 LOC |
| Cross-validation script vs pandas-ta-classic on real yfinance data (Queue UU MACD pattern) | ~1 hour |
| Real-Dhan backtest verification of `vwap-bounce` template | ~30 min |
| Documentation (`docs/VWAP_SESSION_ANCHORING.md`) + audit doc back-fill | ~30 min |
| Regression suite + flip `is_active=true` + seed-loader rerun | ~30 min |

**Complexity:** LOW. Single math file + single 3-line caller edit. No
schema migrations, no broker SDK changes, no sacred-zone touches. The
function signature gains an optional `timestamps` parameter
(backwards-compatible default: None → behaves as current
anchored-at-start, so any other future caller doesn't break).

**What unblocks it:**

1. **Pine reference output:** pandas-ta-classic's `ta.vwap()`
   implements the TV-docs session-anchored convention. Per Queue UU,
   this is a reliable proxy for TradingView UI behaviour and doesn't
   require a TV screenshot. Already available in `/tmp/uu-venv`
   (installed by Queue UU for the MACD audit). **NOT a blocker.**
2. **Real Dhan historical data:** any 30-day window covering a normal
   trading session is sufficient. Can be pulled via the existing
   Dhan historical fetch path or yfinance ^NSEI as a proxy. **NOT a
   blocker.**
3. **Schema decisions:** the function-signature change (add
   `timestamps`) is internal-only — the registry's `calculation_function`
   resolver doesn't introspect arguments. **NOT a blocker.**
4. **Founder gate:** before reactivating the templates, founder
   reviews the new fixture + regenerated `vwap-bounce` backtest
   equity curve. **The only real blocker** — and it's a 30-min
   review, not weeks.

**Concrete recommended path:** ship the fix as `Queue WW`-style
single-day sprint when bandwidth opens up. Reactivation of the 2
templates lands in the SAME PR as the fix so the two changes can be
reviewed together and rolled back together if something surfaces.

---

## 6. Recommendation for Commit 5

**Delete the remaining 4 orphan indicator classes + their tests + the
Phase F regenerator infrastructure. ~1,500 LOC.**

This is the same surgical pattern as Commit 2. Same justification
(reachability proof + customer-surface absence). Slightly larger
scope only because there are 4 indicators instead of 1.

### Precise file list for Commit 5

**Delete:**
- `backend/app/services/indicators/__init__.py`
- `backend/app/services/indicators/_types.py`
- `backend/app/services/indicators/base.py`
- `backend/app/services/indicators/sma.py`
- `backend/app/services/indicators/ema.py`
- `backend/app/services/indicators/rsi.py`
- `backend/app/services/indicators/bb.py`
- `backend/app/services/indicators/BACKTEST_USAGE.md`
- `backend/tests/services/indicators/conftest.py`
- `backend/tests/services/indicators/test_sma.py`
- `backend/tests/services/indicators/test_ema.py`
- `backend/tests/services/indicators/test_rsi.py`
- `backend/tests/services/indicators/test_bb.py`
- `backend/tests/services/indicators/fixtures/_generate_phase_f_fixtures.py`
- `backend/tests/services/indicators/fixtures/_deviation_analysis.py`
- `backend/tests/services/indicators/fixtures/*.csv` (all expected/input
  fixtures — they test deleted code)

**Keep (intentionally):**
- `backend/tests/services/indicators/fixtures/_queue_uu_macd_quantification.py`
  — Queue UU reproducible analysis script; calls `talib.MACD`
  directly, doesn't import any orphan code. Docstring already
  updated in Commit 2 (`8d7b8a8`).

### Why ~1,500 LOC vs ~250 LOC (Commit 2)

Commit 2 was MACD-specific. Commit 5 is the rest of the package
(4 indicator classes + their unit tests + the Phase F infra that
generated their fixtures). Each indicator's footprint is similar
to MacdIndicator's; multiplied by ~4 plus the shared `base.py`
infrastructure plus the Phase F fixture-generation scripts that were
written specifically to validate this package against Pine docs and
no longer have a target.

If you'd prefer to delete only the indicator classes (not the Phase F
generators), that's about ~700 LOC. Saying so as an option, not
recommending — the Phase F generators only generate fixtures for the
about-to-be-deleted tests, so they're independently dead.

---

## 7. Summary table for the founder

| Question | Answer |
|---|---|
| Do any of SMA/EMA/RSI/BB have a Queue-UU-style convention divergence? | **No.** All pairs agree at machine epsilon on real NIFTY. |
| Do any have multiple impls in production? | **No.** Each has exactly one customer-facing impl (FE TS chart-side, strategy_engine backtest-side). services/indicators/* is orphan. |
| Does the orphan services/indicators/* package mirror the deleted MacdIndicator pattern? | **Yes.** Identical reachability story. |
| Customer impact of deleting the orphans (Commit 5)? | **Zero.** Same evidence as Queue UU §5/§6 (Aug 31 architectural finding). |
| Other audit findings worth flagging? | VWAP all-NaN on continuous multi-day input (§5) — unrelated to triple-impl pattern; flagged for separate ticket. |

Awaiting founder decision on Commit 5 scope.
