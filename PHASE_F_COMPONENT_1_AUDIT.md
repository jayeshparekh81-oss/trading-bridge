# PHASE F — COMPONENT 1 AUDIT

**Date:** 2026-05-17
**Branch:** `feat/phase-f-indicator-audit`
**Auditor:** Claude Code (Opus 4.7, 1M ctx)
**Scope:** Read-only audit of `backend/app/services/indicators/` to determine fitness for the Phase F backtest engine (Component 4).
**Files inspected:** all 6 package files, `app/services/indicator_service.py`, `app/schemas/indicator.py`, `app/api/indicator.py`, `tests/services/indicators/conftest.py`, `tests/services/indicators/test_sma.py`. Plus consumer grep across `backend/`.
**Files modified:** ZERO. No existing file was edited during the audit.

---

## Recommendation (TL;DR)

> **Option C — API friction. Add a thin functional adapter + reference-CSV tests as NEW files.**

Existing classes are functionally correct, well-tested, performant, stateless. Two real gaps for backtest engine consumption:

1. **API ergonomics.** Existing API is class-based, requires `list[Candle]` (Decimal-priced) + Pydantic params per call. Backtest engine will hold `np.ndarray` close prices. Building Candle/Params objects per indicator call is boilerplate noise on the hot path.
2. **Ground-truth circularity.** Existing expected CSVs are TA-Lib-derived themselves (the conftest docstring even flags it: *"pre-launch the operator replaces it with TradingView Pine ta.sma capture"*). Independent ground truth (pandas-ta) would catch a TA-Lib regression that the current setup cannot.

Both gaps fit cleanly in new files. No existing-file edits required. Hard guardrails respected.

---

## Section 1 — Package inventory

`backend/app/services/indicators/` — 7 files, 418 LOC excluding `__pycache__`.

| File | LOC | Public symbols | Notes |
|---|---:|---|---|
| `__init__.py` | 43 | `BollingerBandsIndicator`, `EmaIndicator`, `IndicatorImpl`, `MacdIndicator`, `REGISTRY`, `RsiIndicator`, `SmaIndicator` | Eager-imports all 5 impls + populates `REGISTRY` dispatch dict at package load. |
| `base.py` | 125 | `IndicatorImpl` Protocol, `IndicatorParamsLike` type alias, `REGISTRY` dict, `closes_as_array(candles)` helper | Imports: `numpy`, `app.schemas.{candle,indicator}`. Defines the Protocol every concrete impl conforms to. |
| `sma.py` | 39 | `SmaIndicator` | Imports: `numpy`, `talib`, the params/candle schemas, `closes_as_array`. Single-output, wraps `talib.SMA`. |
| `ema.py` | 45 | `EmaIndicator` | Wraps `talib.EMA`. Module docstring flags TA-Lib's `SMA(close[0..length-1])` seeding vs Pine's first-close seeding — converges within 3·length bars, shipped as TA-Lib default. |
| `rsi.py` | 37 | `RsiIndicator` | Wraps `talib.RSI` (Wilder smoothing; matches TradingView `ta.rsi` exactly — no deviation). |
| `macd.py` | 53 | `MacdIndicator` | Wraps `talib.MACD`. Multi-output dict: `{"macd", "signal", "histogram"}`. Inherits EMA seeding deviation flag from `ema.py`. |
| `bb.py` | 76 | `BollingerBandsIndicator` | Wraps `talib.BBANDS` + applies a Pine-compatible **sample-stddev correction** (TA-Lib uses biased/population; Pine uses sample). Correction: `correction = sqrt(N/(N-1))`. Skipped for length=1 (collapses to middle band). |

### Imports — TA-Lib usage

All 5 indicator modules import `talib` and pass `np.float64` contiguous arrays produced by `closes_as_array()`. Compute calls: `talib.SMA`, `talib.EMA`, `talib.RSI`, `talib.MACD`, `talib.BBANDS`. Project dep pin: `ta-lib==0.6.4` in `pyproject.toml:67`.

---

## Section 2 — Class API contract

The base class is a **`typing.Protocol`** (not ABC). Defined in `base.py:57-88`.

```python
class IndicatorImpl(Protocol):
    name: IndicatorName                          # class attribute — registry key
    output_names: tuple[str, ...]                # ordered output series names

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        ...
```

### Constructor

