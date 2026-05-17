# PHASE F COMPONENT 1 — BLOCKERS

**Status:** STOP. Two of four pre-flight checks failed. No branch created, no code written, no commits. Working tree clean on `main`.

**Date:** 2026-05-17
**Run from:** Claude Code (Opus 4.7, 1M ctx) session
**Spec received:** "TRADETRI Phase F — Component 1: Indicator Library Backend"

---

## Pre-flight check results

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | TA-Lib importable in backend venv | ⚠️ Cannot verify | No project venv on disk (`backend/.venv` does not exist). System `python3` (3.14.3) lacks `talib`. `pyproject.toml` pins `ta-lib==0.6.4` (NOT `>=0.4.28` as PATCH plan assumes — see Section C). |
| 2 | pandas-ta installs cleanly | ❌ Not present anywhere | Not in `pyproject.toml`, not installed in system `python3`. Spec calls it "test-only dependency"; need a venv before this can be verified end-to-end. |
| 3 | Branch `feat/phase-f-indicator-library` does not already exist | ✅ PASS | `git branch --list "feat/phase-f-indicator-library"` empty. |
| 4 | `backend/app/services/indicators/` does not already exist | ❌ **HARD FAIL** | Directory exists with **6 source files / 418 LOC** dated 2026-05-14 21:17 — matches Day-6 indicator sprint from memory. Live in-use package; see Section A. |

---

## Section A — The existing indicators package is LIVE

This is not a stale stub. The collision is real and far-reaching.

### Files present at `backend/app/services/indicators/`

```
__init__.py       43 LOC  — registers REGISTRY dispatch dict
base.py          125 LOC  — IndicatorImpl Protocol + closes_as_array() helper
sma.py            39 LOC  — class SmaIndicator
ema.py            45 LOC  — class EmaIndicator
rsi.py            37 LOC  — class RsiIndicator
macd.py           53 LOC  — class MacdIndicator
bb.py             76 LOC  — class BollingerBandsIndicator
```

### Existing tests at `backend/tests/services/indicators/`

```
__init__.py
conftest.py
test_sma.py
test_ema.py
test_rsi.py
test_macd.py
test_bb.py
```

