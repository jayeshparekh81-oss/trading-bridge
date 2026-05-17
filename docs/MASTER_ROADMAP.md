# Master Roadmap — TRADETRI

**Single source of truth for Phase 1-12 status with completion percentages.**

**Snapshot:** 2026-05-17 (end of May 17 sprint day; see
`docs/POST_MAY_17_RETROSPECTIVE.md` for what landed today).

**Companion doc:** `docs/roadmap.md` is the public-facing feature list. This file is the **internal status tracker** with completion percentages, blockers, and current owners.

---

## How to read this doc

Each phase carries:
- A **Status** chip — `🚧 IN PROGRESS` / `✅ COMPLETE` / `📋 SCOPED` / `🧠 NOT STARTED`
- A **Completion %** — rough; updated at major sprint ends
- A **What ships** list — concrete deliverables
- A **What blocks completion** list — gaps + their pointer to a BLOCKERS file or design doc

Tasks marked with [BLOCKERS_<NAME>.md] reference the open-questions
files in the repo root. Founder reviews → percentage moves.

---

## Phase 1 — The Bridge (TradingView webhook → broker)

**Status:** ✅ COMPLETE
**Completion:** 100%

What ships:
- TradingView webhook receiver (`/api/webhook/{token}` + new `/api/webhook/strategy/{token}`)
- `BrokerInterface` abstraction + Fyers v3 + Dhan HQ live integrations
- 4 broker stubs (Shoonya, Zerodha, Upstox, AngelOne) — stub state, not active
- Kill switch (per-user daily loss limit + auto square-off)
- Circuit breaker, idempotency, multi-strategy, JWT auth
- Email (SES) + Telegram notifications
- Docker Compose full stack + EC2 deploy
- Test coverage: 96%+ on production code path

---

## Phase 2 — Strategy Templates Catalog

**Status:** 🚧 IN PROGRESS (most-of-the-way)
**Completion:** 85%

What ships:
- 113-entry catalog (`backend/data/strategy_templates_seed.json`)
- 45 active equity templates (up from 15 morning of May 17)
- 5 inactive equity (blocked on indicator commission)
- 63 inactive options templates (Phase 7-8 unlock)
- `POST /api/templates/{slug}/clone` flow live
- Strategy detail page surfaces template_origin (fix shipped May 17)

What blocks 100%:
- 5 inactive equity templates need indicator commission
  (`renko`, `heikin_ashi`, `alma`, `kama`, `pivot_swing`) —
  see `BLOCKERS_PHASE_2_PART_2.md`. Estimated effort: ~5 dev-days
- 15 Queue I configs proposed but not merged — see
  `BLOCKERS_PHASE_2_TEMPLATES.md` for the founder review checklist
- Indicator-name canonical-vs-informal drift between Phase 1 seed
  and `strategy_engine` registry — same BLOCKERS_PHASE_2 file

---

## Phase 3 — Backtest Engine (Phase D Strategy Tester)

