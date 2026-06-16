# Queue III — `test_placeholder_prefixes_registered` pollution analysis

**Status: NOT FIXED this session (overnight, unattended). Baseline stays in place** — it is correctly marked TEMPORARY in `ci/known_failures.txt`. This doc gives the next attended session everything needed to fix it.

**Branch:** `chore/queue-iii` · **Date:** 2026-06-16 · **No code/test change applied** (see "Why not auto-fixed" below).

---

## TL;DR

`tests/test_main.py::TestRouters::test_placeholder_prefixes_registered` fails **only in CI**, as a single "new" failure over the 44-baseline. It is a **test-pollution / collection-order flake**, NOT a product bug. **Key correction to the original premise:** it is **NOT DB-related** — the CI backend job runs the suite with **no Postgres/Redis at all** (no `services:` block, no `docker-compose-test` up — see `.github/workflows/ci.yml`), exactly like a local no-DB run. So "stand up local PG/redis to reproduce" does **not** apply. The differentiator is the **CI environment + collection order** (ubuntu-latest + fresh `pip install -e .[dev]`), which does **not reproduce** on the macOS dev venv.

## Evidence

| Run | DB present? | `test_placeholder` result | suite |
|---|---|---|---|
| **Local** (macOS, `backend/.venv`, full suite) | no | **PASS** | 44 failed / 4286 passed |
| **CI** (ubuntu, fresh install, full suite) | no | **FAIL** | 45 failed / 4285 passed |

- Backend code is **byte-identical** between the last green main and the commit where CI first went red (`git diff 62f84f3..68e144c -- backend/` is empty — only a frontend file changed). So it is not a code regression — purely environment/order.
- The CI failure assertion: `assert '/health' in {'', '/docs', '/docs/oauth2-redirect', '/openapi.json', '/redoc'}` → the app under test has **only FastAPI default routes**, i.e. `create_app()` registered **zero** application routers.

## Mechanism (root-cause shape)

- The `app` fixture (`tests/test_main.py:47`) is **function-scoped**: it mocks DB/Redis then calls `create_app()` **fresh per test**. So this is **not** simple shared-app-instance leakage.
- `create_app() → _register_routers(app)` (`backend/app/main.py:179+`) does ~30 **unconditional** `include_router(...)` calls with **no try/except**. A failed router *import* would therefore **raise** (test would ERROR), not silently yield a router-less app.
- Yet CI sees a router-less app from a *successful* `create_app()`. That points to a prior test **poisoning router registration at the module/import level** under CI's collection order — e.g. a leaked `monkeypatch`/`setattr` on `app.main` / a router module, an `importlib.reload`, or a `sys.modules` mutation whose restore interacts badly with CI's ordering.

### Suspects to check first (code-analysis, not yet confirmed)
- `tests/test_notification_service.py:180,204` — `with patch.dict("sys.modules", {"boto3": mock_boto})` (context-managed, *should* restore — but verify under CI order).
- The many `create_app()` call sites that also `app.include_router(...)` / set `app.dependency_overrides[...]` on their own apps: `test_strategy_tester_api.py`, `test_trade_markers_api.py`, `test_kill_switch_api.py`, `auth/test_require_admin.py`, `test_webhook*.py`, `tests/integration/*`. Most are function-scoped (own app), so unlikely — but a leaked `monkeypatch.setattr` on a shared module target is the prime vector.

## Recommended fix path (next ATTENDED session, with a CI-like env)

1. **Reproduce in a CI-matching container** (the only place it manifests):
   `docker run --rm -it -v "$PWD":/w -w /w/backend python:3.11-slim bash -lc "apt-get update && <ta-lib install> && pip install -e '.[dev]' && PYTEST_BIN=python ../ci/check_pytest_baseline.sh"` (mirror `ci.yml` steps 90–134).
2. **Bisect the polluter:** run `pytest tests/test_main.py::TestRouters::test_placeholder_prefixes_registered` alone (passes), then prepend progressively larger slices of the alphabetical collection until it flips to FAIL → the last-added file contains the polluter. `pytest -p no:cacheprovider` (matches the gate). Consider `pytest --forked` to confirm it's in-process pollution.
3. **Fix the isolation** at the source: make the polluting test context-manage / restore its mutation, OR add an `autouse` conftest fixture that snapshots+restores `sys.modules` (and any `app.main` attribute it patches) around each test. Do **not** mask it by reloading inside the assertion test, and do **not** change production `create_app`/`_register_routers` (sacred-adjacent + the founder's "no existing-endpoint-logic change" rule).
4. **Un-baseline** `tests/test_main.py::TestRouters::test_placeholder_prefixes_registered` (remove its line + comment block from `ci/known_failures.txt`) **only after** CI confirms green on the fix.

## Why not auto-fixed / un-baselined this session
- Cannot reproduce locally → **cannot verify** any candidate fix.
- Un-baselining an unverified fix would risk turning CI **red** for every PR, violating the overnight guardrail "Build/test fail → leave branch last-good."
- A CI-matching container build (ta-lib compile ~3–5 min) + multi-run bisect is a long, uncertain task unsuited to unattended overnight work, for the lowest-value module (one already-baselined flaky test). Per the module's own escape clause ("too risky → document + stop"), stopping here is the correct call.
