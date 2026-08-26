# TRADETRI PROJECT DNA — Full Read-Only Audit (2026-07-31)

**Source of truth: the code** on branch `docs/stale-copy-cleanup` (working tree, HEAD 5de282f).
Produced by a 9-area parallel code audit (routers, execution core, data pipeline, database,
S1/S2/S3, frontend, live strategies, customer journey, docs reconciliation). READ-ONLY — no code,
git state, services, or EC2 touched. **Every item carries a status tag**:
`BUILT-LIVE` (implemented + registered/wired in this tree) · `READY-not-wired` (code merged,
dormant behind a flag / no caller) · `PARTIAL` · `STUB` · `PENDING` (not built) · `STALE` ·
`UNVERIFIABLE-LOCALLY` (prod DB/env runtime state on EC2 — cannot be read from this machine).

**Repos on this machine**
- `~/projects/trading-bridge/` — THE PLATFORM (this audit). Monorepo: `backend/` (FastAPI,
  `app/{api,services,brokers,tasks,workers,db,strategy_engine,domains,auth,core}`), `frontend/`
  (Next.js 15, `src/app/{(auth),(dashboard),(public),onboarding}`), `docs/` (~140 files),
  `scripts/`, `orderflow_engine/` (source on feat/orderflow-* branches; only .pyc on this branch),
  `trend_engine/` + `singhvi_levels/` (untracked research).
- `~/tradetri-strategies/pine_replica/` — SEPARATE project: the v4.8.1 engine replica + shadow
  recorder + executor M1/M2 (noted, out of scope here).
- `~/tradetri-backup/` — S3-pull landing dir (Sunday job; its `pull_s3.sh` currently missing).

**Prod state (freshest local evidence, still UNVERIFIABLE-LOCALLY):** deploy-log commit `a9a9952`
on branch `docs/customer-dashboard-spec` says **prod = main@2b909c5 + migration 040 live
(2026-07-20), all flags dormant**. This supersedes older session-memory claims of 038.

---

## 1. BACKEND

### 1a. API routers (all in `backend/app/api/`, registered in `app/main.py:256-316` unless noted)