**Status:** 🚧 IN PROGRESS (engine done; extension layer prep'd)
**Completion:** 65%

What ships:
- Deterministic Pure-Python engine at `app/strategy_engine/backtest/`
  (2617 LOC across 8 files; 165 indicator dispatch branches)
- `POST /api/strategies/{id}/backtest` synchronous endpoint
- Strategy Coach Hinglish health card
- Reliability + truth + regime + deviation reports

What blocks 100%:
- Async + persisted + idempotent extension layer is SKELETON only
  on `feat/backtest-engine-week2-prep` — 7-day supervised Week-2
  sprint plan in `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`
- Migration 028 DRAFT not applied; 3 new tables (`backtest_runs`,
  `backtest_trades`, `backtest_metrics`) pending
- Rate-limit + queue-isolation decisions open
  (`BLOCKERS_BACKTEST_WEEK2.md` Q1-Q2)
- Engine versioning + cache-bust policy proposed; founder ratification needed

---

## Phase 4 — Reliability / Truth Score / Coach

**Status:** ✅ MOSTLY COMPLETE (production-quality)
**Completion:** 90%

What ships:
- `app/strategy_engine/reliability/` — walk-forward, parameter
  sensitivity, out-of-sample, reliability report
- `app/strategy_engine/truth/` — strategy truth scoring
- `app/strategy_engine/coach/` — Hinglish health card generator
- `app/strategy_engine/regime/` — market regime detection
- `app/strategy_engine/deviation/` — live-vs-backtest deviation
- `app/strategy_engine/advisor/` — diagnose + trade quality
- All wired into the Phase D Strategy Tester response envelope

What blocks 100%:
- Coach copy stale relative to current product state (mentions
  features removed; covered in `BLOCKERS_DOCS.md` if applicable)
- No per-strategy-segment truth score yet (options-specific
  truth lands Phase 7-8)

---

## Phase 5 — Visual No-Code Strategy Builder

**Status:** 📋 SCOPED (scaffold landed today; supervised work to begin)
**Completion:** 10%

What ships:
- `/strategies/builder` route (UI scaffold on
  `feat/strategy-builder-scaffold`) — 5 components + types + smoke
  test
- IndicatorPanel calls live `GET /api/strategies/indicators` (281
  indicator entries; 230 active)
- Existing per-rules editors at `/strategies/builder/{entry,exit,risk}`
  also operational (separate concept from the visual builder)

What blocks 100%:
- `@xyflow/react` dependency flagged in `BLOCKERS_STRATEGY_BUILDER.md`
  — not yet installed. Founder approval gate.
- Reducer + drag-drop + emit + save are 4 sequential PRs (PR-A
  through PR-D) per `docs/STRATEGY_BUILDER_SPEC.md` — ~5 dev-days
- Edit-existing-strategy mode (PR-E) — ~2 dev-days
- Visual-builder ↔ per-rules-template integration design — see
  `BLOCKERS_STRATEGY_BUILDER.md` Q3

---

## Phase 6 — AI Advisor (LLM-driven coach + Q&A)

**Status:** 🚧 IN PROGRESS (advisor scaffolding live, LLM not wired)
**Completion:** 30%

What ships:
- `app/strategy_engine/advisor/` exposes `diagnose_strategy` +
  `compute_trade_quality` — pure-Python, no LLM
- Strategy Coach card consumes these (lives in Phase 4 production
  shipping)

What blocks 100%:
- No actual LLM integration yet (advisor decisions are
  rule-based, not model-driven)
- AI strategy doctor doc (`docs/ai-strategy-doctor.md`) describes
  proposed behaviour; implementation pending
- Founder voice + Hinglish prompt-engineering work to do
- Token-cost + latency-budget gates to design

---

## Phase 7-8 — Charting + Options Analytics + Options Strategy Builder

**Status:** 🚧 PARTIALLY IN PROGRESS (charting live; options builder not started)
**Completion:** 40% (charting), 0% (options builder)

What ships:
- Chart module live (`frontend/src/app/(dashboard)/chart/` +
  `backend/app/chart/`)
- Lightweight-charts integration, dark theme, mock-toggle
- WebSocket ticks + candles channels
- Trade markers overlay (Phase E)
- 5 chart-side indicators (Phase F Component 1) shipping

What blocks 100%:
- Options chain viewer + Greeks calculator not started
- IV surface, max pain, OI analysis dashboard not started
- Options strategy builder (Iron Condor, Straddle) not started —
  needs the visual builder (Phase 5) shipped first
- 63 inactive option templates in the catalog wait for this

---

## Phase 8B — Live data feed (Dhan ticks + historical)

**Status:** ✅ COMPLETE
**Completion:** 100%

Backtest + strategy tester pull from Dhan when available, synthetic
fallback when not. Live trading uses Dhan order API.

---

## Phase 9 — Strategy Marketplace + Copy Trading

**Status:** 🧠 NOT STARTED (deliberate — needs proof base first)
**Completion:** 0%

Marketplace gating requires:
- Backtest engine extension done (Phase 3 → 100%)
- Truth score + reliability + deviation = 30-day customer-visible
  history for at least 50 customers
- SEBI registration status clarified
- Anti-grift validation lifecycle defined (every listed strategy
  must pass backtest + reliability + paper-mode-validation +
  live-deviation gates before listing)

Estimated start: 8-12 weeks post-launch, depending on adoption.

---

## Phase 10-11 — Multi-asset expansion (Mutual Funds, ETF, MCX, US stocks, Crypto)

**Status:** 🧠 NOT STARTED
**Completion:** 0%

Roadmap target. No work scoped yet. Sequencing TBD.

---

## Phase 12+ — Platform Expansion (desktop, mobile, voice)

**Status:** 🧠 NOT STARTED
**Completion:** 0%

Roadmap target. Mobile app likely takes precedence over desktop +
voice. Sequencing TBD.

---

## Cross-cutting infrastructure

| Sub-system | Status | Completion | Notes |
|---|---|---:|---|
| CI/CD | 🚧 IN PROGRESS | 30% | GH Actions workflow staged at `docs/integration-workflow.yml.staged`; manual install pending |
| Integration test framework | 🚧 IN PROGRESS | 40% | Tier-1 shield live (May-17 deploy-path regressions); Tier-3 pending |
| Observability (logs + metrics) | ✅ MOSTLY COMPLETE | 85% | Structured JSON logs everywhere; Prometheus counters live on key endpoints |
| Disaster recovery | ✅ MOSTLY COMPLETE | 80% | Auto-backups + restore runbook live (`backend/DISASTER_RECOVERY.md`) |
| Security audit | 🧠 NOT STARTED | 0% | External pen-test needed pre-public-launch |
| SEBI IA registration | 🚧 IN PROGRESS | 25% | Filed Q1 2026; awaiting response |

---

## Quick wins backlog (would move multiple phases forward)

1. **Install @xyflow/react** (`BLOCKERS_STRATEGY_BUILDER.md` Q2) → unblocks Phase 5 PR-A
2. **Commission `kama` indicator** (0.5 dev-day) → unblocks 1 Phase 2 template
3. **Manual install of CI workflow YAML** (`MANUAL_INSTALL_CI_WORKFLOW.md`) → activates Tier-1 regression gate
4. **Apply migration 028** in dev → unblocks Phase 3 Day-1
5. **Founder reviews 15 Queue I template configs** → unblocks Phase 2 → ~92%

Each is < 1 hour of founder/operator time. Prioritised by phase-lift.

---

## Phase completion summary

| Phase | Completion | Trend |
|---|---:|---|
| Phase 1 — The Bridge | 100% | ✅ shipped |
| Phase 2 — Templates | 85% | ↑ from 30% morning of May 17 |
| Phase 3 — Backtest Engine | 65% | ↑ skeleton landed |
| Phase 4 — Reliability/Truth/Coach | 90% | ↔ stable |
| Phase 5 — Visual Builder | 10% | ↑ from 0% (scaffold landed May 17) |
| Phase 6 — AI Advisor | 30% | ↔ stable |
| Phase 7-8 — Options Analytics | 20% (avg) | ↔ stable |
| Phase 8B — Live data feed | 100% | ✅ shipped |
| Phase 9 — Marketplace | 0% | gated on prior phases |
| Phase 10-12 — Asset / Platform expansion | 0% | not scoped |

**Aggregate platform completion (Phase 1-9 weighted-avg):** ~58%
**Trajectory:** trending up. Phase 2, 3, 5 are the active heavy-lifting fronts.
