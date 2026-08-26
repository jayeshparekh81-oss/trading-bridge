# Queue TT — Parallel Work Audit (DISCOVERY ONLY)

**Branch:** `docs/queue-tt-audit` (from `origin/main` `3f40721`). **Zero code
edits** — this doc is the only artifact. Audited range `0716e4e` (May 21
baseline) → `origin/main` `3f40721` (May 31).

---

## Executive summary (5 findings)

1. **No untracked active parallel work exists.** Every commit on main in the
   audited window traces to *your own* queue lineage (Phase F indicators,
   translator stack A2–E2, CI gate, dhan-casing, DEPLOY.md, RC1 synthetic data)
   or the already-reconciled `deploy/3fixes` hotfixes. The feared "mid-session
   surprises" are all accounted for.
2. **`3f40721` ("RC1 richer synthetic data — 12/12 templates fire", May 31
   01:01) is YOUR OWN Queue SS work**, merged to main by you — the merge range
   `4da606a..3f40721` contains exactly `7b26d2a` + the identical 4 files. **Not**
   a parallel re-implementation.
3. **RC1 is merged to main but NOT deployed.** The last deployed release
   (`release-cutover-2` = `19e4689`) does **not** contain `3f40721`, so prod
   still runs the **old pure-sine synthetic generator** — this is precisely why
   Queue RR observed 0 trades in production. **Deploying RC1 closes Queue RR.**
4. **Phase F (May 17) is old, merged, and largely resolved.** It fixed a real
   data-integrity bug (Bollinger bands inflated **+2.60%**); MACD seeding is
   DEFERRED (documented xfail); EMA-docstring + SMA-NaN are minor open notes.
5. **Phase 5 Strategy Builder is near-complete and already in prod, not
   in-flight WIP.** The "unlock when Phase 5 ships" UI text is honest marketing;
   the actual gate is driven by `strategy_json` presence. **No active parallel
   author on the builder → translator work is safe to continue.**

> 🔒 **Read-only discipline kept.** No code/test/config edited; no branch for
> code; no push to main. Only `docs/QUEUE_TT_PARALLEL_AUDIT.md` created.

---

## Phase 1 — Phase F (indicator Pine-parity audit, May 17)

> The exact file `docs/parallel-cc-notes/PHASE_F_ROADMAP_DIAGNOSIS.md` does **not
> exist** in this checkout. The Phase F doc set lives in `docs/archive/` (6 docs).

**Scope:** audit the 5 MVP indicators (SMA/EMA/RSI/MACD/Bollinger) for TradingView
Pine-Script parity before launch; build a functional backtest adapter
(`backtest_adapter.py`) + independent reference tests.

| Indicator | Issue | Severity | Status |
|---|---|---|---|
| **Bollinger** | erroneous `sqrt(N/(N-1))` Bessel correction → bands **+2.60%** too wide (Pine uses biased stddev) | 🔴 **HIGH** | **FIXED** (`63932b0`, `333b675`, `a0bced4`) |
| **MACD** | TA-Lib aligned-seeding vs Pine-docs independent-seeding (~0.6 abs ≈ 0.003%) | 🟠 MEDIUM | **DEFERRED** — xfail + documented; empirical TV check (target 05-25) |
| **SMA** | TA-Lib NaN-poisoning lasts 50+ bars (Pine recovers) | 🟡 LOW | DOCUMENTED (test); footnote pending data-source audit |
| **EMA** | docstring falsely claims a Pine divergence (code is correct) | 🟡 LOW | DEFERRED (cosmetic) |
| **RSI** | none — bit-identical to Pine | — | OK |

- **All 6 cited commits verified real** (dated 05-17): `63932b0 333b675 a0bced4
  c845b3a daad5e7 78379c0`. Phase F **is in main ancestry** (long since deployed).
- 🔴 **Data-integrity callout (Hard-stop #2):** the BB inflation was a genuine
  financial-calc bug — customers would have seen ~50–150 signal disagreements per
  5K-bar backtest vs TradingView. **It is fixed.** The bug survived 8 days because
  the fixture was generated from TRADETRI's own buggy output (self-referential
  test loop) — a process lesson worth noting.
- **Still open:** MACD TV-verification (target 05-25 likely lapsed), EMA docstring,
  SMA-NaN footnote. All minor; backlog candidates.

---

## Phase 2 — DEPLOY.md runbook (157 lines, committed `29bd19b`)

(Authored in the prior Deploy-runbook queue.) Key content, still accurate:
- **Deploy model:** prod deploys from `main` via an **immutable release tag**
  (`release-cutover-N`); never a moving branch.
