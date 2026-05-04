# Phase 0 — Codebase Audit Report

**Date:** 2026-05-04
**Branch:** `feature/ai-trading-system` (clean, off `main`)
**Scope:** Read-only audit per master prompt at `prompts/ai-trading-system-master-prompt.md`. No code modified.
**Author of audit:** Claude (read-only inspection)

---

## 0. Executive Summary

Trading Bridge / tradetri.com is **already a production trading platform** with a deep strategy-execution stack. The master prompt's Phases 1-10 have **substantial overlap** with what already exists. Specifically:

- **Phase 8 (paper trading + broker abstraction) is already implemented** (paper mode flag, `BrokerInterface`, Fyers + Dhan live, 4 stubs, kill switch, circuit breaker).
- **Phase 6 AI advisor partially exists** as `algomitra_ai.py` (Anthropic Claude) and the deterministic `ai_validator.py` (17-indicator weighted scoring).
- **Phase 7 Pine import partially exists** as `pine_mapper.py` — but it maps Pine **alert payloads** (a fired-signal contract), not **Pine source code**. The master prompt asks for source-code conversion, which is genuinely new work.
- **Phase 1-5 (strategy schema, engines, backtest, reliability, UI builder) do NOT exist yet** and are net-new modules.

**Critical implication for the master prompt**: implementing Phase 1+ as if greenfield would duplicate, conflict with, or break the existing live execution stack. The new "AI no-code trading" system must be **additive**: a new `app/strategy_engine/` module alongside the existing `app/services/strategy_executor.py` and friends, with explicit integration points carved out in Phase 8.

The repo is in good shape: 92%+ test coverage, ruff + mypy strict, App Router, TypeScript everywhere, clean migrations 001-008, recent commits show the team has been carefully removing mock data behind `<ComingSoon />` rather than letting it leak to customers. Phase 0 should not block.

---

## 1. Stack Overview

### 1.1 Frontend
- **Framework:** Next.js **16.2.4** (App Router). `frontend/AGENTS.md` warns: *"This is NOT the Next.js you know. APIs and conventions may differ from training data — read `node_modules/next/dist/docs/` before writing code."*
- **React:** 19.2.4
- **Language:** TypeScript 5 (`strict: true`, path alias `@/* → ./src/*`)
- **Styling:** Tailwind CSS 4 + `tw-animate-css`, design tokens in `src/app/globals.css`. Dark/glassmorphism aesthetic.
- **Component library:** shadcn/ui v4 (style `base-nova`), built on `@base-ui/react`. Lucide icons, Sonner toasts, Framer Motion animations, Recharts for charts.
- **Theming:** `next-themes` + custom `theme-context.tsx` (multiple branded themes including festive ones).
- **State:** Local component state + custom `useApi` hook (no Zustand/Redux). JWT in `localStorage`.
- **Package manager:** **npm** (`package-lock.json` present, no pnpm/yarn lockfile).
- **Build:** `npm run dev | build | start | lint` — no `test` or `typecheck` script today.
- **Deploy:** Vercel (`.vercel/` present at root and inside `frontend/`). Production = `tradetri.com`.

### 1.2 Backend
- **Framework:** FastAPI on Python 3.11+, Uvicorn + uvloop.
- **DB:** PostgreSQL 16, SQLAlchemy 2.0 async, Alembic migrations 001-008 (latest = `008_direct_exit_support`).
- **Cache/queue:** Redis 7 (rate limit, kill switch, idempotency, P&L), Celery 5.4 (notification + scheduled tasks).
- **Validation:** Pydantic v2 (+ pydantic-settings).
- **HTTP client:** httpx[http2]; broker SDKs: `fyers-apiv3`.
- **AI:** `anthropic>=0.40.0` for the AlgoMitra chat companion (claude-sonnet-4-6 default).
- **Security:** Fernet AES at-rest, bcrypt + argon2-cffi, JWT (HS256), HMAC-SHA256 webhook signing.
- **Observability:** structlog (JSON), prometheus-client, orjson.
- **Tooling:** ruff (lint+format), mypy strict (`disallow_untyped_defs`, `strict=true`, pydantic plugin), pytest 8 + pytest-asyncio + pytest-cov + pytest-benchmark, fakeredis, aiosqlite for tests.
- **Tests:** ~920 test functions across 52 files (`backend/tests/`), README claims 620+ — both numbers compatible (some files have multiple parametrised cases). Coverage 92%+ per README.
- **Deploy:** Dockerfile + docker-compose.yml + docker-compose.prod.yml + nginx.conf. Production target = AWS EC2 (frontend `next.config.ts` rewrites `/api/* → http://43.205.195.227:8000/api/*`).

### 1.3 Repository layout (top level)

