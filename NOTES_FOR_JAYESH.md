# NOTES FOR JAYESH — Razorpay billing (Phase 2)

**Branch:** `feat/razorpay-billing` (off `main` @ 730ce91). Pushed. **NOT merged to main, NOT deployed.**
(This NOTES file did not exist on `main`; it's a fresh one for the Razorpay track. The marketplace-fanout NOTES live on that branch.)

---

# Phase 2 (Razorpay), Module 1 — recurring core + platform-plan flow

**Goal:** wire Razorpay recurring subscriptions to the EXISTING entitlement layer (B1–B3) — the verified, idempotent webhook drives `users.plan_status` / `active_plan_id` / `plan_expires_at`. Payment-only. **No trading code touched. `paywall_enforced` stays False (building billing ≠ enforcing).**

## Endpoints (all NEW, under `/api/billing`)
| Method + path | Auth | Purpose |
|---|---|---|
| `POST /api/billing/subscribe` | user | Create a Razorpay recurring Subscription for the caller + a plan; persist the row; returns `{razorpay_subscription_id, razorpay_key_id (PUBLIC), status, short_url, plan_tier, amount_inr}` for the frontend checkout. |
| `POST /api/billing/webhook/razorpay` | public (Razorpay) | **Verifies `X-Razorpay-Signature` HMAC FIRST**, then idempotently applies the event. Invalid signature → 400, grants nothing. |
| `POST /api/billing/admin/sync-plans` | admin | Map each active plan tier → a Razorpay Plan (create-if-absent, no duplicates). |

## Webhook events handled → entitlement transition (REUSES the B2 fields)
| Razorpay event | `users.plan_status` | also sets |
|---|---|---|
| `subscription.activated` / `subscription.charged` | `active` | `active_plan_id` = plan, `plan_expires_at` = `current_end` |
| `subscription.halted` | `expired` | — |
| `subscription.cancelled` | `cancelled` | — |
| `subscription.completed` | `expired` | — |
Every event is logged (`razorpay.webhook.*`) and writes an `audit_logs` row (ActorType.SYSTEM), mirroring `admin.set_user_plan`. `plan_is_active()` (the paywall predicate) is reused unchanged.

## Env vars needed (secrets via ENV only, default EMPTY — nothing hardcoded/committed)
- `RAZORPAY_KEY_ID` — API key id (also the PUBLIC id the frontend checkout uses).
- `RAZORPAY_KEY_SECRET` — API secret (server-only; never returned/logged).
- `RAZORPAY_WEBHOOK_SECRET` — webhook signing secret. **Empty → every webhook is rejected (fail-closed).**
Use Razorpay **TEST** keys in dev; never live keys in code/tests.

## Security + correctness guarantees
- **Signature-verified:** `razorpay_webhook` calls `verify_webhook_signature(raw_body, X-Razorpay-Signature, RAZORPAY_WEBHOOK_SECRET)` BEFORE touching the body. This reuses the platform's existing constant-time `app.core.security.verify_hmac_signature` (Razorpay signs the exact body with HMAC-SHA256 hex — same scheme). A spoofed/unverified webhook can NEVER grant a plan; an empty secret rejects everything.
- **Idempotent:** durable `razorpay_webhook_events` table with a UNIQUE `event_id` (the `X-Razorpay-Event-Id` header, else a derived `{event}:{entity}:{created_at}` hash). A duplicate delivery dedupes → the entitlement effect happens **exactly once** (proven: a duplicate `event_id` carrying a `cancelled` body does NOT override the prior `active`).
- **Entitlement-reused:** the webhook writes ONLY the B2 triple via `_apply_entitlement` — same fields `plan_is_active` reads. Plan/status logic is NOT rebuilt.
- **No trading code touched:** confirmed `strategy_webhook`/`executor`/`direct_exit`/`kill_switch`/`brokers`/`marketplace_fanout`/`position*`/`reconciliation` are absent from the diff.
- **`paywall_enforced` unchanged** (default False) — billing is built, not enforced.

## Data (migration 034_razorpay_billing — additive, off main's head 033)
- NEW `razorpay_payments` (user_id, plan_id, razorpay_order_id, razorpay_subscription_id, razorpay_payment_id, status, amount_inr, notes, created_at) — the durable `sub_… → user+plan` link.
- NEW `razorpay_webhook_events` (UNIQUE event_id) — idempotency ledger.
- ADD `users.razorpay_subscription_id` (nullable) + `subscription_plans.razorpay_plan_id` (nullable, create-if-absent map).
- Changes no existing column, no backfill. Reversible.
- ⚠️ **Revision-id note:** both this branch and `feat/marketplace-fanout` fork off 033, so each has a "034". This one is `034_razorpay_billing` (distinct id from the marketplace `034_subscription_scoping`); when both land on main, a single alembic **merge revision** will join the two heads. Kept ≤32 chars (alembic_version VARCHAR(32) — lesson from the marketplace closeout).

## Verify (done locally)
- **Migration on REAL local Postgres 16** (docker `:5433`): clean `033→034_razorpay_billing`, clean downgrade `034→033`, clean re-upgrade to head. Schema confirmed: both tables + the UNIQUE `event_id` + the two nullable handle columns. Local DB torn down. **NOT run on prod (prod stays at 033).**
- **Tests (MOCKED Razorpay, no live calls):** `cd backend && .venv/bin/python -m pytest tests/integration/test_razorpay_billing.py -q` → **5 passed** — subscription creation persists + returns the handle (plan create-if-absent); signature valid passes / invalid rejected; webhook endpoint bad-sig → 400 grants nothing, good-sig → 200 applies; duplicate event_id = single effect; `charged→active` / `cancelled→cancelled` reuse `plan_is_active`.
- `ruff` clean on all new files. (`main.py` carries a pre-existing I001 unchanged — HEAD=1, now=1.) Entitlement/config regression unaffected.

## Deliberately NOT done (follow-ups)
- **Sandbox end-to-end** (real Razorpay test-mode order → checkout → real webhook) — pending once `RAZORPAY_*` TEST keys are in the env. The SDK call layer is mocked in tests; the live path is wired but unexercised against Razorpay.
- The frontend checkout wiring (open Razorpay checkout.js with `razorpay_subscription_id` + `razorpay_key_id`) — a later module.
- `paywall_enforced` flip — separate, deliberate decision.
- No deploy, no merge to main.
