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
- KEY GAP: subscribing creates nothing runnable — no FK from `marketplace_subscriptions` →
  `strategies`, no clone/provision on subscribe. "One strategy → many customers" is modeled for
  VIEWING, not EXECUTION.
- Billing: subscription table exists but payment is a STUB; no Razorpay; no plan/tier on users.

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
