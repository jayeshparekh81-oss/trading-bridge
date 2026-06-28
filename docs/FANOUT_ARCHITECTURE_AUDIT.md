# Fan-Out / Marketplace Architecture Audit

- **Date:** 2026-06-28
- **Status:** Design-phase reference. Read-only audit — nothing built from this yet.

> **REAL-MONEY FAN-OUT IS GATED ON SEBI EMPANELMENT. This document plans PAPER-mode hardening (Stage 1) only. Stage 2 (real-broker activation) is future, post-empanelment.**

---

"Fan-out" = one strategy's signal being distributed/executed across multiple users' broker accounts, vs. the current single-account setup where every strategy belongs to one owner.

**Bottom line:** fan-out is already scaffolded end-to-end, merged to `main`, but **dormant** (`marketplace_fanout_enabled` default `False`, unset in prod) and **PAPER-only**. The data model is ~80% real-money-ready; the execution / risk / lifecycle / money paths are 0–10% built.

---

## Topology (how it's modeled)

```
Strategy (SINGLE owner: user_id)              ← unchanged, no many-to-many
   └─< marketplace_listings  (creator_id = owner, strategy_id, pricing, status)
          └─< marketplace_subscriptions  (subscriber_id + per-subscriber config)
                 └─ scopes → strategy_executions.subscription_id
                            → strategy_positions.subscription_id   (NULL = owner)
```

Fan-out is **layered on top** of the single-owner `Strategy` via listings → subscriptions, and isolates subscriber rows with a nullable `subscription_id` (NULL = owner). **No `Strategy` schema change is needed.**

Per-subscriber config columns already exist on `marketplace_subscriptions` (migration 035): `lots_override`, `execution_mode` (auto/one_click/offline), `is_paper`, `direction_filter` (all/long/short), `broker_credential_id`. Several are **CARRIED but NOT yet branched on**.

`copy_trading_*` (Phase-5 skeleton, dead) and `subscription_plans` (platform pricing tiers) are **separate concerns**, not on the fan-out path.

---

## Execution flow

### Owner path (real, mode-dependent) — 1→1
`webhook` → Celery `dispatch_signal` → `_process_entry` → `place_strategy_orders` → `_load_credential` resolves **one** account from `strategy.broker_credential_id`:
- Primary lookup: `strategy_executor.py:736-743` (`id == credential_id AND user_id AND is_active`).
- Auto-login-rotation fallback: `strategy_executor.py:752-762` (most-recent active cred for `(user_id, broker_name)`, logs `strategy_executor.credential_rotated`).
- Builds exactly one broker; real vs paper per `resolve_paper_mode(strategy)` (honours `strategy.is_paper`).

### Fan-out tail (PAPER-only, flag-gated, additive)
`strategy_webhook.py:680`, runs **after** the owner dispatch, wrapped in `try/except` so it can never affect the owner response:
```python
# 15. Marketplace fan-out — ADDITIVE, flag-gated, PAPER-ONLY.
if get_settings().marketplace_fanout_enabled:                 # :680 flag guard
    try:
        subscribers = await resolve_active_subscriptions(strategy_id, session)
        await dispatch_subscriber_executions(
            signal=signal, strategy=strategy, subscribers=subscribers,
            db=session, signal_hash=signal_hash,
        )
    except Exception as exc:
        logger.warning("fanout.failed", ...)
```
When `marketplace_fanout_enabled=False` (prod default, unset), the entire block is skipped — owner path is byte-identical, cost is one short-circuiting bool read.

**Owner vs fan-out, confirmed differences:**

| | Owner path | Fan-out (subscriber) path |
|---|---|---|
| Entry fn | `place_strategy_orders` (`strategy_executor.py:119`) | `dispatch_subscriber_executions` (`marketplace_fanout.py:304`) |
| Dispatch | async via Celery | **inline** in webhook request |
| Paper/live | `resolve_paper_mode(strategy)` — can be **LIVE** | **FORCED PAPER** regardless of any flag |
| Broker call | live → `broker.place_order` | **none** — only `_simulate_fill` (`:402`), pure, no broker |
| Credential | decrypted + used to build broker | resolved read-only, **recorded but NEVER used** |
| Row scoping | `subscription_id IS NULL` | `subscription_id == sub.subscription_id` |

---

## ✅ Implemented & reusable (the assets you already have)

