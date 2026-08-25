# RESTING_STOP_ITEM7_SCOPE.md — Item 7: real resting stops at Dhan (SCOPING RECORD, pre-build)

Status: **SCOPED, NOT BUILT — now BUILDABLE.** Dhan answered 2026-08-12 (§DHAN'S ANSWERS).
Capability confirmed; ONE blocking unknown remains (held-by-Dhan vs resting-at-exchange).
Still sequenced behind the 12-Aug incident's open items, the resolver, and E5.

## 🔴 THE ARGUMENT THAT NOW LEADS: SINGLE-POINT-OF-FAILURE REMOVAL (evidence, 2026-08-12)

Re-weighted on founder's order 2026-08-12. Item 7 was scoped on slippage (₹42.2k/yr). That
is no longer the lead argument, because on 12 Aug we watched the failure it prevents:

  * An expired TLS certificate (Let's Encrypt, notAfter 11 Aug 13:58 GMT) made **every POST
    fail with SSLError for ~4 hours of market time**, 11:46-15:31 IST.
  * The **SL_HIT exit for a real, live 200-contract position never left the box.** It sat in
    the pending queue while the position stayed open at the broker.
  * Price fell **-2.86%** that day. The model's stop had triggered; the broker never heard.
  * **The fallback was a human.** There was no other.

A broker-held resting order fires **regardless of our certificate, our box, our cron, our
code, or our network**. That is not slippage recovery — it is the removal of a single point
of failure that we have now SEEN fail, in production, on a live position. It is a different
CLASS of argument from ₹42.2k/yr and it leads.

The slippage number remains true and secondary: ₹42.2k/yr, 88% of it short-side squeezes
(see TICK_WATCHER_SPEC.md for the split — the tick-watcher owns the intraday squeeze pool,
item 7 owns overnight gaps PLUS this existence property).

## THE REAL TRADE-OFF (founder-required framing — decide with eyes open)

Today's virtual stop can be **LATE** (~₹42.2k/yr in slippage, measured: 481 events) and it is
**ABSENT entirely if the bridge cannot post** — no longer hypothetical, see above. But it can
**NEVER send a wrong order** — every order the bridge emits is computed fresh from the engine
against the current position.

Item 7 closes the naked-position hole and recovers the slippage — **at the price of
introducing a wrong-order path that does not exist today**:

- A stale 400-qty resting SELL stop standing after a partial halved the position to 200
  **OPENS A 200-CONTRACT SHORT on trigger**. That is the same class of failure
  (unintended live order) that took weeks to close out of the webhook/dedup/ledger path.
- **THE ORPHAN HAZARD IN REVERSE — ANSWERED, AND IT IS THE BAD ANSWER (Dhan, 2026-08-12):**
  the bridge exits normally, the resting stop is LEFT STANDING, price later touches it —
  and it opens a fresh position in the opposite direction **from flat**. Dhan **does NOT
  auto-cancel**. Verbatim: *"if you close your F&O position separately while the Stop Loss
  and Target Forever Orders are still active, you need to manually cancel those orders. If
  they are not cancelled, the order may get executed when the Stop Loss or Target price is
  reached."*
  **CANCEL-ON-EXIT IS THE HOT PATH, NOT THE EDGE CASE** (founder, 2026-08-12) — measured:
      resting stop covers ......... STOP_LOSS          481 events
      closed by OTHER routes ...... VWAP/EMA/RR_TP/SIGNAL  234 events  -> each needs a CANCEL
      reduced by ................... PARTIAL            406 events  -> each needs a qty MODIFY 400->200
  So the majority of position-state changes do NOT come through the resting order at all;
  they arrive by a route that must then reach across and cancel or resize it. Design to
  that shape: **every exit route cancels, every partial modifies, and a FAILED CANCEL
  ALARMS LOUDLY — because its consequence is an UNWANTED POSITION, not a missed one.**
  Failure direction is asymmetric and the design must respect it: a failed PLACE leaves us
  where we are today (no resting stop, bridge-only); a failed CANCEL leaves a live order
  that can open a position from flat.
- A stale level after a LOOSENING move (21% of in-position bars loosen — measured) sits
  tighter than the model and **fires a premature exit the model would not have taken**.

So the honest ledger is: **"₹41k/yr + one hole closed, MINUS a new wrong-order path"** —
not "₹41k plus safety." The build is justified only if the modify machinery is loud,
reconciled, and fails toward CANCEL (no resting order = today's status quo) rather than
toward stale-order-standing.

## DHAN'S ANSWERS (received 2026-08-12) — capability CONFIRMED

  1. Sell-side Forever Order on FUTURES: **YES.**
  2. Forever **OCO** (stop + target, either triggering AUTO-CANCELS THE OTHER): **YES.**
     Note the asymmetry this reveals: Dhan cancels the SIBLING leg automatically, but does
     NOT cancel either leg when the POSITION is closed elsewhere. Sibling-cancel is not
     position-awareness.
  3. Validity: **365 DAYS, all segments**; removed from the tab at contract expiry.
  4. Place AND MODIFY via API: **YES.**
  5. Auto-cancel when the position is closed separately: **NO** — see the orphan hazard above.

### 🔴 CORRECTION TO THIS DOCUMENT'S EARLIER SCOPING (365-day validity)
My Q3 scoping assumed **DAY validity** (from the adapter's hardcoded `validity="DAY"`) and
concluded that every held-overnight position needed a fresh placement each morning, creating
a **daily 09:15-09:31 naked window** that pushed the design platform-side. **That window does
not exist.** With 365-day validity the order is placed once at entry and lives until it
triggers, is cancelled, or the contract expires. Consequences:
  * No daily re-placement, no morning scheduler, no 09:15-09:31 hole.
  * The overnight-gap protection is continuous, not re-armed daily.
  * The Q3 architecture fork (platform-owned placement so a 09:15 scheduler could re-place)
    loses THAT justification. Platform-side may still be right for the CUSTOMER feature, but
    it is no longer forced for the founder's own account — a bridge-side placer is viable.
  * The N=5 expiry roll interacts cleanly: orders are removed at contract expiry, and entries
    roll to the next month anyway, so no cross-expiry order can strand.

### 🔴 BLOCKING UNKNOWN — HELD BY DHAN, OR RESTING AT THE EXCHANGE?
NOT answerable from Dhan's public material: the DhanHQ v2 Forever docs describe request/
response shapes and statuses (PENDING/TRANSIT) but say nothing about where a pending order
lives; the Forever support page states only the 365-day validity. A "placed and maintained in
Dhan, sent to the exchange when the price is reached" phrasing appears in THIRD-PARTY
explainers and in a search-engine synthesis — **not verified from Dhan**, so it is a hint, not
an answer, and must not be built on. Ask Dhan directly (draft below). It decides three things:
  (a) **TRIGGER LATENCY — item 7's speed claim, currently UNMEASURED.** If Dhan holds it, the
      trigger is Dhan's monitoring cadence plus order transmission; if it rests at the
      exchange, it is exchange matching. These differ by orders of magnitude and we have
      claimed nothing yet. No latency number goes in any customer-facing or planning material
      until this is answered and measured.
  (b) **CAS INTERACTION.** SEBI's Closing Auction Session cancels pending STOP-LOSS orders at
      15:15 and disallows them inside the auction. If the Forever Order rests AT THE EXCHANGE
      as a stop, that cancellation may take it — silently removing our protection daily. If
      Dhan holds it, CAS likely does not touch it, but Dhan's own behaviour during 15:15-15:40
      then becomes the question. Either way this must be pinned BEFORE relying on it, and it
      is a NEW question created by CAS going live on 3 Aug.
  (c) **WHAT WE ARE ACTUALLY DEPENDING ON.** If Dhan holds it, we swap OUR uptime for DHAN'S
      GTT monitoring uptime. That is still a large win — their monitoring did not go down when
      our certificate expired — but it is a DEPENDENCY SWAP, not elimination, and it must be
      named as such rather than sold as "fires no matter what."

## THE FIVE SCOPING ANSWERS (measured 2026-08-11, read-only)

1. **Modify volume trivial; modify FAILURE is the design problem.** Stop level moves on
   79% of in-position bars → ~31 modifies/position-run, ~8.8/trading day (18,062
   in-position bars, 457 position-runs, instrumented replay). Dhan bills per *executed*
   order — modifies are free; rate limits are orders of magnitude away. A failed modify
   leaves the OLD order standing at the OLD level (= the Q2 stale state). A modify can
   race the trigger: the reject must be read as "possibly already executing," never
   blind-retried.
2. **Stale stop, measured, two-sided.** Direction: 59% tighten / 21% LOOSEN / 21% flat.
   One missed cycle: level off by median 4.4 bps, p90 27. Three missed: median 15,
   p90 143. (p99 readings contaminated by run-boundary artifacts — do not quote.)
   Verdict: against bridge-death, stale ≫ nothing; against ordinary missed-modify noise,
   a small two-directional cost. Better than today IFF modify failures are loud and rare.
3. **Bridge dies → the stop fires. That is the point, and it holds — within DAY
   validity.** The resting order lives at the broker/exchange, independent of our
   processes. Boundary: adapter validity is hardcoded DAY; median hold is 1 calendar day
   so most positions cross a session boundary → fresh placement every morning. Under the
   bridge's own rhythm (first cycle 09:31) that placement leaves a daily 09:15–09:31
   naked window → **architecture fork resolved toward PLATFORM-OWNED placement**
   (platform places on entry fill, re-places at 09:15 open by its own scheduler,
   level-updates from bridge signals). Accepted by founder. This makes item 7 a platform
   feature with a bridge signal extension.
4. **Dhan capabilities:** SL/SL-M on NRML stock futures confirmed in the adapter
   (`OrderType.SL → "STOP_LOSS"`, `SL_M → "STOP_LOSS_MARKET"`, `modify_order` = PUT with
   qty+trigger, validity DAY). Forever/GTT (365-day validity, API-managed) exists but
   **F&O sell-side support is UNVERIFIED** — one source says buy-side-only via OCO.
   Support ticket gates the overnight design: GTT-native vs synthetic (fresh DAY order
   each morning).
5. **Partial interaction is the sharpest edge.** Partial-fill → stop-qty-modify must be
   effectively atomic. Named failure windows: (a) partial filled, qty-modify failed →
   oversized stop standing (the short-opening hazard: loud alarm + prefer CANCEL over
   stale); (b) stop fires while the partial's modify is in flight → double-execution
   race the reconciliation must own.

## RELATED, POSSIBLY ITS OWN CHEAPER ITEM — the 09:15–09:31 gap TODAY

The first-cycle-at-09:31 window is NOT introduced by item 7 — it exists today: a stop
breach on the 09:15 bar is undetected until 09:31. Quantified over 6.5y (2026-08-11,
same replay + live-proxy convention as E5; baseline reproduced E5 exactly):

- 791 overnight boundaries with an open position (121/yr); **11.9% breached the stop on
  the first bar** → 94 events (14.4/yr), total cost **₹10.8k/yr**.
- The money is ALL in the **true gaps at open**: 23 events (3.5/yr), mean ₹2,759/event,
  ₹9.7k/yr, single worst event +546 bps = ₹76.5k (2025-05-07 short). Intrabar touches on
  the first bar are free (₹1.1k/yr, median +0.7 bps).
- Two-sided and tail-driven: live is BETTER than model on 53% of first-bar events
  (median −5.5 bps — gaps often retrace by 09:30); yearly sign flips (2020 −₹68k,
  2025 +₹101k).
- **THE CASE IS THE TAIL, NOT THE MEAN (founder framing, 2026-08-11).** The mean
  (₹10.8k/yr) argues against bothering. The tail argues for it: the single worst event
  cost **₹76,500 against a ₹1.47L max drawdown — one gap took half the drawdown, and
  more than seven years of the mean.** Item 7's morning placement is the ONLY thing that
  covers that event class, and that — not the average — is its real justification.
- Structural point: no bar-based system can beat this — the 09:15 bar doesn't exist
  until 09:30, and the 09:31 cycle is already near-optimal for bar-based detection.
  **Only an order resting at the exchange before open captures the gap subset.** So the
  finding argues FOR item 7's platform-owned 09:15 placement (which covers it for free)
  rather than for an earlier cron cycle. A static overnight-only variant (place stop at
  last-known level + yesterday's qty at 09:15, hand off to the bridge at 09:31) would be
  a cheaper subset — but it shares the wrong-order class (qty correctness,
  stop-fires-vs-bridge-exits race) and buys only the ₹9.7k/yr gap slice.

## WHAT ITEM 7 IS NOT

- Not a bridge-side quick patch (the fork resolved platform-side).
- Not "free safety" (see trade-off above).
- Not started before: resolver deployed + expiry-week acceptance done + E5 flipped
  (Wed 26 Aug) — and not before Dhan answers the GTT question.