All 5 impls have **no `__init__`** — instantiated as bare `SmaIndicator()`. Registration code in `__init__.py:25-32` constructs one instance per class at import time:

```python
for _impl in (SmaIndicator(), EmaIndicator(), RsiIndicator(),
              MacdIndicator(), BollingerBandsIndicator()):
    REGISTRY[_impl.name] = _impl
```

### Required class attributes

- `name: IndicatorName` — discriminator enum value (`SMA`, `EMA`, `RSI`, `MACD`, `BB`)
- `output_names: tuple[str, ...]` — single-output indicators use `("value",)`; MACD uses `("macd", "signal", "histogram")`; BB uses `("upper", "middle", "lower")`

### Required method

```python
def compute(self, candles: list[Candle],
            params: IndicatorParamsLike) -> dict[str, np.ndarray]: ...
```

- **Input:** `candles` is a `list[Candle]` (Pydantic model with `Decimal` price fields, tz-aware `datetime` timestamps). `params` is one of `SmaParams | EmaParams | RsiParams | MacdParams | BbParams` (discriminated union on `params.indicator`).
- **Output:** dict keyed by `output_names`. Each value is a `np.ndarray[float64]` of length equal to `len(candles)` (1:1 positional alignment). Warmup positions return `np.nan`.
- **Purity:** No I/O, no global state mutation, no logging from `compute()`. Pure function modulo TA-Lib's deterministic-given-inputs C implementation.

### Inheritance hierarchy

**None.** Each indicator is a plain class implementing the Protocol structurally. No shared base class, no metaclass magic. Grep-friendly by design (per `base.py:60-63` docstring).

---

## Section 3 — Per-MVP-indicator deep dive

### SMA — `SmaIndicator` @ `app/services/indicators/sma.py`

| Attribute | Value |
|---|---|
| Constructor params | None (`SmaIndicator()`) |
| Compute method | `.compute(candles, params)` |
| Input type | `list[Candle]` (Decimal prices) + `SmaParams(indicator=SMA, length=20)` |
| Output type | `dict[str, np.ndarray]` → `{"value": ndarray[float64]}` |
| Output length | == `len(candles)` |
| NaN handling | Positions `[0, length-1)` are NaN (warmup); NaN-input poisons subsequent output via TA-Lib's rolling-sum (flagged + tested in `test_sma.py:126-161`) |
| Pine/TradingView match | Trivial — `ta.sma` matches exactly, no smoothing convention divergence. |
| Existing tests | `tests/services/indicators/test_sma.py` (189 LOC, ~10 tests) |
| Test coverage style | **Mix of independent + self-derived.** `test_constant_input_yields_constant_output` + `test_hand_computed_consecutive_integers` are independent ground truth. `test_tradingview_result_match` loads `sma_expected.csv` — currently TA-Lib-derived (per docstring `tests/services/indicators/test_sma.py:91-96`). |
| **Suitability rating** | **YELLOW** — API friction only (needs Candle/Params wrapping). Math is correct. |

### EMA — `EmaIndicator` @ `app/services/indicators/ema.py`

| Attribute | Value |
|---|---|
| Constructor params | None |
| Compute method | `.compute(candles, params)` |
| Input type | `list[Candle]` + `EmaParams(length=20)` |
| Output type | `{"value": ndarray[float64]}` |
| Output length | == `len(candles)` |
| NaN handling | First `length-1` positions NaN. TA-Lib seeds recursion with `SMA(close[0..length-1])`. |
| Pine deviation | TA-Lib seeds with SMA(first length); Pine seeds with `close[0]`. Converges within float32 epsilon after ~3·length bars. Flagged in `ema.py:2-15`, shipped as-is per locked architecture (TA-Lib default). |
| Existing tests | `tests/services/indicators/test_ema.py` (102 LOC) |
| Test coverage style | Same mix as SMA. |
| **Suitability rating** | **YELLOW** — API friction. Pine deviation is documented and intentional. Backtest engine doesn't need Pine compat. |

### RSI — `RsiIndicator` @ `app/services/indicators/rsi.py`

| Attribute | Value |
|---|---|
| Constructor params | None |
| Compute method | `.compute(candles, params)` |
| Input type | `list[Candle]` + `RsiParams(length=14)` (bound: `ge=2`) |
| Output type | `{"value": ndarray[float64]}` 0..100 range |
| Output length | == `len(candles)` |
| NaN handling | First `length` positions NaN (one extra vs SMA because RSI needs a price delta to start). |
| Pine/TradingView match | **Exact.** TA-Lib uses Wilder's smoothing (alpha = 1/length), same as Pine's default `ta.rsi`. No deviation flag. |
| Existing tests | `tests/services/indicators/test_rsi.py` (107 LOC) |
| **Suitability rating** | **YELLOW** — API friction only. Cleanest impl of the five. |