- **Pre-deploy gates:** tag → EC2 fetch+checkout → `docker compose build backend`
  → **arm rollback before recreate** via `docker export | docker import` into
  `:pre-cutover` (the containerd image store makes `docker tag`/`commit` fail;
  bake only PATH, never secrets) → app-only recreate (`--no-deps backend
  celery_worker celery_beat`, leave postgres/redis).
- **Verify:** health, BSE `is_paper=false`, Dhan cred under lowercase `dhan`, kill
  switch, webhook, celery via **logs not healthcheck**.
- **Rollback:** retag `:pre-cutover`→`:latest` + recreate.
- **Cutover naming:** `release-cutover-N` = the Nth main→prod cutover; `:pre-cutover`
  = the captured rollback image; `prod-pre-cutover` = the git rollback tag.
- **Verdict:** follow it as-is. It is the canonical process and matches how the
  last two cutovers were executed.

---

## Phase 3 — Release tags

| Tag | Commit | Date | Meaning |
|---|---|---|---|
| `prod-pre-cutover` | `837a3fe` | 05-26 | git rollback anchor (pre-cutover prod state); ancestor of cutover-1 |
| `release-cutover-1` | `ca902dc` | 05-29 | 1st main→prod cutover (CI/talib + stack) |
| `release-cutover-2` | `19e4689` | 05-30 | 2nd cutover — **current deployed prod** (adds dhan-casing fix) |
| `pre-rc1-deploy` | `99c5473` | 05-27 | marks translator-stack tip; baseline label before RC1 (note: predates the cutover tags despite the name) |

- **Shipped cutover-1→cutover-2:** only the Dhan lowercase-key auth fix (`9cc23a8`).
- **Cadence:** roughly **one cutover/day** during this active window (05-29, 05-30),
  each scoped to a single fix/merge — a healthy small-batch rhythm.
- **No `release-cutover-3` yet** → **RC1 (`3f40721`) is undeployed.**

---

## Phase 4 — Commit audit `0716e4e..3f40721` (with SACRED flags)

🔴SACRED = executor/direct_exit/webhook/kill_switch/brokers/migrations · 🟡TRANSLATOR · FE · CI · TEST

| Commit | Date | Flags | Summary | Provenance |
|---|---|---|---|---|
| c1cb0f6 | 05-21 | — | broker_credentials dedup+case script (Queue LL) | yours |
| 7b26aee | 05-23 | 🔴 TEST | retain options columns in Dhan scrip-master parser | options work (dormant, per Queue RR) |
| 9c351a0 | 05-23 | TEST | pine mapper options support (NRML) | options work |
| b912a17 | 05-24 | 🔴 TEST | celery persistent per-process event loop | deploy/3fixes hotfix |
| 564079f | 05-24 | 🔴 TEST | executor at-least-once idempotency guard | deploy/3fixes hotfix |
| 0f7dcc5 | 05-24 | TEST | Telegram HTML alerts | deploy/3fixes hotfix |
| 68b9f74 | 05-25 | — | resolver CDSL mappings | resolver work |
| aebe07d | 05-25 | 🔴 TEST | resolver real SEM_EXPIRY_DATE (R4) | resolver work |
| 0f143e3 | 05-26 | TEST | resolver roll expired FUT to front month | resolver work |
| 8c6be3c | 05-26 | 🔴 TEST | webhook pin exit-class to stored symbol (14:30 fix) | deploy/3fixes hotfix |
| 837a3fe | 05-26 | — | skip re-resolve for exit-class actions | = prod-pre-cutover |
| 84ef9f9–04a0ddd | 05-26/27 | 🟡 TEST | translator stack A2/C2/D2/E2 (Queues MM/OO/PP/QQ) | **yours** |
| 99c5473 | 05-27 | — | merge translator stack (8→20 coverage) | **yours** = pre-rc1-deploy |
| efd5ae9 | 05-28 | 🔴 TEST | merge deploy/3fixes into main (reconcile) | reconcile |
| fa8f515 | 05-28 | 🔴 FE CI TEST | cleanup Phase A (shadow backups/.bak) | **yours** |
| a60b0eb,feb7d01 | 05-28 | — | docs/standards (CLAUDE.md, CONVENTIONS.md) | **yours** |
| ead57d1,ab20900 | 05-29 | FE CI | CI baseline gate + diff-lint gate | **yours** |
| bd75fb2,ba224ee | 05-29 | CI | pandas-ta→crossval; native TA-Lib in CI | **yours** |
| ca902dc | 05-29 | — | merge ci-talib-native | = release-cutover-1 |
| 9cc23a8,19e4689 | 05-30 | — | Dhan lowercase-key auth fix | **yours** = release-cutover-2 |
| 29bd19b,4da606a | 05-30 | — | DEPLOY.md runbook | **yours** |
| 7b26d2a,3f40721 | 05-31 | TEST | RC1 richer synthetic data | **yours** (Queue SS) |