```
trading-bridge/
├── backend/
│   ├── app/
│   │   ├── api/        (15 routers: auth, users, brokers, webhook, strategy_webhook,
│   │   │                strategy_signals, strategy_positions, kill_switch, admin,
│   │   │                algomitra, health, deps, docs)
│   │   ├── brokers/    (base.py, fyers.py, dhan.py, stubs.py, registry.py)
│   │   ├── core/       (config, security, security_ext, exceptions, logging, redis_client,
│   │   │                performance, startup_checks)
│   │   ├── db/         (base.py, session.py, models/* — 13 model files)
│   │   ├── middleware/ (security: request-id, size-limit, trusted-proxy, timing,
│   │   │                sensitive-filter, security-headers)
│   │   ├── schemas/    (pydantic: auth, broker, ai_decision, kill_switch, webhook,
│   │   │                strategy_webhook, strategy_signal, strategy_position,
│   │   │                strategy_execution)
│   │   ├── services/   (16 services: order, ai_validator, algomitra_ai, auth,
│   │   │                circuit_breaker, direct_exit, kill_switch, notification,
│   │   │                pine_mapper, pnl, position_manager, rate_limiter,
│   │   │                strategy_executor, telegram_alerts, user_context)
│   │   ├── tasks/      (celery_app, kill_switch_tasks, notification_tasks)
│   │   ├── workers/    (position_loop, reconciliation_loop)
│   │   ├── templates/  (email + telegram)
│   │   └── main.py     (FastAPI app factory + lifespan)
│   ├── tests/          (52 test files, ~920 tests, integration/ subdir for E2E)
│   ├── migrations/versions/  (001-008)
│   └── scripts/        (seed_dev, sign_webhook, deploy.sh)
├── frontend/
│   └── src/
│       ├── app/        (route groups: (auth), (dashboard), (public))
│       ├── components/ (algomitra, brokers, charts, dashboard, ui, brand)
│       ├── hooks/      (useAlgoMitra, useAlgoMitraLive)
│       └── lib/        (api.ts, use-api.ts, auth.tsx, mock-data.ts,
│                        algomitra-* x4, themes, language-detector, pnl-tracker)
├── docs/               (architecture, api-reference, deployment, roadmap, runbooks)
└── prompts/            (master prompt + prior prompts)
```

---

## 2. Routing & API Conventions

### 2.1 Frontend routing
Next.js App Router with route groups:
- `(auth)/login`, `(auth)/register` — outside dashboard chrome.
- `(public)/home`, `/about`, `/contact`, `/pricing` — marketing.
- `(dashboard)/` — authenticated app, shared layout in `(dashboard)/layout.tsx` with `Sidebar` + `TopBar` + `MobileNav`.

Sidebar items (14 entries, source: `src/components/dashboard/sidebar.tsx`):
- **Wired to backend:** `/` (overview), `/brokers`, `/positions`, `/trades`, `/strategies` (read-only), `/kill-switch`.
- **`<ComingSoon />` placeholder:** `/analytics`, `/webhooks`, `/alerts`, `/settings`, `/admin/*` (5 admin sub-pages).

API client: `src/lib/api.ts` is a thin fetch wrapper with JWT attach, 401 → refresh-once, typed error class. `src/lib/use-api.ts` is a `useApi(url, fallback, intervalMs)` hook with auto-refresh.

### 2.2 Backend routing
All routers mount under `/api/*` (see `backend/app/main.py:166`). Tags:

| Router | Prefix | Notes |
|---|---|---|
| `auth` | `/api/auth` | register / login / refresh / logout / password / profile |
| `users` | `/api/users` | profile, brokers, webhooks, **strategies**, trades, exports |
| `brokers` | `/api/brokers` | OAuth callbacks |
| `webhook` | `/api/webhook` | Legacy single-broker webhook |
| `strategy_webhook` | `/api/webhook/strategy/{token}` | **Strategy-engine receiver** — Pine + native, AI-validated |
| `strategy_signals` | `/api/strategies` | `/signals`, `/signals/{id}`, `/executions` |
| `strategy_positions` | `/api/strategies` | `/positions`, `/kill-switch` |
| `kill_switch` | `/api/kill-switch` | status / config / reset / history / test |
| `admin` | `/api/admin` | users, audit, announcements, KS events |
| `algomitra` | `/api/algomitra` | `/messages`, `/quota`, `/sessions` |
| `health` | `/api/health` | liveness / readiness / detailed |

### 2.3 Frontend → Backend wiring
`frontend/next.config.ts` rewrites `/api/:path*` → `http://43.205.195.227:8000/api/:path*` (EC2 backend). Local dev hits the same rewrite by default; `NEXT_PUBLIC_API_URL` overrides if set (see `lib/api.ts:9`).

---

## 3. Auth & User System

