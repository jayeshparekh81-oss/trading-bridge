# TRADETRI — Master Project Context

**Stable big-picture context.** Paste alongside `docs/SESSION_HANDOFF.md` at the start of every new chat.

This file changes rarely (architecture, sacred rules, completed phases, regulatory state). For session-volatile state — current branch HEADs, gates, last week's commits — see `SESSION_HANDOFF.md`.

**Last refresh:** 2026-06-14 · **No autonomous edits** — founder reviews changes before commit.

---

## 1. Who + Mission

**Product:** TRADETRI (`tradetri.com`) — no-code algorithmic trading platform for retail India.

**Founder:** Jayesh Parekh (jayeshparekh81@gmail.com). Solo founder; works through paired Claude Code sessions across frontend (Mac) and backend (EC2) tracks.

**Mission:** Bring institutional-grade systematic trading to retail traders who can't or won't write code — without the black-box opacity that SEBI's Feb 2025 framework forbids for retail.

**Wedge:** "Glass Box AI" — every signal, every score, every trade decision is white-box auditable. The **Strategy Transparency Ledger** (Polygon blockchain, 90-day forward-test claim verification, tagline _"Backtest nahi, Proof."_) is the regulatory + trust moat.

**Customer state:** 2 live customers already onboarded [verify current count].

### Origins (April 2026)
- Grew from a personal **Pine-script backtesting project** — the live BSE LTD strategy (§5) is the direct ancestor of the entire product.
- Competitor benchmark: **StrykeX** (`stockwiz.in`).
- Five **USA-inspired feature pillars** that shaped scope:
  1. TradingView Webhook Bridge (Phase 1, ✅)
  2. Paper Trading + Leaderboard (paper trading ✅, leaderboard [verify])
  3. Options Payoff Builder (deferred Q4 2026)
  4. 0DTE Daily Expiry Suite (deferred with options)
  5. Prop Firm Evaluation (not started)
- Brand: **24-petal mandala + Tiranga (Indian tricolour)** logo, Sanskrit tagline.
- **Revenue trajectory (founder projection):** Year 1 ₹30 L – ₹1 Cr → Year 5 unicorn aspiration.
- Domain via **Hostinger**, A-record pointed at Vercel.

---

## 2. Sacred Rules (from `CLAUDE.md`, verbatim binding)

### Production safety
- **BSE LTD strategy `89423ecc-c76e-432c-b107-0791508542f0` is LIVE REAL MONEY on Dhan.**
- Never modify without founder confirming `is_paper=false` first: `is_paper` column, `strategy_executor`, `direct_exit.py`, webhook handlers, `kill_switch_*`, broker adapters (`brokers/dhan.py`, `brokers/fyers.py`), any `*strategies*` migration.
- **FUTURES = NRML only.** MIS / INTRADAY for F&O is forbidden. Equity intraday is fine.

### Protected zones (never touch unless explicitly named)
R:R block · Brahmastra trail · entry/exit logic · JSON DSL builder.

### Workflow
- One module per task. Never one-shot.
- Plan first, edit after founder approves.
- Work on a branch, never commit to `main` directly. Never force-push.
- Show actual diff before commit. Run FULL test suite, never a subset.
- Two deploy hard-stops max: before migrations, before container restart.
- Founder gates every deploy.
- Unsure → STOP and ask.

### Push discipline
Never push during a session unless authorised. NEVER push to `main`.

### Communication
Hinglish + engineering-grade detail. User-facing errors in Hinglish. Structured logs are JSON with named fields; never per-item logs in a loop.

### Parallel-session pattern
Multiple Claude Code sessions run concurrently (Mac frontend vs EC2 backend in `../trading-bridge-smoketests` worktree or similar). Discipline: **NEW-FILES-ONLY** on parallel branches, plus `PATCH_INSTRUCTIONS.md` for needed existing-file edits. Reconcile via **merge, not rebase** — preserve deployed SHA history.

---

## 3. Tech Stack + Infrastructure

