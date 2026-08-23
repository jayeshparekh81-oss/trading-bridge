# TRADETRI — Customer Dashboard & Product Spec (Consolidated)

**Purpose:** one reference for the entire customer-facing product — business model, every screen, the
subscribe flow, black-box/showcase, builder+backtest, broadcast/fan-out, sync-safety. Consolidated
2026-07-26 from the context docs + the actual code. Supersedes scattered notes.

**Status legend (evidence-based, from code — not aspiration):**
`BUILT` = wired to real backend/data · `PARTIAL` = exists but incomplete/inert · `DESIGN` = doc/plan
only, no working code · `STALE` = outdated/contradictory, needs correction.

**North-star doctrine (unchanged):** a premium, transparent **"Glass Box"** algo platform. Customers see
REAL performance (backtest/live/own-execution, separated + labelled), verify via the Transparency Ledger
("Backtest nahi, Proof."), control quantity + broker + start/stop + manual-exit, and funds never leave
their own broker. NOT a signal-selling / guaranteed-profit product. Safe language only (no "guaranteed
/ assured / sure-shot"). Source: `docs/CUSTOMER_PLATFORM.md`.

---

## 0. Source documents consolidated (what was read)

| Doc | Role |
|---|---|
| `docs/CUSTOMER_PLATFORM.md` | North-star customer spec + risk-ordered build sequence (§ below flags its stale parts) |
| `docs/MASTER_CONTEXT.md`, `docs/PROJECT_MAP.md`, `docs/SESSION_HANDOFF.md` | Overall project + prod state (also mirrored in `/Users/jayeshparekh/trading-bridge-chart/docs/`) |
| `docs/MARKETPLACE_ARCHITECTURE.md` | Broadcast/fan-out + per-subscriber config design |
| `M4_CONSOLIDATION_SPEC.md` (repo root, **untracked**) | UnifiedBuilder plan — "awaiting founder review, nothing implemented" |
| `docs/B3_PAYWALL_PLAN.md`, `docs/B3.2_GATE_ENDPOINTS_SPEC.md`, `docs/B3.3_BACKTEST_FIELD_GATING_SPEC.md`, `docs/B3.4_FRONTEND_WALLS_SPEC.md` | Paywall / entitlement design |
| `docs/MILESTONE_3_DESIGN_NOTES.md`, `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`, `docs/EXISTING_BACKTEST_ENGINE_AUDIT.md`, `docs/BACKTEST_DAY_4_INTEGRATION.md`, `docs/api/BACKTEST.md` | Backtest engine + extension |
| `docs/archive/PHASE_F_*`, `docs/parallel-cc-notes/PHASE_F_ROADMAP_DIAGNOSIS.md` | Native-builder (Phase F) history |
| `backend/scripts/SHOWCASE_BACKEND_DESIGN.md` | Showcase masking design ("proposal — do NOT ship" stamp, but it shipped) |
| `/Users/jayeshparekh/Desktop/tradetri-tomorrow.txt` | Loose planning note (Desktop) |
| **Code** (source of truth) | `frontend/src/app/(dashboard)/*`, `(public)/pricing`, `components/marketplace/*`, `components/billing/*`, `lib/billing/*`; `backend/app/api/*`, `strategy_engine/api/*`, `db/models/*`, `migrations/*`, `services/*`, `workers/*` |

> Note: `/Users/jayeshparekh/Desktop/cowork Jayesh_Live_Trading/` holds broker **credential** files
> (`fyers_token.txt` etc.) — deliberately **not** read; they are secrets, not product design.

---

## 1. Business model & pricing — **FLAT SUBSCRIPTION (no profit-share)**

The model is a **flat platform subscription**, three named tiers, two billing intervals. There is **no
profit-share / revenue-share anywhere in live code** — the pivot is complete. Marketing copy states it
explicitly: *"flat fee, profit share nahi"* (`frontend/src/lib/marketing/twitter/pricing-reveal.ts:12,27`).

### Plans (real, DB-seeded — `backend/migrations/versions/031_subscription_plans.py:37-118`)

| Tier | Monthly | Yearly (effective /mo, **20% off**) | Feature limits* | Status |
|---|---|---|---|---|
| **Starter** | ₹999/mo | ₹799/mo (billed ₹9,588/yr) | 1 broker, 5 strategies, Kill Switch | `BUILT` |
| **Pro** ("Most Popular") | ₹2,499/mo | ₹1,999/mo | 3 brokers, 50 strategies, + Analytics + Telegram + CSV export | `BUILT` |
| **Premium** | ₹4,999/mo | ₹3,999/mo | 6 brokers, 200 strategies, + AI Smart Signals + Shadow Stop-Loss | `BUILT` |

Served at runtime from the `subscription_plans` table via **`GET /api/pricing/plans`** (no-auth,
`backend/app/api/pricing.py:46-75`); both `/pricing` and the home cards read that one source
(`frontend/src/app/(public)/pricing/page.tsx:72-223`, `components/marketing/HomePricing.tsx`,
`lib/billing/plans.ts`). Trial/terms shown: **7-day free trial, no credit card, cancel anytime**, pay via
UPI/card/netbanking (Razorpay).

> *\* `STALE`/inaccurate:* the per-tier numeric limits (1/3/6 brokers, 5/50/200 strategies) are
> **display-only marketing** — **no backend enforces them.** The gate is flat all-or-nothing "premium",
> not per-tier caps. If tiered caps are intended, that's unbuilt.

### Entitlement & paywall (`BUILT`, but **DORMANT**)
- Users carry `active_plan_id / plan_status / plan_expires_at` (migration 032), **decoupled from RBAC**
  (never drives role/admin/live-trading) — `backend/app/db/models/user.py`.
- Gate: `require_active_plan` dep → **`402 {code:"PLAN_REQUIRED", upgrade_url:"/pricing"}`**
  (`backend/app/auth/entitlements.py:45-96`). Frontend surfaces it via `useApi`'s `paywalled` flag +
  the `UpgradeWall` component (`components/billing/upgrade-wall.tsx`).
- **Master kill-switch flag `PAYWALL_ENFORCED` defaults `False`** (`backend/app/core/config.py:379`) →
  today **every authenticated user sees all features**. Gated endpoints when flipped on: trades history +
  CSV export, `/strategies/executions`, marketplace ledger + history; backtest advanced panels are
  **field-nulled** (never 402). `PARTIAL` overall (built, off).
- **Razorpay billing** (subscribe/cancel/change-plan/HMAC webhook/admin-reconcile) is `BUILT`
  (`backend/app/api/billing.py`, migration 034) but **DORMANT — keys empty in prod** (fail-closed 503),
  and it does **not** auto-flip `PAYWALL_ENFORCED`. Interim provisioning: admin
  `PUT /api/admin/users/{id}/plan` (audit-logged).

---

## 2. Dashboard layout & every screen

Left sidebar + mobile drawer, **15 nav screens** under `frontend/src/app/(dashboard)/`. **13 BUILT on
real data** (via the shared `useApi` hook); 2 are non-functional.

| Screen | Status | What it does (evidence) |
|---|---|---|
| **Overview** `/` | `BUILT` | Kill-switch status, positions, signals (→ ConvictionSignals), brokers, P&L. `page.tsx:71-127` |
| **Positions** `/positions` | `BUILT` | `useApi` PositionsResponse, 15s auto-refresh, status filter. **Read-only — no close button by design** (exits arrive as Pine webhooks). `positions/page.tsx:46,72-77` |
| **Trades** `/trades` | `BUILT` | Execution history, **paywall-aware** (402 → UpgradeWall). `trades/page.tsx:76-80` |
| **Marketplace** `/marketplace`, `/[id]`, `/me` | `BUILT` | Browse + detail + "my subscriptions" (per-sub settings panel). `marketplace/page.tsx:50` |
| **Signals** `/signals` | `DESIGN` (mock) | Phase-1a **mock-only** feed + one-click confirm (no-op, no backend). `signals/page.tsx` — *this is the new module; see §4/§8* |
| **Kill Switch** `/kill-switch` | `BUILT` | Customer emergency close; token-confirmed trip/reset; daily loss/trade limits + auto-square-off config. `kill-switch/page.tsx:66-162` |
| **Analytics** `/analytics` | `BUILT` | Real P&L / win-rate from `/users/me/trades/stats`. `analytics/page.tsx:62-68` |
| **Chart** `/chart` | `BUILT` | ChartContainer + StrategyTesterPanel. ⚠️ **hardcodes `MVP_STRATEGY_ID = 89423ecc` (the LIVE BSE strategy) for every customer** — `chart/page.tsx:14,23` (config smell, see §11) |
| **Strategies** `/strategies` (+ `/new`, `/builder`, `/templates`, `/import-pine`) | `BUILT` | Strategy list + the builder suite (§5) |
| **Brokers** `/brokers` | `BUILT` (partial) | Live broker list + connect/disconnect + Fyers OAuth; **still imports mockDashboard for the "Coming Soon" broker cards** (mixed real+mock). `brokers/page.tsx` |
| **Webhooks** `/webhooks` | `BUILT` | TradingView webhook URL CRUD (`https://api.tradetri.com/api/webhook/strategy/<token>`). `webhooks/page.tsx` |
| **Settings** `/settings` | `BUILT` | `PUT /users/me` profile save. `settings/page.tsx:83` |
| **Compliance** `/compliance` | `BUILT` | Per-strategy compliance/audit report. `compliance/page.tsx:53-84` |
| **Help** `/help` | `BUILT` | Bilingual searchable FAQ (static content by design). |
| **Alerts** `/alerts` | `DESIGN` (stub) | `ComingSoon` placeholder — per-event Telegram toggles pending a preferences endpoint. `alerts/page.tsx` |

**Billing screens:** pricing is public (`/pricing`); post-checkout activation is webhook-driven + client
polling (`PlanCheckoutButton`). There is no dedicated in-dashboard "billing management" page yet beyond
Settings + the marketplace `/me` panel.

---

## 3. Subscribe flow & per-subscriber config (the vehicle/direction/qty selector)

**Subscribe is one-click, not a wizard.** `SubscribeButton` (on the listing detail page) POSTs an empty
`{}` to `/marketplace/listings/{id}/subscribe`; free/unconfigured → immediate `active`; paid → Razorpay
Checkout + poll `/subscriptions/me` until the webhook flips `active`
(`components/marketplace/subscribe-button.tsx`, `strategy_engine/api/marketplace.py:587-714`). The
**only** config surface is the inline **`SubscriptionSettings` panel in `/marketplace/me`** (per-row
"Settings" toggle, Active + pending subs).

### The vehicle → direction → quantity selector (target design vs reality)

| Control | Rule | Status | Evidence |
|---|---|---|---|
| **Quantity** — even-only 2–20 (+/− by 2) | min 2, even, blank = strategy default | `PARTIAL` — bare `<input type=number>` + client `validateLotsOverride` + server `_even_lots`; **persists** via `lots_override`. No stepper component. | `lib/billing/subscription-settings.ts:36-51`; `marketplace.py:200-209` |
| **Direction** — Long / Short / Both (**Cash = long-only**) | "Both" maps to the existing value `'all'` | `DESIGN` — **column exists** (`direction_filter` `'all'|'long'|'short'`, CHECK, migration 035) but is **not in the PATCH/GET schema, no UI, not enforced in fan-out** ("CARRIED, not branched on") | `db/models/marketplace_subscription.py:87-91` |
| **Vehicle** — Cash / Futures / Options | vehicle constrains direction | `DESIGN` — **absent entirely**: no vehicle column on the subscription, no UI. Vehicle lives on the **strategy** (`strategy_json['instrument_type']`, `resolve_instrument_type`, futures-default) and **no marketplace API exposes it to the client**. | `instrument_router.py:59-108`; grep vehicle/cash/futures in billing = none |
| Execution mode — paper/auto/one_click/offline | `offline`(MANUAL) is the new-subscriber default (migration 040) | `PARTIAL` — 4-mode dropdown BUILT; **only `paper` actually runs**; auto/one_click/offline are inert previews. | `marketplace.py:67-69`; `subscription-settings.ts:14-26` |
| is_paper toggle | paper vs live (live gated to later phase) | `PARTIAL` — bare checkbox; fan-out forces paper today. | `subscription-settings.tsx:169` |
| Sizing risk-preview | honest max-drawdown note | `PARTIAL` — "Historical max drawdown ~X% … Bigger size = bigger swings." | `subscription-settings.tsx:181-196` |

**Fit for the new selector (recommended, from the deep-audit):** add **Direction** + **Vehicle** as
sibling blocks in the existing `/me` settings grid and swap the bare qty input for an even-stepper —
frontend-only for qty (persists today) + direction-in-preview; **backend follow-ons** = expose
`direction_filter` in the PATCH/GET schema + enforce in fan-out (no migration — column exists), and
**expose the strategy's `instrument_type`** so Vehicle can display read-only and gate direction (recommend
vehicle **derived from the strategy**, not a new stored per-sub choice). Per-subscriber config columns
(`lots_override / execution_mode / is_paper / direction_filter / broker_credential_id`) already exist
(migration 035/037/038/040).

