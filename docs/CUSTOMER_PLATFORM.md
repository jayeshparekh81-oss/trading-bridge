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

## 7. Simple mode (2026-09-05) — NO LOCKS

- **What**: a NEW signup sees Simple mode: no sidebar; the four big tiles in order (Strategy chuno · Broker jodo · Aaj ke signals · Madad), a status strip, the always-on safety bar (Rok do · Sab band · Settings · Bahar), then **"Aur seekhein"** with OPEN tiles (Templates dekho · Apni strategy banao · Pro mode) under one soft hint ("Pehle upar wale 4 karo, phir yeh — aaram se."), the journey line ("Aapka safar: 1 / 4 kadam · Agla: …", guidance only), the day's lesson, and a quiet Pro-mode card. Nothing is locked; no route is blocked in either mode. Simplicity comes from ORDER and plain words (founder's call, 2026-09-05 evening — the earlier lock/gate design was removed the same day).
- **Who starts where**: accounts created before `LADDER_LAUNCH_AT` (2026-09-05) and admin/founder accounts default to Pro; new signups to Simple. Simple ⇄ Pro is the Settings → Mode card, the Pro tile, or the Pro card; choosing a mode LANDS on that mode's home. Switching into Pro shows the expanded-sidebar nudge once. Nothing switches to Pro on its own.
- **Where it lives**: `frontend/src/lib/simple/level.ts` (mode + journey rules, tiles, routes), `journey.ts` (journey line + "Aur seekhein" one-liners), `copy.ts` (hinglish/hi/gu/en, `JARGON_BLOCKLIST`), `lessons.ts`, `hooks/useLadder.tsx` (state persisted in `users.notification_prefs._ui_ladder` through the EXISTING `PUT /api/users/me`, read-merge-write; no migration), `components/simple/*` (home, shell with "‹ Wapas" on every non-home path, safety bar, mode card, 3-step onboarding, first-Pro nudge), `hooks/useSimpleStatus.ts` (facts from existing endpoints).
- **AlgoMitra one-liners**: a first-visit nudge on the home, and one line on the first tap of each "Aur seekhein" tile (remembered per account in `tipsShown`).
- **Words**: no jargon on Simple surfaces; `tests/simple/words-and-dev-notes.test.ts` lints every Simple string in all four languages (including "no lock words") and every customer page for roadmap/dev text. `tests/simple/simple-nav.test.tsx` proves every tile and every "Aur seekhein" tile is reachable on a FRESH account with zero actions, that "‹ Wapas" returns home in one tap, and that browser back never redirects.
- **Analytics (Pro)** reads `strategy_executions` + closed `strategy_positions` through `backend/app/services/owner_executions.py` — the same owner-scoped query as the /trades page and both CSV exports. Money comes only from PRICED attribution tags (`bot_only` / `account_flat`); human-interfered round trips are counted, never priced.

## 8. ONE SITE, NOT TWO (2026-09-06)

- **The rule.** Public = shop window only. App = the whole shop. One thing never lives in two places two different ways. Frontend-only; no flag, no backend change.
- **One strategy component.** `components/strategy/strategy-card.tsx` is THE card — backtest stats with their honest labels, risk band, min-capital note, the live-record state, one CTA — and `strategy-detail.tsx` wraps it with Subscribe, the transparency ledger and ratings for `/marketplace/[id]`. `hooks/useShowcase.ts` is the ONE data source (`/api/showcase`, `/{key}`, `/{key}/live`, joined to a marketplace listing by the live record's `listing_id`). Surfaces: public `/showcase` (Proof), in-app `/marketplace` (Simple: one full card at a time with Pichla/Agla and Subscribe on the card via `components/simple/strategy-pick.tsx`; Pro: the grid of compact cards), `/marketplace/[id]`. The bare `listing-card` and `listing-detail-header` are retired. A listing the showcase does not know renders the same card `unproven`: the non-claiming risk RANGE, no numbers, "no verified record yet" — never a fabricated zero. `tests/site/one-strategy-component.test.tsx` renders public and app from one fixture and compares the printed strings.
- **Subscribe lives in the app.** The public card is read-only with one CTA: logged out → "Start Free" (`/register?next=/marketplace/<listing_id>`), logged in → "App mein kholo" (the in-app detail). Masking is the API's (S1/S2/S3); the front end adds nothing.
- **Public nav = Home · Proof · Pricing.** About and Contact live in the footer; every old URL still resolves. Logged in, every public header swaps Login / Start Free for one "App kholo →" (to `/`). `tests/site/public-nav.test.tsx`.
- **One face.** `components/site/header-shell.tsx` is the header both the public layout and the app's `TopBar` render (same height, background, border, blur, logo sizes, padding; public keeps `fixed`, the app `sticky`). The site footer's legal link goes to the public `/disclaimer` for a visitor and `/compliance/legal` for a user.
- **Public copy = app truth.** Every public claim was audited against the real routes (56 claims; the table is in the ONE SITE report). Fixed: "one-click deploy" → build + backtest + paper-test; "slippage and latency" dropped; "Start in 3 simple steps" = Simple mode's Bhasha chuno → Broker jodo → Strategy chuno; "6 broker integrations" → 2 live (Dhan, Fyers), the rest coming soon; "you approve it / before it acts" → signals shown, subscriptions confirm in manual mode; "AES-256 / HMAC-signed" → encrypted at rest, optional HMAC; "Never lose more than you set" → caps the damage; "verified Track Record" → Proof; Telegram alerts row → email first; plan changes → next cycle; stale dates removed; site metadata no longer says "AI-Powered". `tests/site/public-copy.test.ts` pins them.
