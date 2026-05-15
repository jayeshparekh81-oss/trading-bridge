# TECH DEBT — pre-existing test failures (snapshot at Phase A wire-up)

Branch: `feat/phase-a-markers`  •  Snapshot date: 2026-05-15  •  Author: Claude (parallel-CC session)

The full backend test suite was run as part of the Phase A trade-markers
router + model-registry wire-up. Result: **3546 passed, 11 failed**
(coverage 89%, 69.77s).

The 11 failures listed below were verified to be **pre-existing**:

- I stashed the two-file Phase A wire-up edit and re-ran the same 11
  tests against the baseline `feat/phase-a-markers` HEAD —
  **all 11 failed identically without my changes** (same error
  messages, same line numbers).
- None of the failing tests touch `trade_markers`, the marker model,
  the `/api/markers` route, or the model-registry `__all__` list. The
  failure surfaces are entirely orthogonal: HMAC signature validation,
  CORS preflight, Celery beat schedule, the
  `'Depends' object has no attribute 'execute'` shape in
  `app/api/users.py:317`, and a Telegram alert wiring assertion.
- The failures exist on `origin/main` and predate Phase A.

Phase A was committed despite these failures because the wire-up is
functionally correct and the regressions are orthogonal. They are
parked here for a separate sprint to triage and fix.

---

## Failing tests (11)

### Category: HMAC / webhook signature (3)

- `tests/integration/test_strategy_webhook_paper_e2e.py::TestSignature::test_invalid_signature_returns_401`
- `tests/integration/test_strategy_webhook_paper_e2e.py::TestSignature::test_missing_signature_returns_401`
- `tests/integration/test_strategy_webhook_tv_ip_bypass.py::TestNonTvIpStillRequiresHmac::test_random_ip_without_hmac_returns_401`

Observation: Strategy-webhook signature/IP-bypass guards not returning
the expected 401. Likely a single root cause in the HMAC verification
path or the dependency override used by these integration tests.

### Category: CORS (1)

- `tests/test_main.py::TestCORS::test_preflight_headers`

Observation: `assert 400 in (...)` — preflight returning 400 instead of
the expected status. Could be a Starlette/FastAPI version drift
interacting with `CORSMiddleware` config or a missing
`Access-Control-Request-Method` header in the test fixture.

### Category: Celery (2)

- `tests/test_celery_tasks.py::TestAutoSquareOff::test_runs`
- `tests/test_celery_tasks.py::TestCeleryApp::test_beat_schedule_populated`

Observation: Celery app / beat-schedule wiring or auto-square-off task
shape has drifted from what the tests expect. Often a sign of a
config-key rename or a registered-task-name mismatch.

### Category: users.py — Depends-vs-session shape (3)

- `tests/test_users_api.py::TestBrokers::test_add_broker`
- `tests/test_users_api.py::TestBrokers::test_reconnect_broker`
- `tests/test_coverage_round2.py::TestUsersNotFoundPaths::test_reconnect_broker_not_found`

Observation: All three blow up at
`app/api/users.py:317` with
`AttributeError: 'Depends' object has no attribute 'execute'`. A
`Depends(...)` is being used directly as a session — almost certainly a
missing `db: AsyncSession = Depends(get_session)`-style annotation, or
a handler that captured the `Depends` object instead of the resolved
dependency value. Fix is likely 1–3 lines in `users.py`.

### Category: Celery extra coverage (1)

- `tests/test_coverage_round3.py::TestKillSwitchTasksExtraCoverage::test_auto_square_off_task`

Observation: Same family as the Celery failures above — kill-switch /
auto-square-off task wiring drift.

### Category: Telegram alert wiring (1)

- `tests/integration/test_telegram_alerts.py::TestOrderPlacedAlertWiring::test_paper_buy_fires_info_and_success_alerts`

Observation: Paper-buy execution path expected to fire both INFO and
SUCCESS Telegram alerts; one (or both) of those alert calls is missing.
Likely a regression in the order-placement notification dispatch.

---

## TODO

- [ ] Triage the `users.py:317` `Depends`-as-session shape (highest
      blast radius — three failing tests, looks like a one-line bug).
- [ ] Resolve the HMAC / signature trio (likely a shared root cause).
- [ ] Investigate Celery beat-schedule drift (two related failures +
      one auto-square-off).
- [ ] Verify Telegram paper-buy alert wiring (one failure, low risk).
- [ ] CORS preflight regression (one failure, possibly framework-version).

Owner: TBD (separate sprint).