| Capability | Where |
|---|---|
| Flag gate (`marketplace_fanout_enabled`, default False, dormant in prod) | `config.py:393`; `marketplace_fanout.py:133`; gate at `strategy_webhook.py:680` |
| Subscriber lookup (active subs via listing join, `status='active'`) | `marketplace_fanout.py:159-186` |
| Per-subscriber **credential resolution** (explicit→fallback→none, ownership+active checks) | `marketplace_fanout.py:206-249` |
| Per-subscriber **sizing knob** (`lots_override` → `entry_lots` → 1) | `marketplace_fanout.py:392` |
| **Idempotency** (per-subscription Redis key `{sub_id}:{signal_hash}`, distinct from owner; fail-open) | `marketplace_fanout.py:252-279,416-444` |
| **Partial-failure isolation** (per-subscriber SAVEPOINT + try/except + Telegram alert) | `marketplace_fanout.py:447,565-596` |
| **Owner isolation** (subscriber rows carry `subscription_id`; owner reads filter `IS NULL`) | `strategy_executor.py:387-391`; FK `strategy_execution.py:52`, `strategy_position.py:70` |
| Subscription model carries subscriber's **own `broker_credential_id`** (real-money-ready) | `marketplace_subscription.py:93-98` |
| Subscribe / unsubscribe / settings API + billing (Razorpay) | `strategy_engine/api/marketplace.py:587-917` |

---

## ⚠️ Stubbed — PAPER-only (where the real-money path plugs in)

- **No real broker order ever placed.** Sole primitive is `_simulate_fill` → `PAPER-{uuid}` (`marketplace_fanout.py:402`). It does **not** branch on `is_paper` / `execution_mode` / `direction_filter` — these are read into a `SubscriberRef` (`:179-183`) but never acted on. The module *explicitly refuses* to go live (`:322-327`).
- **Resolved credential is recorded-but-unused.** Subscriber position/execution rows are stamped with the **owner's** `strategy.broker_credential_id` as a paper placeholder (`:471,:492`); a real path must swap to `cred.credential_id` and call a real broker.
- **`pending_fanout_merge` / `_columns_present` is now vestigial** (M0–M5 merged; migration 035 applied → always resolved) — dead/misleading scaffolding (`marketplace.py:821-841`).

---

## ❌ Missing entirely

- **Subscriber EXIT / PARTIAL / SL_HIT** — only ENTRY is handled; non-entry actions are log-only, no persist (`:380-384,407,548-549`). *Positions could open with no programmatic way to close.*
- **Real lot-size scaling** — `lots` used directly as quantity (paper `lot_size=1`); no `lots × contract_lot_size`.
- **Per-subscriber risk gates** — kill-switch / max-daily-trades / max-daily-loss / market-hours / market-shield / anomaly-shield all run **once on the owner** before fan-out; never per subscriber.
- **Async/concurrent dispatch** — fan-out loop is **inline + sequential** in the web request (owner path uses Celery).
- **Subscriber reconciliation** — `reconciliation_loop.py:144` explicitly excludes `subscription_id IS NOT NULL`.
- **Cross-subscriber emergency square-off** — `kill_switch_service.py:567-571` has no subscription scoping.
- **Fee / execution billing coupling** — `amount_paid_inr` is access-only; no per-fill attribution / ledger.

---

## Prioritized gap list for the next phase