| Router | Endpoints | Auth scope | Status | Key notes |
|---|---|---|---|---|
| auth.py | 6 (register/login/refresh/logout/change-password/me) | public + user | BUILT-LIVE | no OTP / no email verification (auth.py:34-51) |
| users.py | 19 (me, brokers×6, webhooks×4, strategies×4, trades×3) | user; **trades×3 gated `require_active_plan`** (users.py:606,656) | BUILT-LIVE | the paywall enforcement point (dormant while flag off) |
| pricing.py | 1 (GET /pricing/plans) | public | BUILT-LIVE | DB-read-only |
| billing.py | 8 (me/subscribe/cancel/change-plan/admin×3/razorpay webhook) | user/admin/public+HMAC | BUILT-LIVE code, **runtime-dormant** | 503 "Billing is not configured" when Razorpay keys empty (billing.py:111-115) |
| brokers.py | 4 (fyers connect+callback, dhan update-token+status) | user (callback public) | BUILT-LIVE | dhan/update-token probes real `/v2/fundlimit` before persisting (brokers.py:376-392) |
| strategy_webhook.py | 1 (**POST /api/webhook/strategy/{token}**) | token-in-path | BUILT-LIVE | THE live signal path; fan-out block flag-gated at :702 |
| webhook.py (legacy) | 1 | token(+opt HMAC) | READY-not-wired (conditional) | mounted only when `strategy_paper_mode=False` (main.py:255) |
| kill_switch.py | 9 (status/config/reset-token/reset/history/test/trip/daily-summary) | user | BUILT-LIVE | sacred file |
| strategy_signals.py | 3 (signals, signals/{id}, executions) | user | BUILT-LIVE | **owner-only** — excludes subscriber rows (`subscription_id IS NULL`, :94) |
| strategy_positions.py | 2 (positions, kill-switch) | user | BUILT-LIVE | |
| showcase_api.py | 3 (showcase, /{key}, /{key}/live) | public | BUILT-LIVE | see §2 (S1/S2/S3) |
| chart.py / chart_markers.py / trade_markers.py / strategy_tester.py | 2/1/2/3 | user | BUILT-LIVE | real Dhan on-demand candle fetch; `/chart` page hardcodes live UUID (see §3) |
| admin.py | 12-13 | admin | BUILT-LIVE | `PUT /users/{id}/plan` = manual provisioning stopgap "until Razorpay webhook" (admin.py:214) |
| admin_indicators.py / indicators.py | 6/4 | admin / creator+ | BUILT-LIVE | indicator approval queue |
| algomitra.py | 4 | user | BUILT-LIVE | real Anthropic (claude-sonnet-4-6) + Redis quota; key presence UNVERIFIABLE-LOCALLY |
| system.py / health.py | 1/4 | public | BUILT-LIVE | /api/system/mode exposes paper/kill-switch flags |
| role_demo.py | 4 | tiered roles | STUB (by design) | self-labelled demo, "Phase 3 replaces" |
| strategy_engine/api/* (crud, backtest, **marketplace** (1088 lines), marketplace_ledger, onboarding, pine_import, compliance, support, live_orders, templates×3) + backtest_extension | many | user | BUILT-LIVE | all registered; zero imported-but-unregistered routers found |

No `NotImplementedError`/mock-return endpoints anywhere in `app/api/` except role_demo.

### 1b. Execution core — how a signal becomes a Dhan order TODAY (owner path)
1. **Ingress** `POST /api/webhook/strategy/{token}` (strategy_webhook.py:128-142). Gate order
   (:159-671): platform-halt → token lookup → rate-limit 60/min → JSON → HMAC (**only if
   `webhook_require_hmac=True`; DEFAULT False → URL-token-only auth**, config.py:367) → Redis 60s
   content-hash idempotency → kill-switch → user-active → max-daily-trades → strategy resolve →
   market-hours 09:15-15:25 IST (paper-only bypass) → Pine detect/map → **symbol resolve** →
   Pydantic → qty ceiling 10000 → persist StrategySignal → Celery dispatch. BUILT-LIVE.
2. **Symbol resolution** (futures_resolver.py): `_TV_ROOT_TO_DHAN_ROOT` maps exactly
   BSE/CDSL/ANGELONE ×4 alias forms (:84-97); real `SEM_EXPIRY_DATE` from scrip master; 14:30
   expiry-day cutover. **Exit-class actions never re-resolve — pinned to stored position symbol**
   (strategy_webhook.py:399-428 → position_lookup.py). BUILT-LIVE.
3. **Celery** `execute_signal_async` (tasks/signal_execution.py:87, retries=3, acks_late) on a
   **shared persistent event loop** (core/async_bridge.py:96 — the asyncio.run-per-task bug fix IS
   in this tree). Same-fire duplicate guard (24h lookback, :149-189). BUILT-LIVE.
4. **AI validator** (ai_validator.py): LONG≥85→4 lots, ≥51→2, else reject; SHORT ≥51
   (:61-63,331-353). **Score precedence: Pine payload `score` honoured first; server
   `compute_score` is the FALLBACK** (ai_validator.py:411-412, pine_mapper.py:123-141). ⚠️ This
   CONTRADICTS the older session-memory claim of an always-injected server score — that memory is
   STALE vs this tree.
5. **Sizing** (strategy_executor.py): AI-on → `min(reco, entry_lots)×lot_size` (:485); lot size
   live from scrip-master `SEM_LOT_UNITS` via broker (dhan.py:1116-1126), never hardcoded; paper
   uses `lot_size_hint` default 1 (positions understate — known). Whole/even-lot validation.
6. **Order** `_live_place_order` (:848): session check → symbol probe → funds floor ×1.10 →
   per-signal broker idempotency claim → `broker.place_order`. Dhan adapter POST /orders, v2, NO
   deprecated drv* fields (dhan.py:1299-1316); **NRML trap: F&O + INTRADAY raises**
   (dhan.py:1284-1296). BUILT-LIVE.
7. **Exits** direct_exit.py execute_partial/execute_exit, lot-rounded; benign no-op if no
   position. BUILT-LIVE.
8. **Kill switch**: per-user gate in webhook + full API + auto-trip post-trade + emergency
   square-off — BUILT-LIVE. **Marketplace tiers 1/2/3 (kill_subscriber/kill_strategy/
   master_emergency): services exist but ZERO HTTP call sites — READY-not-wired** (only the
   TIER-3 halt *read* is wired into the webhook, :159).
9. **Reconciliation** `workers/reconciliation_loop.py` — lifespan asyncio task, diffs DB open
   positions vs broker per live credential, CRITICAL Telegram on mismatch. **Detection-only, no
   auto-heal.** BUILT-LIVE. Plus `position_loop.py` (internal target/SL/trail manager) and a
   Celery `pnl_reconciler` (every 15m market-hours; **log-only** — `pnl_reconciler_write`
   default False).
10. **Marketplace fan-out (Module B)**: wired at strategy_webhook.py:702 behind
    `marketplace_fanout_enabled` (default False) + exit mirroring in direct_exit. **PAPER-ONLY BY
    CONSTRUCTION** — subscribers forced to paper regardless of settings; broker credential
    resolved but used as placeholder; `execution_mode`/`direction_filter` stored but **not
    branched on** (marketplace_fanout.py:88-89,466-468). Real-money subscriber execution =
    PENDING. (config.py:393's "zero call sites" docstring is STALE — call sites exist.)

### 1c. THE DATA PIPELINE (executor-reuse map)
- **Daily Dhan token login — BUILT-LIVE (code); host-cron install UNVERIFIABLE-LOCALLY.**
  `scripts/auto_login.py`: pyotp TOTP → `POST auth.dhan.co/app/generateAccessToken` (3 attempts,
  TOTP slot guard, lockout-abort); token valid 23h30m; **writes the DB, not env** — Fernet-encrypts
  and atomically rotates `broker_credentials` (newest-active-row wins; `CRED_RELINK_ENABLED`
  default False). Telegram alert on failure. Scheduled per DEPLOY.md:122 as host cron
  `0 3 * * 1-5` UTC (=08:30 IST); log `/home/ubuntu/trading-bridge/logs/auto_login.log`.
  Fyers refresh = DEAD CODE (SEBI Apr-2026: manual daily login).
- **Market-data download — there is NO scheduled price-store job in the platform.** Charts fetch
  Dhan candles on demand per request (services/indicator_candles.py, nothing persisted). The
  Phase-3 historical backfill system (orchestrator + `DhanHistoricalClient` + tables
  `historical_candles`/`historical_backfill_jobs`, migrations 029/030) is **READY-not-wired**:
  `BACKFILL_ENABLED` default False, no beat entry, no API router, credential resolution is a
  `NotImplementedError` TODO.
- **Daily bhavcopy — DOES NOT EXIST in the platform.** Repo-wide `bhav` grep hits only
  `trend_engine/fetch_nse_delivery.py` (research CLI, manual, NSE archive
  `sec_bhavdata_full_*.csv` → gitignored parquet) and a docs mention (future cross-check).
  PENDING as a platform feature.
- **Celery beat jobs (tasks/celery_app.py:61-131)** — BUILT-LIVE: daily-pnl-reset 09:00 IST,
  market-status 60s, session/idempotency cleanups, daily trade report 16:00 IST, notifications,
  pnl-reconciler (log-only), **scrip-master warm 09:05 IST + 6h** (kills the ~9s F&O order-path
  download), options-expiry-sweep 15:35 (dormant, flag off).
- **Other**: Postgres backup cron drop-in (`backend/scripts/cron/tradetri-backup.cron`: pg_dump→
  S3 21:30 UTC + restore-verify + weekly Glacier) — code READY, install UNVERIFIABLE-LOCALLY.
  Orderflow recorder: **source not on this branch** (only .pyc); lives on feat/orderflow-*
  (self-scheduled daemon 09:05→15:40 IST + S3 backup); runtime state UNVERIFIABLE-LOCALLY.
- **Executor-reuse contract**: token source = newest active `broker_credentials` row (broker key
  lowercase `dhan`); no EOD price store exists — activate the backfill path or productionize the
  trend_engine fetcher if the executor needs stored prices.

### 1d. Database (42 migration files, 001→040; local head **040_manual_exec_default**)
- Two parallel 034/035 tracks merged by 037; `alembic upgrade head` unambiguous. 039 = data-only
  copy fix; 040 flips `marketplace_subscriptions.execution_mode` DEFAULT auto→**offline**
  (default-only). ORM model already matches 040 (marketplace_subscription.py:78-80) — the spec's
  C8 "ORM divergence" note is now resolved.
- Key models (`app/db/models/`, 34 files): `users` (entitlement block: active_plan_id,
  plan_status default 'none', razorpay_subscription_id — deliberately decoupled from RBAC);
  `strategies` (**is_paper NOT NULL default TRUE**; migration 027 backfilled all TRUE except
  hardcoded founder id `89423ecc-…` → FALSE; **no execution_mode / no options_config column** —
  options parse from `strategy_json["options"]`; the 029-options branch is unmerged);
  `marketplace_listings` / `marketplace_subscriptions` (lots_override, execution_mode 'offline',
  is_paper TRUE, direction_filter — **carried, not consumed**); `strategy_positions` +
  `strategy_executions` (+`subscription_id` FK for subscriber isolation);
  `trades`, `strategy_signals`, `webhook_events` (schema live; this webhook path writes
  `strategy_signals`, NOT webhook_events — consistent with the long-observed empty table);
  Razorpay: `razorpay_payments` + `razorpay_webhook_events` (idempotent) + `subscription_plans`;
  `audit_logs` + `strategy_state_audit` (033 PG trigger on is_paper/is_active flips — no ORM
  model, DB-trigger-written); `copy_trading_*` — STALE (superseded by marketplace).

---

## 2. S1 / S2 / S3 — DEFINITIVELY RESOLVED
**They are the anonymised public showcase codes for the three futures strategies:**
`s1 = BSE (live UUID 89423ecc…)`, `s2 = CDSL (0252e82c…)`, `s3 = ANGELONE (None — paper, no live
id)`. Not DB slots, not tables, not seeds.
- Defined in exactly two places: `showcase_api.py:35-39` (`_LIVE_STRATEGY` hardcoded dict; UUID
  used only for an internal reconciled-trades SQL join, never returned) and the checked-in
  artifact `backend/scripts/showcase_backtest.json` ("Strategy S1/S2/S3", masked by hand in
  commit `0e522bd`, 2026-07-11).
- Consumed by public `GET /api/showcase*` + frontend `(public)/showcase/page.tsx` (key-agnostic).
  `/{key}/live` counts real reconciled trades (`is_paper=false`, `final_pnl NOT NULL`,
  `broker_order_id NOT LIKE 'PAPER-%'`).
- Feed pipeline: TV trade-list CSVs → `ingest_backtest_trade_list.py` /
  `ingest_angelone_trade_list.py` → sqlite `backtest_signal_history.sqlite3::backtest_trades`
  (BSE 1149 / CDSL 1032 / ANGELONE 942 rows verified) → `showcase_metrics.py build_doc()` → JSON.
- ⚠️ **STALE / regeneration hazard**: `showcase_metrics.py:335` still emits REAL identities
  (`bse`/`cdsl`/`angelone` keys + display names + lot sizes). **Re-running the generator would
  produce an UNMASKED artifact that leaks identity publicly AND breaks `/live`** (keys no longer
  match `_LIVE_STRATEGY`). The mask exists only in the hand-edited artifact + API dict.
- Untracked `backend/scripts/ingest_backtest_signal_log.py` = a separate entries-only Pine
  signal/feature store (table `backtest_signal_history`) — READY-not-wired, nothing in `app/`
  consumes it (research ingestion).
- Unrelated same-name uses: pivot-point indicator levels (S1/S2 supports); the frontend mock
  signal feed labels ("Strategy S1/S2/S3" in `lib/mock/signals-mock.ts`); QA/smoke doc IDs.

---

## 3. FRONTEND (Next.js, `frontend/src/app`)
**13 of 15 dashboard screens are wired to the real backend.** Real: login/register, dashboard
home, positions (15s poll), trades (+402 paywall plumbing ready), analytics, marketplace
(browse/detail/subscribe/ratings), marketplace/me + subscribe-settings, webhooks, kill-switch
(two-step confirm trip), chart (live WS ticks + strategy tester), settings, onboarding,
compliance, help/support, indicators glossary+requests, strategies list/detail/backtest
(sync+async poll), builders (beginner/intermediate/expert + entry/exit/risk templates +
Pine import), admin suite (users/audit/kill-switch-events/announcements/compliance/indicators),
public pages + pricing + showcase.
- **/signals — STUB (deliberate mock)**: renders `MOCK_SIGNALS` from `lib/mock/signals-mock.ts`
  (page.tsx:33; "swap for useApi fetch when the backend lands"). Customer-visible in the sidebar.