---

## 4. Black-box, showcase masking & the "30% reveal"

**Black-box has two coherent senses:** (1) marketing — opaque black-box signals are the *enemy*; TRADETRI
is the white/glass-box alternative; (2) marketplace — a subscriber sees a strategy's *performance* but
never its *internals*.

- **Showcase identity masking** `BUILT` — public `/api/showcase` anonymises to `s1/s2/s3`; real strategy
  UUIDs (`89423ecc`, `0252e82c`) are used only for an internal SQL count and **never returned**; the
  shipped artifact masks the instrument to a generic **"Equity F&O"** and name **"Strategy S1/S2/S3"**
  (stronger than the design doc). `backend/app/api/showcase_api.py:31-139`, `showcase_backtest.json`.
- **Internals hidden by owner-scoping** `BUILT` — every strategy read is filtered
  `Strategy.user_id == current_user.id` (404 for non-owners), and no marketplace endpoint returns rules/
  indicators/Pine. `ListingRead` carries only title/price/tags/perf-snapshot/counts + `strategy_id`/
  `creator_id` (opaque UUIDs). Creator ID is anonymised in the UI. `strategies.py:304-306`,
  `marketplace.py:101-121`, `listing-detail-header.tsx`.
- **Honest live record** `BUILT` — `/showcase/{key}/live` returns only an integer reconciled-trade count
  + honest note (paper → "paper_no_live"; 0 real → "tracking active, none reconciled"). No fabricated P&L.