> **Stage gating:** P0/P1 below describe what a *real-money* flip would require. Per the SEBI-empanelment gate, **Stage 1 is PAPER-mode hardening only** — activate the inert config branches, fix isolation/correctness, and add observability while execution stays simulated. **Stage 2 (the real-broker activation items, esp. P0 #1–#8) is future, post-empanelment.**

### P0 — blocks any `is_paper=false` flip (can lose money) — Stage 2
1. No real order placement (swap `_simulate_fill` for a broker build on the subscriber's credential).
2. **No subscriber exit path** — open-but-uncloseable real positions (the single most dangerous gap).
3. Subscriber kill-switch never consulted (owner-only gate at `strategy_webhook.py:268`).
4. Emergency square-off doesn't scope/cover subscribers (`kill_switch_service.py:567`).
5. Subscriber positions excluded from reconciliation (`reconciliation_loop.py:144`).
6. No real lot-size scaling (silent under-sizing).
7. No per-subscriber token-health / auto-login fallback (stale-token failures at scale).
8. `broker_credential_id` nullable + SET NULL + not ownership-validated against `subscriber_id`.

### P1 — required for a safe v1
9. Activate inert columns: `is_paper`, `execution_mode` (auto/one_click/offline), `direction_filter` (all/long/short), `access_until`, `lots_override`. *(Stage 1 can wire these branches in paper.)*
10. Move dispatch to Celery (not inline-sequential) — last subscriber's fill currently delayed by the sum of all prior broker latencies.
11. Retry / dead-letter semantics (today per-subscriber failure is dropped after one inline shot).
12. Durable (DB-backed) + fail-**closed** idempotency for live; 60s fail-open Redis slot is paper-grade only.
13. Re-evaluate owner-only guards (market-hours, market-shield exit-hold, anomaly-shield) per subscriber where relevant.
14. Per-subscriber risk controls: max-daily-loss, max-open-positions, capital/margin adequacy; proportional / risk-based sizing (not just fixed lots).

### P2 — scale / operability
15. Billing / ledger / fee coupling on the execution path (`monthly_billing_cycles`, ledger attestation). `amount_paid_inr` is access-only today.
16. Observability: per-subscriber metrics (fill latency, fill/reject rate, credential-source distribution, fan-degree) + audit trail. Fan-out writes no `webhook_event` / `audit_log`.
17. Backpressure / fan-degree limit; wire the existing `broker_guard` engine (`app/strategy_engine/broker_guard/`) into fan-out.
18. Reconcile the parallel **`copy_trading_*`** dead schema (it has `quantity_multiplier` / `max_quantity` / NOT-NULL `follower_credential_id` — the proportional-sizing primitives fan-out lacks) before duplicating them; pick a single source of truth.

### P3 — cleanup / correctness debt
19. Remove vestigial `pending_fanout_merge` / `_columns_present` and the stale "On THIS branch they're absent" comments.
20. Add a defense-in-depth internal flag re-check in the service (today the only gate is the call site).
21. Verify `execution_mode="paper"` (accepted by the settings PATCH) vs the model's CHECK enum (auto/one_click/offline) after migration 038 (`exec_mode_paper`).
22. Confirm the open-position upsert/lookup key includes `subscription_id` (historical key was `(strategy, symbol)`) so owner/subscriber positions on the same symbol can't collide.

---

## Current scale (prod DB, 2026-06-28)

| Metric | Count |
|---|---|
| Users | 7 |
| Broker credentials | 72 |
| Strategies | 5 |
| Marketplace subscriptions | **0** |

Fan-out / billing tables present: `marketplace_listings`, `marketplace_ratings`, `marketplace_subscriptions`, `monthly_billing_cycles`, `subscription_plans`.
Flags (deployed): `MARKETPLACE_FANOUT_ENABLED` unset → **False**; `PAYWALL_ENFORCED` unset → **False**; `STRATEGY_PAPER_MODE=true`.

---

## Key files

- Fan-out service: `backend/app/services/marketplace_fanout.py`
- Call site / gate: `backend/app/api/strategy_webhook.py` (gate `:268-346`, fan-out `:668-706`)
- Owner executor: `backend/app/services/strategy_executor.py` (`_load_credential:718-776`, `_simulate_fill:1049`, `_find_existing_open_position:366`)
- Kill-switch square-off scope: `backend/app/services/kill_switch_service.py:567-571`
- Reconciliation exclusion: `backend/app/workers/reconciliation_loop.py:143-144`
- Data model: `backend/app/db/models/marketplace_subscription.py`, `marketplace_listing.py`, `copy_trading.py`, `subscription_plan.py`; `subscription_id` scoping on `strategy_execution.py:52`, `strategy_position.py:70`
- Marketplace API: `backend/app/strategy_engine/api/marketplace.py:587-917`
- Flag definition: `backend/app/core/config.py:393` (`marketplace_fanout_enabled`), `:379` (`paywall_enforced`)
- Migrations: 018 marketplace_tables, 031 subscription_plans, 034 subscription_position_scoping, 035 subscription_execution_fields, 037 merge_fanout_billing, 038 exec_mode_paper

---

*Read-only audit. Source: multi-agent code+DB trace of `main` (== `origin/main`) on 2026-06-28. Nothing in this document has been built or deployed.*

---

## SUBSCRIBER DASHBOARD DESIGN (2026-06-28)

> Still gated on SEBI empanelment for any real-broker execution. Everything below is built and shipped in **PAPER mode (Stage 1)** first; the real-broker swap is Stage 2 (post-empanelment).

### Build order (paper-first)

1. **Subscriber EXIT / PARTIAL / SL lifecycle path** (P0 #2 — most critical). Entries currently open with **no programmatic close path**; this must exist before anything else, even in paper, or simulated positions accumulate uncloseable.
2. **Subscriber safety primitives:** per-subscriber kill-switch consultation, cross-subscriber emergency square-off, and subscriber-scoped reconciliation. (Addresses P0 #3, #4, #5 — in paper these protect data integrity; in Stage 2 they protect real money.)
3. **Subscriber performance dashboard** (this section).
4. **[Post-SEBI] real-broker swap** + remaining P0 (#1, #6, #7, #8) + the gated `is_paper=false` flip.

### Dashboard design

- **Two separate sections:**
  - **"Subscribed strategies (standardized view)"** — strategies the user follows via the marketplace.
  - **"My strategies"** — the user's own strategies (existing single-owner view).
- **Standardized view normalization:** a **fixed ₹10 lakh base per strategy** + a **defined per-strategy lot-sizing rule**, so a return % is consistent across instruments at very different price levels (e.g. BSE ~₹4000 vs ANGELONE ~₹335). Without a sizing rule, raw lot counts would make a cheap and an expensive instrument incomparable.
- **PRIMARY metric = return %** — honest, capital-agnostic, **net of fees/brokerage, realized**. This is what the subscriber sees first.
- **SECONDARY = absolute ₹** — **ALWAYS** labelled **"illustrative, on ₹10L base — NOT your actual broker P&L"**. **Never** show a bare ₹ profit figure.
- **Show per subscribed strategy:**
  - Strategy name + subscribe-date.
  - Closed-trade count.
  - Open-position count (shown **separately** from closed).
  - **Cumulative return % equity curve from subscribe-date** (on the standard base).
  - Win rate (on the standard base).
- **Open positions:** unrealized P&L shown **separately** and **clearly marked** as unrealized/open.
- **PAPER phase:** a loud **"SIMULATED"** badge everywhere on this view.

### Guardrails (non-negotiable)

- Show the **subscriber's OWN data only** — never the strategy aggregate or backtest presented as "expected return".
- **Realized vs unrealized** always separated.
- All figures **net of fees/brokerage**.
- Paper/simulated state **clearly labelled** at all times.

### Open questions (unresolved — decide before build)

1. **Owner exit → subscriber exit trigger:** does a subscriber position close by *mirroring the owner's exit signal*, or via a *subscriber-local SL computed on the subscriber's own entry/slippage*? (Mirroring is simpler and keeps followers aligned with the owner; subscriber-local SL is safer against per-account slippage divergence but needs independent SL tracking.)
2. **₹10L base lot-sizing rule per strategy:** the exact formula that maps a ₹10L notional base + instrument price → standardized lots, so return % is comparable across instruments.

---

*Dashboard design section appended 2026-06-28. Design-phase notes only — not built.*

---

## DASHBOARD vs SAFETY — TWO SEPARATE SYSTEMS (2026-06-28)

**CLARIFICATION** (resolves how the ₹10L illustration relates to subscriber state):

The subscriber dashboard and the safety/position-check are **TWO INDEPENDENT systems** with different purposes.

### 1. ₹10L ILLUSTRATION DASHBOARD = "what the STRATEGY did" (signal-based)
- Computed purely from the strategy's signals (long / partial / exit) applied to a **fixed ₹10L illustrative base**.
- **Identical for all subscribers** — it's the strategy's performance, not anyone's personal P&L.
- **INDEPENDENT of what the subscriber actually did in their broker.** If a subscriber manually closes early, the illustration is **UNAFFECTED** — it keeps following the strategy.
- This is **tool-route-safe**: a neutral factual record of the strategy ("what it did on a ₹10L example base"), **NOT** a personalized performance/return claim and **NOT** a promise of what the user will earn.

### 2. POSITION-CHECK / RECONCILIATION = "what's REALLY in the subscriber's broker" (safety)
- Runs against the subscriber's **actual broker** (live position fetch + background reconciliation).
- **Purpose:** prevent the unwanted-short bug; skip actions when no real position exists.
- Driven by the broker's **real state**, not the illustration.

### KEY
These two systems **never touch each other**:
- **Illustration = display** (strategy performance, ₹10L, signal-based).
- **Position-check = safety** (real broker, prevents wrong orders).

### MANDATORY LABEL on the dashboard
(avoid confusion + stay tool-route-compliant)

> **"This shows the STRATEGY's performance on a ₹10L illustrative base — NOT your actual P&L. If you closed early or your capital differs, your real result will differ. See your broker app for your actual P&L."**

*Example:* a subscriber books **+₹2,000** by closing early, but the illustration shows the strategy continued to **+₹5,000** on the ₹10L base — the label explains why they differ.

This keeps the real-investment / privacy / performance-claim risks **OUT** (decided: **no real-investment-return display**).

**NOTE:** This supersedes/clarifies the earlier "own data only" guardrail. The ₹10L illustration is intentionally the STRATEGY's signal-based record (same for all subscribers), framed as such with the mandatory label — it is NOT a personalized return claim. "Own data only" applies to any genuinely personal view (e.g. which strategies a subscriber follows, their subscribe-dates); it does not require per-subscriber P&L, which is deliberately avoided for privacy + tool-route reasons.

---

*Dashboard-vs-safety clarification appended 2026-06-28. Design-phase notes only — not built.*
