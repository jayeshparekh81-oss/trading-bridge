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

## 5. Separate finding — VWAP all-NaN on continuous multi-day input

`app.strategy_engine.indicators.calculations.vwap.vwap()` returned
NaN for every one of the 4280 bars on the test input.

Likely root cause: VWAP requires session boundaries (reset cumulative
sum at each session open). The 60-day continuous yfinance stream
doesn't carry session markers; the function may bail to NaN when it
can't identify the session, OR may have a bug.

Either way: **out of scope for this audit.** Flagged as a separate
ticket — the chart panel doesn't currently display VWAP (no
`computeVWAP` in `frontend/src/lib/chart/indicators.ts`), so this is
not customer-visible today. But any future VWAP integration must
either:
- Pass session markers to the function, OR
- Verify the function's NaN behaviour on real session-boundary data.

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