- **One-click confirm — STUB (no-op by design)**: `one-click-confirm-button.tsx:44-56` — real
  `api.post(/marketplace/signals/{id}/confirm)` commented out ("Phase-1c backend-blocked");
  click = 350ms fake latency + "Mock confirm — no order placed" toast.
- **/alerts — STUB** (ComingSoon). **/brokers — PARTIAL** (real CRUD; `mockDashboard` used only
  for cosmetic coming-soon cards).
- **subscribe-settings — PARTIAL by design**: even-qty lots stepper LIVE (`api.patch` persists);
  direction + vehicle are PREVIEW-ONLY local state (backend PATCH schema lacks
  `direction_filter`; vehicle absent server-side entirely).
- ⚠️ `/chart` hardcodes `MVP_STRATEGY_ID = "89423ecc…"` — every customer's chart page is pinned
  to the founder's live BSE strategy id.
- **UnifiedBuilder (M4) — PENDING**: zero references in src; only the Expert builder handles
  `?edit=` (expert/page.tsx:351); mode-selector orphaned. Matches M4 spec.
- Mock inventory (runtime-consumed): signals-mock (whole feed), mock-data (cosmetic broker
  cards); `admin-mock-data.ts` is dead/unimported — STALE.
- Branches: `feat/signal-feed-mock` + `feat/green-plus-signals` are MERGED into this lineage
  (877b945); `feat/signal-feed-live` does not exist; `feat/marketplace-fanout` backend deployed
  per docs; assorted unmerged feature branches (analytics-real etc.) not page-audited.