- **Users table** (`backend/app/db/models/user.py`): email, phone, password_hash (bcrypt), full_name, is_active, is_admin, telegram_chat_id, notification_prefs (JSON). Cascade-deletes broker_credentials, webhook_tokens, strategies, kill_switch_config.
- **JWT**: HS256, secret = `settings.jwt_secret`, default `access_token_expire_minutes=60`, `refresh_token_expire_days=7`. Tokens stored client-side in `localStorage` (keys `tb_access_token`, `tb_refresh_token`).
- **Webhook auth**: Per-token HMAC-SHA256 (`webhook_tokens.hmac_secret_enc`, Fernet-encrypted). Can be sent via `X-Signature` header OR in-body `signature` field. TradingView free-tier IPs in `settings.tradingview_trusted_ips` bypass HMAC (other gates still run).
- **Brute-force protection**: `brute_force_max_attempts=5`, `lock_minutes=60` per `core/security_ext.py`.
- **Sensitive-data filter middleware** scrubs request bodies before logging.

---

## 4. Database / Models

13 SQLAlchemy models across 8 Alembic migrations. Most relevant to the new system:

| Model | File | Purpose |
|---|---|---|
| `User` | `db/models/user.py` | Account root |
| `BrokerCredential` | `db/models/broker_credential.py` | Per-user broker auth (Fernet-encrypted at rest) |
| `WebhookToken` | `db/models/webhook_token.py` | Public token + HMAC secret |
| `Strategy` | `db/models/strategy.py` | **Existing strategy binding** (see §5) |
| `StrategySignal` | `db/models/strategy_signal.py` | Inbound TV/Pine alert audit row |
| `StrategyExecution` | `db/models/strategy_execution.py` | Per-leg broker-order audit |
| `StrategyPosition` | `db/models/strategy_position.py` | Live position state with action_history JSON |
| `Trade` | `db/models/trade.py` | Closed trade record |
| `KillSwitchConfig`, `KillSwitchEvent` | `db/models/kill_switch.py` | Daily-loss + max-trades gate |
| `IdempotencyRecord` | `db/models/idempotency.py` | Deduplication |
| `AuditLog` | `db/models/audit_log.py` | Generic audit |
| `AlgomitraMessage` | `db/models/algomitra_message.py` | Chat history |
| `WebhookEvent` | `db/models/webhook_event.py` | Webhook delivery log |
| `CopyTrading` | `db/models/copy_trading.py` | Future: copy-trading rows |

**Conventions:** UUID primary keys (`UUIDPrimaryKeyMixin`), timezone-aware timestamps via `TimestampMixin`, JSON columns for flexible payloads (`raw_payload`, `action_history`, `notification_prefs`, `allowed_symbols`).

---

## 5. Existing Trading / Strategy / Pine / Backtest / Broker Code

This is the most important section for Phase 1 planning.

### 5.1 `Strategy` model (existing)
`backend/app/db/models/strategy.py` — a strategy is a **binding**, not a logic spec:
- Links: `user_id`, `webhook_token_id`, `broker_credential_id`.
- Risk config: `entry_lots`, `partial_profit_lots`, `partial_profit_target_pct`, `trail_lots`, `trail_offset_pct`, `hard_sl_pct`, `max_loss_per_day`.
- Modes: `ai_validation_enabled` (bool), `exit_strategy_type` ∈ {`internal`, `direct_exit`}, `is_active`.
- Symbol gate: `allowed_symbols` JSON array, `max_position_size`.

There is **no column for strategy logic JSON** today. The "logic" is whatever Pine Script runs on TradingView's side; TRADETRI receives the alert payload and acts on it. Phase 1 of the master prompt requires storing internal strategy JSON — that means **adding a new column** (or new sibling table) to `strategies`. See §11 (file plan).

### 5.2 Pine handling (existing) — critical naming clash
`backend/app/services/pine_mapper.py` translates **Pine alert payloads** (action/type/qty/indicators) → native TRADETRI payload. Example handled types: `LONG_ENTRY`, `SHORT_ENTRY`, `LONG_PARTIAL`, `LONG_EXIT`, `LONG_SL`, etc.

This is **not** the same thing the master prompt's Phase 7 asks for. Phase 7 asks for a **Pine source-code subset importer** (`ta.ema → EMA`, `ta.crossover → CROSSOVER`, etc.) that converts Pine *code* into the new internal strategy JSON. The two should coexist:

- Existing `pine_mapper.py` stays put (alert-payload mapping, used by the live webhook).
- New Phase 7 module (e.g. `app/strategy_engine/pine_subset/`) parses Pine source code into the new strategy JSON.

Naming in this report: I'll call them **Pine alert-mapper** and **Pine source-importer** to keep them straight.

### 5.3 AI validator (existing, deterministic)
`backend/app/services/ai_validator.py` is a **deterministic** scorer (NOT an LLM):
- 17-22 indicator weighted score (`LONG_W`, `SHORT_W`), thresholds (LONG ≥51% / ≥85% for 4-lot tier, SHORT ≥51%).
- VIX modulation (halve if VIX outside 11.5-20.0).
- Optional regime detection (`USE_REGIME_DETECTION` env, default off).
- Reads `raw_payload['indicators']` from the alert. Does NOT compute indicators — TradingView's Pine does.
- Returns `AIDecision { decision, reasoning, confidence, recommended_lots }`.