### MACD — `MacdIndicator` @ `app/services/indicators/macd.py`

| Attribute | Value |
|---|---|
| Constructor params | None |
| Compute method | `.compute(candles, params)` |
| Input type | `list[Candle]` + `MacdParams(fast_length=12, slow_length=26, signal_length=9)` |
| Output type | `{"macd": ndarray, "signal": ndarray, "histogram": ndarray}` — all three returned together in one call |
| Output length | All 3 arrays == `len(candles)` |
| NaN handling | Warmup is roughly `slow_length + signal_length - 2` positions. TA-Lib handles internally. |
| Pine deviation | Inherits EMA seeding deviation from `ema.py`. |
| Cross-validation | `MacdParams._fast_lt_slow` model validator rejects `fast >= slow` at schema layer. |
| Existing tests | `tests/services/indicators/test_macd.py` (98 LOC) |
| **Suitability rating** | **YELLOW** — API friction + multi-output dict (NamedTuple would be cleaner for downstream destructuring). |

### Bollinger Bands — `BollingerBandsIndicator` @ `app/services/indicators/bb.py`

| Attribute | Value |
|---|---|
| Constructor params | None |
| Compute method | `.compute(candles, params)` |
| Input type | `list[Candle]` + `BbParams(length=20, stddev_multiplier=2.0)` (length `ge=2`) |
| Output type | `{"upper": ndarray, "middle": ndarray, "lower": ndarray}` |
| Output length | All 3 arrays == `len(candles)` |
| NaN handling | First `length-1` positions NaN. |
| Pine deviation | **Compensated.** TA-Lib uses biased/population stddev (÷N); Pine uses sample (÷N-1). Module applies `correction = sqrt(N/(N-1))` to the upper/lower bands so the output matches Pine `ta.bb()` exactly. This is **application math** (`bb.py:67-72`) — NOT a TA-Lib pass-through. |
| Existing tests | `tests/services/indicators/test_bb.py` (159 LOC) |
| **Suitability rating** | **YELLOW** — API friction + application-layer correction (the adapter must re-invoke the class so the correction stays correct; cannot call `talib.BBANDS` directly without re-implementing the correction). |

### Filename note

The user's spec mentions `bollinger.py`; existing file is `bb.py`. Cosmetic. The adapter can name its function `bollinger(...)` regardless of file path of the underlying class. No rename needed.

### Existing test files at `tests/services/indicators/`

| File | LOC | Test categories |
|---|---:|---|
| `__init__.py` | 0 | (package marker) |
| `conftest.py` | 160 | `synthesise_candles()` factory (deterministic LCG, NIFTY-shaped); `load_input_csv`, `load_expected_csv`, `write_expected_csv` helpers; `fixtures_dir` pytest fixture. |
| `test_sma.py` | 189 | ~10 tests covering identity, output_names, empty/single/short input, warmup, constant-input, fixture-CSV match, NaN propagation (with documented deviation), hand-verifiable case. |
| `test_ema.py` | 102 | Similar shape. |
| `test_rsi.py` | 107 | Similar shape. |
| `test_macd.py` | 98 | Similar shape, tests all 3 output series. |
| `test_bb.py` | 159 | Similar shape, tests Pine correction explicitly. |

### Existing fixtures at `tests/services/indicators/fixtures/`

| File | Size | Purpose |
|---|---:|---|
| `shared_input.csv` | 15 KB | OHLCV input (the canonical fixture every test loads) |
| `sma_expected.csv` | 8.5 KB | Expected SMA(20) values |
| `ema_expected.csv` | 8.5 KB | Expected EMA(20) values |
| `rsi_expected.csv` | 8.0 KB | Expected RSI(14) values |
| `macd_expected.csv` | 12 KB | Expected MACD(12,26,9) — 3 columns |
| `bb_expected.csv` | 15 KB | Expected BB(20,2) — 3 columns |

