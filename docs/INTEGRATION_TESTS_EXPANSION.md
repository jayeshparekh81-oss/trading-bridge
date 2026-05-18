# Integration Tests Expansion

**Branch:** `feat/integration-tests-expansion`
**Date:** 2026-05-17 → 2026-05-18
**Builds on:** `docs/INTEGRATION_TEST_FRAMEWORK.md`

---

## TL;DR

4 new integration test files at `backend/tests/integration_e2e/`,
totalling 16 tests (14 pass, 1 skipped, 1 pandas-ta-gated module).
Each catches a category of bug visible in May-17 incident reports.

```
backend/tests/integration_e2e/
    __init__.py                                    NEW (empty)
    test_template_clone_full_flow.py               NEW (2 tests)
    test_strategy_crud_with_origin.py              NEW (7 tests)
    test_indicator_runner_cross_validation.py      NEW (skipped — needs pandas-ta)
    test_seed_loader_idempotency.py                NEW (5 tests)
```

Path note: spec said `backend/tests/integration/`, but the existing
`tests/integration/conftest.py` imports the full app dep tree
(including `bcrypt` which isn't installed in the lightweight test
env). The new tests live in a sibling `tests/integration_e2e/` so
they don't inherit the heavy conftest. They still test end-to-end
flows.

---

## What each test file catches

### `test_template_clone_full_flow.py` — 2 tests

**Catches:** the May-17 clone-flow UX bug — clone POST creates Strategy
with `strategy_json=None` + a `strategy_template_origin` row, but the
detail page's GET endpoint doesn't surface the origin (regression
shield for `fix/strategy-detail-clone`).

| Test | What it asserts |
|---|---|
| `test_clone_then_detail_surfaces_template_origin` | POST /api/templates/{slug}/clone → 201 → GET /api/strategies/{id}.template_origin is populated with slug/name/category/complexity/cloned_at/config_json |
| `test_handbuilt_strategy_detail_has_no_template_origin` | Belt-and-braces — hand-built Strategy (POST /api/strategies) has template_origin=None |

### `test_strategy_crud_with_origin.py` — 7 tests

**Catches:** regressions where a CRUD endpoint change breaks one row
type while passing tests on the other.

| Test | What it asserts |
|---|---|
| `test_list_contains_both_handbuilt_and_cloned` | LIST endpoint returns both row types; template_origin is NOT in list response (perf decision) |
| `test_get_cloned_strategy_has_origin` | GET on cloned → template_origin populated |
| `test_get_handbuilt_strategy_has_no_origin` | GET on hand-built → template_origin null |
| `test_put_handbuilt_strategy_does_not_create_origin` | PUT (rename, etc.) doesn't spawn a template_origin row |
| `test_delete_handbuilt_strategy_404s_subsequent_get` | DELETE → 204 → subsequent GET → 404 |
| `test_delete_cloned_strategy_cascade_origin` | DELETE on cloned → strategy gone + origin row cascade-deleted via FK |
| `test_clone_unknown_template_returns_404` | POST /api/templates/<unknown-slug>/clone → 404 |

### `test_indicator_runner_cross_validation.py` — 10 reference tests (module-level skip if pandas-ta missing)

**Catches:** silent indicator math drift from upstream Pine / TA-Lib.
For each of the 10 most-used indicators (SMA, EMA, WMA, RSI, ATR,
Heikin-Ashi, KAMA, OBV, VWAP, MACD), computes our series + pandas-ta
reference, asserts max abs diff is within tolerance.

Tolerances:
- SMA, WMA: < 1e-9 (exact match expected)
- EMA: < 1e-4 (Wilder smoothing accumulates tiny float error)
- RSI, MACD, KAMA, ATR: < 1e-2 (Wilder + smoothing accumulates)
- OBV, Heikin-Ashi close: < 1e-6 / < 1e-9 (no smoothing)
- VWAP: sanity-bound test only (pandas-ta needs DatetimeIndex)

Pandas-ta is NOT in `pyproject.toml` deps. The whole file's tests
skip via `pytest.importorskip` if absent — graceful, no CI red.

### `test_seed_loader_idempotency.py` — 5 tests

**Catches:** seed-loader double-run safety. The May-17 deploy
runbook re-runs `python -m app.templates.scripts.seed_strategy_templates`
on every deploy.

| Test | What it asserts |
|---|---|
| `test_first_run_inserts_all_rows` | Fresh DB → 3 INSERTs, 0 UPDATEs |
| `test_second_run_updates_all_rows_no_new_inserts` | Same seed again → 0 INSERTs, 3 UPDATEs |
| `test_row_count_stable_across_runs` | row count constant before/after re-run |
| `test_row_data_stable_across_runs` | every column snapshot byte-for-byte identical |
| `test_seed_edit_updates_existing_row_in_place` | Edit seed → row UPDATE (same id, new content); `created_at` preserved |

---

## Hard constraints honoured

- ✅ All tests run via existing pytest infrastructure (no new test runner)
- ✅ All tests self-contained — own setup/teardown, in-memory aiosqlite
- ✅ NO modifications to existing tests
- ✅ NO bugs in existing code surfaced; if any did, surfacing in BLOCKERS would precede a fix on a separate branch (none did this branch)

---

## See also

- `docs/INTEGRATION_TEST_FRAMEWORK.md` — Queue I Task 3 base framework
- `backend/tests/deploy_path/test_deploy_path.py` — Tier-1 static-analysis shield