**This satisfies the master prompt's requirement #15 ("AI must NOT calculate backtest results")** but is materially different from the Phase 6 "rule-based AI advisor" described in the master prompt (which suggests/explains/warns rather than approves/rejects orders). They are complementary: keep both, name the new one differently (e.g. `app/strategy_engine/advisor/`).

### 5.4 Strategy executor (existing)
`backend/app/services/strategy_executor.py`:
- `place_strategy_orders()` — builds `OrderRequest`, places via broker (or simulates fill in paper mode), records `StrategyExecution` rows + opens `StrategyPosition`.
- Paper mode: `settings.strategy_paper_mode` (process-wide, **default True**). Simulates fills with `PAPER-{uuid}` ids.
- Live mode: pre-trade margin floor (`pre_trade_margin_per_lot_inr`, default ₹1L/lot × 1.10 buffer), symbol validation, lot-multiple checks, even-lot enforcement when partial_profit_lots > 0.
- Position summing: re-entries for an open (strategy, symbol, side) are added to existing position rather than opening a new one.

### 5.5 Direct-exit handler (existing)
`backend/app/services/direct_exit.py` (referenced but not read this session) — handles Pine-driven `PARTIAL` / `EXIT` / `SL_HIT` actions, distinct from the autonomous internal-exit position loop.

### 5.6 Position-management workers (existing)
- `backend/app/workers/position_loop.py` — polls `strategy_positions` (open|partial), applies trailing-SL math, fires exits via the executor. No-op in paper mode... actually re-check: comment says it's no-op in paper mode but is configurable via `strategy_position_poll_seconds`.
- `backend/app/workers/reconciliation_loop.py` — periodic broker drift detection (`reconciliation_poll_seconds=60`), no-op in paper mode.

### 5.7 Kill switch + circuit breaker (existing)
- `app/services/kill_switch_service.py` — daily loss limit + max trades/day gate; triggers via Redis flag and DB rows.
- `app/services/circuit_breaker_service.py` — market-volatility ALLOW/PAUSE/HALT.

### 5.8 Broker abstraction (existing — strong fit for Phase 8)
`backend/app/brokers/base.py` defines `BrokerInterface` ABC with: `login`, `is_session_valid`, `place_order`, `modify_order`, `cancel_order`, `get_order_status`, `get_positions`, `get_holdings`, `get_funds`, `get_quote`, `validate_symbol`, `square_off_all`, `cancel_all_pending`, `normalize_symbol`. Registered via `app/brokers/registry.py`. Concrete implementations: `fyers.py`, `dhan.py` (live); `stubs.py` covers Shoonya, Zerodha, Upstox, AngelOne.

**Phase 8 should reuse this contract**, not introduce a parallel one. The master prompt's broker interface (`connect / getProfile / getFunds / getPositions / placeOrder / cancelOrder / getOrderStatus`) is a subset of what already exists.

### 5.9 AlgoMitra AI chat (existing, separate from validator)
`backend/app/services/algomitra_ai.py` is a Claude-based chat companion (Anthropic SDK, claude-sonnet-4-6 default, prompt caching on the system prompt). UI lives at `frontend/src/components/algomitra/` (ChatWidget + supporting components). This is the **end-user chat product** and is unrelated to the deterministic ai_validator.

The master prompt's Phase 6 ("AI advisor / coach") sits between these two: rule-based, no LLM required by default, strategy-aware. Build it as a third module — do not merge it into AlgoMitra.

### 5.10 Backtest — does NOT exist
No backtest engine, no historical data ingestion, no equity-curve generator on the backend. The frontend FAQ explicitly states *"TRADETRI execution layer hai, backtest engine nahi"* (`frontend/src/lib/algomitra-faqs.ts:226`). Phase 3 is genuinely net-new and will need to be honest with users that it changes TRADETRI's positioning.

### 5.11 Indicator registry — does NOT exist
No central indicator registry exists today. The deterministic `ai_validator.py` references 22 indicators by name as weight-table keys, but those values **come from the Pine alert payload** — TRADETRI never computes them. Phase 1 is also genuinely net-new.

---

## 6. Frontend Pages — wired vs placeholder

| Route | Status | Backend endpoint |
|---|---|---|
| `/` (overview) | ✅ wired | `/kill-switch/status`, `/strategies/positions`, `/strategies/signals`, `/users/me/brokers`, `/health` |
| `/brokers` | ✅ wired (with mock for "coming_soon" rows) | `/users/me/brokers` |
| `/positions` | ✅ wired | `/strategies/positions` |
| `/trades` | ✅ wired | `/users/me/trades` |
| `/strategies` | ✅ wired (read-only list) | `/users/me/strategies` |
| `/kill-switch` | ✅ wired | `/kill-switch/*` |
| `/analytics`, `/webhooks`, `/alerts`, `/settings` | 🚧 `<ComingSoon />` placeholder | — |
| `/admin/*` (5 pages) | 🚧 `<ComingSoon />` placeholder | — |
| `/(auth)/login`, `/(auth)/register` | ✅ wired | `/auth/login`, `/auth/register` |
| `/(public)/home`, `/about`, `/contact`, `/pricing` | ✅ static marketing | — |