- API base fallback hardcoded `https://api.tradetri.com/api` (lib/api.ts:13); Vercel-preview
  CORS blocker is backend-allowlist (unverifiable locally).

---

## 4. LIVE STRATEGIES (BSE / CDSL / ANGELONE)
- **Single shared code path, zero per-underlying branches** — a strategy is (user_id,
  webhook_token → strategy row); adding an F&O underlying = adding 4 alias keys to
  `_TV_ROOT_TO_DHAN_ROOT`.
- **BSE**: resolver BSE1!/NSE:BSE/BSE:NSE/BSE → front-month `BSE-…-FUT` via live scrip master.
  is_paper=false was seeded for `89423ecc` by migration 027:72-81 (the only hardcoded strategy
  id in the schema). Current DB value UNVERIFIABLE-LOCALLY.
- **CDSL**: identical plumbing (4 keys). Live status (0252e82c is_paper) UNVERIFIABLE-LOCALLY.
- **ANGELONE**: resolver keys exist; **no other ANGELONE-specific code anywhere**; live/paper
  status UNVERIFIABLE-LOCALLY (doc-claims: paper, AI-gate rejects at 48.35 < threshold 51 —
  consistent with ai_validator.py:61).
- Alert flow: TV alert (Pine v4.8.1 payload w/ ~17 indicator keys + optional score, or native
  payload) → webhook gates → resolver → Celery → AI validator → executor → Dhan NRML order.
  Lot sizes live from scrip master. Market-hours 403 outside 09:15-15:25 for non-paper.
