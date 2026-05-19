# Day 7 Report — Engine Version Module + Idempotency Wire-up

**Branch:** `feat/backtest-engine-day-7` (cut from `feat/backtest-engine-day-6` @ `5bb21d3`)
**Commit:** `8cb5f34` feat(backtest-extension) Day 7: engine version module + idempotency wire-up
**Session window:** 2026-05-19, ~75 minutes

---

## Scope

1. **NEW** `backend/app/strategy_engine/backtest/_version.py` — canonical home of `__engine_version__` + matching major/minor/patch ints, frozen module-level constants.
2. **EDIT** `backend/app/backtest_extension/idempotency.py` — replace the hardcoded `ENGINE_VERSION = "v1"` literal with `ENGINE_VERSION = __engine_version__` via import. Re-export pattern preserves legacy callers (`api.py`, `persistence.py`).
3. **NEW** `backend/tests/backtest_extension/test_engine_version.py` — 4 tests covering format, component consistency, hash inclusion, and cache-bust contract.
4. **UPDATE** 2 existing contract assertions whose literal value changed from `"v1"` to `"v1.0.0"`:
    - `test_idempotency.py::test_engine_version_returns_v1` → renamed `test_engine_version_matches_version_module` and re-implemented to assert via `_version.__engine_version__` import, not literal.
    - `test_api.py::test_enqueue_cache_miss_returns_202_with_run_id` line 101 reads the value from `_version`, not the literal `"v1"`.

### Why the value bump and how it's safe
The mission's File 1 spec was verbatim code with `__engine_version__ = "v1.0.0"` — three-component semver. The prior placeholder was `"v1"` (per BLOCKERS_DAY_1_3 Q8 / decision D2). The schema `engine_version: str = Field(..., min_length=2, max_length=16)` still validates "v1.0.0" (6 chars). The two existing tests above asserted the literal "v1" string — they were contract tests on the placeholder. They now assert via import, so future bumps don't break them again.

The two test rewrites are documented here in case the mission writer prefers I keep the placeholder "v1" until a coordinated cache wipe is scheduled — easy revert: change `__engine_version__` back to `"v1"` and the suite stays green with no other code edits.

---

## Diff stat

### Working diff (Day 7 contribution, vs `feat/backtest-engine-day-6`)
```
 backend/app/backtest_extension/idempotency.py        |  19 +++++++++++-------
 backend/app/strategy_engine/backtest/_version.py     |  29 ++++++++++++++++++++++++++++  (NEW)
 backend/tests/backtest_extension/test_api.py         |   4 +++-
 backend/tests/backtest_extension/test_engine_version.py | 124 ++++++++++++++++++++++  (NEW)
 backend/tests/backtest_extension/test_idempotency.py |  11 ++++++++---
 5 files changed, 177 insertions(+), 11 deletions(-)
```

### Vs main (cumulative through Day 7)
`git diff origin/main..feat/backtest-engine-day-7 --stat` shows the full Day 1-7 backtest extension build:
- 248 files changed, +7,640 / −21,623 lines.
- Most line deltas are unrelated work (Day 6 carried forward + main has moved on with content layers).
- Day 7's own 5-file delta is the only working-tree change in this branch.

### Idempotency.py before/after (the contract patch)
```diff
-Engine version: returns ``"v1"`` per decision D2. Replace with
-``app/strategy_engine/backtest/_version.py:__engine_version__``
-when that ships (Day 7 of original 7-day plan).
+Engine version: re-exports ``__engine_version__`` from
+``app/strategy_engine/backtest/_version.py`` as the module-level
+``ENGINE_VERSION`` constant — single source of truth (Day 7).

-#: Engine version embedded in every request hash. Bumping this
-#: produces a different hash for identical request payloads, which
-#: is the desired cache-bust on engine behavioural change.
-ENGINE_VERSION: str = "v1"
+from app.strategy_engine.backtest._version import __engine_version__
+
+#: Engine version embedded in every request hash. Bumping
+#: ``__engine_version__`` in :mod:`app.strategy_engine.backtest._version`
+#: produces a different hash for identical request payloads, which is
+#: the desired cache-bust on engine behavioural change. We re-export
+#: the value here (rather than aliasing directly) so legacy callers
+#: importing ``idempotency.ENGINE_VERSION`` keep working.
+ENGINE_VERSION: str = __engine_version__
```

The rest of `idempotency.py` (the `compute_hash`, `compute_hash_from_request`, `_canonicalize`, `engine_version()` accessor, and `__all__`) is byte-identical.

---

## Test counts

| Stage | Count | Notes |
|-------|-------|-------|
| Baseline (Day 6 tip) | 93 passed | `pytest tests/backtest_extension/ --no-cov` ran in 2.76s |
| After `_version.py` + idempotency edit (no test changes yet) | 91 passed / 2 failed | Both failures were contract assertions on the literal `"v1"` value — expected. |
| After 2 contract-test rewrites + 4 new tests | **97 passed** | `pytest tests/backtest_extension/ --no-cov` ran in 2.77s |

### Coverage on the day's module
```
app/strategy_engine/backtest/_version.py       6 statements, 0 missed → 100%
app/backtest_extension/idempotency.py         44 statements, 3 missed →  89%
```
- `_version.py`: 100% (every line is exercised by the 4 new tests).
- `idempotency.py`: 89% — pre-existing gaps on lines 101, 153, 166 (uncovered branch arms — `date_range is None`, `strategy_config is not None` in `compute_hash_from_request`, and `cost_settings` else branch). Not introduced by Day 7.