Recent commits (last 5) show ongoing front-end clean-up — the team is removing mock data leakage behind `<ComingSoon />` placeholders. Expectation per `docs/FRONTEND_NEXT_SPRINT.md` is that wiring continues in subsequent sprints.

Tracked memory note (auto-memory): "Distinguish type-only imports when auditing for mock data — type-only imports don't mean a page is mock-driven; check actual runtime consumption before flagging." This applies here: `components/ui/trade-row.tsx` imports `type { Trade } from "@/lib/mock-data"` but is rendered with real data; `app/(dashboard)/brokers/page.tsx` is the only page that actually consumes mock-data values, and only for the **coming-soon placeholder rows**.

---

## 7. Environment, Config, Deployment

### 7.1 Environment files
- `backend/.env`, `backend/.env.example`, `backend/.env.production.example`.
- `frontend/.env.local` (Next.js runtime envs).
- `.env.local` at root (per-developer).

Required backend env vars (per `core/config.py`):
- **mandatory**: `ENCRYPTION_KEY` (Fernet), `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `WEBHOOK_HMAC_SECRET`.
- broker creds for OAuth: `FYERS_APP_ID`, `FYERS_APP_SECRET`, `FYERS_REDIRECT_URI`, `DHAN_*`.
- AI: `ANTHROPIC_API_KEY` (empty disables AlgoMitra).
- safety: `STRATEGY_PAPER_MODE` (default **True**), `KILL_SWITCH_CHECK_ENABLED`, `CIRCUIT_BREAKER_ENABLED`.
- ops: `TELEGRAM_BOT_TOKEN`, `AWS_SES_*`, `CORS_ALLOW_ORIGINS`, `TRADINGVIEW_TRUSTED_IPS`, `TRUSTED_PROXY_IPS`.

### 7.2 Build / dev / test commands

**Backend**:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m scripts.seed_dev
uvicorn app.main:app --reload          # dev server
pytest                                  # tests (~920 functions)
pytest --cov=app                        # with coverage
ruff check . && ruff format --check .   # lint
mypy app                                # strict type check
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev      # Next.js dev (port 3000)
npm run build    # production build
npm run lint     # eslint via flat config (eslint.config.mjs)
# No test or typecheck script defined.
```

**Docker / prod**: `docker-compose up -d postgres redis` for local infra; `docker-compose.prod.yml` + `nginx.conf` + `deploy-production.sh` for AWS EC2. Frontend deploys to Vercel.

---

## 8. Testing Framework

- **Backend**: pytest 8 (`asyncio_mode=auto`), pytest-asyncio, pytest-cov (terminal + HTML reports), pytest-benchmark. Strict markers + strict config. fakeredis + aiosqlite for in-memory tests. Custom test selectors via `tests/conftest.py` (TestClient with cross-loop session pool; position-loop disabled in tests). Integration tests under `tests/integration/`. Dhan scrip-master mocking is wired for paper-mode flows.
- **Frontend**: **none configured**. No Vitest/Jest/Playwright in `package.json`. Phase 5 (UI builder) and beyond will need a test runner introduced. Vitest + React Testing Library is the standard fit for Next.js 16; flag this as a Phase-5 prerequisite.

---

## 9. Risk Assessment

### 9.1 High risk — must not touch in any phase
| Area | Files | Why |
|---|---|---|
| Live broker order placement | `app/brokers/fyers.py`, `app/brokers/dhan.py`, `app/services/strategy_executor.py:_live_place_order`, `app/services/direct_exit.py` | Master prompt rule #6 — never modify live broker execution behaviour without explicit approval. Real money. |
| HMAC verification + idempotency | `app/api/strategy_webhook.py` lines 154-220 | Replay-attack surface. |
| Encryption-at-rest | `app/core/security.py:encrypt_credential / decrypt_credential` | Fernet key compromise = total breach. |
| Migration history | `backend/migrations/versions/001-008` | New migrations must be additive; never edit a shipped migration. |

### 9.2 Medium risk — naming clashes / confused refactors
- **Pine alert-mapper vs Pine source-importer**: do not modify `app/services/pine_mapper.py` when building Phase 7. New module name, new file location.
- **AI validator vs AI advisor**: `ai_validator.py` is the deterministic order-gate; new Phase 6 advisor is suggestion-only. Keep both; do not rename.
- **`Strategy` model migration**: adding a `strategy_json` column or sibling table needs a careful Alembic migration and read-path that keeps the existing Pine-binding flow working.
- **`strategy_paper_mode` is process-wide**: the new builder UI will want **per-strategy** mode (a beginner-built strategy in paper while a Pine-bound strategy in live). Phase 8 will need a per-strategy mode column or env override map.
- **Frontend Next.js 16 quirks**: `frontend/AGENTS.md` flags potential breaking changes from training data. Phase 5 UI work must read `node_modules/next/dist/docs/` before committing.

