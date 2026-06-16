# Billing / monetisation — plan (India)

**Status today (code-verified):** there is **no billing**. `/(public)/pricing` is fully static (hardcoded tiers); there is **no `/api/billing`, `/api/plans`, or `/api/subscriptions` router** anywhere. Marketplace "subscriptions" record an amount but the payment gateway is a **stub** (no real charge). So monetisation is greenfield. This doc is a plan, not a build.

## 1. Gateway choice (India-first)

| Gateway | Why | Notes |
|---|---|---|
| **Razorpay** (recommended primary) | Best India DX, UPI + cards + netbanking + wallets, **Subscriptions/Plans API** for recurring SaaS, webhooks, good docs, India-domiciled (RBI-compliant settlement) | RBI e-mandate / recurring rules apply (max ₹15k/txn without additional auth; AFA for higher). Razorpay handles the e-mandate flow. |
| **Cashfree** | Cheaper MDR for some methods, good UPI Autopay | Viable alt/secondary. |
| **PayU India** | Established, broad method support | Heavier integration. |
| **Stripe** | Best DX globally | **Stripe India recurring is limited** by RBI e-mandate; for INR recurring, Razorpay is smoother. Keep Stripe only if/when there's USD/international demand. |

**Recommendation:** Razorpay primary (Subscriptions API for tiers), revisit a second gateway only for redundancy/MDR once volume justifies it.

## 2. Pricing tiers (proposal — founder sets final numbers)
Three tiers map cleanly to the existing RBAC roles (`role_demo` already models `me/pro/creator/super-admin`):
- **Free** — paper trading only, N strategies, recent-100 analytics, no live orders. (Customer acquisition + the SEBI "advisory/paper" safe zone.)
- **Pro (₹/mo)** — live webhook→broker, full-history analytics, alerts (when shipped), more strategies, priority AlgoMitra quota.
- **Creator/Marketplace (₹/mo + rev-share)** — publish strategies to the marketplace, Transparency-Ledger listings, subscriber payouts.

Gate features by `user.role` + a new `subscription` record (status, plan, current_period_end). The auth/me response already serialises enough; add `plan`/`subscription_status`.

## 3. What it needs to build (backend, additive)
1. **Data:** `subscriptions` table (user_id, plan, gateway_sub_id, status, current_period_start/end, created/updated) + `payments`/`invoices` ledger (gateway_payment_id, amount, currency, status, raw). Net-new migration.
2. **Router** `/api/billing` (additive): `GET /plans` (catalog), `POST /subscribe` (creates a Razorpay subscription, returns the checkout/short-url), `GET /me/subscription`, `POST /cancel`. All JWT-gated.
3. **Webhook** `/api/billing/webhook` — Razorpay signature-verified (HMAC over body with the webhook secret); handle `subscription.activated/charged/halted/cancelled`, `payment.captured/failed`. **This is the source of truth for status** (never trust the client redirect). Idempotent on `event.id`.
4. **Feature gating** — a dependency (e.g. `require_plan("pro")`) that 402s/403s when the user's active subscription doesn't cover the feature. Apply to live-order + alerts + marketplace-publish routes.
5. **Frontend** — wire `/(public)/pricing` to `/api/billing/plans`, add a real checkout flow (Razorpay Checkout JS), a `/settings/billing` page (current plan, invoices, cancel).

## 4. Compliance / gotchas (India + SEBI)
- **RBI e-mandate** for recurring INR: handled by Razorpay Subscriptions, but the AFA/notification rules are real — use their managed flow, don't roll your own mandate.
- **GST** — invoices must show GSTIN + 18% GST on SaaS. Razorpay can attach tax; you still need a registered GSTIN + invoice numbering.
- **SEBI IA framing** — the product is positioned advisory/white-box (AlgoMitra is advisory-only). Charging for *signals/execution* vs *advice* has different SEBI implications; the live-order tier is execution-bridge (customer's own broker), which is the safer framing. **Confirm with the SEBI IA registration track (≈30% per roadmap) before charging for anything that looks like advisory fees.**
- **Refund/cooling-off** policy + T&C must exist before taking money.
- **Don't** store card/UPI data — Razorpay tokenises; you store only their IDs.

## 5. Suggested sequencing
1. Razorpay test account + Plans created in their dashboard.
2. Build subscriptions/payments tables + `/api/billing` (plans, subscribe, me) + the **webhook** (most important — status truth).
3. Feature-gate live-orders behind an active Pro subscription (flagged OFF until tested).
4. Wire pricing + checkout + `/settings/billing`.
5. Go live in **test mode** end-to-end (test cards/UPI) → then a single real ₹1 transaction → then enable.

**Not started — this is the plan only.** No billing code exists yet; nothing here touches the live trading path.
