# EXPIRY_ROLLOVER_SPEC.md — N=5 entry-roll + T-2 backstop (APPROVED, pre-code)

Approved by founder 2026-08-06 with two sequencing changes and two spec amendments
(boundary decision, cross-boundary exits). Code begins only after the market-hours depth
check reports. Deploy deadline: **working by 20 Aug 2026** (AUG dies Tue 25 Aug 14:30 IST).

## THE GOVERNING SENTENCE
**The N=5 rule governs ENTRY SELECTION ONLY. Exits and partials always follow the position
they belong to — the stored `open_position.symbol` — on both sides of every switch, forever.**
(Mechanism verified in the running image: `strategy_webhook.py:406-424` pins EXIT-class AND
PARTIAL; never re-resolved.)

## THE RULE
- Vehicle for NEW entries = earliest contract with `(SEM_EXPIRY_DATE − today).days > 5`.
- **Boundary is EXCLUSIVE, in CALENDAR days, by date subtraction** — never sessions:
  for AUG-2026 (expires Tue 25 Aug): last AUG entry day **19 Aug (T-6)**; **SEP from 20 Aug (T-5)**.
- Expiries from the scrip master's real `SEM_EXPIRY_DATE` on every run — never a date list,
  never a manual edit (founder requirement: set once, correct forever).
- Resolver-level: every root (BSE/CDSL/ANGELONE + TV aliases) and the expired-explicit-symbol
  re-roll path inherit. **TradingView inherits too if its alerts are ever re-enabled — stated
  deliberately, not a surprise.**
- The existing same-day/14:30 rule ("never serve a contract past its own settlement") remains
  as a SEPARATE, separately-asserted guard — it protects against N-misconfiguration.