**SACRED-area assessment:** every 🔴 commit is a **known, already-deployed**
deploy/3fixes hotfix or the additive (dormant) options scrip-master parser — all
covered by prior queues/memory. **No unexpected sacred-area change.** (Detail
refs: executor `564079f`, celery `b912a17`, webhook `8c6be3c`, resolver
`aebe07d` — all in `release-cutover-2`, live since 05-30.)

---

## Phase 5 — Open branches (50 total: 30 merged, 20 unmerged)

- **Active in the last 7 days (since 05-24):** only `main`,
  `feat/synthetic-data-richer` (now merged), and the translator A2–E2 branches
  (yours, merged into 99c5473). **No unrecognized active branch.**
- **The 20 "unmerged" branches are all ≤ 05-24** and fall into two buckets:
  - **Superseded `deploy/3fixes` source branches** (`fix/signal-idempotency-wire`,
    `fix/celery-worker-event-loop`, `fix/reconciliation-poll-and-writeback`,
    `fix/symbol-normalizer`, `fix/telegram-400`, etc.) — their *content* is in
    main via the squash-reconcile (`efd5ae9`), so they read "unmerged" by SHA but
    are functionally **dead/deployed**. Safe to prune.
  - **Old docs/audit branches** (queue-hh/ii/jj, marketing kits, retrospective,
    test-coverage) — **dormant**, never merged, low value. Prune candidates.
- **Assessment:** no "alive parallel work." The unmerged set is
  **merged-by-content** or **abandoned**. A branch-prune pass is overdue (you ran
  one at `337c973` previously; ~20 more are stale now).

---

## Phase 6 — Phase 5 Strategy Builder

- **Gate text:** `frontend/src/app/(dashboard)/strategies/[id]/page.tsx:283-286`
  ("Live trading aur backtest tab unlock honge jab Strategy Builder (Phase 5) ship
  hoga"), plus `TemplateCard.tsx:57` and `templates/page.tsx:198`.
- **What drives the gate:** **`strategy_json` presence** —
  `page.tsx:211` `const hasDsl = !!strategy.strategy_json`. With a DSL the backtest
  link + GoLive are enabled; without it (cloned, un-translated) the "Phase 5" lock
  shows. It is **not** a feature flag or env gate.
- **Build-out state: NEAR-COMPLETE (~90%+), already in prod (`release-cutover-2`).**
  Three skill-level builders (beginner 463 / intermediate 553 / expert 903 lines),
  entry/exit/risk template builders, onboarding modal, full DSL schema +
  `translate_template`, backtest engine consuming `strategy_json`. **The only GA
  blocker is live order execution (GoLive endpoint, Phase 6-7).**
- 🟢 **Hard-stop #4 cleared:** Phase 5 is **not in-flight WIP** — it's a merged,
  near-complete feature with **no active parallel author**. Translator/backtest
  work that touches `strategy_json` / templates is **safe to continue**.

---

## Coordination recommendations

**Overlap-risk map (future queues vs existing work):**
- *Backtest/synthetic* (just did RC1) — overlaps the Phase F `backtest_adapter`
  and the backtest engine. Low risk now (RC1 merged), but the **MACD-seeding
  deferral** means MACD-driven template signals may still differ from TradingView
  until the TV check is done.
- *Translator/templates* — your active area; Phase 5 builder consumes the same
  DSL. No competing author, but changes to `strategy_json` shape ripple to the
  frontend gate and the builder.
- *Sacred trading paths* — all recent changes are deployed & known; keep the
  CLAUDE.md freeze discipline.

**Process to avoid surprises:**
- Adopt the existing **release-tag cadence** (DEPLOY.md) as the single source of
  "what's live"; check `git merge-base --is-ancestor <commit> <release-tag>`
  before assuming something is deployed.
- A periodic `git branch -r --no-merged origin/main` sweep (this audit) catches
  drift; prune the 20 stale branches.

**Defer until coordinated / sequenced:**
- **Deploy RC1 first** (cut `release-cutover-3` from `3f40721`) — it closes the
  Queue RR 0-trades-in-prod gap before any new template/backtest queue.
- Resolve the **MACD TV-verification** (Phase F deferral) before shipping
  MACD-signal-heavy templates as "TradingView-accurate."

---

## Next-queue recommendation

**Deploy RC1 (`release-cutover-3` from `3f40721`).** It's your own validated work,
already on main, and it's the missing piece that makes the newly-unlocked
templates actually produce trades in production (Queue RR root cause #1). It's a
small, low-risk cutover following the proven DEPLOY.md runbook — the highest-value
next step before starting any new feature queue.
