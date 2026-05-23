# Webhook Async Refactor — Notes (Bug #2 / Phase 2C)

**Branch:** `feat/webhook-async-tests-docs` (off `main` @ `3f8dd65`)
**Date:** 2026-05-24 (Sunday — markets closed)
**Scope chosen:** *Cover + document the existing implementation.* No change to
the live webhook handler or the BSE-LTD `89423ecc` execution path.

---

## 0. TL;DR — the premise changed under us

The Phase 2C work-order assumed the webhook handler "processes the signal
synchronously, ~4 s response time" and asked us to refactor it into a
two-phase async flow using FastAPI `BackgroundTasks`.

**That refactor already exists on `main`.** `backend/app/api/strategy_webhook.py`
already:

- returns **`202 Accepted`** the moment the audit row is written, and
- runs all execution (AI-validate → broker) in
  `_process_signal_in_background` / `_process_direct_exit_in_background`
  via `BackgroundTasks.add_task(...)`.

The two-phase pattern dates back to the foundational commit `cda3cb6`, and
**all six 2026-05-20 fixes are already present** in that background path.

What was actually *missing* (and is what this branch delivers) was the
**test coverage + documentation** for that async behaviour, because the
only async test suite (`test_strategy_webhook_async.py`) lived on the
abandoned Celery branch (see §6).

So this branch is **additive**:

| Deliverable | File |
|---|---|
| Async-contract test suite (19 tests) | `backend/tests/integration/test_strategy_webhook_async.py` |
| Per-`signal_id` idempotency helper (additive, not yet wired) | `backend/app/core/signal_idempotency.py` |
| This document | `WEBHOOK_ASYNC_NOTES.md` |

Nothing in `strategy_webhook.py`, the executor, the brokers, the kill
switch, reconciliation, or any migration was touched.

---

## 1. Latency — before / after

| Phase | Before (the bug) | Now (already on `main`) |
|---|---|---|
| Synchronous response | signal validated **and executed** inline → ~4 s, blew TradingView's 5 s timeout → "Webhook delivery failed" | Phase 1 only (auth → rate-limit → HMAC → idempotency → persist → schedule), returns `202` |
| Execution | inside the request | `BackgroundTasks`, after the response is sent |

**Phase 1 budget:** < 200 ms.
`test_phase1_responds_under_200ms` measures the synchronous request path
with `perf_counter` (the background coroutine is stubbed to a no-op so the
measurement is Phase 1 only — TestClient otherwise runs `BackgroundTasks`
inline before `.post()` returns). It passes with comfortable margin on the
in-memory harness.

> Caveat worth flagging for a real-world latency audit: Phase 1 still does a
> handful of awaits before returning — token lookup, rate-limit, kill-switch,
> user/max-trades, strategy resolve, and **symbol normalization**
> (`futures_resolver.resolve_or_passthrough`, which can consult the Dhan
> scrip master). If a production "~4 s" is ever observed *after* this branch,
> the suspect is symbol normalization in Phase 1, **not** the executor — and
> that resolver is on the frozen `89423ecc` path, so any change there is a
> separate, carefully-scoped task.

---

## 2. Failure-mode matrix (as implemented on `main`, pinned by the new tests)

