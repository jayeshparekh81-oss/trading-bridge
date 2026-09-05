# TRADETRI — Customer Platform: North-Star Spec

**What this is:** the reference for what the customer-facing platform should be, and the order we
build it. Read this before any customer-platform task. **REFERENCE, not a build-all-at-once
instruction** — build follows the risk-sequenced plan in §5, module-by-module, founder-gated. All
CLAUDE.md safety rules apply in full.

## 1. Product vision (what the customer gets)
A premium, transparent, "Glass Box" algo-trading platform. Customers can:
- See REAL performance — backtest, live, and their own execution, clearly separated + labeled.
- See real risk + drawdown before subscribing.
- Verify via the Transparency Ledger ("Backtest nahi, Proof").
- Control quantity (even, 2–20), choose segment + broker, start/stop, manual-exit anytime.
- Trade by system + discipline, not signals + emotion.
NOT a signal-selling site, fake-screenshot platform, or guaranteed-profit product.

## 2. Positioning + safe language (always)
Use: historical performance, rule-based strategy, live execution record, risk/drawdown visible,
user-controlled, "past performance does not guarantee future results."
Never: guaranteed profit, fixed/assured return, sure shot, risk-free, daily income, 100% success.
Disclaimer (where relevant): "TRADETRI provides strategy automation tools, dashboards, and
execution controls. We do not provide guaranteed returns. Trading involves risk. Past performance
does not guarantee future results. Users are responsible for their own trading decisions."

## 3. Premium UX bar
Clean, fast, trustworthy. Green = profit only, red = loss/risk only, neutral for info. Risk
visible, not hidden. Real empty/loading/error states — never fake numbers. Mobile clean. Locked
sections look premium, not broken. "Unpad aadmi bhi use kar sake."

## 4. Architecture reality (from audit — don't rebuild what exists)
- `strategies` = per-user execution rows (own broker cred + webhook token); registry-driven, no
  hardcoded strategy branches.
- Two template concepts: `strategy_templates` (catalog → clone makes a per-user `strategies` row) +
  `marketplace_listings`/`marketplace_subscriptions` (creator publishes a strategy; customers
  subscribe to VIEW).
- Multi-user execution architecture EXISTS: Celery+Redis queue; `user_id` is the pivot; executor
  loads strategy via `webhook_token → strategy_id` → that user's broker cred. (Only founder today.)
- Brokers: Dhan = prod; Fyers = code-ready (verify broker-side algo-order permission);
  Angel/Zerodha/Upstox/Shoonya = stubs.
- Showcase (dashboards/marketplace/ledger/backtest) = REAL data, honestly labeled.
- FAN-OUT (updated): "one strategy → many customers" EXECUTION now exists as a wired but **DORMANT**
  spine — `strategy_webhook.py` fans a signal out to subscribers (per-subscriber size/mode/paper/
  direction columns on `marketplace_subscriptions`, migration 035/040), **paper-only** and gated behind
  `MARKETPLACE_FANOUT_ENABLED` (default False). It creates isolated per-subscriber paper positions; a
  real clone/provision-on-subscribe path is still not built. (Original note said "subscribing creates
  nothing runnable" — that is now stale.)
- Billing (updated): Razorpay is **BUILT** (subscribe/cancel/change-plan/HMAC webhook, migrations
  034-037) with plan/tier on users (`active_plan_id`/`plan_status`, migration 032) and DB-seeded
  Starter/Pro/Premium plans (migration 031) served via `GET /api/pricing/plans`. All **DORMANT** in prod:
  `PAYWALL_ENFORCED=False` + Razorpay keys empty → today every user sees all features. (Original note
  said "payment is a STUB; no Razorpay; no plan/tier" — now stale.)

## 5. Build sequence (risk-ordered — SAFE first, DANGEROUS last)
1. Data honesty + world-class showcase — SAFE. (Mostly done.)
2. Billing + access control — SAFE. Razorpay + checkout + plan/tier + real pricing + lock premium
   by subscription. LAUNCH GATE.
3. Customer config + lifecycle — MODERATE. Segment/broker/even-quantity (2–20, backend-validated),
   start/stop, manual exit, broker status.
4. Multi-user fan-out execution — DANGEROUS, LAST. Subscription→execution (e.g. clone-on-subscribe
   + signal fan-out to all subscribers). Never run multi-user in prod → paper-test → staged →
   gated; real customer money only after thorough paper validation.
5. Admin add/clone + scale (3 → 25–50) — LATER. Not needed to launch with 3.

Launch-model decision (OPEN): (a) launch view/access + billing first, auto-execution later
[safer/faster]; vs (b) auto-execution before launch [full vision, slower/riskier].

## 6. Customer-platform safety (in addition to all CLAUDE.md rules)
- Every deploy gates through the founder; build on branches; review before deploy.
- Multi-user execution = the highest-risk component — build last, paper-test before any real
  customer money.
- BSE LTD strategy is live real money — customer-platform work must never touch the live execution
  path without explicit gating + is_paper verification.

## 7. Simple mode + the level ladder (2026-09-05)

- **What**: a NEW signup sees Level 1 ("NAYA"): no sidebar, four tiles (Strategy chuno · Broker jodo · Aaj ke signals · Madad), a status strip, the day's lesson ("Aaj ka sabak", from `src/data/glossary.json`) and an always-on safety bar (Rok do · Sab band · Settings · Bahar). Levels unlock by doing: L2 SEEKH RAHA (broker + first subscription + first signal seen → Templates), L3 BANANE WALA (template cloned + backtest run → Apni strategy banao, Learn Indicators), L4 PRO (strategy built, or the Settings toggle → full UI). Every unlock is announced on the home card + one AlgoMitra nudge.
- **Who starts where**: accounts created before `LADDER_LAUNCH_AT` (2026-09-05) and admin/founder accounts are Pro; new signups are Level 1. Simple ⇄ Pro is a toggle in Settings → "Mode" (`#mode`). Simple caps at Level 3 and keeps the earned level.
- **Where it lives**: `frontend/src/lib/simple/level.ts` (rules, route table, tile routes), `copy.ts` (hinglish/hi/gu/en, `JARGON_BLOCKLIST`), `hooks/useLadder.tsx` (state, persisted in `users.notification_prefs._ui_ladder` through the EXISTING `PUT /api/users/me`, read-merge-write; no migration, no backend change), `components/simple/*` (home, shell, safety bar, gate, onboarding, Pro nudge), `hooks/useSimpleStatus.ts` (facts from existing endpoints).
- **Gate**: `(dashboard)/layout.tsx` renders `GatePage` IN PLACE (never a redirect) when `canOpen(level, path)` is false. Analytics, Chart, Webhooks, Compliance, Indicator Library, Pine import are Level 4. To add a route, extend the table in `level.ts`; the tests in `frontend/tests/simple/` pin both directions.
- **Facts**: action sites report unlock facts with `window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { … } }))` (subscribe button, broker connect, template clone, beginner builder, signals page). Facts are monotonic; the ladder never goes down.
- **Words**: no jargon on Levels 1–3 (no deploy / lots / NRML / webhook / paper / kill switch…). "Paper mode" is "seekhne wala mode"; Stop is "Rok do"; the kill switch is "Sab band". `tests/simple/words-and-dev-notes.test.ts` lints every Simple string in all four languages and every customer page for roadmap/dev text.
- **Analytics (Pro)** reads `strategy_executions` + closed `strategy_positions` through `backend/app/services/owner_executions.py` — the same owner-scoped query as the /trades page and both CSV exports. Money comes only from PRICED attribution tags (`bot_only` / `account_flat`); human-interfered round trips are counted, never priced.
