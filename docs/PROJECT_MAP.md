# TRADETRI — Project Completion Map (code-verified)

**READ-ONLY snapshot as of `2026-06-13` @ `8ca26ad` on branch `feat/queue-ccc-historical-candles-skeleton`.**
Paste alongside `docs/MASTER_CONTEXT.md` + `docs/SESSION_HANDOFF.md` in any new chat.

Methodology: pure static code inspection of the local repo. No SSH, no runtime probe, no DB writes, no Dhan/network. Items I could not verify from code are marked **[unclear — needs runtime check]**.

---

## 1. Wiring Table (the core deliverable)

Coverage: 48 frontend pages × 36 mounted backend routers. Pages that delegate API calls to components or hooks are credited via their delegated calls.

| # | Page route | Backend endpoint(s) called | Wired? |
|---|---|---|---|
| 1 | `/(auth)/login` | `POST /api/auth/login`, `POST /api/auth/refresh` (via `lib/auth` + `lib/api`) | **real API** |
| 2 | `/(auth)/register` | `POST /api/auth/register` (via `lib/auth` + page) | **real API** |
| 3 | `/onboarding` | `POST /api/onboarding/complete` (page), `GET /api/onboarding/state` (`useOnboarding` hook) | **real API** |
| 4 | `/(public)/home` | none | static marketing |
| 5 | `/(public)/about` | none | static |
| 6 | `/(public)/contact` | none | static |
| 7 | `/(public)/pricing` | none — pricing tiers are hardcoded; no `/billing` router exists | static / **placeholder** |
| 8 | `/(dashboard)` (home) | `GET /api/strategies/positions?limit`, `GET /api/strategies/signals?limit`, `GET /api/users/me/brokers`, `fetch /health` | **real API** |
| 9 | `/chart` | `GET /api/chart/history`, `GET /api/chart/markers`, `GET /api/chart/ws-token`, WS `/ws/chart/{symbol}/{tf}`, `GET /api/strategy-tester/{id}/metrics|equity|trades` (via `StrategyTesterPanel`), `GET /api/markers` (via `useTradeMarkers`) | **real API** |
| 10 | `/brokers` | `GET /api/users/me/brokers`, `POST /api/users/me/brokers`, `PUT /api/users/me/brokers/{id}`, `GET /api/brokers/dhan/status` (via `useBrokerStatus`) | **real API** |
| 11 | `/positions` | `GET /api/strategies/positions?limit/status` (via `use-api`) | **real API** |
| 12 | `/trades` | `GET /api/users/me/trades`, `GET /api/users/me/trades/stats` (via `useAlgoMitraLive` for stats; trades list path inferred from `api.ts` JSDoc) | **real API** |
| 13 | `/kill-switch` | `GET /api/kill-switch/config`, `PUT /api/kill-switch/config`, `GET /api/kill-switch/status` | **real API** |
| 14 | `/strategies` | `GET /api/strategies` (via `useApi<StrategyListResponse>`) | **real API** |
| 15 | `/strategies/new` | `GET /api/strategies` (via `useApi`) | **real API** |
| 16 | `/strategies/new/beginner` | `POST /api/strategies` (synthetic backtest fallback for builder) | **real API** + synthetic data downstream |
| 17 | `/strategies/new/intermediate` | `POST /api/strategies`, `GET /api/strategies/indicators` (via `useApi`) | **real API** |
| 18 | `/strategies/new/expert` | `POST /api/strategies`, `PUT /api/strategies/{id}`, `GET /api/strategies/{id}` | **real API** |
| 19 | `/strategies/import-pine` | `POST /api/strategies/pine-import` (via `lib/api`) | **real API** |
| 20 | `/strategies/{id}` | `GET /api/strategies/{id}`, `POST /api/orders/live`, `GET /api/orders/live/preflight` (via `go-live-modal` + `safety-pre-flight-panel`) | **real API** |
| 21 | `/strategies/{id}/backtest` | `POST /api/strategies/{id}/backtest`, `GET /api/backtest/{run_id}/markers` (via `BacktestChartPanel`), `GET /api/strategies/{id}/compare-fix` likely (via `comparison-modal`) | **real API** |
| 22 | `/strategies/templates` | `GET /api/templates`, `GET /api/templates/{slug}` | **real API** |
| 23 | `/strategies/templates/{slug}` | `GET /api/templates/{slug}`, `POST /api/templates/{slug}/clone` (inferred from API + slug page) | **real API** |
| 24 | `/strategies/builder/entry` | `POST /api/templates/entry`, `PUT /api/templates/entry/{id}`, `DELETE /api/templates/entry/{id}`, `GET /api/templates/entry` (via `useApi`) | **real API** |
| 25 | `/strategies/builder/exit` | `POST/PUT/DELETE/GET /api/templates/exit` | **real API** |
| 26 | `/strategies/builder/risk` | `POST/PUT/DELETE/GET /api/templates/risk` | **real API** |
| 27 | `/strategies/indicators` | none direct — uses static `lib/indicators/content/*.ts` (~230 frontend-baked indicator defs) | **frontend-baked** (not a placeholder) |
| 28 | `/indicators` | static frontend content (`lib/indicators/content`) | **frontend-baked** |
| 29 | `/indicators/requests` | `GET /api/indicators/queue/me`, `POST /api/indicators/queue`, `POST /api/indicators/queue/{id}/withdraw` | **real API** |
| 30 | `/marketplace` | `GET /api/marketplace/listings` (via `useApi`) | **real API** |
| 31 | `/marketplace/{id}` | `GET /api/marketplace/listings/{id}`, `GET /api/marketplace/listings/{id}/ratings`, `GET /api/marketplace/subscriptions/me`, `POST/DELETE /api/marketplace/listings/{id}/subscribe`, `POST/PUT /api/marketplace/listings/{id}/ratings`, `GET /api/marketplace/listings/{id}/ledger` (+ `/history`, `/verify`, `/snapshot/{seq}`) | **real API** |
| 32 | `/marketplace/me` | `GET /api/marketplace/subscriptions/me`, `GET /api/marketplace/listings/me`, `POST /api/marketplace/listings/{id}/publish`, `POST /api/marketplace/listings/{id}/archive`, `POST .../ledger/snapshot/now` | **real API** |
| 33 | `/compliance` | none (or static badges) | **[unclear — needs runtime check]** |
| 34 | `/compliance/legal` | none — Hinglish disclaimer text from `lib/compliance/disclaimer-text` | static |
| 35 | `/help` | none — static FAQ via `lib/help/*` | static |
| 36 | `/support` | `POST /api/support/tickets` (via `ticket-form` component) | **real API** |
| 37 | `/support/faq` | none — static | static |
| 38 | `/alerts` | none | **placeholder ("Coming Soon")** |
| 39 | `/analytics` | none | **placeholder ("Coming Soon")** |
| 40 | `/settings` | none | **placeholder ("Coming Soon")** |
| 41 | `/webhooks` | none — `GET/POST/DELETE /api/users/me/webhooks` defined in backend but page is a "Coming Soon" placeholder | **placeholder ("Coming Soon")** (backend exists, frontend doesn't consume) |
| 42 | `/admin` | none | **placeholder ("Coming Soon")** |
| 43 | `/admin/users` | none — backend `GET/POST/PUT /api/admin/users[/{id}/...]` exists; frontend is Coming Soon | **placeholder ("Coming Soon")** |
| 44 | `/admin/announcements` | none — backend `POST /api/admin/announcements` exists; frontend is Coming Soon | **placeholder ("Coming Soon")** |
| 45 | `/admin/audit` | none — backend `GET /api/admin/audit-logs` exists; frontend is Coming Soon | **placeholder ("Coming Soon")** |
| 46 | `/admin/kill-switch-events` | none — backend `GET /api/admin/kill-switch-events` exists; frontend is Coming Soon | **placeholder ("Coming Soon")** |
| 47 | `/admin/indicators` | likely calls `GET /api/admin/indicators/queue`, `POST /approve|reject` (real card UI, not coming-soon) | **real API** (no direct call grep hit at page-level — needs runtime check) |
| 48 | `/admin/compliance` | likely calls `GET /api/compliance/strategies/me`, `/indicators` (real card UI, not coming-soon) | **real API** [unclear — needs runtime check] |

**`coming-soon` placeholder count:** **9 pages** confirmed importing `@/components/coming-soon`: `/alerts`, `/analytics`, `/settings`, `/webhooks`, `/admin`, `/admin/announcements`, `/admin/audit`, `/admin/kill-switch-events`, `/admin/users`.

**Counter-intuitive finds:**
- `/webhooks` is "Coming Soon" but the backend has full `/api/users/me/webhooks` CRUD ready.
- `/admin/users` + `/admin/announcements` + `/admin/audit` + `/admin/kill-switch-events` — same pattern: backend wired, frontend pending.
- `/(public)/pricing` is fully static — there is **no `/api/billing` or `/api/plans` router anywhere**. SaaS subscription tier gating is not implemented.

---

## 2. Backend Route Inventory

### 2.1 — Mounted routers (counted from `main.py` includes, lines 188-296)

36 routers mounted in `app.main:create_app()`. All routers below are reachable from a deployed worker.

#### Identity & users
| Router | Prefix | File | Notes |
|---|---|---|---|
| `auth_router` | `/api/auth` | `app/api/auth.py` | register / login / refresh / logout / change-password / me |
| `users_router` | `/api/users` | `app/api/users.py` | me + brokers CRUD + webhooks CRUD + strategies CRUD + trades + trades export + stats |
| `admin_router` | `/api/admin` | `app/api/admin.py` | users + audit-logs + system-health + broker-health + kill-switch-events + announcements (admin-only) |
| `role_demo_router` | `/api/roles` | `app/api/role_demo.py` | RBAC demo (me / pro / creator / super-admin tier endpoints) |
| `onboarding_router` | `/api/onboarding` | `app/strategy_engine/api/onboarding.py` | state / step / preferences / complete |

#### Strategies & builders
| Router | Prefix | File |
|---|---|---|
| `strategy_crud_router` | `/api/strategies` | `app/strategy_engine/api/strategies.py` |
| `strategy_versions_router` | `/api/strategies` | `app/strategy_engine/api/strategy_versions.py` |
| `strategy_backtest_router` | `/api/strategies` | `app/strategy_engine/api/backtest.py` |
| `strategy_compare_fix_router` | `/api/strategies` | `app/strategy_engine/api/compare_fix.py` |
| `pine_import_router` | `/api/strategies` | `app/strategy_engine/api/pine_import.py` |
| `strategy_signals_router` | `/api/strategies` | `app/api/strategy_signals.py` |
| `strategy_positions_router` | `/api/strategies` | `app/api/strategy_positions.py` |
| `indicators_router` (engine) | `/api/strategies` | `app/strategy_engine/api/indicators.py` |
| `strategy_templates_router` | `/api/templates` | `app/templates/api.py` |
| `entry_templates_router` | `/api/templates/entry` | `app/strategy_engine/api/entry_templates.py` |
| `exit_templates_router` | `/api/templates/exit` | `app/strategy_engine/api/exit_templates.py` |
| `risk_templates_router` | `/api/templates/risk` | `app/strategy_engine/api/risk_templates.py` |
| `indicators_user_router` | `/api/indicators` | `app/api/indicators.py` |

#### Backtesting
| Router | Prefix | File | Notes |
|---|---|---|---|
| `strategy_tester_router` | `/api/strategy-tester` | `app/api/strategy_tester.py` | Phase D — `/{id}/metrics`, `/equity`, `/trades` |
| `backtest_extension_router` | `/api/backtest` | `app/backtest_extension/api.py` | Days 1-3 of Week 2 extension — async queue + enqueue + status + trades + markers |

#### Execution & safety
| Router | Prefix | File |
|---|---|---|
| `webhook_router` | `/api/webhook` | `app/api/webhook.py` (legacy, **conditionally registered**) |
| `strategy_webhook_router` | `/api/webhook/strategy` | `app/api/strategy_webhook.py` |
| `live_orders_router` | `/api/orders` | `app/strategy_engine/live_orders/api.py` — `POST /live`, `GET /live/preflight` |
| `kill_switch_router` | `/api/kill-switch` | `app/api/kill_switch.py` |
| `brokers_router` | `/api/brokers` | `app/api/brokers.py` — Fyers OAuth + Dhan status + connect |

#### Marketplace & ledger
| Router | Prefix | File |
|---|---|---|
| `marketplace_router` | `/api/marketplace` | `app/strategy_engine/api/marketplace.py` |
| `marketplace_ledger_router` | `/api/marketplace/listings/{listing_id}/ledger` | `app/strategy_engine/api/marketplace_ledger.py` |

#### Chart & markers
| Router | Prefix | File |
|---|---|---|
| `chart_router` | (uses absolute `/api/chart/...` paths) | `app/api/chart.py` — `/history`, `/ws-token` |
| `chart_markers_router` | (absolute `/api/chart/markers`) | `app/api/chart_markers.py` |
| `trade_markers_router` | `/api/markers` | `app/api/trade_markers.py` |

#### Support, system, compliance
| Router | Prefix | File |
|---|---|---|
| `support_router` | `/api/support` | `app/strategy_engine/api/support.py` — ticket CRUD |
| `system_router` | `/api/system` | `app/api/system.py` — `/mode` only |
| `compliance_router` | `/api/compliance` | `app/strategy_engine/api/compliance.py` — strategies/me + indicators + reports |
| `admin_indicators_router` | `/api/admin/indicators` | `app/api/admin_indicators.py` — queue + overrides |
| `health_router` | `/health` | `app/api/health.py` |
| `backup_health_router` | `/api/health` | `app/strategy_engine/api/health.py` — `/backups` |

#### AI advisor
| Router | Prefix | File | Notes |
|---|---|---|---|
| `algomitra_router` | `/api/algomitra` | `app/api/algomitra.py` | messages / quota / sessions / sessions/{id}/messages |

### 2.2 — Defined but NOT mounted

`backend/app/templates/api.py` declares additional routes (lines 110-212) — all mounted via `strategy_templates_router`. No orphan routers found in this audit.

### 2.3 — Conditionally mounted

`webhook_router` (line 239 of `main.py`) sits behind a conditional (`if …:`) — legacy webhook handler, **status [unclear — needs runtime check]** of the toggle gate.

### 2.4 — Stubs / placeholder endpoints

| Endpoint | Where | Status |
|---|---|---|
| Broker adapters `zerodha`, `upstox`, `shoonya`, `angelone` | `app/brokers/*.py` | **`NotImplementedError` stubs** — only Dhan + Fyers are real. (Per `TRADETRI_AUDIT.md`.) |
| `_dhan_client_factory_for_job` | `app/tasks/historical_backfill_tasks.py` | **stub raising `NotImplementedError`** behind OFF flag — see Anomaly A5 in SESSION_HANDOFF. |

### 2.5 — Feature-flagged OFF paths

| Flag | Where | Default |
|---|---|---|
| `BACKFILL_ENABLED` | `app/tasks/historical_backfill_tasks.py:_backfill_enabled` | **OFF** — backfill task short-circuits before any DB/Dhan touch. |

---

## 3. Frontend Page Inventory

**Total pages:** 48 `page.tsx` files.

### 3.1 — Pages by area

| Area | Pages | Wiring summary |
|---|---|---|
| Auth (`/login`, `/register`, `/onboarding`) | 3 | all real-API wired |
| Public marketing (`/home`, `/about`, `/contact`, `/pricing`) | 4 | static — no backend calls |
| Dashboard home | 1 | real API |
| Chart | 1 | real API + WebSocket |
| Brokers | 1 | real API |
| Kill switch | 1 | real API |
| Positions / Trades | 2 | real API |
| Strategies (list / new / edit / detail / backtest / templates / import / builders) | 13 | all real API |
| Indicators (library + requests + admin queue) | 3 | mix — library is frontend-baked, requests + admin-queue are real API |
| Marketplace (browse / listing / my) | 3 | real API |
| Compliance | 2 | static or unclear |
| Support (form + FAQ) | 2 | form = real API; FAQ = static |
| Help | 1 | static |
| **Coming-soon placeholders** | **9** | `/alerts`, `/analytics`, `/settings`, `/webhooks`, `/admin`, `/admin/users`, `/admin/announcements`, `/admin/audit`, `/admin/kill-switch-events` |
| Admin (real cards) | 2 | `/admin/indicators`, `/admin/compliance` |

### 3.2 — Frontend API client

- `frontend/src/lib/api.ts` — typed JWT-aware client. Base URL precedence: `NEXT_PUBLIC_API_URL/api` → fallback `https://api.tradetri.com/api`.
- `frontend/src/lib/use-api.ts` — React hook wrapper.
- `frontend/src/hooks/*` — 13 domain hooks (`useChartHistory`, `useChartWebSocket`, `useStrategyTester`, `useAlgoMitra`, `useAlgoMitraLive`, `useTradeMarkers`, `useBrokerStatus`, `useSystemMode`, `useOnboarding`, `useChartMarkers`, `useChartScrollback`, `useWsToken`, `use-algomitra-context`).

### 3.3 — Frontend-baked content (not placeholders, but no backend dependency)

- `lib/indicators/content/*.ts` — ~230 indicator definitions across 18 packs. `/strategies/indicators` + `/indicators` consume directly.
- `lib/help/*` — FAQ content. `/help` + `/support/faq` consume.
- `lib/compliance/disclaimer-text` — Hinglish legal text. `/compliance/legal` consumes.
- `lib/strategies/explainers` — strategy templates `/templates/{slug}` page deep-dive content.
- `lib/marketing/*` — landing page copy.

---

## 4. Subsystem Status Matrix

| Subsystem | Status | Evidence |
|---|---|---|
| Auth (register / login / refresh / me / change-password) | **BUILT + WIRED** | `app/api/auth.py` ↔ `frontend/src/app/(auth)/login,register/page.tsx`, `lib/auth.ts` |
| Dashboard overview | **BUILT + WIRED** | `(dashboard)/page.tsx` calls `/strategies/positions`, `/strategies/signals`, `/users/me/brokers`, `/health` |
| Brokers (Dhan + Fyers) | **BUILT + WIRED** | `app/brokers/dhan.py`, `dhan_historical.py`, `dhan_websocket.py`, `fyers.py`; frontend `/brokers` page + `useBrokerStatus`. Other brokers = `NotImplementedError` stubs. |
| Live positions | **BUILT + WIRED** | `app/api/strategy_positions.py` ↔ `/positions/page.tsx` |
| Trade history | **BUILT + WIRED** | `app/api/users.py:/me/trades` + `/trades/export` + `/trades/stats` ↔ `/trades/page.tsx` |
| Kill switch | **BUILT + WIRED** | `app/api/kill_switch.py` (8 endpoints) ↔ `/kill-switch/page.tsx` |
| Strategies CRUD | **BUILT + WIRED** | `app/strategy_engine/api/strategies.py` (6 endpoints) ↔ `/strategies/...` pages |
| Strategy Builder — beginner | **BUILT + WIRED** | `/strategies/new/beginner/page.tsx` POSTs to `/api/strategies`. Backtest uses synthetic data (per docstring + earlier audit). |
| Strategy Builder — intermediate | **BUILT + WIRED** | ~553 LOC component; POST/GET wired |
| Strategy Builder — expert | **BUILT + WIRED** | full indicator catalogue + JSON / Pine editor |
| Strategy Builder v2 (visual `@xyflow/react`) | **PARTIAL** | per MASTER_ROADMAP §Phase 5: v1 LIVE (~30%). v1.1 hydrate + v2 AND/OR + exit conditions pending. |
| Indicator Library | **BUILT + WIRED** (frontend-baked) | ~230 indicator defs in `lib/indicators/content/*.ts` |
| Indicator promote/deprecate queue | **BUILT + WIRED** | `/api/indicators/queue/*` + `/api/admin/indicators/queue/*` ↔ `/indicators/requests` + `/admin/indicators` |
| Strategy Tester (Phase D, synchronous) | **BUILT + WIRED** | `app/api/strategy_tester.py` (3 endpoints) ↔ `useStrategyTester` ↔ `StrategyTesterPanel` on `/chart` |
| Backtest Extension (Days 1-3, async) | **BUILT + WIRED (partially)** | router mounted `/api/backtest`. `BacktestChartPanel` consumes `/backtest/{runId}/markers`. POST `/api/backtest/runs` + GET `/api/backtest/{id}` exist server-side. |
| Charting (Lightweight Charts + WS) | **BUILT + WIRED** | `lib/chart/api.ts` calls `/chart/history`, `/chart/markers`, `/chart/ws-token`; `useChartWebSocket` opens WS. |
| Marketplace (browse / subscribe / rate / list / publish) | **BUILT + WIRED** | `app/strategy_engine/api/marketplace.py` + `marketplace_ledger.py` ↔ 3 frontend pages |
| Transparency Ledger | **BUILT + WIRED** | `/api/marketplace/listings/{id}/ledger/...` (5 endpoints) ↔ `transparency-ledger-panel.tsx` |
| Trust / Public Proof Dashboard `/proof` | **NOT STARTED** | No `proof` route in `app/`. Mockup-only per MASTER_CONTEXT §6. |
| AlgoMitra | **BUILT + WIRED** | `app/api/algomitra.py` (4 endpoints) ↔ `ChatWidget`, `AlwaysOnAlgoMitraPanelMount` mounted in dashboard layout. |
| Webhook Bridge (TradingView → broker) | **BUILT + WIRED** | `app/api/strategy_webhook.py` (HMAC-verified `POST /api/webhook/strategy/...`). Legacy `webhook_router` conditionally mounted. |
| Order router & SafetyChain | **BUILT + WIRED** | `app/strategy_engine/live_orders/api.py` (`POST /api/orders/live`, `GET /api/orders/live/preflight`) + `safety_chain.py`, `broker_guard/` |
| Options engine | **PARTIAL** (~30%, deferred Q4 2026) | 63 stranded options templates config-hidden (per MASTER_CONTEXT §10) |
| Historical candles (Queue CCC) | **BUILT + WIRED (skeleton)** | This weekend's work — `historical_candle.py` ORM, `029_historical_candles` migration applied locally, repo + bridge + tests, manual Dhan smoke test executed. No frontend consumer yet. |
| Backfill jobs (Queue CCC Phase 3) | **BUILT (not wired)** | `historical_backfill_job.py` ORM + `030_historical_backfill_jobs` migration applied. Celery task registered. Drain blocked on Anomaly A5 (credential factory stub). |
| `/analytics` | **STUB** (Coming Soon) | `(dashboard)/analytics/page.tsx` imports `@/components/coming-soon`. No backend `/api/analytics` router. |
| `/webhooks` page | **STUB** (Coming Soon) | Page is Coming Soon. Backend `/api/users/me/webhooks` is fully built. |
| `/alerts` | **STUB** (Coming Soon) | No backend `/api/alerts` router. |
| `/settings` | **STUB** (Coming Soon) | No backend `/api/settings` router. |
| `/admin` (most pages) | **STUB** (Coming Soon) | 5 of 7 admin pages Coming Soon; backend admin endpoints fully built. Frontend not consuming. |
| `/pricing` + billing | **STUB** (static page) | No `/api/billing`, `/api/plans`, `/api/subscriptions` (platform) router anywhere. Marketplace subscriptions = recorded amount, payment gateway = stub per `TRADETRI_AUDIT.md`. |

---

## 5. Verified Pending / Gap List (cross-check vs founder's known list)

| # | Founder claim | Verified from code? | Detail |
|---|---|---|---|
| 1 | **~9 sidebar pages "Coming Soon"** | ✅ **VERIFIED exact = 9** | `/alerts`, `/analytics`, `/settings`, `/webhooks`, `/admin`, `/admin/announcements`, `/admin/audit`, `/admin/kill-switch-events`, `/admin/users`. |
| 2 | **A5 credential factory + drain + 22-symbol execution pending** | ✅ VERIFIED | `_dhan_client_factory_for_job` raises `NotImplementedError`; `BACKFILL_ENABLED` defaults OFF; 22 PENDING rows visible in local dev DB per SESSION_HANDOFF. |
| 3 | **Gate (d): 3 branches not on main** | ✅ VERIFIED | `feat/queue-ccc-historical-candles-skeleton`, `fix/queue-ddd-migration-027-uuid-cast`, `feat/queue-eee-indicator-smoketests` all on origin, not merged. `origin/main` HEAD = `f62585d`. |
| 4 | **VWAP templates (`vwap-bounce`, `camarilla-pivots-intraday`) deactivated** | ✅ VERIFIED | `backend/data/strategy_templates_seed.json`: both have `is_active: False`. |
| 5 | **`inside-bar-breakout` synthetic-xfail** | ✅ VERIFIED nuanced | Template `is_active: True` in seed; `pytest.mark.xfail(strict=False)` mechanism in `backend/tests/queue_ww_sprint_8/test_sprint_7e_overrides.py` for synthetic-data shortfall. Needs real-data retest. |
| 6 | **Options engine ~30%, 63 stranded options templates, 86 unbuilt** | ✅ VERIFIED partially | Seed: 113 total, 27 active, **86 inactive** (matches "86 unbuilt"). 63-stranded-options figure [unclear — needs runtime check] (not separately enumerable from `is_active` alone). |
| 7 | **OLD-format → StrategyJSON migration (Phase 5 critical path)** | **[unclear — needs runtime check]** | Phase 5 is at ~30% per MASTER_ROADMAP. No specific OLD→JSON migration file or audit doc surfaced in this scan. Worth opening as a separate gap. |
| 8 | **Webhook base URL stale (`api.tradeforge.in` vs `api.tradetri.com`)** | ✅ VERIFIED stale | `backend/nginx.conf` still has `server_name api.tradeforge.in;` (2 occurrences). `backend/docker-compose.prod.yml` uses `tradeforge_*` container + image names (5 occurrences). Frontend `lib/api.ts` fallback IS `api.tradetri.com` — frontend correct, infra config stale. |
| 9 | **BSE strategy name misleading "tradetri-strategy-paper-test"; BSE allowed_symbols restrict to ["BSE1!"]** | **[unclear — needs runtime check]** | Cannot verify without DB read; the strategy row's name + allowed_symbols are runtime state, not in seed. |
| 10 | **Postgres audit trigger on strategies missing; ₹1.9 L final_pnl backfill** | ✅ VERIFIED absent | No `CREATE TRIGGER` / `AUDIT` migration found in `backend/migrations/versions/*.py`. The ₹1.9 L backfill is data-state, not code-verifiable. |
| 11 | **Premium UI polish gaps (login/dashboard/builder)** | qualitative — not testable from code | Per MASTER_CONTEXT: ~78% / ~62% / ~58% [verify per founder May-10 snapshot]. |
| 12 | **Localisation of indicator badges/tooltips (English-only)** | **[unclear — needs runtime check]** | `lib/indicators/content/*.ts` would need to be inspected per entry for i18n strings. Sprint 9 shipped tooltips in English per MASTER_CONTEXT §9. |
| 13 | **44 pre-existing test failures on main baseline** | ✅ acknowledged | Captured in MASTER_CONTEXT §10 cutover-12 row; not verifiable without running suite (which is out-of-scope read-only). |

---

## 6. Dead code / stubs / disabled flags found

| Item | Where | Effect |
|---|---|---|
| **`_dhan_client_factory_for_job` stub** | `app/tasks/historical_backfill_tasks.py` | Raises `NotImplementedError`. Reachable only under `BACKFILL_ENABLED=true` (currently OFF). Blocks Queue CCC drain. |
| **`BACKFILL_ENABLED` env var defaults OFF** | `app/tasks/historical_backfill_tasks.py:_backfill_enabled` | Backfill task short-circuits with `{"status": "disabled"}`. |
| **`webhook_router` conditional mount** | `app/main.py:239` | Legacy `/api/webhook` handler behind an `if`. New traffic uses `/api/webhook/strategy/...`. |
| **Broker adapters** (`zerodha`, `upstox`, `shoonya`, `angelone`) | `app/brokers/*.py` | Per `TRADETRI_AUDIT.md`, `NotImplementedError` stubs. Only Dhan + Fyers real. |
| **Stale `tradeforge` infra naming** | `backend/nginx.conf` (`server_name api.tradeforge.in;`), `backend/docker-compose.prod.yml` (`tradeforge_redis`, `tradeforge_backend`, `tradeforge_celery_*`, `tradeforge_nginx`) | Pre-rebrand carry-over. Production deployment scripts likely still reference this name; verify before next deploy. |
| **`/(public)/pricing` is static** | `frontend/src/app/(public)/pricing/page.tsx` | 0 backend calls; no `/api/billing` router exists. SaaS pricing tier gating not implemented. |
| **9 "Coming Soon" placeholder pages** | `frontend/src/components/coming-soon.tsx` consumed by `/alerts`, `/analytics`, `/settings`, `/webhooks`, `/admin`, `/admin/announcements`, `/admin/audit`, `/admin/kill-switch-events`, `/admin/users` | UI shows placeholder; backend (for `/webhooks` and 4 admin pages) is fully built but not consumed. |
| **`/strategies/builder/` v2 design-only** | per MASTER_ROADMAP Phase 5 (~30%) | v1 LIVE; v1.1 hydrate / v2 AND-OR / v2 exit conditions are docs-only. |
| **`/proof` Trust Dashboard mockup-only** | not present in `frontend/src/app/` | Deferred post-launch. |
| **Audit trigger absent** | `backend/migrations/versions/*.py` | No `CREATE TRIGGER` migration found. The ₹1.9 L final_pnl backfill mentioned by founder is data-state, requires a separate one-off script. |
| **Synthetic backtest data for beginner builder** | `/strategies/new/beginner/page.tsx` (per `TRADETRI_AUDIT.md`) | Backtest runs against synthetic candles, not real Dhan; explicit user-visible behavior. |

---

## 7. Critical Path to Launch (honest read)

Ordered by **blast radius × proximity to launch**, not founder preference.

### 7.1 — Pre-flight infra hygiene (NON-NEGOTIABLE before any production push)
1. **Rebrand `tradeforge` → `tradetri` in `backend/nginx.conf` + `backend/docker-compose.prod.yml`.** Stale `server_name api.tradeforge.in` will reject genuine TradingView webhooks if DNS shifts. (#5 verified gap)
2. **Apply migrations 029 + 030 on dev / staging / prod EC2** in that order, separately from this branch's merge. Production is at 028; both new tables are net-new and additive. (Gate (d) prep)
3. **Resolve Anomaly A5** — implement the per-user + service-account Dhan credential resolver in `_dhan_client_factory_for_job`. Without this, the 22 PENDING backfill jobs cannot drain, and any future user-initiated backfill faceplants. (Queue CCC drain unblock)

### 7.2 — Customer-facing UX gaps (blocks "feels finished")
4. **9 Coming-Soon pages.** Decide for each: (a) ship the missing frontend (4 of 9 have backends ready: `/webhooks`, `/admin/users`, `/admin/announcements`, `/admin/audit`, `/admin/kill-switch-events`), (b) ship a backend + frontend (`/alerts`, `/analytics`, `/settings`), (c) hide from sidebar until built. Default position: hide.
5. **`/(public)/pricing` has no billing wiring.** If launch monetises, this is launch-blocking. Decide: free-tier-only at launch (defer billing) vs. ship a payment gateway integration first.
6. **Visual Strategy Builder v1.1** — hydrate existing strategy on edit. Currently a one-way build. Returning users will lose drafts.

### 7.3 — Test + safety surface (blocks confidence)
7. **44 pre-existing test failures on `main` baseline** must be triaged. Even if known-not-regressions, an opaque red board burns founder trust at deploy time.
8. **`inside-bar-breakout` xfail** — re-test against real Dhan candles once 029 is on dev. Convert xfail → pass or relax the template's `is_active` flag.
9. **`vwap-bounce`, `camarilla-pivots-intraday`** — same 30-day real-Dhan verify before re-activating.
10. **Postgres audit trigger** on `strategies` table — recommended by founder for compliance trail. Easy migration, big confidence-of-record win.

### 7.4 — Regulatory + ops gates
11. **NSE / BSE algo-provider empanelment** [verify current status from MASTER_CONTEXT §9]. Active live customers on BSE LTD futures pre-empanelment = founder-accepted risk; revisit at every monthly checkpoint.
12. **SEBI IA registration completion** — per MASTER_ROADMAP ~30%.
13. **External security pen-test** — required pre-public-launch.
14. **AWS Budget alerts + automated DB backups** — already specified as non-negotiable per ops-learnings (MASTER_CONTEXT §9). Verify active.

### 7.5 — Defer post-launch (founder-validated)
- Options engine completion (Q4 2026 target).
- `/proof` Trust dashboard lean-MVP.
- Hetzner migration (₹500-900/mo from ₹5,100/mo).
- Competitor feature audit refresh.
- Pine → Python port for live strategy reproducibility.

---

_End of PROJECT_MAP.md_