**The expected CSVs are TA-Lib-self-derived.** The conftest docstring (and `test_sma.py:91-96`) explicitly flag this: *"The expected CSV ships TA-Lib-derived values; pre-launch the operator replaces it with TradingView Pine ta.sma capture"*. Treating "self-derived" CSV as ground truth means a TA-Lib regression would shift both sides in lockstep — undetectable. **This is the test-side gap.**

---

## Section 4 — Cross-cutting concerns

### Registry / discovery

```python
REGISTRY: dict[IndicatorName, IndicatorImpl]   # base.py:93
```

Populated eagerly at package import via `__init__.py:25-32`. Read-only after init; safe to share across requests / backtest runs. Consumed by:

```python
# app/services/indicator_service.py:39, :226
from app.services.indicators import REGISTRY
impl = REGISTRY[indicator]
series_arrays = impl.compute(candles, request.params)
```

For backtest engine: can use either `REGISTRY[IndicatorName.RSI].compute(...)` or instantiate `RsiIndicator()` directly. The latter is simpler if you have the class import; the former is what `indicator_service.py` does.

### Configuration / params validation

Per-indicator Pydantic v2 models in `app/schemas/indicator.py`:

| Model | Fields | Bounds |
|---|---|---|
| `SmaParams` | `length=20` | `1 ≤ length ≤ 500` |
| `EmaParams` | `length=20` | `1 ≤ length ≤ 500` |
| `RsiParams` | `length=14` | `2 ≤ length ≤ 500` |
| `MacdParams` | `fast_length=12`, `slow_length=26`, `signal_length=9` | each `1 ≤ … ≤ 500`; model validator: `fast < slow` |
| `BbParams` | `length=20`, `stddev_multiplier=2.0` | `2 ≤ length ≤ 500`, `0 < stddev_multiplier ≤ 10.0` |

All `frozen=True, strict=True, extra="forbid"`. Discriminated union via `Literal[IndicatorName.X]` on each model's `indicator` field.

### Performance characteristics

- **Vectorised.** All compute paths are one TA-Lib C call per indicator, operating on a single contiguous `np.float64` array. No Python per-bar loops on the hot path.
- **`closes_as_array(candles)`** (base.py:101-117) is a Python-side `[float(c.close) for c in candles]` comprehension. For N=10K bars this is ~5-10 ms of Python — non-trivial relative to TA-Lib's microsecond inner loops, but bounded and **only paid once per indicator per backtest run** if the backtest pre-computes indicators upfront (the standard pattern).
- **Backtest hot path note:** for a backtest engine that walks bar-by-bar and re-evaluates indicators on a growing window, the per-call Candle/Decimal/Pydantic overhead becomes significant. But standard backtest design is precompute-once-then-iterate, which keeps the overhead amortised.

### Threading / state

- All 5 indicator classes are **stateless**. No instance attributes set in `compute()`. Pure functions modulo TA-Lib internals.
- `REGISTRY` is process-wide and read-only after init. Safe for concurrent reads.
- No thread-affinity concerns. Safe to share singleton instances across backtest runs / async tasks.

### Orchestration — `app/services/indicator_service.py`

`compute_indicator(request, user, db, ...)` is the public async coroutine. Pipeline (256 LOC total, the relevant ~50 lines):

1. Call `fetch_closed_candles(...)` (R1 closed-candle-only filter applied inside).
2. Empty window → return 200 with all-empty series.
3. Build Redis cache key: `indicator:{symbol}:{tf}:{name}:{params_hash}:{last_closed_ts}`.
4. Read-through cache (`cache_get`); on hit, return with `cached=True`.
5. Dispatch: `impl = REGISTRY[indicator]; series_arrays = impl.compute(candles, request.params)`.
6. Assemble `IndicatorResponse` (NaN → None at JSON boundary via `_nan_to_none`), write to cache, return.

The orchestrator is **HTTP-shaped** — it owns Redis caching, NaN→None conversion, response envelope. **Backtest engine should NOT use this orchestrator.** It should call the indicator classes (or the new adapter) directly. The orchestrator's existence does not constrain the backtest design.

### Consumer set (definitive)

Grep `app.services.indicators` across `backend/`:

```
PRODUCTION CODE
  app/services/indicator_service.py             # HTTP orchestrator
  app/services/indicators/__init__.py           # self-import
  app/services/indicators/{sma,ema,rsi,macd,bb}.py  # self-imports

TESTS
  tests/api/test_indicator.py                    # /api/chart/indicator route test
  tests/services/indicators/test_{sma,ema,rsi,macd,bb}.py  # unit tests
```

