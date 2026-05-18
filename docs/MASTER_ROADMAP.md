# Master Roadmap — TRADETRI

**Single source of truth for Phase 1-12 status with completion percentages.**

**Snapshot:** 2026-05-18 (post Queue III sprint).

**Companion docs:**
- `docs/roadmap.md` — public-facing feature checklist
- `docs/POST_MAY_18_RETROSPECTIVE.md` — chronological recap
- `docs/README.md` — directory index

---

## How to read this doc

Each phase carries:
- **Status** chip — `🚧 IN PROGRESS` / `✅ COMPLETE` / `📋 SCOPED` / `🧠 NOT STARTED`
- **Completion %** — rough; updated at major sprint ends
- **What ships** — concrete deliverables
- **What blocks completion** — gaps + their pointer to BLOCKERS / design doc

Branches reference origin paths; "deployed" means merged to main +
visible on dev/staging/prod.

---

## Phase 1 — The Bridge (TradingView webhook → broker)

**Status:** ✅ COMPLETE
**Completion:** 100%

- TradingView webhook receiver + `BrokerInterface` abstraction
- Fyers v3 + Dhan HQ live integrations
- Kill switch, circuit breaker, idempotency, JWT auth
- Email (SES) + Telegram notifications
- Docker Compose full stack + EC2 deploy

---

## Phase 2 — Strategy Templates Catalog

**Status:** 🚧 IN PROGRESS (most-of-the-way)
**Completion:** 90% (was 85% pre-Queue III)

What ships:
- 113-entry catalog in `backend/data/strategy_templates_seed.json`
- 45 active equity templates
- 5 inactive equity templates → 5 indicators **commissioned** this
  sprint (`feat/indicator-commission-batch-1`): heikin_ashi, alma,
  kama, pivot_swing, fibonacci_retracement
- 63 inactive options templates (Phase 7-8 unlock)
- `POST /api/templates/{slug}/clone` flow live (May-17 fix shipped)

What blocks 100%:
- `indicator_runner.py` dispatch entries for the 5 new indicators
  (BLOCKER Q6 in `BLOCKERS_INDICATOR_COMMISSION_1.md` — separate
  follow-up sprint needed)
- Once dispatch lands, the 5 inactive equity templates can be
  promoted (`renko-trend` still blocked on Renko transform — that's
  Batch 2)
- 15 Queue I Task 2 proposed configs pending founder review
  (`docs/PHASE_2_TEMPLATE_CONFIGS.md`)

---

## Phase 3 — Backtest Engine

**Status:** 🚧 IN PROGRESS (engine done; extension layer Days 1-3 deployed dormant)
**Completion:** 75% (was 65% pre-Queue III; deployment of Days 1-3 lifted it)

What ships:
- Deterministic Pure-Python engine at `app/strategy_engine/backtest/`
  (2617 LOC; 165 indicator dispatch branches)
- `POST /api/strategies/{id}/backtest` synchronous endpoint (Phase D
  Strategy Tester)
- **Days 1-3 of Week 2 extension** (`feat/backtest-engine-day-1-3`):
  - Migration 028 APPLY-READY (3 new tables — backtest_runs / trades / metrics)
  - SQLAlchemy ORM models + 8 persistence helpers
  - Celery `@shared_task run_backtest_task` with PENDING→RUNNING→
    SUCCEEDED|FAILED state machine
  - SHA-256 idempotency hash with engine_version invalidation
  - 3 API endpoints (POST enqueue, GET run, GET trades) — router
    NOT registered in main.py
  - 65/65 tests passing in 2.09s
- Phase F Component 1: BB stddev bug fix shipped

What blocks 100%:
- Days 4-7 of Week 2 plan (`docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`)
  pending supervised execution: rate limit, queue isolation,
  anonymous-config preview, engine versioning, observability sweep
- Migration 028 NOT applied to any env (needs founder dev-DB apply)
- Router needs manual founder mount in `main.py`

---

## Phase 4 — Reliability / Truth / Coach

**Status:** ✅ MOSTLY COMPLETE
**Completion:** 90% (unchanged)

What ships:
- `reliability/` walk-forward, parameter sensitivity, out-of-sample
- `truth/` strategy truth scoring
- `coach/` Hinglish health card
- `regime/` market regime detection
- `deviation/` live-vs-backtest deviation
- `advisor/` diagnose + trade quality

What blocks 100%:
- Coach copy stale relative to current product state — review pass needed
- Per-segment truth scoring (options-specific) → Phase 7-8

---

## Phase 5 — Visual No-Code Strategy Builder

**Status:** 🚧 IN PROGRESS (v1 LIVE on branch)
**Completion:** 30% (was 10% pre-Queue III; major lift)

What ships:
- `/strategies/builder` route with full functional drag-drop
  (`feat/strategy-builder-v1`)
- Real @xyflow/react canvas with 3 custom node types
- IndicatorPanel pulls from live `GET /api/strategies/indicators`,
  supports HTML5 drag + double-click fallback