### 9.3 Low risk — informational
- Frontend FAQ explicitly states "no backtest engine" — Phase 3 changes the product story; marketing/copy may need updating once shipped.
- AlgoMitra has its own quota system (`algomitra_daily_message_limit=50`); the new advisor (rule-based, no LLM) does not need quota.
- Frontend has no Storybook; consider adding one in Phase 5 if component velocity demands it (not blocking).
- `mockDashboard` in `frontend/src/lib/mock-data.ts` is still imported by `brokers/page.tsx` for the static "coming-soon brokers" list; safe today, but track for cleanup if the broker registry moves to backend.

---

## 10. Recommended Module Structure (additive, not replacement)

All new code lives under `backend/app/strategy_engine/` and `frontend/src/lib/strategy/` + `frontend/src/app/(dashboard)/builder/`. **No existing `app/services/*` files are modified**; integration points (Phase 8) call into the new module via clean boundaries.

```
backend/app/strategy_engine/
├── __init__.py
├── schema/
│   ├── __init__.py
│   ├── strategy.py          # Strategy JSON Pydantic models (id, name, mode, indicators[], entry, exit, risk, execution)
│   ├── indicator.py         # IndicatorMetadata Pydantic model
│   └── ohlcv.py             # Candle / OHLCV typing
├── indicators/
│   ├── __init__.py
│   ├── registry.py          # INDICATOR_REGISTRY dict + helpers
│   └── calculations/
│       ├── __init__.py
│       ├── ema.py
│       ├── sma.py
│       ├── wma.py
│       ├── rsi.py
│       ├── macd.py
│       ├── bollinger.py
│       ├── atr.py
│       ├── vwap.py
│       ├── obv.py
│       └── volume_sma.py
├── engines/                 # Phase 2
│   ├── entry.py
│   ├── exit.py
│   ├── candle.py
│   ├── time_condition.py
│   ├── price_condition.py
│   ├── position.py
│   └── risk.py
├── backtest/                # Phase 3
│   ├── normalizer.py
│   ├── simulator.py
│   ├── metrics.py
│   ├── costs.py
│   └── trade_log.py
├── reliability/             # Phase 4
│   ├── trust_score.py
│   ├── out_of_sample.py
│   ├── walk_forward.py
│   └── sensitivity.py
├── advisor/                 # Phase 6 — rule-based, no LLM by default
│   ├── rules.py
│   ├── patterns.py
│   ├── explainability.py
│   └── llm_provider.py      # pluggable, optional
├── pine_subset/             # Phase 7 — Pine SOURCE-CODE importer (distinct from pine_mapper)
│   ├── lexer.py
│   ├── mapper.py
│   ├── validator.py
│   └── unsupported.py
└── execution_bridge/        # Phase 8 — adapter to existing services/strategy_executor.py
    ├── paper_runner.py      # builder-built strategy → paper trade simulation
    └── live_guard.py        # reliability + risk gate before live mode flip

backend/tests/strategy_engine/   # mirrors module tree
```

Frontend:

```
frontend/src/
├── app/(dashboard)/builder/    # Phase 5
│   ├── page.tsx                # dashboard / list
│   ├── new/page.tsx            # mode picker (beginner / intermediate / expert)
│   ├── beginner/[id]/page.tsx
│   ├── intermediate/[id]/page.tsx
│   ├── expert/[id]/page.tsx
│   ├── library/page.tsx        # indicator browser
│   ├── results/[id]/page.tsx   # backtest + reliability panels
│   └── pine-import/page.tsx    # Phase 7
├── components/builder/         # condition editor, indicator chips, JSON preview, etc.
├── hooks/builder/              # useStrategyDraft, useBacktestRun
└── lib/strategy/               # client-side types mirrored from backend Pydantic
```

---

## 11. Recommended Implementation Order

The master prompt's order is mostly correct, with **two adjustments** for our existing codebase:

| Phase | Master prompt | Action for this repo |
|---|---|---|
| **1** | Strategy schema + 10 indicators | Build under `backend/app/strategy_engine/` per §10. **No DB migration yet** — the Strategy JSON lives in memory / fixture files until Phase 5 needs persistence. |
| **2** | Entry/exit/position/risk engines | Pure-Python under `strategy_engine/engines/`. No DB. |
| **3** | Deterministic backtest engine | Pure-Python under `strategy_engine/backtest/`. No DB; tests use fixture OHLCV CSVs. |
| **4** | Trust score + out-of-sample + walk-forward + sensitivity | Pure-Python under `strategy_engine/reliability/`. No DB. |
| **5** | UI builder | **First DB migration here**: add `strategy_json: JSONB NULL` column to `strategies` table (or new `strategy_definitions` table). New API router `app/api/strategy_builder.py`. Add Vitest + RTL to frontend if not present. |
| **6** | AI advisor (rule-based) | Pure-Python `strategy_engine/advisor/`. Optional LLM-provider interface kept abstract. **DO NOT touch AlgoMitra or the deterministic ai_validator.** |
| **7** | Pine source-importer | New module `strategy_engine/pine_subset/`. **DO NOT touch `app/services/pine_mapper.py`** — that file is the alert-payload mapper and must stay live. |
| **8** | Paper trading + broker abstraction | **Reuse existing `BrokerInterface`** (`app/brokers/base.py`). New `strategy_engine/execution_bridge/paper_runner.py` for builder-built strategies (separate from live Pine flow). Add per-strategy `execution_mode` enum (`backtest | paper | live`) — Alembic migration #009. **Live mode opt-in** with reliability score gate. |
| **9** | 100+ indicator expansion | Add active calculations + `coming_soon` registry stubs. |
| **10** | Final hardening + docs | All-of-the-above smoke + new `docs/strategy-json.md` etc. |

---

## 12. Phase 1 File Plan

Phase 1 is a pure-Python schema + indicator-registry + 10-indicator-calculation drop. **No frontend, no DB migration, no API routes, no UI, no changes to any existing file.**

### 12.1 New files

```
backend/app/strategy_engine/__init__.py
backend/app/strategy_engine/schema/__init__.py
backend/app/strategy_engine/schema/strategy.py
backend/app/strategy_engine/schema/indicator.py
backend/app/strategy_engine/schema/ohlcv.py
backend/app/strategy_engine/indicators/__init__.py
backend/app/strategy_engine/indicators/registry.py
backend/app/strategy_engine/indicators/calculations/__init__.py
backend/app/strategy_engine/indicators/calculations/ema.py
backend/app/strategy_engine/indicators/calculations/sma.py
backend/app/strategy_engine/indicators/calculations/wma.py
backend/app/strategy_engine/indicators/calculations/rsi.py
backend/app/strategy_engine/indicators/calculations/macd.py
backend/app/strategy_engine/indicators/calculations/bollinger.py
backend/app/strategy_engine/indicators/calculations/atr.py
backend/app/strategy_engine/indicators/calculations/vwap.py
backend/app/strategy_engine/indicators/calculations/obv.py
backend/app/strategy_engine/indicators/calculations/volume_sma.py

backend/tests/strategy_engine/__init__.py
backend/tests/strategy_engine/test_schema_strategy.py
backend/tests/strategy_engine/test_schema_indicator.py
backend/tests/strategy_engine/test_registry.py
backend/tests/strategy_engine/test_ema.py
backend/tests/strategy_engine/test_sma.py
backend/tests/strategy_engine/test_wma.py
backend/tests/strategy_engine/test_rsi.py
backend/tests/strategy_engine/test_macd.py
backend/tests/strategy_engine/test_bollinger.py
backend/tests/strategy_engine/test_atr.py
backend/tests/strategy_engine/test_vwap.py
backend/tests/strategy_engine/test_obv.py
backend/tests/strategy_engine/test_volume_sma.py
backend/tests/strategy_engine/fixtures/__init__.py
backend/tests/strategy_engine/fixtures/ohlcv_sample.py
```

### 12.2 Module responsibilities

- **`schema/strategy.py`** — Pydantic v2 models matching the master prompt's example JSON exactly:
  - `StrategyJSON` with fields: `id, name, mode (Literal['beginner','intermediate','expert']), version, indicators[IndicatorConfig], entry (EntryRules), exit (ExitRules), risk (RiskRules), execution (ExecutionConfig)`.
  - `IndicatorConfig`: `id, type, params: dict[str, Any]`.
  - `EntryRules`: `side ('BUY' | 'SELL'), operator ('AND' | 'OR'), conditions[Condition]` — `Condition` is a discriminated union (`indicator | candle | time | price`).
  - `ExitRules`: `targetPercent, stopLossPercent, trailingStopPercent, partialExits[], squareOffTime`.
  - `RiskRules`: `maxDailyLossPercent, maxTradesPerDay, maxLossStreak, maxCapitalPerTradePercent`.
  - `ExecutionConfig`: `mode (backtest | paper | live), orderType, productType`.
  - All optional fields explicit; round-trip JSON ↔ model verified by test.