### Backend (`backend/`)
- **Runtime:** Python 3.11+ via Docker.
- **Web framework:** FastAPI ≥0.115, uvicorn[standard] with uvloop.
- **ORM + DB:** SQLAlchemy 2.0 async, Alembic migrations, PostgreSQL 16 (asyncpg + psycopg2-binary).
- **Cache / queue:** Redis 7, Celery ≥5.4.
- **Auth / crypto:** python-jose JWT, bcrypt, argon2-cffi, cryptography Fernet for credential storage.
- **HTTP client:** httpx[http2].
- **Logging / metrics:** structlog (JSON), prometheus-client.
- **Brokers / AI:** fyers-apiv3, anthropic SDK.
- **TA:** ta-lib (compiled from upstream in the runtime image).

### Frontend (`frontend/`)
- **Framework:** Next.js 16 App Router, React 19.
- **Styling:** Tailwind CSS, Framer Motion.
- **Charts:** TradingView Lightweight Charts ^4.2 (Apache 2.0).
- **Builder canvas:** `@xyflow/react`.
- **Tests:** Vitest unit + integration; Playwright e2e (staged).

### Infrastructure
- **Production backend:** AWS EC2, Mumbai region, **Elastic IP `13.127.224.68`**.
- **Production frontend:** Vercel → `tradetri.com`.
- **Storage:** RDS (Postgres) + ElastiCache (Redis) [verify region/sizing for current setup].
- **Notifications:** AWS SES (email) + Telegram Bot API.
- **Docker Compose services (dev):** `postgres`, `redis`, `backend`, `celery_worker`, `celery_beat`.

---

## 4. Architecture

### High-level flow
```
TradingView Alerts ──HMAC POST──▶ FastAPI Webhook
                                    │
User / Web UI ──JWT──▶ FastAPI ─── 7 Safety Gates ─── Broker Registry ─▶ Dhan / Fyers
                          │                                                (Zerodha/Upstox/
                          │                                                 AngelOne stubs)
                          ├──▶ Redis (cache, rate limit, kill switch, P&L counters)
                          ├──▶ Postgres (durable state, audit)
                          └──▶ Celery workers (notifications, scheduled jobs)

Web App (Next.js) ─JWT─▶ FastAPI
                  └─WS─▶ Indicator Engine / Chart history
```

### 7 Safety Gates (TradingView → broker)
HMAC verify · idempotency check (Redis) · per-user rate-limit · kill-switch state · broker-guard pre-flight · safety-chain (position sizing, exposure) · order_router final dispatch. [verify exact gate ordering from `app/strategy_engine/live_orders/` + `app/strategy_engine/broker_guard/`].

