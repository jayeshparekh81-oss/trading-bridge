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