(File names match Phase F's planned `test_<indicator>.py` — every single one collides.)

### Live consumers — non-test code that imports the existing package

```
app/services/indicator_service.py:39
    from app.services.indicators import REGISTRY

tests/api/test_indicator.py:22
    from app.services.indicators import REGISTRY

tests/test_admin_indicators_api.py
    (admin API test — also depends on the existing REGISTRY)
```

The existing package is wired into:
- `app/services/indicator_service.py` (orchestrator that the HTTP API calls)
- The admin-indicators HTTP route (already in prod per memory: Day-6 sprint shipped)
- The strategy_engine pack tests (`tests/strategy_engine/test_pack*_indicators.py` — 17 pack test files)

### API shape mismatch

| Concept | Existing (live) | Phase F spec |
|---|---|---|
| Public surface | classes implementing `IndicatorImpl` Protocol | free functions `rsi(close, period=14)` etc. |
| Inputs | `compute(candles: list[Candle], params: …Params)` | `rsi(close: np.ndarray, period: int)` |
| Multi-output return | `dict[str, np.ndarray]` keyed by `output_names` | `MACDResult`/`BollingerResult` NamedTuples |
| Param validation | Pydantic param classes (`SmaParams`, `MacdParams`, etc.) in `app/schemas/indicator.py` | private `_validators.py` with `validate_close_array(...)` |
| Decimal handling | `closes_as_array()` converts `Decimal → float` per-row | spec says "DO NOT touch Decimal" — inputs already float |
| Registry / dispatch | `REGISTRY: dict[IndicatorName, IndicatorImpl]` consumed by orchestrator | none — caller imports the function directly |

Two ENTIRELY different design philosophies sharing the same package path. They cannot coexist under `app/services/indicators/` without one breaking the other.

---

## Section B — Why "force through" would break production

The Phase F spec includes a hard constraint:

> **New-files-only doctrine:** do NOT modify any existing file in `backend/app/` or `backend/tests/`

But the spec also calls for these exact paths to be created:

- `backend/app/services/indicators/__init__.py` — EXISTS (would overwrite or conflict)
- `backend/app/services/indicators/rsi.py` — EXISTS (different API)
- `backend/app/services/indicators/sma.py` — EXISTS
- `backend/app/services/indicators/ema.py` — EXISTS
- `backend/app/services/indicators/macd.py` — EXISTS
- `backend/app/services/indicators/bollinger.py` — closest existing is `bb.py` (name-mismatch but same indicator)
- `backend/tests/services/indicators/test_rsi.py` etc. — ALL EXIST
- `backend/tests/services/indicators/conftest.py` — EXISTS

Adding `_validators.py`, `_types.py`, `README.md`, and the fixture CSVs would be the only "truly new" files. The 5 indicator source files + their tests are direct overwrites — would either:
1. Break the live admin-indicators HTTP route (production has 2 LIVE customers in paper_mode), OR
2. Break the strategy_engine pack tests (17 pack files depend on indicator behaviour), OR
3. Break the orchestrator at `indicator_service.py:39` which expects `REGISTRY` to be importable.

---

## Section C — Other plan-vs-repo mismatches

These are smaller but worth surfacing now rather than mid-build.

### C1 — `backend/requirements.txt` does not exist

PATCH_INSTRUCTIONS template asks Jayesh to:
> [ ] Verify backend/requirements.txt has `TA-Lib>=0.4.28`
> [ ] Add to backend/requirements-test.txt: `pandas-ta>=0.3.14b0`

Backend uses **`pyproject.toml`** (no `requirements.txt`, no `requirements-test.txt`). Already in memory under "Repo path pitfalls": *"strategy_engine uses pyproject (not requirements.txt)"* — applies to the whole backend.

Current TA-Lib pin in `pyproject.toml:67`:
```
"ta-lib==0.6.4",
```

Note: **0.6.4**, not 0.4.28. The spec's "TA-Lib>=0.4.28" line in PATCH_INSTRUCTIONS would technically be satisfied but the assumption "TA-Lib 0.4.x is deployed" is wrong.

### C2 — Decimal note is half-correct

Spec says "Decimal types — indicators are float64 math, never Decimal". The existing code agrees on the math side (TA-Lib returns float64). But the existing `closes_as_array()` helper at `base.py:101` documents *why* it does per-row `float(c.close)` casts — because input `Candle.close` IS a `Decimal` (Pydantic validator `gt=0`). So a Phase F redesign that takes `np.ndarray` inputs directly assumes the caller has already done the Decimal→float conversion; the existing design does it at the boundary. Worth a docstring note in whatever ships.

### C3 — Bollinger filename: `bollinger.py` (spec) vs `bb.py` (existing)

Cosmetic but flagged: existing file is `bb.py`, spec wants `bollinger.py`. If we end up replacing the live package, one or the other has to win.

---

## Section D — Options for Jayesh

Pick one. I'm not going to force through any of them without your call.

### Option 1 — Refactor existing package to the Phase F functional API (RECOMMENDED for clean future)

- Take the existing class-based impls, extract the math into free functions in the new shape (`rsi(close, period)`, etc.)
- Keep `REGISTRY` + `IndicatorImpl` as a thin façade that calls the new functions, so `indicator_service.py:39` and the admin API keep working unchanged
- Modify existing files → violates "new-files-only" doctrine. **Requires you to authorise edits.**
- Pros: one package, no duplication, future backtest engine can call the clean functional surface; HTTP route keeps working
- Cons: must touch existing files (5 indicator modules + base + `__init__`), violates the doctrine

**Estimated blast radius:** medium. Pack tests in `strategy_engine` reference indicator *behaviour*, not class instances, so as long as the math stays equivalent the pack suite should stay green. Admin-indicators API tests reference `REGISTRY` directly — the façade must preserve that name. 96%+ coverage target survives if we test both surfaces.

### Option 2 — New package at a different path (e.g. `backend/app/services/indicators_v2/` or `backend/app/services/indicator_math/`)

- Drop the entire Phase F spec into a sibling package, untouched names, no collisions
- Backtest engine (Component 4) imports from the new path
- Existing `app/services/indicators/` stays as-is, used only by the HTTP route + strategy_engine
- Pros: zero blast radius, strict new-files-only compliance preserved, can build in parallel with the live system
- Cons: two indicator packages in the same backend forever (or until a future consolidation sprint); risk of math drift between them; readers will be confused

**Estimated blast radius:** zero on existing code; the cost is permanent duplication + a future cleanup story.

### Option 3 — Cancel Phase F Component 1 and reuse existing classes from the backtest engine

- The existing classes already wrap TA-Lib correctly (NaN-propagating, float64, deterministic). They're tested. They're in prod.
- Component 4 (backtest engine) can construct the impl from `REGISTRY` and call `.compute(candles, params)` directly — no new library needed
- Pros: no new code, no duplication, fastest path to a working backtest
- Cons: backtest engine has to construct `IndicatorParamsLike` Pydantic objects per call (a few extra lines per indicator), and the API isn't as clean as `rsi(close, 14)`

**Estimated blast radius:** zero. But you lose the clean functional surface the spec was after.

### Option 4 — Force through anyway (NOT RECOMMENDED, listed for completeness)

Create the branch, write Phase F files on top of the existing ones, accept overwrites. This will:
- Break `indicator_service.py:39` (import path semantics survive but `REGISTRY` disappears)
- Break the admin-indicators HTTP route in prod the moment the branch merges
- Break ~17 strategy_engine pack tests
- Violate the spec's own "new-files-only doctrine"

I will not do this without explicit `--yes-overwrite` instruction.

---

## Section E — My recommendation

**Option 1.** The existing package is the right design for the HTTP/API side (Pydantic params + dispatch); the Phase F spec is the right design for the backtest/math side (numpy in/out, no Pydantic). They converge if we keep `REGISTRY` as a thin façade calling free functions underneath. We get one source of truth, one set of tests, and the backtest engine gets the clean functional API it wants.

Pre-conditions for going Option 1:
1. You explicitly authorise editing existing files in `app/services/indicators/` + `tests/services/indicators/` for this sprint only (overrides the new-files-only doctrine just for the Phase F refactor)
2. We pin a coverage baseline before the refactor (current coverage on the existing package) so we can prove we didn't regress
3. PATCH_INSTRUCTIONS_PHASE_F_COMPONENT_1.md becomes "we refactored, here's the new public surface, here's the migration note for indicator_service.py if anything moved"

If you'd rather keep the doctrine, **Option 2** is the safe-but-uglier alternative. **Option 3** is the cheapest.

---

## What I did NOT do

- ❌ Did not create branch `feat/phase-f-indicator-library`
- ❌ Did not write any Phase F code
- ❌ Did not edit any existing file
- ❌ Did not commit anything (`git status` was clean before; this file is the only untracked change at repo root)
- ❌ Did not run any installs (no `pip install pandas-ta`, no venv creation)
- ❌ Did not push anything

## What I DID do

- ✅ Ran all 4 pre-flight checks
- ✅ Read the existing package's `__init__.py` and `base.py` to understand the live design
- ✅ Mapped which files in the existing codebase import the existing indicators package
- ✅ Wrote this blocker file at repo root

## Next step

Reply with your choice (Option 1 / 2 / 3 / 4), or ask for more detail on any of them.

---

# Finding #2 — TA-Lib MACD diverges from Pine-documented composition

**Date:** 2026-05-17 (during combined BB-fix + Phase B Option C sprint)
**Branch:** `feat/phase-f-indicator-audit`
**Trigger:** Hard guardrail in user's combined-sprint spec — *"If anything else fails, STOP → BLOCKERS. Part 2 analysis would have been wrong."*

**Status:** STOP. BB fix portion of the combined sprint NOT applied. Phase B infrastructure (adapter, fixtures, reference tests) committed independently; MACD reference test deliberately failing as evidence. Awaiting expanded authorization or defer decision.

## What was discovered

While running the new reference test `test_macd_matches_pine_reference` against the Pine-derived fixture, the test failed at every post-warmup bar with TRADETRI MACD diverging from the fixture by ~0.6 absolute. Empirical investigation traced the cause:

`talib.MACD(close, 12, 26, 9)` does **not** equal `talib.EMA(close, 12) - talib.EMA(close, 26)`. The standalone TA-Lib EMAs match the SMA-seeded recurrence to machine epsilon (~7e-12) — they ARE Pine-correct individually. But the internal MACD function uses a DIFFERENT seeding for the fast EMA:

- **Standalone `talib.EMA(close, 12)`:** seeds at index `12-1 = 11` with `SMA(close[0..11])`, then recurses. Matches Pine `ta.ema(close, 12)`.
- **Internal `talib.MACD` fast EMA:** seeds at index `slow-1 = 25` (NOT `fast-1 = 11`) with `SMA(close[slow-fast..slow-1]) = SMA(close[14..25])`. Then recurses from index 26 onward.

Verified empirically: the "aligned seeding" hypothesis (fast EMA seeded at index `slow-1` with the immediately-preceding `fast` closes) reproduces `talib.MACD`'s output to machine epsilon (1.5e-11 max abs diff across all three series).

### Why Part 2 analysis missed this

`PHASE_F_DEVIATION_ANALYSIS_PART2.md` Section 5 (MACD) verdict was CONVENTION (non-deviation, max %diff = 0.00e+00). That verdict was based on the `_deviation_analysis.py` Part 2 script comparing `macd_lines(close)` against `macd_lines(close)` (the same hand-rolled function aliased as "TRADETRI" and "Pine"). It **never compared TRADETRI's actual `MacdIndicator` (TA-Lib) against the hand-roll**, so the aligned-seeding divergence was invisible.

The Part 2 verdict was wrong. The sprint guardrail caught it.

### Why pandas-ta-classic's behaviour is split

pandas-ta-classic's top-level `ta.macd(...)` uses `presma=False` for its internal EMAs (NOT Pine-style SMA seeding), and produces output matching `talib.MACD` (with aligned seeding). pandas-ta-classic's standalone `ta.ema(presma=True)` matches the Pine-style independent SMA seeding. So depending on which API path is used, pandas-ta-classic gives either of two answers:
- `ta.macd(...)`  → TA-Lib aligned-seeding result (18.902 at bar 33)
- Compositionally built from `ta.ema(presma=True)` → Pine-docs result (18.267 at bar 33)

Both implementations exist in the wild. The Pine reference docs describe the second one (independent SMA-seeded EMAs); de-facto industry implementations (TA-Lib, pandas-ta-classic's `ta.macd`) use the first.

## Verdict

**AMBIGUOUS, not BUG.** Different from the BB case where Pine and TA-Lib both use biased stddev unambiguously and `bb.py` applies a wrong-direction correction. For MACD, the underlying conventions DIVERGE in published implementations, and Pine's docs and Pine's reference implementations disagree on what `ta.macd` actually computes internally.

That said: customer-impact is real. The 0.6-ish absolute MACD difference at price level ~22000 means MACD crossover signals fire on different bars between TRADETRI and TradingView. On a 100-bar series the difference is small in % terms (~0.003%) but signal-relevant.

## Customer impact estimate

On the synthetic 100-bar series:
- TRADETRI macd_line range post-warmup: ~-31 to ~+22
- Pine-docs macd_line range post-warmup: ~-31 to ~+22 (similar magnitude)
- Per-bar abs diff: 0.4 to 0.7
- Signal-line crossover counts (close vs macd): would need re-running with both conventions to count flips — left as a follow-up

## What I executed before stopping

Phase B infrastructure (all new files; new-files-only doctrine respected):

1. `backend/app/services/indicators/_types.py` — NamedTuples `MACDResult`, `BollingerResult`
2. `backend/app/services/indicators/backtest_adapter.py` — functional wrappers (sma, ema, rsi, macd, bollinger)
3. `backend/tests/services/indicators/fixtures/_generate_phase_f_fixtures.py` — fixture generator using pandas-ta-classic + hand-rolled Pine references
4. `backend/tests/services/indicators/fixtures/nifty_100_bars_5m.csv` — deterministic OHLCV input
5. `backend/tests/services/indicators/fixtures/{rsi_14,sma_20,ema_20,macd_12_26_9,bollinger_20_2}_pine_expected.csv` — 5 Pine-reference CSVs
6. `backend/tests/services/indicators/test_indicators_phase_f_reference.py` — reference tests, 9 assertions

Test results pre-BB-fix:
- 7 PASS: SMA, EMA, RSI, adapter equivalence, 3 validation tests
- 2 FAIL:
  - `test_bollinger_matches_pine_reference` — expected (BB bug from Part 1; will pass after authorized BB fix)
  - `test_macd_matches_pine_reference` — **unexpected**; surfaces this new finding

## What I did NOT execute

- ❌ BB math fix at `bb.py:67-72` — held pending expanded authorization
- ❌ `bb_expected.csv` regeneration
- ❌ `BACKTEST_USAGE.md`
- ❌ `PATCH_INSTRUCTIONS_PHASE_F_COMPONENT_1.md`
- ❌ `PHASE_F_OVERRIDE_LOG.md`

## Decision needed from Jayesh

Three options, ordered by my preference:

### Option α — Expand authorization to include MACD documentation footnote, defer MACD code change

- Apply BB fix as currently authorized (clear bug, clean fix)
- Leave `macd.py` UNCHANGED — TA-Lib's aligned-seeding is industry standard and matches pandas-ta-classic's native `ta.macd()`. Pine's documented spec is the outlier here.
- Add a customer-facing footnote: *"TRADETRI's MACD follows the TA-Lib + pandas-ta industry convention which seeds the fast EMA at the same point as the slow EMA. TradingView's Pine `ta.macd` documentation describes a different composition; in practice TradingView's implementation may differ from the docs. Expect macd_line values to differ by ~0.001-0.005% between TRADETRI and TradingView."*
- Modify `test_macd_matches_pine_reference` to mark it as `xfail` with a clear reason pointing at this finding. The test stays in code as a watch-this-space marker.
- Cost: docstring + xfail marker + customer docs note. Zero code change.
- Risk: customers comparing strategies might see different MACD-driven entry timing. We disclose upfront.

**This is my recommendation.** TA-Lib's MACD is the de-facto standard. Pine docs probably describe an idealization that doesn't match TradingView's actual implementation either. Re-implementing MACD to match the Pine docs would diverge from every other industry library and create its own credibility issue.

### Option β — Expand authorization to fix MACD seeding in `macd.py`

- Replicate `talib.MACD` math in Python with INDEPENDENT EMA seeding (matches Pine docs). Bypass `talib.MACD`; use `talib.EMA` for each component and subtract.
- This is a real existing-file edit to `macd.py` — needs explicit one-time override.
- Regenerate `macd_expected.csv` against the new output.
- The reference test passes against the Pine-docs fixture.
- Cost: ~20 lines of code change in `macd.py` + fixture regen + EXISTING `test_macd.py` may need adjustments depending on what it asserts.
- Risk: TRADETRI MACD diverges from EVERY other industry library (TA-Lib, pandas-ta default). Customers using strategies imported from TradingView would actually want this fidelity though.

### Option γ — Ship MACD bug acknowledged; xfail the test; full BB fix proceeds

- Same as Option α but skip the customer-facing docs note. Ship as-is, the bug remains, test stays xfailed.
- Cost: smallest. xfail marker only.
- Risk: surprise customers when they notice the discrepancy themselves; reactive support load.

## What ships if Jayesh picks Option α (recommended)

I resume the sprint and execute:
1. Apply BB fix at `bb.py:67-72`
2. Regenerate `bb_expected.csv`
3. Add `pytest.mark.xfail(reason="MACD Pine-vs-TA-Lib convention split; see BLOCKERS Finding #2", strict=False)` on `test_macd_matches_pine_reference`
4. Run full test suite — expected GREEN (xfail counts as not-failed)
5. Write `BACKTEST_USAGE.md`
6. Write `PATCH_INSTRUCTIONS_PHASE_F_COMPONENT_1.md` (includes MACD footnote text for customer docs)
7. Write `PHASE_F_OVERRIDE_LOG.md` (single entry: BB fix only)
8. Commits 4-7 (BB math, BB fixture, full docs)
9. Hand back for review

If Jayesh picks Option β, add MACD to authorization scope + macd.py rewrite to the steps above. If γ, drop the docs footnote.

## Awaiting your call

---

# Finding #3 — `test_pine_compat_correction_applied` asserts the BB bug is present

**Date:** 2026-05-17 (resumed sprint, Option α-modified)
**Branch:** `feat/phase-f-indicator-audit` @ `333b675`
**Trigger:** Same guardrail as Finding #2 — *"If anything else fails, STOP → BLOCKERS. No further auto-investigation."*

**Status:** STOP. BB math fix applied (commit `63932b0`). `bb_expected.csv` regenerated (commit `333b675`). MACD xfail and downstream docs **NOT executed** — held pending authorization expansion.

## What was discovered

After applying the authorized BB math fix at `bb.py:67-72` and regenerating `bb_expected.csv`, running the full existing `test_bb.py` suite produces **10 PASS / 1 FAIL**. The failure is:

```
tests/services/indicators/test_bb.py::test_pine_compat_correction_applied
```

Located at `test_bb.py:82-101`. Test body (verbatim, line 95-99):

```python
out = BollingerBandsIndicator().compute(candles, BbParams(length=20))
factor = math.sqrt(20 / 19)
raw_half_width = raw_upper[-1] - raw_middle[-1]
pine_half_width = out["upper"][-1] - out["middle"][-1]
assert abs(pine_half_width - raw_half_width * factor) < 1e-9
```

The test explicitly asserts that `BollingerBandsIndicator`'s output band width equals `raw_TALib_band_width × sqrt(20/19)` — i.e. that the now-removed correction WAS applied. The "Pine compat" in the test name is **factually misleading**: the correction made bands *less* like Pine, not more (per Phase F deviation analysis). The test is testing the bug's presence, not Pine compatibility.

Empirical failure message confirms the diagnosis precisely:

```
E   assert np.float64(0.8506898697613892) < 1e-09
E    +  where 0.8506898697613892 = abs((32.7461 − 32.7461 × 1.02598))
```

The 0.85 absolute difference is exactly the inflation factor `(sqrt(20/19) − 1) × raw_half_width` — the bug's amplitude.

## Why it wasn't anticipated in the resume spec

The resumed sprint spec said *"Verify: `pytest backend/tests/services/indicators/test_bb.py -v` → expected PASS"* — but the spec authors didn't grep through `test_bb.py`'s individual test bodies to find that one of the 11 tests pins the bug's behaviour in place. It's the same pattern as Finding #2's "Part 2 was wrong" trigger: a downstream assumption based on a higher-level pass/fail expectation that doesn't survive contact with the actual test body.

## Authorization-scope question

The user's resume spec listed exactly two existing files as ALLOWED for edit:

- ✅ `backend/app/services/indicators/bb.py` lines 67-72
- ✅ `backend/tests/services/indicators/fixtures/bb_expected.csv`

The earlier "broader Phase F" guardrails included *"ZERO edits to existing test files."* `test_bb.py` is on neither the allow nor the deny list explicitly, but the broader rule + the resumed-sprint scope strongly imply it's off-limits without expanded authorization.

## Three options (founder picks)

### Option α₁ — Delete `test_bb.py::test_pine_compat_correction_applied` (one-time existing-test edit)

The test tests the absence of a bug-fixing change. After the fix, the test has no positive purpose. Deletion is the minimum-touch authorized edit.

- Files touched: `test_bb.py` (delete 20 lines)
- Cost: trivial
- Risk: zero — the new `test_indicators_phase_f_reference.py::test_bollinger_matches_pine_reference` already validates the Pine-correctness of BB output against an independent fixture, so coverage is preserved (and improved).

**This is my recommendation.** Cleanest outcome — the bad test goes away, the new authoritative test stays.

### Option α₂ — Invert the test to assert NO correction is applied

Change lines 95-99 to assert `pine_half_width == raw_half_width` instead of `× factor`. Renames the test (`test_no_bessel_correction_applied`) to reflect what's actually being tested.

- Files touched: `test_bb.py` (rewrite ~10 lines)
- Cost: small
- Risk: zero
- Tradeoff vs α₁: keeps a regression-trip wire that catches any future "let's add a stddev correction" patch by accident. Minor coverage value.

### Option α₃ — xfail the test (least surgical)

Mark with `@pytest.mark.xfail(reason="Test asserts presence of removed Bessel correction — see Finding #3", strict=False)`.

- Files touched: `test_bb.py` (3-line decorator)
- Cost: trivial
- Risk: leaves dead-test surface in the file forever; readers will wonder why it's xfailed
- Not recommended — α₁ or α₂ is cleaner

## What I committed before halting

| Commit | Subject |
|---|---|
| `63932b0` | `fix(indicators):` BB stddev — remove erroneous Bessel correction at bb.py:67-72 (authorized override) |
| `333b675` | `test(indicators):` regenerate bb_expected.csv against Pine reference (authorized override) |

## What I did NOT execute (Steps 3-5 of resume spec)

- ❌ MACD xfail marker in `test_indicators_phase_f_reference.py` (Finding #2)
- ❌ Full test suite verification
- ❌ `BACKTEST_USAGE.md`
- ❌ `PATCH_INSTRUCTIONS_PHASE_F_COMPONENT_1.md`
- ❌ `PHASE_F_OVERRIDE_LOG.md` (with the two entries you specified)

These are all clean follow-ons once the test_bb.py question is resolved. No new investigation needed — just execute the spec.

## Awaiting your call (Finding #3 only)

Option α₁ / α₂ / α₃ to resolve the test_bb.py question. Once authorized, the remaining Steps 3-5 of the resume spec execute back-to-back without further pause.