### Key directories
- `backend/app/api/` — HTTP endpoints.
- `backend/app/services/` — business logic.
- `backend/app/brokers/` — broker adapters (real: dhan.py, fyers.py; stubs: zerodha/upstox/shoonya/angelone — `NotImplementedError`).
- `backend/app/strategy_engine/` — backtest engine + indicators + paper-trading + live-orders + safety + truth/reliability/coach/regime/deviation/advisor packages.
- `backend/app/db/models/` — 12-table schema (users, brokers, strategies, trades, …) [verify count].
- `backend/migrations/versions/` — Alembic migrations (`001` → `030` as of 2026-06-13).
- `frontend/src/app/` — App Router routes.
- `frontend/src/lib/indicators/content/*.ts` — frontend-baked indicator definitions (~230+).
- `trading-bridge-chart/` — charting module repo (this repo's chart submodule scope).

### 12-table DB schema (high level)
users, broker_credentials, strategies, kill_switch_configs, webhook_tokens, paper_sessions / paper_trades, strategy_signals / strategy_positions, marketplace_listings, ledger_*, support_tickets, indicator_status_overrides / indicator_approval_queue, trade_markers, strategy_templates, backtest_runs / backtest_trades / backtest_metrics, historical_candles, historical_backfill_jobs. [verify exhaustive list against `app/db/models/__init__.py`].

---

## 5. Live Strategies (all on Dhan)

| Strategy | UUID | Status | Notes |
|---|---|---|---|
| **BSE LTD** | `89423ecc-c76e-432c-b107-0791508542f0` | LIVE, `is_paper=FALSE` | **SACRED.** Real money. Untouchable without explicit gate. Equity intraday on BSE_EQ. |
| **CDSL** | `0252e82c-484a-4891-b0e4-496de9664d17` | LIVE | NSE_EQ. |
| **ANGELONE** | (futures via futures_resolver) | LIVE since `release-cutover-10` [verify SHA] | NSE F&O, NRML only. Added via the resolver layer that maps `NSE:ANGELONE` / `ANGELONE1!` → Dhan root for auto-rolling futures. |

### Live strategy lineage (origin Pine)
Pine name: **"MA + Gaussian + OrderFlow (PRO FINAL) + SHORT v4.8.1"** — 18 indicators (MA cross, Gaussian filter long+short, order-flow/delta, RSI, VWAP, RVOL, ATR%, HTF trend, India VIX sizing, …). 15-min bars + NIFTY SMA200 regime filter.

Current production Pine: **`v4.10.1-LITE`** — added `symbolOverride`, restored `symbolToSend` and `quantity_unit` JSON fields.

**Documented flaws in original Pine** (Pine→Python port is future work, ~95-97% match achievable):
- Lookahead bias (`request.security` with `lookahead_on`).
- 100% percent-of-equity compounding inflating backtest.
- Slippage / commission too low.
- Parameter overfitting (curve-fit to one symbol).

---

## 6. Subsystems

| System | Status | Notes |
|---|---|---|
| **AlgoMitra** | shipped | 4-pillar AI coach (hospitality + IT + trading + psychology). Hinglish + 10 Indian languages. Anthropic SDK. **Advisory only, never autonomous execution.** |
| **Marketplace** | shipped May 9-10 2026 | Browse / subscribe / rate listings. Subscription fee recorded but payment is a stub (no gateway wired). |
| **Strategy Transparency Ledger** | shipped | Polygon blockchain, 90-day forward-test, _"Backtest nahi, Proof."_. Tamper-evident. |
| **Trust / Public Proof Dashboard** (`/proof`) | mockup only | Lean-MVP deferred to post-launch. |
| **Charting** | shipped | TradingView Lightweight Charts (Apache 2.0). Lives in `trading-bridge-chart` repo. WS at `wss://…/ws/chart/{symbol}/{timeframe}?token=`. |
| **No-code Strategy Builder** | v1 LIVE | `@xyflow/react` canvas, 3 custom node types. 230+ frontend-baked indicator definitions across 18 packs. Edit-existing-strategy hydrate is v1.1. |
| **AI Advisor** | rule-based scaffolding | No LLM yet (~30% complete per MASTER_ROADMAP). |
| **Kill switch** | shipped | DB-backed config + Redis state. Daily P&L roll-up via Celery beat. |
| **Backtest engine** | ~75% [pre-Queue CCC] | Deterministic pure-Python at `app/strategy_engine/backtest/`. Days 1-3 of Week 2 extension layer deployed dormant; Days 4-7 pending. |
| **historical_candles store** | NEW (Queue CCC, June 2026) | Real-Dhan persistent OHLC store with ON CONFLICT DO NOTHING upserts. Migration 029. Phase 3 backfill jobs at migration 030 (this weekend). |

---

## 7. Completed Work (queue-by-queue summary)

Compiled from `docs/MASTER_ROADMAP.md` (snapshot 2026-05-18) + the QUEUE reports in `docs/`. **Per-queue percentages are approximate and likely stale post-May-18 — [verify] before quoting externally.**

| Phase | Status | Approx % | Highlights |
|---|---|---:|---|
| **Phase 1 — The Bridge** (TV → broker) | ✅ COMPLETE | 100% | Webhook + `BrokerInterface` + Dhan + Fyers + kill switch + circuit breaker + idempotency + JWT + SES + Telegram. |
| **Phase 2 — Strategy Templates Catalog** | 🚧 IN PROGRESS | ~90% | 113-entry seed JSON, 27 active templates (current snapshot: 26 fire backtests, 1 xfail, 2 deactivated for real-Dhan verify, 86 unbuilt). |
| **Phase 3 — Backtest Engine** | 🚧 IN PROGRESS | ~75% | Pure-Python engine 2617 LOC. Days 1-3 deployed dormant. Days 4-7 plan in `BACKTEST_ENGINE_EXTENSION_PLAN.md`. Queue CCC's Phase 3 (`historical_candles` + 030 backfill jobs + orchestrator + rate-limit guard) sits **alongside** this — different scope despite name collision. |
| **Phase 4 — Reliability / Truth / Coach** | ✅ MOSTLY | ~90% | walk-forward, OOS, truth scoring, Hinglish health card, regime, deviation, advisor. |
| **Phase 5 — Visual No-Code Builder** | 🚧 IN PROGRESS | ~30% | v1 LIVE (drag-drop + 3 nodes + serializer + 29 tests). v1.1 = hydrate existing. v2 = AND/OR + exit conditions. |
| **Phase 6 — AI Advisor (LLM)** | 🚧 IN PROGRESS | ~30% | Rule-based only. LLM integration not started. |
| **Phase 7-8 — Charting + Options Analytics** | 🚧 PARTIAL | charting 40% / options 0% | Charting + WS + markers + 5 chart indicators shipped. Options chain / Greeks / IV surface / options builder not started — blocks the 63 inactive options templates. |
| **Phase 8B — Live data feed** | ✅ COMPLETE | 100% | Dhan ticks + historical via `data_provider`. Live order API via Dhan. |
| **Phase 9 — Marketplace / Copy Trading** | 🧠 NOT STARTED | 0% | Gated on Phase 3 → 100%, 30+ days customer deviation, 50+ customers, SEBI registration, anti-grift validation. ETA 8-12 weeks post-launch. |
| **Phase 10-12 — Multi-asset / Platform expansion** | 🧠 NOT STARTED | 0% | No commits. |

### Cross-cutting infrastructure
| Sub-system | % | Notes |
|---|---:|---|
| CI/CD | ~35% | GH Actions YAML staged at `docs/integration-workflow.yml.staged`. |
| Integration tests | ~55% | Tier-1 deploy_path shield live; Tier-2 e2e at `tests/integration_e2e/`. |
| Observability | ~85% | Structured JSON logs everywhere; Prometheus on key endpoints. |
| Disaster recovery | ~80% | Auto-backups + restore runbook live. |
| Security audit | 0% | External pen-test needed pre-public-launch. |
| SEBI IA registration | ~30% | Q1 2026 filing; status page drafted [verify current]. |

### Queues completed (chronological hint, not exhaustive)
Queue AA → BB → CC → DD → EE → FF → LL → MM → OO → PP → QQ → SS → UU → VV → WW → XX → YY → ZZ → Z → AAA → BBB → CCC → EEE. Each has reports under `docs/QUEUE_*_REPORT.md`. Recent threads: **Queue BBB** (frontend Sprint 9 — badges + tooltips + nav), **Queue CCC** (real-Dhan historical pipeline — this weekend, see `SESSION_HANDOFF.md`), **Queue EEE** (parallel indicator smoketests — **MERGED to main 2026-06-13 via PR #13**, 137 indicators 127/6/0).

---

## 8. Product Vision (condensed roadmap)

| Phase | What | Status |
|---|---|---|
| 1 | The Bridge (TV → broker) | ✅ |
| 2 | Strategy Templates | 🚧 ~90% |
| 3 | Backtest Engine + real-Dhan data | 🚧 |
| 4 | Reliability / Truth / Coach | ✅ ~90% |
| 5 | Visual No-Code Builder | 🚧 |
| 6 | AI Advisor (LLM) | 🚧 ~30% |
| 7-8 | Charting + Options Analytics | partial / not started |
| 8B | Live data feed | ✅ |
| 9 | Marketplace + Copy Trading | 🧠 gated |
| 10-11 | Multi-asset (MF, ETF, MCX, US, Crypto) | 🧠 |
| 12+ | Platform (desktop, mobile, voice) — mobile likely first | 🧠 |

**Aggregate platform completion (Phases 1-9, weighted):** ~62% as of 2026-05-18 [verify post-CCC].

---

## 9. Regulatory + Launch + Ops

### SEBI framework
- **SEBI Algorithmic Trading Framework** (Feb 2025) enforceable from **April 1 2026**.
- Real-money algo orders require **NSE / BSE algo-provider empanelment**. Empanelment is a months-long process [verify current status].
- BSE LTD futures running pre-empanelment = **founder-accepted risk**, documented.
- **White-box only** — black-box LSTM / RL strategies rejected by SEBI for retail. The Glass Box positioning is mandatory, not stylistic.
- AlgoMitra is **advisory only**, never autonomous execution — explicit SEBI compliance choice.

### Launch dates (originals — both passed; current status [verify])
- **Paper launch target:** 2026-05-18.
- **Live launch target:** 2026-07-01.
- Verify current launch status against `docs/launch-checklist.md` (107 lines) and `docs/POST_MAY_18_RETROSPECTIVE.md`.

### Regulatory moat
Strategy Transparency Ledger + Glass Box AI + advisory-only AlgoMitra = the **regulatory + trust differentiator** vs. black-box retail algo vendors.

### Ops learnings & infra cost
- **AWS suspension incident — 2026-06-10:** account suspended due to **free-tier credit expiry**, NOT non-payment. Now on **pay-as-you-go ≈ ₹5,100 / month** [verify current bill].
- **Hetzner migration** identified as ~₹500–900 / month alternative — **deferred until post-go-live**. Migration risk during pre-launch judged higher than the cost saving.
- **Non-negotiable safeguards** going forward:
  - AWS Budget alerts active.
  - Automated DB backups running.
- **Stranded resource flag:** `Jayesh-Trading-Robot` t3.micro at IP **`3.6.56.69`** — likely unused; founder-flagged for review / shutdown [verify before terminating].

---

## 10. Decision Log (founder-supplied, not derived)

| Date approx | Decision | Why |
|---|---|---|
| ongoing | **White-box only** for retail | SEBI Feb 2025 retail black-box ban. |
| ongoing | **AlgoMitra advisory only**, never autonomous | SEBI compliance. |
| ongoing | **FUTURES = NRML only**, MIS/INTRADAY forbidden | Risk policy. |
| ongoing | **Paper / live gated by `is_paper` per-strategy** | Migration 027 introduced after May-18 incident where global flag converted BSE LTD live → paper silently. |
| 2026-05-21 | Migration **027 + 028 + (post) 029 + 030** chain | 027 = `is_paper` flag; 028 = backtest_runs/trades/metrics; 029 = `historical_candles`; 030 = `historical_backfill_jobs` (file-only until founder applies). |
| 2026-06-03 | **Queue CCC v2 design approved** | Real-Dhan historical pipeline, 22-symbol seed (BSE LTD + CDSL + 5 indices + 15 NIFTY-50), quality_score per Q6A, rate-limit guard 80/20 + paused_live override. |
| 2026-06-07 (cutover-12) | **Safety fix: `backtest.py:403` score-write gated** to `candles_source == "dhan_historical"` only | Prevents synthetic-data backtest scores polluting the SafetyChain live-order gate (Trust ≥ 70 / Truth ≥ 55). Baseline carried: **44 pre-existing test failures on `main`** — known, not regressions of this fix. |
| weekend 2026-06-12/13 | **Queue DDD 027 UUID-cast fix** via `CAST(:live_id AS uuid)` | SQLAlchemy `text()` parser collides with `::uuid` suffix; ANSI CAST avoids it. |
| 2026-06-13 | **Queue EEE merged to main via PR #13** | 137 indicator smoke battery (127 PASS / 6 WARN / 0 FAIL). Tests + docs only, no production code touched. Lint-fix pass `38436b2` cleared the BLOCKING `lint-diff` gate. Merge via GitHub API (`gh pr merge --merge`) — not a direct push. New `origin/main` HEAD = `34357dd`. |
| 2026-06-13 | **Gate (d): Queue CCC skeleton + DDD fix merged to main via PR #14** | Full Queue CCC Sprint 2 + Phase 3 skeleton + DDD 027 UUID-cast fix landed on main. Code-land only — migrations 029/030 ship as files; EC2 alembic upgrade remains a separate founder-gated step. Celery task gated OFF (`BACKFILL_ENABLED` defaults OFF). Lint-fix `390bb4f` + module-skipif test-gate fix `5ab0ef4` cleared CI. Merge via GitHub API (`gh pr merge --merge`) — not a direct push. New `origin/main` HEAD = `96fc3a1`. |
| 2026-06-13 | **Queue FFF: A5 Dhan credential factory code-merged via PR #16** | Replaces the `_dhan_client_factory_for_job` `NotImplementedError` stub with a 3-tier resolver — per-user (`job.requested_by_user_id`) → service-account-β (`BACKFILL_DHAN_USER_ID` env → DB lookup) → service-account-α (`BACKFILL_DHAN_CLIENT_ID`+`BACKFILL_DHAN_ACCESS_TOKEN` env, sentinel UUID `…0002` for rate-limit keying). Sacred-zone READ-only (BrokerCredential lookup + decrypt — same pattern as production webhook/exec). 20 new tests, 131/131 historical_candles suite green. `BACKFILL_ENABLED` defaults OFF (unchanged) — drain still requires EC2 deploy of 029+030 + flag flip in a separate founder-gated session. New `origin/main` HEAD = `c602aca`. |
| 2026-06-14 | **Queue HHH overnight buildout — 10 branches on `origin`, zero merged, prod untouched** | Built out all 9 Coming-Soon pages (`PROJECT_MAP.md` §1/§5) as isolated feature branches: M1 `feat/hhh-admin-auth-guard` (`35e5b2f`), M2 `feat/hhh-webhooks` (`f74a785`, customer-facing TOP priority — TradingView token CRUD), M3 `feat/hhh-admin-users` (`ccbd9dd`), M4 `feat/hhh-admin-announcements` (`412e688`), M5 `feat/hhh-admin-audit` (`522577f`), M6 `feat/hhh-admin-kill-switch-events` (`fa5c586`), M7 `feat/hhh-admin-home` (`732e04b`), M8 `feat/hhh-settings` (`79db7fc`), M9 `feat/hhh-analytics` (`7ee3fda`), M10 `feat/hhh-alerts` (`4ffebba`) + `docs/hhh-summary` (`4092b44`). COMPLETE: M1/M2/M4/M5/M6/M7. SCAFFOLDED: M3/M8/M9 (M9 = recent-100-trades, full-history flagged) and M10 (storage only — alerts **engine NOT built**, load-bearing amber banner, needs **migration 031** on EC2; mig 031 is LOCAL-dev + M10-branch only, NOT on main/prod). Customer-facing UI **CC cannot self-verify** → founder visual review gates every merge. |
| 2026-06-14 | **Decided 2-phase next-session plan — do NOT bundle into one autonomous prompt** | **Phase 1 = HHH visual review + merge** (founder reviews each branch via Vercel preview URL or local `npm run dev`; order M1 auth-guard → M2 webhooks → M3–M7 admin → M8/M9 → M10 verify amber banner; merge only approved branches, one PR each). **Phase 2 = real-Dhan go-live**, a GATED deploy the founder gates step-by-step: DB backup FIRST → **full backend jump `cutover-8` → `main`** (NOT just migrations — EC2 still at `cutover-8` `55047df`) with health check + verify BSE LTD intact → migrations 029+030 (dev→staging→prod, before-migrations hard-stop) → creds (β `BACKFILL_DHAN_USER_ID` or α `BACKFILL_DHAN_CLIENT_ID`+`BACKFILL_DHAN_ACCESS_TOKEN`) → restart `celery_worker`+`celery_beat` (before-restart hard-stop) → `BACKFILL_ENABLED=true`, drain **1–2 symbols first** (not all 22), verify real data → confirm BSE LTD `89423ecc` untouched before Monday 09:15 IST. |
| 2026-06-16 | **Queue HHH SHIPPED — webhooks + 6 admin pages MERGED & LIVE on tradetri.com** | Phase 1 of the 2026-06-14 plan executed. Merged to `main` (each frontend-only + proactive `prettier@3` style fix, CI-green, backend-live verified vs the cutover-12 prod OpenAPI): M1 auth-guard #18, M2 webhooks #26 (+#31 modal URL fix → `/api/webhook/strategy/<token>`, +#30 nav SOON removal), M3 users #19, M4 announcements #20, M5 audit #21, M6 kill-switch-events #23, M7 admin-home #22. `origin/main` = `1919265`. Also: test-pollution baseline #29 (Queue III). **Still scaffolded/unmerged:** analytics M9 #24, settings M8 #25, alerts M10 (no PR — backend alerts engine unbuilt). Corrections surfaced this session: prod backend is **cutover-12 `a63d5e8`** (NOT cutover-8 — §2/§5 rows stale), and backend `create_webhook` (`users.py:387`) returns the wrong relative legacy webhook URL (frontend modal works around it client-side; backend fix tracked in `SESSION_HANDOFF.md` §6 for the Phase-2 deploy). |
| ongoing | **Options engine deferred** to Q4 2026 [verify] | Engine ~30% built. Decisions made: Dhan NFO single broker, Plan A directional, NRML carry-forward only, lot toggle even-only (2/4/6/8/10), cash equity DROPPED, 63 stranded options templates config-hidden. |
| ongoing | **Pine → Python port** is future work, target ~95-97% match | Reproducibility goal for the live strategy. |
| ongoing | **`/proof` (Trust dashboard) → post-launch lean-MVP** | Mockup built; ship after main launch. |
| ongoing | **Marketing assets only** via Google AI Pro (Nano Banana) | Image gen for marketing; no LLM in product runtime yet. |
| ongoing | **Verification status = INTERNAL only**, not customer-facing | Sprint 10 direction; final call deferred to pre-launch window. |
| ongoing | **Parallel-session new-files-only + `PATCH_INSTRUCTIONS.md`** | Conflict avoidance across concurrent CC sessions. |

---

## 11. Pending / Backlog (not started, but on the radar)

| Item | Detail | Status |
|---|---|---|
| **Competitor feature audit** | Compare TRADETRI strategy-builder against **Tradetron, AlgoTest, Streak, Sensibull, Opstra**. Buckets defined: <br/>• **MUST:** trigger entry, absolute + % SL/target, trailing SL, time/day filters, position sizing, OTM strikes. <br/>• **NICE:** multi-leg, Greeks, volatility filter. <br/>Original May-18 purpose is now stale — refresh framing before kicking off. | not started |
| **Pine → Python port (95-97% match target)** | Reproduce the live Pine v4.10.1-LITE strategy faithfully in Python so backtests + live execution agree to within ~3-5%. Documented Pine flaws (§5) get fixed in the port. | not started |
| **Options engine completion** | Currently ~30%. Q4 2026 target [verify]. Decisions in §10 already lock the design surface. | parked Q4 2026 |
| **Trust / Public Proof Dashboard (`/proof`)** | Mockup built; lean-MVP deferred to post-launch (also in §6). | mockup only |
| **Edit-existing-strategy hydrate** (Visual Builder v1.1) | GET → state-hydrate side of the no-code builder. | next-up |
| **AND/OR multi-condition combinator** (Visual Builder v2) | Currently single-condition only. | v2 scope |
| **Exit-side indicator conditions** (Visual Builder v2) | Today exits are SL/TP only. | v2 scope |
| **External security pen-test** | Required pre-public-launch. | not scoped |
| **SEBI IA registration completion** | Q1 2026 filing in progress [verify current state]. | ~30% per MASTER_ROADMAP |
| **CI/CD workflow YAML manual install** | Lives staged at `docs/integration-workflow.yml.staged`. ~15 min activation. | quick-win |

---

## 12. How to use this file (every new chat)

### Recommended paste order
1. Paste **`docs/MASTER_CONTEXT.md`** (this file) first.
2. Paste **`docs/SESSION_HANDOFF.md`** second.
3. Then ask your question.

### What this file gives Claude
- The non-negotiable rules from CLAUDE.md.
- The architecture map and tech stack.
- The product vision and regulatory state.
- The decision log explaining "why" behind the constraints.

### What SESSION_HANDOFF.md gives Claude (and this file does NOT)
- Current branch HEADs, last-N commit SHAs.
- Open / parked gates from the most recent session.
- This-week anomaly list (A1–An).
- Live DB state in dev.

### Hard rules for Claude when reasoning from this file
- **Never guess a SHA, tag, or gate state on a live-money platform.** Read it from `SESSION_HANDOFF.md` or ask the founder.
- **Never edit a sacred-zone file** (§2 list) without an explicit founder-confirmed `is_paper=false` gate.
- **Never push to `main`.**
- **When in doubt, STOP and ask.** Founder gates every deploy, every sacred-zone edit, every push.

### What to do if a value looks stale or wrong
Stale `[verify]` items are expected — flag them in the session and propose a refresh, but **do not silently update**. Founder reviews changes to this file before commit and never pushes auto-edits.

---

_End of MASTER_CONTEXT.md_