- ConditionBuilder inspector with 3 modes (indicator / condition / exit)
- SaveStrategyDialog POSTs/PUTs to existing `/api/strategies`
- BuilderState ↔ StrategyJSON serializer with expression parser
  (>, <, >=, <=, ==, !=, crossover, crossunder)
- 29 unit tests across 3 files passing

What blocks 100%:
- Edit-existing-strategy load-side (GET → hydrate state) — v1.1
- AND/OR multi-condition combinator — v2
- Exit-side indicator conditions (not just SL/TP) — v2
- Backtest-from-builder integration → blocked on Phase 3 router mount
- Live preview / visual debugger — v3

---

## Phase 6 — AI Advisor

**Status:** 🚧 IN PROGRESS (rule-based scaffolding, no LLM yet)
**Completion:** 30% (unchanged)

Rule-based diagnose + trade quality live. No LLM integration yet —
the `ai_advisor` and `ai_strategy_doctor` docs describe proposed
behaviour, not shipping.

---

## Phase 7-8 — Charting + Options Analytics

**Status:** 🚧 PARTIAL (charting live; options builder not started)
**Completion:** 40% / 0%

Charting module + WebSocket + trade markers + 5 chart indicators
shipping. Options chain viewer, Greeks, IV surface, strategy builder
not started — block 63 inactive options templates.

---

## Phase 8B — Live data feed

**Status:** ✅ COMPLETE
**Completion:** 100%

Dhan ticks + historical via `data_provider`. Live order API via Dhan.

---

## Phase 9 — Marketplace + Copy Trading

**Status:** 🧠 NOT STARTED (gated on prior phases)
**Completion:** 0%

Gated on: Phase 3 → 100%, customer deviation history (30+ days /
50+ customers), SEBI registration, anti-grift validation lifecycle.

Estimated start: 8-12 weeks post-launch.

---

## Phase 10-11 — Multi-asset expansion (Mutual Funds, ETF, MCX, US stocks, Crypto)

**Status:** 🧠 NOT STARTED
**Completion:** 0%

No work scoped.

---

## Phase 12+ — Platform expansion (desktop, mobile, voice)

**Status:** 🧠 NOT STARTED
**Completion:** 0%

Mobile app likely takes precedence over desktop + voice.

---

## Cross-cutting infrastructure

| Sub-system | Status | Completion | Notes |
|---|---|---:|---|
| CI/CD | 🚧 IN PROGRESS | 35% | GH Actions workflow at docs/integration-workflow.yml.staged; manual install pending |
| Integration test framework | 🚧 IN PROGRESS | 55% (was 40%) | Tier-1 deploy_path shield live; Tier-2 e2e tests at `tests/integration_e2e/` (Queue III Task 3 — 14 tests passing) |
| Observability | ✅ MOSTLY COMPLETE | 85% | Structured JSON logs everywhere; Prometheus counters live on key endpoints |
| Disaster recovery | ✅ MOSTLY COMPLETE | 80% | Auto-backups + restore runbook live |
| Security audit | 🧠 NOT STARTED | 0% | External pen-test needed pre-public-launch |
| SEBI IA registration | 🚧 IN PROGRESS | 30% (was 25%) | Q1 2026 filing; status page now drafted |

---

## Quick wins backlog (sort by phase-lift per founder-hour)

1. **Apply migration 028 on dev DB** (10 min) → unblocks Phase 3 ~75% → 80%
2. **Mount `backtest_extension` router** (10 min) → unblocks Phase 3 → 82%
3. **Founder reviews + activates 5 indicator dispatch entries** (1 hour) → unblocks Phase 2 → 95%
4. **Manual install of CI workflow YAML** (15 min) → activates Tier-1 regression gate
5. **Founder reviews 15 Queue I template configs** (1 hour) → unblocks Phase 2 → ~98%

---

## Phase completion summary

| Phase | Completion |  Δ since 2026-05-17 |
|---|---:|---:|
| Phase 1 — The Bridge | 100% | unchanged |
| Phase 2 — Templates | 90% | ↑ 5pp (5 indicators commissioned) |
| Phase 3 — Backtest Engine | 75% | ↑ 10pp (Days 1-3 deployed dormant) |
| Phase 4 — Reliability/Truth/Coach | 90% | unchanged |
| Phase 5 — Visual Builder | 30% | ↑ 20pp (v1 LIVE) |
| Phase 6 — AI Advisor | 30% | unchanged |
| Phase 7-8 — Options Analytics | 20% avg | unchanged |
| Phase 8B — Live data feed | 100% | unchanged |
| Phase 9 — Marketplace | 0% | gated |
| Phase 10-12 — Asset / Platform expansion | 0% | not scoped |

**Aggregate platform completion (weighted-avg, Phases 1-9):** ~62% (was ~58% on May 17)
**Trajectory:** trending up; Phases 2 + 3 + 5 are the active fronts.

---

## Status legend

- ✅ COMPLETE — production-ready; all customers can use
- 🚧 IN PROGRESS — partial; some customers can use some features
- 📋 SCOPED — design + skeleton landed; implementation in flight
- 🧠 NOT STARTED — no commits yet; just on the roadmap