- **`schema/indicator.py`** — `IndicatorMetadata` Pydantic model: `id, name, category, description, inputs[InputSpec], outputs[str], chartType ('overlay' | 'separate'), pineAliases[str], difficulty ('beginner' | 'intermediate' | 'expert'), status ('active' | 'coming_soon' | 'experimental'), aiExplanation, tags[str], calculationFunction (str | None)`.
- **`schema/ohlcv.py`** — `Candle` (time, open, high, low, close, volume) + `Series` typing helpers; consumed by calculation functions.
- **`indicators/registry.py`** — `INDICATOR_REGISTRY: dict[str, IndicatorMetadata]` populated at import time with the 10 active entries. Helpers:
  - `get_indicator_by_id(id) -> IndicatorMetadata | None`
  - `get_indicators_by_category(category) -> list[IndicatorMetadata]`
  - `get_active_indicators() -> list[IndicatorMetadata]`
  - `get_beginner_recommended_indicators() -> list[IndicatorMetadata]`
  - `validate_indicator_params(id, params) -> tuple[bool, list[str]]`
- **`indicators/calculations/*.py`** — pure functions: `def ema(values: Sequence[float], period: int) -> list[float]:` etc. No DB, no I/O, no global state. Edge cases: empty input → empty output; period > len(values) → fill with `None` (or NaN equivalent — to be decided in Phase 1 and documented).

### 12.3 Test plan (per master prompt §1 quality gate)

- `test_registry.py`: registry loads, all 10 entries valid, helpers return expected subsets.
- `test_ema.py`: known-input/known-output sequence (canonical test vector); period=1 returns input; period > len returns shorter window.
- `test_sma.py`, `test_rsi.py`: same structure with canonical vectors.
- `test_validation.py` (`test_schema_strategy.py` + `test_schema_indicator.py`): invalid params rejected; unknown indicator id rejected.
- All async-free (calculations are sync); follows existing pytest config (`asyncio_mode=auto` doesn't interfere).
- Coverage target: 100% for the new module (small surface area, easy to hit).

### 12.4 Quality gate commands

```bash
cd backend
ruff check app/strategy_engine tests/strategy_engine
ruff format --check app/strategy_engine tests/strategy_engine
mypy app/strategy_engine
pytest tests/strategy_engine -v
pytest --cov=app/strategy_engine --cov-fail-under=100 tests/strategy_engine
```

Frontend has no Phase 1 changes → frontend `npm run build` and `npm run lint` should still pass (no diff).

### 12.5 Phase 1 explicit non-goals
- No DB migration, no new column on `strategies`.
- No API endpoint, no router registration in `main.py`.
- No frontend changes.
- No changes to existing `app/services/*`.
- No backtest, no engine, no UI — those land in Phases 2-5.
- No indicator beyond the 10 listed in the master prompt.

---

## 13. Open Questions / TODOs Before Phase 1 Approval

These are not blocking but worth confirming before code-write begins:

1. **None-handling in indicator outputs**: master prompt example has fixed-length output. Real EMA needs warm-up. Confirm the convention — `None` for warm-up positions, or omit them? My recommendation: list-of-`None` placeholders to keep output length == input length, matching pandas behaviour. Will lock this in Phase 1 doc.
2. **Strategy JSON storage shape** (Phase 5, not Phase 1): new column on `strategies` vs new `strategy_definitions` table? My recommendation: new column `strategy_json JSONB NULL` (single FK, simpler). Decision can wait until Phase 5.
3. **Vitest for frontend** (Phase 5): introduce in Phase 5 first commit, or earlier? Recommendation: introduce when we write the first non-trivial component test (Phase 5).
4. **Persistence of backtest results** (Phase 3): in-memory only, or new `backtest_runs` table? Recommendation: in-memory + downloadable JSON in Phase 3; persistence in Phase 5 when the UI needs history. Confirm later.
5. **Live mode flip** (Phase 8): minimum reliability score required before `execution_mode = live` is allowed for a builder-built strategy? Suggested default 60, with paper-trading session-count gate. Decision belongs to Phase 8.

---

## 14. Suggested Git Workflow for Phase 1

Per master prompt §"Git and Checkpoint Rules":

- Branch already created: `feature/ai-trading-system`. ✅
- This audit report is the only write of Phase 0; no commit required unless you ask me to commit it.
- For Phase 1, recommended commit message:
  ```
  feat(strategy-core): add strategy schema and indicator registry
  ```
- After Phase 1, run all listed quality-gate commands and report results in the same 12-line output format the master prompt requires.

---

## 15. Final Verdict

- ✅ Repo is in good shape; all master prompt phases are achievable without breaking existing functionality.
- ✅ Phase 1 (this session's next phase, **pending your approval**) is fully isolated — pure new files, no migrations, no API, no UI, no touches to live execution paths.
- ⚠️ The new system must be built **alongside**, not instead of, the existing Pine alert-mapper / AI validator / strategy executor. Phase 8 is the only phase with non-trivial integration risk.
- ⚠️ Phase 5 introduces the first DB migration and is the first phase that touches the existing `strategies` table — plan a careful Alembic migration #009 then.
- ⚠️ Frontend Next.js 16 has potential breaking changes vs. training data — the team must read `node_modules/next/dist/docs/` before significant frontend work in Phase 5+.

**Recommended next action:** review this audit, then approve Phase 1 to begin the schema + 10-indicator drop. I will wait for explicit approval before writing any code.