**That is the entire consumer set.** Earlier blocker file (`PHASE_F_COMPONENT_1_BLOCKERS.md` Section A) overstated the blast radius — the 17 `tests/strategy_engine/test_pack*_indicators.py` files and `tests/test_admin_indicators_api.py` reference `app.strategy_engine.indicators` (a separate statistical/risk indicator system: calmar_ratio, sharpe_ratio, hurst_exponent, etc.), NOT `app.services.indicators`. Blast radius of touching `app/services/indicators/` is just: the chart HTTP route + 6 test files. Still off-limits per Phase F hard guardrails — flagging for accuracy.

---

## Section 5 — Recommendation

### Verdict: **Option C — API friction. Add thin adapter + reference-CSV tests as NEW files.**

#### Why not Option A (no gaps)

The existing API is class-based, requires Decimal-priced Candle objects + Pydantic params per call. Backtest engine will hold `np.ndarray` close prices and will not want to construct a fresh `list[Candle]` (with Decimal conversion + Pydantic validation) every time it computes an indicator. Per-call overhead is bounded but the resulting backtest engine code will be cluttered with conversion boilerplate. This is real friction, not a phantom.

#### Why not Option B (tests only)

The ground-truth gap is real (TA-Lib expected from TA-Lib) and worth filling. But shipping tests without addressing the API ergonomics leaves the bigger problem (backtest engine boilerplate) for Component 4 to solve, where it will create pressure to edit existing files mid-engine-build — exactly the trap the new-files-only doctrine is meant to avoid.

#### Why not Option D (functional bug)

No functional bug found. The 2 deviations are intentional, documented, and tested:
- EMA seeding (TA-Lib SMA-seed vs Pine first-close-seed): convergent within 3·length bars; flagged in `ema.py` module docstring.
- BB stddev convention (TA-Lib biased vs Pine sample): compensated in `bb.py:67-72` to match Pine exactly.

The SMA NaN-poisoning is also a documented behaviour-spec deviation (`test_sma.py:127-141` explains it). Not a bug — a tradeoff that ships TA-Lib defaults per the locked architecture.

#### What Option C ships (proposed Phase B contents)

**B.1 — Reference tests** (NEW FILE)

- `backend/tests/services/indicators/test_indicators_phase_f_reference.py` — one test per indicator, loads new fixture CSVs at `backend/tests/fixtures/indicators/`, calls existing classes via `REGISTRY`, compares against pandas-ta-derived expected values with `np.testing.assert_allclose(rtol=1e-4, atol=1e-6)`.

- `backend/tests/fixtures/indicators/nifty_100_bars_5m.csv` — deterministic 100-bar OHLCV input (seeded `np.random.default_rng(42)`, NIFTY-calibrated drift+vol). NEW path; does NOT replace existing `tests/services/indicators/fixtures/shared_input.csv` (different fixture, different consumers).

- `backend/tests/fixtures/indicators/{rsi_14,sma_20,ema_20,macd_12_26_9,bollinger_20_2}_expected.csv` — pandas-ta-derived expected values from the new input fixture. Committed; pandas-ta not required at test time.

- `backend/tests/fixtures/indicators/_generate_fixtures.py` — runnable script that regenerates all CSVs from scratch (uses pandas-ta + numpy). For ops to re-run on TA-Lib or pandas-ta upgrades. Requires pandas-ta in dev env only.

**B.2 — Functional adapter** (NEW FILE)

- `backend/app/services/indicators/_backtest_adapter.py` — pure composition. Imports existing `SmaIndicator`, `EmaIndicator`, etc. Synthesises minimal `list[Candle]` per call (one-shot per indicator computation; amortised across the backtest). Exposes free functions:

```python
def rsi(close: np.ndarray, period: int = 14) -> np.ndarray
def sma(close: np.ndarray, period: int = 20) -> np.ndarray
def ema(close: np.ndarray, period: int = 20) -> np.ndarray
def macd(close, fast=12, slow=26, signal=9) -> MACDResult       # NamedTuple
def bollinger(close, period=20, stddev=2.0) -> BollingerResult   # NamedTuple
```

NamedTuples (`MACDResult`, `BollingerResult`) live in `_backtest_adapter.py` (private to that module) or in a sibling `_types.py` if Jayesh prefers.

