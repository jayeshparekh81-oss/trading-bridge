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

---

# Phase 2 (Razorpay), Module 2 — marketplace per-strategy recurring subscription

**Goal:** replace the marketplace **stub** subscribe with a real Razorpay recurring subscription, REUSING M1's client + the ONE signature-verified idempotent webhook. The paid, **active** `marketplace_subscription` is the row the Phase-1 fan-out spine routes signals to — but **paying ≠ real trading yet**: fan-out stays disabled and execution stays PAPER (real-money subscriber execution is a later phase, post-empanelment).

## What changed
| Endpoint | Before (stub) | After (M2) |
|---|---|---|
| `POST /api/marketplace/listings/{id}/subscribe` | Always wrote an **active** sub with `amount_paid_inr = price`, as if paid. | **Paid listing + Razorpay configured** → creates a recurring Razorpay Subscription, persists a **`pending`** sub (+ a `razorpay_payments` row, `kind=marketplace`), returns the **checkout handle**. NOT active until the webhook confirms the charge. **Free listing OR gateway unconfigured** → unchanged stub path (immediate `active`, ₹0/price). |

The webhook is **the same** `POST /api/billing/webhook/razorpay` from M1 — NOT a second webhook. It now routes by `razorpay_payments.kind`:
| `kind` | Webhook effect |
|---|---|
| `platform_plan` (M1) | drives `users.plan_status` (entitlement) — unchanged |
| `marketplace` (M2) | flips the linked `marketplace_subscriptions` row: `charged`/`activated` → `active` (+ `access_until`, + `amount_paid_inr`, + `subscriber_count`++); `cancelled` → `cancelled`; `halted`/`completed` → `expired` |

A marketplace charge writes **only** the subscription's status/access fields + an `audit_logs` row (ActorType.SYSTEM, `resource_type=marketplace_subscription`). It does **not** touch `users.plan_status` — the two kinds are cleanly separated.

## Data (migration `035_razorpay_marketplace` — additive, off this branch's head `034_razorpay_billing`)
- ADD `razorpay_payments.kind` (NOT NULL, default `'platform_plan'`) — the webhook discriminator. Existing M1 rows correctly become `platform_plan`.
- ADD `razorpay_payments.marketplace_subscription_id` (nullable FK → SET NULL) — the durable `sub_… → marketplace_subscription` link.
- ADD `marketplace_subscriptions.razorpay_subscription_id` (nullable, indexed) — the recurring handle on the sub.
- ADD `marketplace_listings.razorpay_plan_id` (nullable) — create-if-absent Razorpay Plan per listing price (no duplicate plans).
- EXPAND the `marketplace_subscriptions` status CHECK to add `'pending'` (drop+recreate `ck_marketplace_subscriptions_status_valid`; purely additive to the allowed set — existing rows stay valid).
- Changes no existing column type, no backfill. Reversible (downgrade restores the original 3-value CHECK; it refuses if `'pending'` rows remain — clear them first).
- ⚠️ **Revision-id note:** like 034, this forks off 033 in parallel with `feat/marketplace-fanout`; a single alembic **merge revision** joins the heads when both land on main. Kept ≤32 chars (`035_razorpay_marketplace` = 24).

## Security + correctness guarantees
- **ONE signature-verified webhook:** marketplace events flow through the SAME `razorpay_webhook` endpoint, which verifies `X-Razorpay-Signature` BEFORE anything (bad sig → 400, grants nothing) and dedupes on the durable `event_id` ledger. No second webhook, no duplicated signature logic. Proven: a bad-sig delivery leaves the sub `pending`; a good-sig one activates it.
- **Idempotent:** a duplicate `event_id` has a SINGLE effect — `subscriber_count` is incremented exactly once across two `charged` deliveries.
- **Paying ≠ real trading (asserted):** a paid, **active** marketplace subscription triggers **zero broker calls** — a test installs recorders on `DhanBroker.place_order` + `FyersBroker.place_order` and asserts they never fire across subscribe + activate; `paywall_enforced` stays **False** and there is no `marketplace_fanout_enabled` on this branch. The fan-out execution spine lives on `feat/marketplace-fanout`, not here.
- **No trading code touched:** diff is the marketplace router + the Razorpay service/models/migration + tests only. `strategy_webhook`/`executor`/`direct_exit`/`kill_switch`/`brokers`/`positions` are NOT in the diff.
- **Secrets via ENV only** (`RAZORPAY_*`, default empty); mocked tests, no live calls; the PUBLIC key id only is returned for checkout.

## Verify (done locally)
- **Migration on REAL local Postgres 16** (docker `:5433`): clean `034→035`, clean downgrade `035→034` (CHECK reverts to the 3-value set), clean re-upgrade to head. Confirmed: `kind` default `platform_plan`, the two FK/handle columns, the listing plan column, and the widened `pending` CHECK. Single alembic head. Local DB torn down.
- **Tests (MOCKED Razorpay, no live calls):** `cd backend && .venv/bin/python -m pytest tests/integration/test_razorpay_marketplace.py -q` → **6 passed** — pending-not-active + Razorpay sub; charged→active (platform entitlement untouched); cancelled→cancelled; idempotent single-count; shared-webhook signature gate; zero-broker-calls.
- **No regression:** the existing marketplace suite (`test_marketplace.py`, 26 tests — they fall to the stub path since Razorpay is unconfigured) + M1 billing (5) all still pass: **37 passed** together.
- `ruff check` clean on all changed files. `mypy` clean on the new code (one **pre-existing** `no-any-return` in M1's `sync_plan_to_razorpay` remains — verified present at HEAD, untouched). The 19 failing local integration tests (`live_order_flow`, `reconciliation_loop`, webhook-HMAC, telegram) are **pre-existing** — verified identical at HEAD with my changes stashed (local-harness gaps: HMAC defaults off, Postgres-needed paths).

## Deliberately NOT done (follow-ups)
- **Sandbox end-to-end** against real Razorpay test-mode — same as M1, pending `RAZORPAY_*` TEST keys in env.
- **Frontend checkout** for the marketplace handle (`requires_payment=true` → open checkout.js).
- **Fan-out activation / real subscriber execution** — deliberately OUT (Phase 3, post-empanelment). A paid sub is access-only today.
- No `paywall_enforced` flip, no deploy, no merge to main.