- **Sacred files all present** and untouched: strategy_executor.py, direct_exit.py, webhook.py +
  strategy_webhook.py, kill_switch.py + kill_switch_service.py, brokers/dhan.py + fyers.py,
  strategies migrations. NRML-only trap enforced in code (dhan.py:1284-96).

---

## 5. CUSTOMER JOURNEY 0→100 (walked in code)
| Leg | State | Break point |
|---|---|---|
| 1. Sign up / login | **WORKS** end-to-end (no OTP/email-verify) | — |
| 2. Pick plan & pay | **BUILT, config-gated**: full Razorpay M1-M4 (subscribe/cancel/change/webhook/reconcile) + frontend checkout modal + 402 UpgradeWall | Keys empty → `503 Billing is not configured` (billing.py:111-115); `paywall_enforced=False` means nothing requires a plan anyway |
| 3. Subscribe to a strategy | **WORKS today for free/unconfigured-gateway listings** (immediate ACTIVE sub row); paid path inherits Leg-2 gate. Settings GET/PATCH live (lots stepper) | — |
| 3.5 Connect own broker | **WORKS** (Dhan token probe-then-store; Fyers OAuth) | — |
| 4. Receive a live signal | **UNBUILT (backend), STUB (frontend)** | No subscriber-feed endpoint exists at all (`/marketplace/signals` = zero hits); owner endpoint filters `subscription_id IS NULL`; frontend renders mock fixtures |
| 5. One-click execute on own Dhan | **UNBUILT** | No confirm endpoint; fan-out is flag-off AND paper-forced by construction (marketplace_fanout.py:466-468) — no code path places a real order on a subscriber's Dhan |