- **"30% partial-strategy reveal / teaser"** `DESIGN` (**does not exist**) — exhaustive greps for
  reveal/30%/teaser/preview/blur/lock-percentage found **nothing**. There is no "show X% of a strategy"
  mechanism. Masking today is all-or-nothing (identity + internals hidden; performance shown). If a
  graduated reveal is wanted, it is entirely unbuilt and undesigned.

### Transparency Ledger `BUILT`
Per-listing tamper-evident ledger (daily cryptographic hash of reconciled trades, "Backtest nahi,
Proof."), chain-verify + 30/60/90-day milestones. Frontend panel reads `/marketplace/listings/{id}/ledger`
(+ `/verify`); plan-gated. `components/marketplace/transparency-ledger-panel.tsx`, migration 019.

---

## 5. Strategy builder & backtest

### Builders — three flows, all `BUILT`
- **4-door fork** `/strategies/new` → Use-a-proven (→marketplace), Build-my-own, Import Pine, Templates.
- **Beginner** — 5-step wizard (Goal→Setup→Preview→Run→Deploy), auto-backtest at step 4. `new/beginner/`.
- **Intermediate** — guardrailed single page (active-only indicators, AND-only entry). `new/intermediate/`.
- **Expert** — full 6-tab DSL (Indicators/Entry/Exit/Risk/Robustness/JSON), the only one honoring
  `?edit=<id>` hydration. `new/expert/`. All emit a strict-superset payload to `POST /strategies`.
- **Pine import** `BUILT` — pure-Python converter (no eval/network). `import-pine/`.
- **Templates catalog + clone** `BUILT` — clone → per-user `strategies` row. `strategies/templates/`.
- **M4 UnifiedBuilder** (collapse the 3 into one capability-matrix shell) — `DESIGN` only; spec
  `M4_CONSOLIDATION_SPEC.md` is **untracked + "awaiting review, nothing implemented."**
- **Block-template builders** (`/strategies/builder/{entry,exit,risk}`) — `PARTIAL`: save endpoints work
  but pages are **UI-orphaned** (no in-app link) and saved blocks feed nothing.
- Indicator catalogue = **70 indicators** (`registry.ts`). *"230 indicators" / "200+ strategies" are
  `STALE` marketing copy.*

### Backtest — the most mature area, `BUILT`
- **Sync engine** — deterministic pure-Python `run_backtest()` (frozen **v1.0.0**), 8-panel Strategy
  Tester (reliability/truth/regime/deviation/trade-quality/AI-doctor). `strategy_engine/backtest/`,
  `[id]/backtest/page.tsx`.
- **Async extension** `BUILT` (contrary to the stale May-2026 skeleton docs) — Celery layer, idempotency,
  persistence, 4 endpoints `POST/GET /api/backtest/*`, migration 028. Powers the **Milestone-3
  chart-with-trade-markers** panel. `backend/app/backtest_extension/`.
- **Premium gate** — advanced backtest panels are field-nulled (not 402) when `PAYWALL_ENFORCED` + not
  entitled. Basic result + equity + candles stay free.

---

## 6. Broadcast / fan-out execution model (`BUILT` but **DORMANT**)

The Tradetron/AlgoTest-style model: one owner's secret Pine signal → **N subscribers, each executing in
their OWN broker at their OWN size**, funds never pooled.

- **Spine is wired but flag-gated OFF**: `strategy_webhook.py` calls the additive, **PAPER-ONLY** fan-out
  block only when `MARKETPLACE_FANOUT_ENABLED` (**default False**, `config.py:393-407`). Today it does
  nothing in prod.
- Per-subscriber config (migration 035/040): `lots_override` (size), `execution_mode` (default
  **MANUAL/`offline`** since migration 040), `is_paper`, `direction_filter`, `broker_credential_id`.
- **Kill-switch tiers + live broker-close for subscribers** are built (subscriber-own-credential close,
  Redis halt store, webhook halt-block) — all dormant behind the same flag, paper-only, `place_order`
  never invoked. (Recent Module B+ work.)
- ⚠️ `CUSTOMER_PLATFORM.md §4` "subscribing creates nothing runnable / no fan-out" is now **STALE** — the
  fan-out spine exists (dormant).

---

## 7. Sync-safety, reconciliation, kill-switch & the exit model

- **Reconciliation loop** `BUILT` (backend-only) — `workers/reconciliation_loop.py`, every ~60s from
  FastAPI lifespan: for each live (`is_paper=False`) strategy's broker, diffs DB open positions vs broker
  positions; on mismatch fires a **CRITICAL Telegram alert to OPS**. No-op in paper; live+owner-scoped.
- **Customer-facing drift / sync-status banner** `DESIGN` (**GAP**) — drift is surfaced only to ops via
  Telegram; there is **no drift/desync badge anywhere in the customer UI**. (Also the stale-DB-row class
  of desync we corrected manually in the 2026-07-20 deploy.)
- **Exit-on-TradeTri model** `BUILT` — by design TradeTri does **not** autonomously square off; exits
  arrive as Pine/TradingView `PARTIAL/EXIT/SL_HIT` webhooks (direct-exit). Stated in the Positions header.
- **Kill Switch (customer emergency close)** `BUILT` — DB config + Redis state; per-user daily loss/trade
  limits + auto-square-off; token-confirmed trip so a stray click can't square off. `auto_square_off`
  opt-out gate added after the **2026-05-08 wipe incident**. `kill_switch_service.py`, `/kill-switch`.
- **Master emergency halt (founder, platform-wide)** `DESIGN`/DORMANT — `master_emergency.py` is a
  pure planner (halt flag + close-all plan + force-subscribers-MANUAL); enforcement wiring not live.

---

## 8. Brokers, capital & signals feed

- **Brokers**: Dhan = **prod (real money)**; Fyers = code-ready (verify broker-side algo permission);
  Zerodha / Upstox / AngelOne / Shoonya = **stubs / NotImplemented**. `docs/CUSTOMER_PLATFORM.md:38-39`.
- **Capital requirements** `DESIGN` — no structured `min_capital` field on templates/strategies; capital
  is mentioned only in explainer prose. If per-strategy capital gating is wanted, it's unbuilt.
- **Signals feed** `DESIGN` (mock) — `/signals` (the new Phase-1a module) is **mock-only**: a MANUAL
  pending-signal list + one-click "Take trade" that is a **no-op** (there is no backend subscriber
  signal-feed or confirm endpoint yet). Real wiring = flagged backend task (subscriber-scoped feed +
  confirm endpoint + server-enforced 5-min/EOD validity).

---

## 9. What's LIVE vs DORMANT today (flag summary)

| Capability | Flag / gate | Prod state |
|---|---|---|
| Paywall enforcement | `PAYWALL_ENFORCED` | **OFF** — everyone sees all features |
| Razorpay billing | keys empty | **DORMANT** (fail-closed) |
| Marketplace fan-out (broadcast) | `MARKETPLACE_FANOUT_ENABLED` | **OFF** — paper-only spine idle |
| Options execution | `OPTIONS_EXECUTION_ENABLED` | **OFF** |
| Cash execution | `CASH_EXECUTION_ENABLED` | **OFF** |
| New-subscriber default mode | migration 040 | `offline` (MANUAL) at DB layer |
| Live real-money strategy | — | **BSE `89423ecc` LIVE** (+ CDSL); never touched by customer-platform work |

---

## 10. ⚠️ STALE / contradictory inventory (correct these)

1. **Old 20% profit-share schema** — migration `007_verified_pnl_schema.py` (customer_capital_snapshots,
   monthly_billing_cycles, `profit_share_pct`) is **dead/superseded** (0 code references). Fully replaced
   by flat subscription. → note as historical; no live code path.
2. **Revenue-share on template clones** — `docs/TEMPLATES_IMPLEMENTATION_ROADMAP.md:73` still proposes it.
   → contradicts flat model; drop or mark future-only.
3. **"Royalty / payout tracking" + "payment stubbed / Phase 3 frontend"** — `marketplace.py:25` docstring
   + Architecture "Phase 4" imply a creator payout/revenue-share. → reconcile with flat-fee reality.
4. **`CUSTOMER_PLATFORM.md §4`** — "Billing: no Razorpay, no plan/tier on users" **and** "subscribing
   creates nothing runnable / no fan-out": **both stale** — Razorpay (mig 034-037) + fan-out spine exist.
5. **Tenor mismatch** — your brief says flat plans **monthly / 3 / 6 / 12-month**, but the **built** model
   is **monthly + yearly** only (Starter/Pro/Premium, mig 031). → decide: keep monthly/yearly, or build
   3/6/12-month tenors (new seed + UI).
6. **Per-tier feature caps are display-only** — the table advertises 1/3/6 brokers + 5/50/200 strategies,
   but nothing enforces them (flat premium gate). → build caps or soften the copy.
7. **"230 indicators" / "200+ strategies"** — stale copy (real = 70 indicators); mig 039 partly fixed the
   Premium bullet.
8. **`/chart` hardcodes the LIVE BSE strategy UUID** (`89423ecc`) for every customer — config smell, not
   money-moving, but wrong for a multi-customer product. → make it per-user.
9. **`M4_CONSOLIDATION_SPEC.md`** untracked + "awaiting review, nothing implemented" — treat as proposal.
10. **`SHOWCASE_BACKEND_DESIGN.md`** stamped "proposal — do NOT ship," but the showcase **is shipped** (and
    masks harder than the doc proposed). → doc lags code.
11. **ORM↔DB `execution_mode` default divergence** — migration 040 flips the DB default to `offline`, but
    on `main` the ORM model still defaults `auto` (the model-flip reconciliation is on an unmerged branch).
    → merge the model default so new ORM-created subscribers actually start MANUAL.

---

## 11. Build sequence (risk-ordered, from CUSTOMER_PLATFORM §5 + current reality)

1. **Data honesty + showcase** — ✅ DONE (masked, honest, live).
2. **Billing + access control** — **code-complete, flags OFF** (LAUNCH GATE — flip `PAYWALL_ENFORCED` +
   Razorpay keys when ready).
3. **Customer config + lifecycle** — PARTIAL: even-qty + execution-mode built; **direction + vehicle +
   customer drift banner + manual-exit UI = the next customer-facing slice.**
4. **Multi-user fan-out execution** — DANGEROUS, LAST: spine built + dormant + paper-only; real money only
   after thorough paper validation, founder-gated.
5. **Admin add/clone + scale (3 → 25–50)** — LATER.

**Smallest useful next customer slice:** wire the `/signals` feed + one-click to a real backend
(subscriber feed + confirm endpoint + validity enforcement), and finish the subscribe **direction/vehicle/
even-stepper** selector — both build directly on what exists, no rebuild.

---
*Generated read-only from code + docs on 2026-07-26. Every status tag is evidence-backed above; correct the
§10 stale items at will — this file is a consolidation, not a source of truth over the code.*