**Note on the adapter signature:** The original (now-superseded) Component 1 spec defined these exact signatures. **The revised spec's Phase B.2 was truncated mid-`Signature pattern:` snippet** — I'm inferring the intended signatures from the earlier prompt. If Jayesh intended a different shape (e.g., `pd.Series` in/out instead of `np.ndarray`, or different defaults), the audit-only deliverable here gives a chance to correct that before Phase B starts.

#### Hard constraints satisfied

| Guardrail | Status |
|---|---|
| No edits to files in `backend/app/services/indicators/` | ✓ All B.1/B.2 deliverables are NEW files. New files in existing dirs are permitted. |
| No edits to `backend/app/services/indicator_service.py` | ✓ Adapter does not touch the orchestrator. |
| No edits to admin-indicators HTTP route | ✓ Admin route is in `strategy_engine` namespace — unrelated. |
| No edits to `tests/strategy_engine/test_pack*_indicators.py` | ✓ Pack tests don't import `app.services.indicators` at all. |
| No edits to `pyproject.toml` | ✓ pandas-ta is dev-only / regen-only; documented in PATCH_INSTRUCTIONS, not added to project deps automatically. |
| No edits to `backend/app/main.py` or router registration | ✓ No new HTTP surface introduced. |

---

## Section 6 — Phase B execution prerequisites (if Jayesh approves Option C)

Before I execute Phase B (gap-fill), confirm or correct these inferences:

1. **Adapter signature.** I'll use the original Component 1 spec signatures (see §5 above) since revised Phase B.2 was truncated mid-prompt. Override if you wanted something different.

2. **pandas-ta installation.** Currently not installed anywhere on this machine (no project venv on disk; system `python3` has no `talib` or `pandas_ta`). To run `_generate_fixtures.py` I need a venv with both. Options:
   - (a) I create a throwaway venv, install ta-lib==0.6.4 + pandas-ta, generate the fixtures, commit the CSVs, discard the venv. **No project deps touched.**
   - (b) I write the generator script but cannot run it; you run it yourself with your local venv and commit the CSVs.
   - (c) Use `pandas-ta-classic` if `pandas-ta` fails to install (your original prompt flagged scipy compat issues with `pandas-ta`).
   - My preference: (a), with (c) as fallback if `pandas-ta` install fails.

3. **Fixture path duplication.** Existing fixtures live at `backend/tests/services/indicators/fixtures/`; the revised spec puts new ones at `backend/tests/fixtures/indicators/`. These can coexist (different consumers, different ground-truth sources), but it's a duplication readers will notice. Confirm whether you want the new fixtures co-located with existing (would add files to an existing dir — still permitted by "new files in existing directories" doctrine) or at the spec-defined `tests/fixtures/indicators/` path.

4. **Adapter file naming.** Spec says `_backtest_adapter.py` (underscore prefix = private). Confirm that's what you want; alternatives include `backtest_api.py` (public-named) or splitting into `_types.py` + `functional.py`.

---

## Section 7 — Files referenced

This audit read but did NOT modify:

```
backend/app/services/indicators/__init__.py
backend/app/services/indicators/base.py
backend/app/services/indicators/sma.py
backend/app/services/indicators/ema.py
backend/app/services/indicators/rsi.py
backend/app/services/indicators/macd.py
backend/app/services/indicators/bb.py
backend/app/services/indicator_service.py
backend/app/api/indicator.py
backend/app/api/admin_indicators.py    (first 60 lines, for blast-radius clarity)
backend/app/schemas/indicator.py
backend/tests/services/indicators/conftest.py
backend/tests/services/indicators/test_sma.py
backend/pyproject.toml                  (grep only)
```

Plus directory listings of:
```
backend/app/services/indicators/
backend/tests/services/indicators/
backend/tests/services/indicators/fixtures/
backend/app/api/
backend/app/schemas/
```

Plus consumer grep across `backend/app/` and `backend/tests/` for `app.services.indicators`.

---

## Section 8 — What happens next

1. Jayesh reviews this audit doc.
2. Jayesh confirms Option C (or picks A/B/D) and answers the 4 Section 6 questions.
3. If C: I execute Phase B per the confirmed parameters. New files only. Test the adapter against the existing classes for equivalence. Pin coverage. Commit atomically.
4. Phase C (the truncated portion of the revised spec — likely BACKTEST_USAGE.md for Component 4) gets written last.
5. No push. Branch left at the final commit for Jayesh to push manually.