**Bottom line: a real customer today gets exactly as far as "subscribed (free listing) with
broker connected and lots configured" — leg 3.5 of 5. The first hard break is Leg 4: the
subscriber signal feed has no backend at all.** (A customer who builds their OWN strategy — not
marketplace — does reach real execution via their own webhook token, subject to is_paper.)

---

## 6. COMPLETION MAP
| Area | % | Ready / Remaining |
|---|---|---|
| Owner execution core (signal→Dhan) | **~95%** | Battle-hardened path incl. resolver, idempotency×3, NRML trap, exits, kill-switch, reconciliation(detect-only). Remaining: nothing blocking; auto-heal reconciliation optional |
| Data pipeline | **~55%** | Token auto-login + scrip-master warm + backups: ready. Remaining: NO stored price data (backfill dormant w/ TODO), NO bhavcopy job, pnl-reconciler write-off |
| Billing (Razorpay) | **~90% code / 0% active** | All endpoints+webhook+models+plans seeded. Remaining: set keys, flip `paywall_enforced`, admin-provisioning → automated |
| Marketplace (browse/subscribe) | **~85%** | Listings/subscribe/ratings/settings live. Remaining: direction_filter+vehicle in PATCH schema & enforcement |
| Fan-out execution (Module B) | **~60%** | Paper fan-out fully wired (flag-off). Remaining: execution_mode branching, real-money path, subscriber kill-switch HTTP surface, compliance gate |
| Subscriber signal feed | **~15%** | Frontend mock only. Remaining: the entire backend endpoint + subscriber-scoped reads |
| One-click execute | **~5%** | Mock button. Remaining: confirm endpoint w/ validity re-check + idempotency + real order path |
| Customer onboarding (auth+broker) | **~100%** | Works. (No email verification — a launch decision) |
| Frontend dashboard | **~85%** | 13/15 screens real. Remaining: /signals live wiring, /alerts, chart de-hardcoding, UnifiedBuilder M4 |
| Showcase | **~90%** | Live+masked. Remaining: fix generator mask (regen hazard) |

---

## 7. RECONCILIATION vs CUSTOMER_DASHBOARD_SPEC.md (branch `docs/customer-dashboard-spec`, 350df52, 2026-07-26)
The spec is the freshest doc and **~95% matches code**. Where reality has moved / needs correction:
- **C4 (subscribe-settings)**: spec's "no stepper / no direction UI" is STALE — commit e017cb6
  (post-spec) shipped the even-qty stepper (live) + direction/vehicle (preview-only). Backend
  PATCH schema still lacks `direction_filter` — that half stands.
- **C8 (ORM default divergence)**: RESOLVED — model now matches migration 040 (`offline`).
- **C9 (stale copy)**: fixed on this branch (5de282f: flat-subscription copy, 70 indicators).
- Everything else confirmed: plans/paywall flag-off, 13/15 screens, showcase mask (and the "30%
  partial reveal" indeed does not exist), fan-out paper-only, reconciliation ops-only, chart
  UUID hardcode.
Older docs, for the record: **MASTER_ROADMAP.md (05-18) is badly STALE** (claims marketplace
"NOT STARTED 0%", backtest router "not registered" — both flatly contradicted by code);
B3_PAYWALL_PLAN + MARKETPLACE_ARCHITECTURE are executed plans whose future-tense sections are
now drift; CUSTOMER_PLATFORM.md is current per its own update markers (launch-model decision
still OPEN).

---

## 8. UNCERTAINTY FLAGS (everything not knowable from this machine)
1. Prod runtime env: `MARKETPLACE_FANOUT_ENABLED`, `PAYWALL_ENFORCED`, Razorpay keys,
   `webhook_require_hmac`, options/cash flags — code defaults all False/empty; deploy-log claims
   all dormant.
2. Prod DB rows: is_paper/is_active for 89423ecc / 0252e82c / ANGELONE; reconciled trade counts
   behind `/showcase/{key}/live`; kill-switch states.
3. Prod head: main@2b909c5 + migration 040 (deploy-log commit dated 2026-07-20) — freshest claim,
   not directly verifiable.
4. Host crons on EC2 (auto_login 08:30 IST, backup cron installed?) and orderflow recorder
   runtime.
5. GitHub-side branch/PR state (e.g. guided-builder PR existence).

*Only file created by this audit: `TRADETRI_PROJECT_DNA.md`. No code, config, git state, or
runtime was touched.*