- **CONSEQUENCE, recorded 2026-08-11 (implemented @ b5be417, founder-accepted):** a new entry ON
  EXPIRY DAY now resolves to the next month at every hour of that day — pre-14:30 included. This
  also sidesteps Dhan's expiry-day carry-forward ban entirely ("only intraday trading will be
  allowed. No fresh carry-forward position"): we never attempt to open the front month that day,
  so the broker rejection path for it is unreachable. The code change and the broker policy
  agree. (Historical context: ~27-29 expiry-day entries existed in the 6.5y record; under both
  the N-rule and Dhan's ban they open in the next month instead of not opening at all.)
- Structural hold (options path): implement as contract-UNIVERSE (`_contracts_for_root`) vs
  SELECTION-POLICY (a function over the universe); the N-rule is the first policy. An options
  vehicle policy (expiry-series, right, strike-policy) plugs the same seam later. Not built now.

## MEASUREMENTS THE RULE RESTS ON (2026-08-06, full 6.5y / 715 trades)
- Straddles (open across expiry): 41 (6.2/yr). Entry→expiry gaps: {T-0:25, T-1:12, T-2:3, T-3:1}
  → the rule retro-covers ALL 41 at any N≥3; **backstop fired 0 times historically**.
- Redirected entries at N=5: 132 (20.3/yr); N=3: 115. Marginal cost of N=5 over N=3 ≈ nil.
- Holding rulers reconciled (same trades): bar-count/25 max 4.3 ≡ 5 trading dates ≡ 7 CALENDAR
  days. Founder's "never beyond 4 days" = bar ruler, correct; rule uses calendar because expiry
  is a calendar date.
- Volume: next-month ≈ 4–9% of front MID-CYCLE, but **surges to front-like size in expiry week**
  (AUG-as-next did 3.27M/day in JUL's expiry week vs 2.52M as front) — redirected entries land
  exactly in that surge. 400 contracts ≈ 0.01% of it.
- Basis vs cash (measured across the JUL-28 regime change): front +22 bps; next +55–71 bps;
  ~50 bps/month carry curve. Cost to us = decay over the hold: ~₹300 median / ~₹1,100 p90 per
  redirected trade at ₹14L notional, direction-symmetric, ≈ net-zero across the book.
- OUTSTANDING before code: **market-hours DEPTH CHECK of next-month bid-ask at ~400-contract
  size** (founder sequencing change #1). Note: account's Data-API subscription status may force
  the fallback (founder reads SEP depth in the Dhan app; agent records).

## WHAT THE RULE IS WORTH IN RUPEES (verified 2026-08-10 — the value is not only risk-avoided)
Letting a stock future reach physical settlement is ~2 ORDERS OF MAGNITUDE more expensive than
squaring off, and the futures charge set is REPLACED, not extended:
  * Dhan settlement brokerage: **0.10% of contract value** — verbatim, dhan.co/pricing note 5:
    "A brokerage fee of 0.10% of the contract value is applicable on all derivative contracts
    (futures and options) that result in physical delivery, along with the relevant Exchange
    charges." On Rs 14,00,000 = **Rs 1,400**. (Peer benchmark: Zerodha charges 0.25% headline /
    0.10% netted-off — Dhan's flat 0.10% is at the LOW end, not a universal number.)
  * **Delivery-equity STT REPLACES futures STT and is payable by BOTH sides** — NSE Clearing,
    verbatim: "STT at the rates as applicable to the delivery-based equity transaction shall
    also be applicable on the physically settled stock derivatives (both Futures and Options).
    The said STT will be payable by both the Purchaser (receiver) as well as by the Seller
    (giver)." At 0.1% on Rs 14,00,000 = **Rs 1,400** on our side alone.
  * plus exchange charges, 18% GST on the brokerage component, stamp duty on the buy leg, and DP
    charges when the received shares are later sold.
  * **TOTAL >= ~Rs 3,100 versus ~Rs 863 to square off** — and you then OWN 400 shares worth
    Rs 14,00,000 that must be funded and later sold, paying delivery STT and brokerage AGAIN.

DELIVERY-MARGIN RAMP (Dhan, published) — this INDEPENDENTLY VALIDATES N=5:
    E-4: 10%   E-3: 25%   E-2: 45%   E-1: 70%   expiry day: 100% of contract value.
N=5 CALENDAR days keeps new entries clear of the whole ramp (E-4 is four SESSIONS out, always
inside 5 calendar days). The rule was chosen on straddle coverage; the ramp confirms it from an
entirely separate direction. Note also Dhan's expiry-day rule: "only intraday trading will be
allowed. No fresh carry-forward position" — a carry-forward order on expiry day is REJECTED, so
the ~27-29 historical expiry-day entries would not even have opened.

## THE BACKSTOP (same design, not separate)

### DAY-COUNT CONVENTIONS — two of them, on purpose (founder decision, 13 Aug 2026)
| rule | counts | why THAT unit is the conservative one here |
|---|---|---|
| entry roll, N=5 | **CALENDAR days** | a MARGIN rule. The delivery-margin ramp (E-4 10% → expiry 100%) and the expiry-day carry-forward ban run on the calendar. 5 calendar days clears the ramp however many are sessions. Counting sessions would make it LOOSER over a holiday week — an entry deeper into the ramp. Wrong direction. |
| exit backstop, T-2 | **TRADING SESSIONS** | an OPPORTUNITY-TO-EXIT rule. A holiday is not a day you can close on. Counting calendar days would OVERSTATE the remaining chances to get out, and an unclosed futures position faces physical delivery. |

Margin accrues on the calendar; exits only happen on sessions. Read as a pair these are
consistent, not contradictory — each rule uses the unit that errs toward safety for the
question it answers. Recorded here and in both module docstrings so a later reader cannot
mistake it for drift. **Session calendar source:** derived, never invented — weekends via
`strategy_engine/trading_calendar.py`, holidays inferred from the scrip master's real
`SEM_EXPIRY_DATE` where the exchange shifted an expiry earlier than the nominal last
Thursday. No hardcoded dates. Residual (a holiday that shifts no expiry) is handled by
direction: the backstop fires EARLIER when uncertain, never later.

Position still open in a contract with **≤2 sessions to its own expiry** → carry-policy-style
first-class action: recorded forced-exit (`decided_by="expiry-backstop-T2"`, policy named in
the record), EXIT payload posted, the engine's eventual real exit **auto-marked handled-by-policy
in the sender at creation time** (model-desync recorded, never inferred from a rejection),
operator ping via the notifier seam. Expected firings ≈ 0/yr (unobserved tail only: entry ≤T-6
holding ≥6 calendar days).

## TEST MATRIX (assert, not assume)
Entry-boundary (resolver, per root, SEM_EXPIRY_DATE fixtures incl. holiday-shifted):
1. T-6 → FRONT (last front-entry day)
2. T-5 → NEXT (both sides of the exclusive boundary)
3. T-4 → NEXT
4. Expiry-day → NEXT **plus** the separate never-serve-dying assertion (14:30 guard) — its own test
5. Multi-root inheritance (CDSL/ANGELONE) + expired-explicit-symbol re-roll path

Cross-boundary exits (the catastrophic-if-wrong class — assert the ACTUAL SYMBOL on the
placed order equals the ENTRY's contract, not merely that an order was placed):
6. LONG entry pre-switch (AUG) → PARTIAL post-switch → order symbol = AUG
7. LONG entry pre-switch → EXIT post-switch → AUG
8. LONG entry pre-switch → SL_HIT post-switch → AUG (most common exit reason)
9. SHORT entry pre-switch → PARTIAL post-switch → AUG
10. SHORT entry pre-switch → EXIT post-switch → AUG
11. SHORT entry pre-switch → SL_HIT post-switch → AUG
12. Exit-pinning regression: `strategy_webhook.py:406-424` stored-symbol behavior asserted directly

Backstop fixture (the only test this code gets before it matters — carries full weight):
13. Synthetic straddle → asserts ALL of: recorded forced-exit + sender auto-marking (replay the
    engine's later real exit; prove it never POSTs and the marking is recorded) + notifier ping
    via the session seam. Falsification twin: policy removed → test fails.

## BUILD ORDER & DEADLINE (founder sequencing change #2)
Depth check (market hours, BEFORE code) → resolver policy + universe/policy split → tests →
backstop (bridge-side) → founder-gated platform deploy (no migrations) by **12–14 Aug** →
container rebuild → **H6 re-verification of both running-image receipts** + SIGNAL_CONTRACT §8
and STRATEGY_LIFECYCLE updates → expiry-week replay acceptance ~18 Aug. Hard wire: 20 Aug.
Bridge is ARMED LIVE as of 06 Aug — a deploy slip past 20 Aug means 20–25 Aug entries open the
dying AUG under the old resolver.

## OPTIONS — WHAT TRANSFERS (design-for, not built)
Entries-only vehicle selection transfers cleanly (no mid-position migration ever needed).
N does NOT transfer (weekly expiries need an options-native N from options holding stats).
Strike continuity is an entry-time strike POLICY, an orthogonal axis. Basis/spread math does
not carry (theta/vega dominate). Resolver seam required: universe vs selection-policy split
(ships now, above).

## AMENDMENT — empty-universe behaviour (decided 9 Aug 2026)
If no contract in the universe satisfies N, the policy returns None and the resolver passes
the symbol through — Dhan rejects loudly. Falling back to the dying front month is explicitly
forbidden; that is the failure the rule exists to prevent. Decided 9 Aug, encoded in
test_policy_returns_none_when_no_contract_satisfies_n.
