# TRADETRI — Marketplace Architecture & Build Plan
*Multi-tenant signal fan-out · grounded in the repo audit · build module-by-module*

---

## 0. The model (one line)

**Your Pine/TradingView generates a secret signal → the platform fans that one signal out to N subscribers, each trade executing in the subscriber's OWN broker account, with the subscriber's OWN size — and your strategy logic is NEVER exposed.**

This is the exact model Tradetron and AlgoTest run. Two things are sacred to this model:
- **Your IP stays secret.** Subscribers receive *trades*, never the Pine/logic.
- **Funds stay with the subscriber.** Each customer connects their own broker; you never hold or touch their money. (Anything else = PMS/pooled = illegal without a licence + doesn't scale.)

---

## 1. What ALREADY EXISTS — REUSE (do not rebuild)

The audit confirmed ~70% of a marketplace is already built and multi-tenant-ready. **Do not touch / do not rebuild these:**

- **Auth / RBAC** — per-user model (`user.py`), self-serve register/login, JWT + Redis blacklist + lockout, roles incl. `creator` / `pro_user` already defined (`auth/roles.py`). Per-user data scoping everywhere.
- **Broker connect** — `BrokerCredential` (per-user, secrets Fernet-encrypted), Dhan + Fyers adapters live (Shoonya/Zerodha/Upstox/AngelOne stubs), Fyers OAuth + Dhan manual creds.
- **Marketplace + billing MODELS** — `marketplace_listing`, `marketplace_subscription`, `marketplace_rating`, `subscription_plan`, `ledger_snapshot`, `ledger_attestation` all exist. `GET /api/pricing/plans` active. User billing cols (`active_plan_id`, `plan_status`, `plan_expires_at`).
- **B3 paywall** — `entitlements.py` (`require_active_plan`, field-gating, 5 gated endpoints) built but inert (`paywall_enforced=False` at `config.py:379`). Flip flag when ready.
- **Frontend** — dashboard (overview/positions/trades/strategies/chart/analytics), **marketplace UI** (browse / detail+subscribe / `me`), brokers-connect, settings (Telegram/notif), webhooks CRUD, admin M1–M7, public/showcase, `UpgradeWall`.
- **Cross-cutting** — per-user notifications (Telegram + SES email + operator alerts), append-only `audit_logs`, `strategy_state_audit` DB trigger (live), onboarding flow, HMAC per-user webhook tokens.

---

## 2. The GENUINELY NEW work — only 2 things + 2 refactors

Everything else is reuse. The new work is small and **independent**:

### NEW-1 — Execution fan-out (the spine) 🔴 sacred
`MarketplaceSubscription` exists but the executor **cannot see it**. The whole new build is wiring one signal → many subscribers. Detailed in §4.

### NEW-2 — Payment gateway (Razorpay) 🟢 non-sacred
Razorpay is comments-only today; subscriptions are stub (`amount_paid_inr` copied from price). Need: order creation + Razorpay webhook → mutate `users.plan_status`/`active_plan_id` and/or `marketplace_subscriptions.status`. **Self-contained — touches no trading code → can be built in parallel.**

### REFACTOR-1 — `auto_login.py` 🟠
Hardcoded `DEFAULT_USER_ID`. Must loop over all users who have live broker creds (each subscriber's daily token refresh).

### REFACTOR-2 — Quantity resolver 🔴 sacred
`strategy_executor.py:429` computes qty as `min(AI_reco, strategy.entry_lots) × lot_size` — per-strategy global. Must support a **per-subscriber qty override**.

---

## 3. Data model — ADDITIVE changes only (no redesign)

The DB already supports per-credential positions, so this is application logic, not a schema rebuild. All changes **additive + nullable** so the owner path stays byte-identical.

- **`marketplace_subscription`** — add execution fields: `broker_credential_id` (which of the subscriber's creds), `lots_override` / `qty_multiplier`, `execution_mode` (`auto` | `one_click` | `offline` | `paper`), `is_paper` (bool), `direction_filter` (`all` | `long` | `short` — **v2, default `all`**), `status` (`active` | `paused` | `cancelled`).
- **`strategy_position`** — add nullable `subscription_id`. Owner rows = NULL (unchanged); subscriber rows carry it. This is the scoping dimension that keeps subscriber positions isolated.
- **`strategy_executions`** — add nullable `subscription_id` for per-subscriber execution records + reconciliation.
- **`kill_switch`** — already per-user (PK `user_id`) ≈ per-subscriber. Optionally add `subscription_id` scope later; reuse as-is initially.

> Migrations are **additive + nullable only**, and each migration is a **gated step** (sacred-adjacent — prod DB is at 033, live). One migration per module, reviewed before apply.

---

## 4. Execution fan-out — the spine (detailed)

**Owner path (today, UNCHANGED):** TradingView → `strategy_webhook.py` resolves strategy by `(owner user_id, token)` → one Celery task → `strategy_executor.py` uses `strategy.broker_credential_id` → places in owner's account. **This stays byte-identical.**

**NEW subscriber fan-out (additive, flag-gated `MARKETPLACE_FANOUT_ENABLED=False`):**
1. After the webhook resolves the strategy (owner path proceeds as normal), the new branch looks up `marketplace_subscription` rows where the listing → this strategy AND `status=active`.
2. For each subscriber, resolve: their `broker_credential_id`, `lots_override`, `execution_mode`, `is_paper`, `direction_filter` (v2).
3. Dispatch a **separate per-subscriber Celery task** (owner task is untouched; subscribers are N independent tasks).
4. Per-subscriber execution: uses the **subscriber's** cred + qty; writes `strategy_position` with `subscription_id`; **subscriber-aware idempotency key** (`subscription_id:signal_hash`).
5. **`execution_mode` branches:** `auto` → place order; `one_click` → notify + await confirm; `offline` → notify only (WhatsApp/SMS/email via existing notifications); `paper` → simulate.
6. **Partial-failure handling:** subscriber 2's broker rejects while subscriber 1 fills → log + alert that subscriber; **never** affects subscriber 1 or the owner. Each subscriber is fully isolated.

**Why this shape:** the owner's live BSE/CDSL path never changes; the fan-out is a brand-new branch behind a flag, defaulting OFF, paper-first.

---

## 4A. Multi-strategy & multi-source (Pine + Python) — the signal contract

The platform is **source-agnostic**: every strategy — Pine, Python, or anything else — is just a *signal source* that POSTs a standard JSON to its own webhook URL. Adding a new strategy needs **zero new execution code** — the fan-out spine (§4) serves it to all its subscribers automatically. (This is what makes "50+ strategies" trivial.)

**Adding a new strategy (Pine or Python):**
1. Create a new webhook token (per-user, HMAC — already exists).
2. Point the source's alert / POST at the webhook URL.
3. (Optional) List it on the marketplace.
4. The same fan-out spine routes it to N subscribers. Done.

**Pine vs Python — one important distinction:**
- **Python that POSTs the signal JSON** (exactly like a TradingView alert) → works on the **same path, zero new code**. The source doesn't matter; the platform only needs a correctly-formatted signal.
- **Platform RUNNING your Python code** (hosting / scheduling / executing your script) → a **separate, large feature** (code-execution sandbox + security). **Out of scope, and not needed** — keep strategies as signal *sources*, not hosted code.

**The signal contract (standardise this):** every source emits the same JSON shape — `action` (entry/exit), `side` (long/short), `symbol`, plus the existing v4.8.1 fields (score, etc.). The current Pine format already defines this; document it once so any future Python/other source follows the identical contract. Same contract → same spine → unlimited strategies.

---

## 5. The SACRED safe-shape (non-negotiable)

The fan-out touches the same code that runs **live BSE (`89423ecc`, real money)** and CDSL. Therefore:

1. **Additive, never in-place mutation.** Add a subscriber branch; do not rewrite the existing 1→1 executor logic.
2. **Flag-gated** (`MARKETPLACE_FANOUT_ENABLED`, default False) — like B3 paywall. Owner path runs whether the flag is on or off, identically.
3. **Owner path byte-identical** — verified by diff + a test asserting owner execution is unchanged, every module.
4. **Paper-first for the entire spine** — subscriber path forced to paper until §7 gates clear. No subscriber real-money order fires until empanelment + paper validation + per-subscriber square-off are all in place.
5. **Every sacred change = explicit founder gate**, per-change, like the whole project so far.

---

## 6. Sacred map (gated — explicit auth per change)

🔴 **Sacred (real money / live path):** `strategy_webhook.py`, `strategy_executor.py`, `signal_execution.py`, `direct_exit.py`, `strategy_position.py`, `kill_switch*`, broker adapters, `decrypt_credential`, `*_strategies_*` + any new migration.
🟠 **Sensitive:** `auto_login.py`, qty resolver, `config.py` (flags).
🟢 **Non-sacred (build freely, still reviewed):** Razorpay, checkout/sizing UI, subscription CRUD, marketplace frontend, notifications.

---

## 7. SEBI / compliance gates (hard)

- **Build can proceed now. Retail REAL-money live trading only AFTER exchange empanelment + RA registration is DONE** (not "in progress"). Until then: paper-only subscribers.
- White-box thesis = compliant category; no guaranteed-return claims anywhere.
- Per-strategy unique **Algo ID** + broker-integrated routing are empanelment deliverables — wire when empanelment lands.

---

## 8. Build sequence — module by module (paper-first, gated)

Each module: built on a branch, verified (tests + owner-path-unchanged diff), founder-reviewed, **then** next. Real money only at Phase 3.

**Phase 0 — Safety scaffold (no live touch)**
- **M0** — Add `MARKETPLACE_FANOUT_ENABLED` flag (default False) + the additive subscriber-execution module shell. Owner path untouched. Nothing executes yet.

**Phase 1 — Fan-out spine, PAPER ONLY (🔴 sacred, gated, additive)**
- **M1** — Subscriber lookup in `strategy_webhook.py` (flag-gated): given a signal, resolve active subscriptions for that strategy. Log only, no execution. + migration: `subscription` execution fields.
- **M2** — Per-subscriber Celery dispatch → **paper** execution for each subscriber. (Force `is_paper=true` on subscriber path regardless of config.)
- **M3** — `subscription_id` on `strategy_position` + `strategy_executions` (migration); per-subscriber paper position tracking + subscriber-aware idempotency.
- **M4** — Per-subscriber qty override (REFACTOR-2) + per-subscriber cred resolution (paper).
- **M5** — Partial-failure handling + per-subscriber alerts. **Gate:** end-to-end test — one signal → N paper subscribers, fully tracked, owner path proven byte-identical.

**Phase 2 — Payment (🟢 non-sacred, PARALLEL with Phase 1)**
- **P1** — Razorpay order creation + webhook → plan/subscription status. Sandbox first.
- **P2** — Checkout UI + per-subscriber sizing/execution-mode UI (size + risk-preview + mode + paper toggle).

**Phase 3 — REAL money (🔴 gated; only after empanelment + Phase 1 validated)**
- **R1** — `auto_login.py` multi-user refactor (REFACTOR-1).
- **R2** — Per-subscriber kill-switch / square-off scoping (extend existing per-user kill).
- **R3** — Flip subscriber path to honour `is_paper` (i.e. allow real) — **gated behind: empanelment done + paper validated + R2 in place + founder go.** Roll out to a tiny set first, watched.
- **R4** — Sizing risk-preview ("max DD ~X%, your capital → ₹Y risk").

**Phase 4 — Launch readiness**
- Compliance checklist, monitoring/dashboards, staged retail go-live (empanelment-gated). Drop showcase DRAFT ribbon, flip paywall when billing is proven.

---

## 9. Constant guardrails (whole project)

- **Module-by-module. No one-shot master prompts.** (This is what caught the 2× drawdown bug, the +16,242% fantasy, the mislabels.)
- **Owner BSE/CDSL path byte-identical**, proven every sacred module.
- **Paper-first**; no subscriber real money until Phase 3 gates.
- **Every sacred/migration change = explicit founder gate.**
- **Deploys only at market-close (15:30 IST), BSE flat** (container recreate + live-position guard).
- **No fabricated data, no compounded totals, no guaranteed-return claims** (carry the showcase honesty doctrine into the product).

---

## 10. What we are NOT doing

- ❌ Not rebuilding auth, broker creds, marketplace models, paywall, or the existing frontend — all reuse.
- ❌ Not executing in the owner's account for customers (no pooling/PMS).
- ❌ Not exposing the Pine/logic to subscribers.
- ❌ Not shipping a Long/Short knob that trades an unvalidated slice (direction = v2, as separately-validated versions).
- ❌ Not going live for retail real money before empanelment.

---

*Next: review this. When ready, build starts at **M0** (the safe flag + scaffold — zero live touch). One CC prompt per module, reviewed between each.*