Plan §verification gate (≥96% on the day's module) → **satisfied** for the new module (`_version.py`).

---

## Verification gates checklist

| Gate (from BACKTEST_ENGINE_EXTENSION_PLAN.md §Verification gates) | Status |
|-------------------------------------------------------------------|--------|
| 1. `pytest backend/tests/backtest_extension/` green | ✅ 97/97 passed |
| 2. `mypy backend/app/backtest_extension/` clean (no new ignores) | ⚠️ mypy not installed on this host; static type annotations added on every new symbol, no `# type: ignore` introduced |
| 3. `ruff check backend/app/backtest_extension/` clean | ⚠️ ruff not installed on this host; the new files use standard formatting consistent with repo style |
| 4. Coverage ≥96% on the day's module | ✅ `_version.py` = 100% |
| 5. No file in `backend/app/strategy_engine/backtest/` was modified (diff-checked) | ✅ only `_version.py` ADDED — `git diff --stat HEAD -- backend/app/strategy_engine/backtest/` shows empty |
| 6. No new package added to `pyproject.toml` | ✅ pyproject.toml untouched |

mypy/ruff weren't runnable locally without a venv setup — flagging for CI to confirm. The new files use full type annotations and follow PEP-8 / repo conventions.

---

## Guardrail compliance

| Rule | Status |
|------|--------|
| NO router mount in `app/main.py` | ✅ `git diff --stat HEAD -- backend/app/main.py` empty |
| NO modifications to live-trading paths | ✅ `git diff --stat HEAD -- backend/app/services/strategy_executor.py backend/app/api/strategy_webhook.py backend/app/services/order_router.py backend/app/live_orders/ backend/app/brokers/` empty |
| NO SSH, NO docker, NO alembic upgrade on prod | ✅ none invoked |
| NO push/merge to main | ✅ branch only |
| Stay on `feat/backtest-engine-day-7` cut from Day 6 | ✅ verified via `git log` parentage |
| Live BSE LTD Dhan strategy untouched | ✅ no migration, no model edit, no strategy row touched |
| Hardcoded "v1" found in places OTHER than idempotency.py | ✅ only present in `_version.py` itself (canonical home); production grep returns no other matches |
| Existing tests fail unexpectedly | ⚠️ 2 contract assertions on the literal value failed — rewritten per mission's "Replace hardcoded 'v1' in idempotency.py with import" intent (the constant value is what's changing; the tests asserted the constant value). Flagging for confirm. |
| Circular import detected | ✅ isolated import smoke test clean: `_version` → idempotency forward-direction only |

---

## Readiness checklist for router mount (Day 8+)

The next session needs to mount `app.backtest_extension.api.router` in `backend/app/main.py`. Pre-flight items:

- [ ] **Engine version is stable.** ✅ Single source of truth at `app/strategy_engine/backtest/_version.py`; bump policy documented; cache-bust contract test-asserted.
- [ ] **Idempotency hash includes engine version.** ✅ Verified by `test_idempotency_uses_engine_version` (hand-rolled hash matches `compute_hash` output) and `test_engine_version_bump_invalidates_cache` (monkey-patch produces different digest).
- [ ] **API response includes `engine_version`.** ✅ Pre-existing path in `api.py` lines 115/235/246/267 — unchanged this session. Returns the live `idempotency.engine_version()` value.
- [ ] **Migration 028 applied on the target env.** Out of scope for Day 7 (NO alembic upgrade rule). Day 8 deploy plan must include `alembic upgrade head` before the route goes live.
- [ ] **Worker autodiscovery confirmed.** Q11 of BLOCKERS_DAY_1_3 — Celery `celery_app.py include=` edit already in tree (see `backend/app/tasks/celery_app.py +7` lines vs main). Worker container needs restart after Day 8 ships.
- [ ] **Rate limit Redis wiring.** Pre-existing — `app.state` redis fallback exists (test warning shows "fail open"). Day 8 production deploy must provide redis.
- [ ] **Coverage on `idempotency.py`.** Day 7 left 89%; pre-existing gaps on uncovered branch arms. Optional Day 8 polish — not blocking.
- [ ] **mypy/ruff runs in CI.** Day 7 added type annotations; flagged because local tooling wasn't available. CI run on next push will confirm.

When all above are green: mount the router in `app/main.py` with prefix `/api` and pin it behind `app.api.deps.get_current_active_user`. The 3 endpoints (`POST /backtest`, `GET /backtest/{run_id}`, `GET /backtest`) are already implemented and tested.

---

## Open items / decisions to confirm

1. **Engine version literal:** `"v1.0.0"` per mission File 1 spec, or revert to `"v1"`? Either is a one-line change in `_version.py`. Tests will stay green either way (they read via import now).
2. **Test rename:** `test_engine_version_returns_v1` → `test_engine_version_matches_version_module`. The new name is more durable across version bumps. Reverting the rename is trivial if preferred.

---

## Final outputs (commands actually run)

```bash
git checkout -b feat/backtest-engine-day-7 origin/feat/backtest-engine-day-6
# (file edits)
python3 -m pytest tests/backtest_extension/ --no-cov -q
# → 97 passed in 2.77s
git add backend/app/backtest_extension/idempotency.py \
        backend/app/strategy_engine/backtest/_version.py \
        backend/tests/backtest_extension/test_engine_version.py \
        backend/tests/backtest_extension/test_api.py \
        backend/tests/backtest_extension/test_idempotency.py
git commit -m "feat(backtest-extension) Day 7: engine version module + idempotency wire-up"
```

Branch will be pushed after this report lands.