| Scenario | Phase | `signal.status` | Telegram | Position created? | Test |
|---|---|---|---|---|---|
| Duplicate signal (idempotency hit) | 1 | — (no new row) | — | no | `test_duplicate_signal_id_returns_duplicate` |
| Distinct signal | 1 | `received` → … | — | — | `test_distinct_signal_id_processes_independently` |
| Happy path (paper) | 2 | `received → executed` | INFO 📝 *PAPER MODE* | yes | `test_background_success_marks_executed` |
| Broker order rejected (`BrokerOrderRejectedError`) | 2 | `failed` | **CRITICAL** 🚨 *BROKER REJECTED* + reason | **no** (Fix #5 short-circuit) | `test_background_broker_rejection_marks_failed_no_phantom_position` |
| Unexpected `Exception` | 2 | `failed` (`notes="unexpected: …"`) | **CRITICAL** *Backend error in executor* | no | `test_background_unexpected_exception_marks_failed` |
| Broker filled (`complete`/`traded`) | 2 | `executed` | SUCCESS ✅ *Order filled* | yes | taxonomy param |
| Broker accepted, pending (`pending`/`open`) | 2 | `executed` | INFO ⏳ *awaiting fill* | yes | taxonomy param |
| Broker unknown status | 2 | `executed` | WARNING ⚠️ *verify manually* | yes | taxonomy param |

### Idempotency, as actually shipped

- **Where:** Phase 1, before any business gate.
- **How:** `redis_client.set_idempotency_key(signal_hash, ttl=60)` →
  `SET key 1 NX EX 60` (atomic; the race loser reads `False`).
- **Key:** `idem:{user_id}:{signal_id-from-payload}` if the alert carries a
  `signal_id`, else `idem:{user_id}:{sha256(raw_body)}`. The content-hash
  fallback dedupes a TradingView retry **even when the alert has no explicit
  id** — which the work-order's "key on `signal_id` only" scheme would not.
- **Duplicate response:** `200 {"status": "duplicate", ...}` (not `409`).

> The work-order asked for a new helper
> `check_and_set_signal_idempotent(redis, signal_id)` keyed on
> `signal:idempotency:{signal_id}` with a 3600 s TTL. That helper is delivered
> in `app/core/signal_idempotency.py` and unit-tested, but **intentionally not
> wired into the live handler** — the production path keeps its proven
> content-hash claim (above). The helper is available for adoption if/when a
> caller mints stable signal ids and wants the longer 1 h window. Wiring it in
> would change live dedupe semantics on `89423ecc`, which is out of scope here.

---

## 3. Why FastAPI `BackgroundTasks`, not Celery

- **Celery worker is unhealthy** (pre-existing, CLAUDE.md §2). Routing the
  hot path through an unhealthy worker would mean signals silently queue and
  never execute — strictly worse than the inline executor we're replacing.
- The earlier `feat/webhook-async-refactor` branch (commit `038377b`, "Bug #2
  … 202 fast path + **Celery worker**") did exactly that: it moved execution
  into `app/tasks/signal_execution.py` (a Celery task `execute_signal_async`)
  and stripped 531 lines out of `strategy_webhook.py`. It was **never merged**
  and is superseded by `main`'s `BackgroundTasks` design.
- `BackgroundTasks` runs in the same process, after the response is flushed.
  No broker, no message bus, no extra moving part to be unhealthy. For a
  single-box deployment with one hot path, this is the right amount of
  machinery.

### Trade-off being accepted

`BackgroundTasks` are **in-process and not durable**: if the process is
killed between the `202` and the broker call, that signal's execution is
lost (the audit row remains at `received`/`validating`). This is acceptable
today because (a) TradingView alerts are idempotent-retried and (b) the
reconciliation loop catches positions that drift from broker truth. It is
the main reason to migrate to a durable queue once the worker is healthy.

---

## 4. Migration path to Celery (Phase 3, when the worker is healthy)

The seam already exists — only the dispatch line changes:

1. Fix worker health (Phase 3, out of scope here).
2. Re-home the body of `_process_signal_in_background` into a Celery task
   (the abandoned `app/tasks/signal_execution.py` from `038377b` is a
   reference, not a drop-in — it predates the 2026-05-20 fix series and would
   need them re-applied).
3. Swap `background.add_task(_process_signal_in_background, str(signal.id))`
   → `execute_signal_async.delay(str(signal.id))`. Phase 1 is unchanged.
4. Keep the `BackgroundTasks` path behind a feature flag for instant
   fallback until the worker has soaked.
5. **Re-validate all six fixes** against the Celery path before cutover (the
   smoke tests in the new suite are the checklist).

Durability bonus once on Celery: en/exit the longer-window
`check_and_set_signal_idempotent` helper (§2) at the task boundary for
at-least-once-safe dedupe.

---

## 5. Rollback plan

This branch adds **only** a test file, a new helper module, and this doc —
no runtime wiring, no schema, no behavioural change.

- **Revert:** `git revert <merge-commit>` (or just delete the three files).
  Nothing else depends on them; the live handler is byte-for-byte `main`.
- **No DB migration** was added, so there is **nothing to roll back in the
  database**.
- The SQLite `@compiles(JSONB, "sqlite")` shim lives **inside the new test
  file** and is dialect-scoped to `sqlite`; it cannot affect Postgres
  (prod/CI) and disappears with the file.

---

## 6. Signal status enum gap (flagged for Phase 3 if needed)

`StrategySignal.status` is a free **`String(32)`** column with
`server_default="received"` — **no DB enum, no CHECK constraint**. So new
status strings need *no migration*; the only risk of inventing them is that
existing queries/dashboards that filter on the documented vocabulary would
stop seeing those rows.

- **Documented vocabulary:** `received | validating | rejected | executing |
  executed | failed` (+ `ignored`, `held` from the Market-Shield port).
- **Work-order asked for:** `queued`, `completed`.
- **Decision:** reuse the documented values — `queued → received`,
  `completed → executed` — exactly as the work-order's fallback rule
  ("use closest existing values") instructs. The new tests assert the values
  `main` actually writes (`received` / `executed`), not the work-order's
  aspirational names.
- **If Phase 3 wants first-class `queued`/`completed`:** add them as new
  allowed strings (still no migration needed for the column itself), then
  audit every status filter in the API, reconciliation, and the dashboard so
  the new states stay visible. Until that audit is done, reusing the existing
  vocabulary is the safe choice.

---

## 7. ⚠️ Blocker discovered: integration suite cannot run on local SQLite

**Pre-existing, not introduced by this branch.**

`app.main` registers `app.templates.models.StrategyTemplate`, whose
`config_json`/etc. columns use `postgresql.JSONB`. The integration harness
(`tests/integration/conftest.py`) runs `Base.metadata.create_all` against
**in-memory aiosqlite**, and SQLite's compiler cannot render `JSONB`:

```
sqlalchemy.exc.CompileError: (in table 'strategy_templates', column 'config_json'):
  Compiler ... can't render element of type JSONB
```

On a clean `main`, **the entire `client`-based integration suite errors at
table creation** (verified: `tests/integration/` = 38 passed / **74 errors**;
`test_strategy_webhook_paper_e2e.py` errors standalone too). The suite is
built for **Postgres in CI** (`docker-compose-test.yml`), where `JSONB` is
native — but the work-order specified "no Docker needed."

**Workaround (in the new test file only):** a dialect-scoped
`@compiles(JSONB, "sqlite")` shim that renders `JSONB` as SQLite `JSON`
(TEXT affinity). With it, `create_all` succeeds and the suite runs locally.

**Recommended follow-up (out of scope here):** promote that shim into
`tests/integration/conftest.py` (or root `tests/conftest.py`) so *every*
integration test runs on local SQLite, not just ones collected alongside
this file. Left out of this branch to honour "cover + document, touch
nothing shared."

---

## 8. Test results

```
backend/tests/integration/test_strategy_webhook_async.py  →  19 passed
```

Coverage of the work-order's required cases:

| Work-order item | Test |
|---|---|
| (a) Phase 1 < 200 ms (`perf_counter`) | `TestPhase1FastPath::test_phase1_responds_under_200ms` |
| (b) Duplicate `signal_id` → "duplicate" | `TestIdempotency::test_duplicate_signal_id_returns_duplicate` |
| (c) Distinct `signal_id` → processes | `TestIdempotency::test_distinct_signal_id_processes_independently` |
| (d) Background runs after response | every `TestBackgroundOutcomes` / `TestTelegramTaxonomy` test (drives the real coroutine) |
| (e) `BrokerOrderRejectedError` → failed + CRITICAL | `test_background_broker_rejection_marks_failed_no_phantom_position` |
| (f) Success → executed | `test_background_success_marks_executed` |
| (g) Exception → failed + logged | `test_background_unexpected_exception_marks_failed` |
| (h) 6-fix smoke: INTRADAY hard-guard (Fix #3) | `TestFixPreservationSmoke::test_intraday_product_type_hard_guarded_for_fno` |
| (h) 6-fix smoke: no phantom position on rejection (Fix #5) | covered in (e) — asserts `position count == 0` |
| (h) 6-fix smoke: Telegram taxonomy Placed/Filled/Rejected (Fix #6) | `TestTelegramTaxonomy::test_alert_level_matches_broker_status` (6 params) |
| (h) 6-fix smoke: Dhan raises typed rejection (Fix #4) | `test_broker_rejection_error_contract` (type contract; adapter HTTP-200 parsing stays in frozen broker tests) |
| (2) idempotency helper | `TestSignalIdempotencyHelper` (4 tests) |

### Regression (existing `strategy_webhook` tests)

Run with the JSONB shim active (i.e. this file collected alongside):

```
tests/integration/test_strategy_webhook_*.py  →  46 passed, 3 failed
```

The **only** 3 failures are the HMAC `*_returns_401` tests, and they are
**pre-existing and unrelated to this branch**:

- `webhook_require_hmac` **defaults to `False`** (`app/core/config.py`), so
  locally an unsigned/invalid request is accepted via the URL token (`202`)
  rather than rejected (`401`). CI sets the flag; local env doesn't.
- Proof it's not us: deselecting **all** tests in this file (so none of our
  tests execute, only the shim is registered) still reproduces exactly those
  3 failures.

---

## 9. Deviations from the work-order (and why)

| Asked | Did | Why |
|---|---|---|
| New branch `feat/webhook-async-refactor` off `main` | New branch `feat/webhook-async-tests-docs` | `feat/webhook-async-refactor` already exists locally **and on origin** (the Celery attempt, §6); `checkout -b` would collide. User chose a fresh branch. |
| Use Phase 2B's `PineAlertPayload` schema | Used `StrategyWebhookPayload` | `PineAlertPayload` does not exist anywhere in the tree; `StrategyWebhookPayload` + the Pine mapper is the real Phase-1 contract. |
| Tests in `backend/tests/api/test_strategy_webhook_async.py` | `backend/tests/integration/test_strategy_webhook_async.py` | The webhook test harness (`conftest` with `seed`/`client`/fakeredis/aiosqlite) lives in `tests/integration/`; `tests/api/` has no webhook fixtures. Sibling webhook tests (and the stale `.pyc`) are in `tests/integration/`. |
| `status='queued'` / `'completed'` | `'received'` / `'executed'` | §6 — reuse documented vocabulary, no migration, keep existing status filters valid. |
| Rewrite handler for two-phase async | Left handler untouched | It already is two-phase async; rewriting would change the live `89423ecc` path (forbidden). |
