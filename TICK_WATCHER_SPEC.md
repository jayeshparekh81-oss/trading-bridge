# TICK_WATCHER_SPEC.md — bridge-side exit tick-watcher (APPROVED 2026-08-11, pre-code)

Status: design approved by founder; build slotted this week AFTER the resolver slice
(Thu tests 6-12 + backstop, Fri 14 gated deploy). Two founder conditions attached, one
already satisfied. Platform-side sibling deliberately out of scope here (designed jointly
with item 7 once Dhan answers the Forever/GTT email).

## WHAT IT IS
A bridge-owned watcher process on the prod EC2 that, during market hours, watches BSE
CASH ticks (sid 19585 — the series the engine computes on; stop levels are cash-price
levels) against the LAST COMPLETED CYCLE's composite stop level, and on a confirmed
breach POSTs the IDENTICAL SL_HIT payload the bar path would post 0-15 minutes later.

Two non-negotiable properties (founder):
  a. ADDITIVE, NOT A REPLACEMENT — the bar path is untouched and runs every cycle.
     Watcher dead / feed lost / late = today, exactly. It can only ever be EARLIER.
  b. SAME signal_id — `pyengine-{bar_time}-SL_HIT-{side}` (bridge.py:217), bar_time =
     the forming bar's timestamp, deterministic at its open. Ledger + server dedup make
     double-fire IMPOSSIBLE BY CONSTRUCTION, not by a branch. (E4's mechanics, aimed at
     exits.)

## DIVISION OF LABOUR vs ITEM 7 (founder-accepted split, measured 2026-08-11)
Side split of the 481 stop-lag events (live next-open vs stop level, 6.5y):
  LONG : n=327, mean −0.8 bps, total +₹33k (₹5.1k/yr) — 97% of it from 09:15-bar events
         (overnight gaps); the intraday long component nets FAVOURABLE.
  SHORT: n=154, mean +11.1 bps, p95 +218.8, p99 +472.7, total +₹243k (₹37.1k/yr) —
         only 16% on 09:15 bars, 30% gap-at-open: the bulk is INTRADAY SQUEEZE
         CONTINUATION. 5 of the 6 ≥₹40k events are shorts.
→ THE WATCHER OWNS the ₹37.1k/yr short-squeeze intraday pool.
→ ITEM 7 OWNS the long side's overnight-gap remainder (₹5.1k/yr) PLUS the
  survives-our-process-dying property. Not redundant, not equal.

## WHAT THE WATCHER CANNOT DO — STATED UP FRONT SO IT IS NEVER OVERSOLD
- It CANNOT watch overnight. On the long side's overnight-gap class the best it can do
  is fire on the FIRST TICK AT OPEN (which still beats today's 09:31 exit); the
  long-side ₹5.1k/yr pool therefore STAYS WITH ITEM 7.
- If the whole box dies, there is no stop — watcher and bar path die together. Only
  item 7's broker-resident order covers that.
- It cannot beat a gap through the open, act through an exchange halt, or survive a
  feed-wide outage (degrades to today, loudly).
- Scope is STOPS ONLY. Partials and close-basis exits stay on their measured, accepted
  paths (E5 = close-basis only; partial stays late by measurement).

## ARCHITECTURE (approved)
- TWO-LAYER FACTORING: `tick_watch/` core (Dhan WS feed client + breach-detector state
  machine + guards; pure Python, zero bridge imports) + thin bridge adapter (level-file
  reader, payload builder via build_payload, notifier seam). The platform sibling later
  vendors the same core and writes its own adapters. Adapters (~half the build) are
  duplicated by design; core + invariants + tests + evidence carry.
- FEED: own single-instrument Dhan WS subscription, full mode. Recorder reuse REJECTED
  (30s parquet flush = too slow; touching a deployed platform service). Dhan cap 5
  connections; recorder 3 + depth 1 = 4, so exactly 1 free (pin depth to 1 — Day 1).

- 🔴 WHICH INSTRUMENT: **BSE CASH, security_id 19585, NSE_EQ** — NOT the futures contract
  that is actually held. VERIFIED IN CODE, not assumed: `executor/live_loop.py:58`
  `CASH_SECURITY_ID = "19585"  # NSE:BSE cash (S0-confirmed; distinct from futures 62395)`
  fetched at :148 with `exchange_segment="NSE_EQ", instrument="EQUITY"`, stored to
  `shadow/store/bse_cash_15m.parquet`. The engine computes every indicator, and therefore
  the composite stop level, from CASH bars. The level is a CASH-PRICE level.
  WHY THIS MATTERS (the trap): the instinct is to subscribe to the contract being closed —
  the dated future. That would compare a FUTURES price against a CASH-derived level, and
  the basis silently displaces the effective stop:
    * measured basis (EXPIRY_ROLLOVER_SPEC): front month ~+22 bps, next month ~+55-71 bps,
      ~50 bps/month carry curve, decaying to ~0 at settlement.
    * LONG (stop below): futures sit ABOVE cash, so futures only reach L once cash is
      ~22 bps BELOW L -> the stop fires LATE by the basis (~Rs 3,080 at Rs 14L).
    * SHORT (stop above): mirror image -> fires EARLY -> a premature exit the model never
      takes. This is the new-wrong-order class, arriving through the back door.
    * The error is NOT constant: it decays over the contract's life and STEP-CHANGES on the
      N=5 entry roll when the traded contract switches month (+22 -> +55-71 bps).
  So: watch cash to stay faithful to the model; execute in futures as today. Exit sizing
  and the payload are unchanged (the payload carries the symbol root; the server resolves
  the contract and pins exits to the stored position symbol).
  THIS IS THE PREMIUM-vs-UNDERLYING FORK ARRIVING EARLY, on futures. The options section
  below records the same decision as OPEN for options; on futures it is DECIDED: underlying.
  Corollary for the watcher's own sanity checks: never compare a cash tick to a futures
  price or vice versa anywhere in the code path; the level, the tick, and the breach test
  are all cash-denominated, and only the ORDER is futures-denominated.

- FEED VENDOR — TrueData vs Dhan, MEASURED LIKE-FOR-LIKE (2026-08-11, both tapes, same
  session). Recorded because the "TrueData = 250 ms" claim was about INDICES and would
  otherwise be re-proposed for this instrument:
    1. THE 250 ms IS NOT A VENDOR PROPERTY. On the SAME instrument (NIFTY index, same day):
       TrueData NIFTY 50 median 250 ms (228.7/min) vs Dhan NIFTY spot median 249 ms
       (239.3/min) — IDENTICAL. 250 ms is the INDEX PUBLICATION CADENCE (~4/s), which both
       vendors relay. It says nothing about either vendor and must never be quoted as a
       TrueData advantage.
    2. "TD IS ~5x SLOWER ON BSE" WAS ONE STREAM OF THREE. TrueData splits its feed:
       BSE26AUGFUT trade-only = 4,472 msgs (11.9/min, median 2,408 ms) — the figure that
       produced the 5x reading — but bidask is a SEPARATE stream of 14,000 msgs. Merged:
       18,472 msgs, 49.3/min, median 1,202 ms, vs Dhan BSE cash 24,076, 62.4/min, 901 ms.
       Honest gap on update rate: ~1.3x, not 5x.
    3. STILL NOT LIKE-FOR-LIKE, and the residual asymmetry is unresolvable from these
       tapes: TrueData captured BSE FUTURES, the Dhan recorder captures BSE CASH. No BSE
       cash exists in the TrueData audit at all — which is also the GATING QUESTION for any
       TrueData proposal, since (per the instrument decision above) the watcher must watch
       CASH. A TrueData BSE-cash subscription would have to be confirmed to exist before
       the comparison is even meaningful.
    4. ON THE METRIC THAT ACTUALLY MATTERS, TRUEDATA IS BETTER, NOT WORSE — exchange-to-
       receipt lag: TD BSE fut median 0.49s / p90 0.90 / p99 1.00; TD NIFTY 0.60 / 0.90 /
       0.91; Dhan BSE cash 0.86 / 1.97 / **5.28**; Dhan NIFTY spot 0.66 / 0.93 / 3.40.
       TrueData's tail is ~5x tighter than Dhan's on the traded name. Mechanism: TD is
       EVENT-DRIVEN (a sparse-trading instrument shows long gaps BETWEEN messages, but each
       message arrives fast after its event), Dhan is a ~900 ms THROTTLED SNAPSHOT (regular
       cadence, but ~450 ms of average built-in staleness plus a fat tail).
    🔴 STANDING INSTRUCTION (founder, 2026-08-12): **NOTHING is to be built, wired, or
    prototyped against TrueData without explicit founder permission.** TD questions are
    QUESTIONS, not authorisation. The trial expires 12 Aug 2026, so any TD work also
    implies a PAID SUBSCRIPTION DECISION — the founder's call, never an implementation
    detail. Permitted without asking: reading already-captured tapes under
    ~/truedata-audit/ for analysis. NOT permitted: opening a TD connection, adding a TD
    client/SDK/dependency, writing a TD adapter or feed class, adding TD credentials or
    config, or designing any component whose default path is TD. A finding that TD is
    technically better is REPORTED, not acted on.
    (Compliance note for the 11-Aug comparison above: it read only tapes already on disk
    from the trial capture — no TD connection was opened, no TD code or dependency added.)

    5. VERDICT FOR THIS BUILD: proceed on Dhan — it is the execution broker, the account is
       entitled, the recorder proves 24 sessions of stability, and it already carries BSE
       CASH. TrueData is NOT rejected on speed (it is arguably faster in the tail); it is
       parked because the cash subscription is unconfirmed and a second vendor is a second
       failure surface for ~0.4s of tail. Revisit only with a measured BSE-cash tape.
    CAVEAT ON ALL OF THE ABOVE: one session per vendor; both exchange timestamps are
    1-SECOND resolution, so sub-second lag figures carry that quantization. Same method
    both sides, so the COMPARISON is fair; the absolute values are coarse.
- STOP LEVEL: not persisted anywhere today (verified — zero hits in executor/). Build
  adds an atomic per-cycle `stop_state.json` {symbol root, side, qty, stop level,
  source bar, forming-bar timestamp}. The level written is the LAST CLOSED bar's level —
  exactly the engine's resting-order semantics (level[i-1] governs bar i, proven by the
  02-18 calibration). Missing/stale file (>20 min) → watcher IDLE + loud, never guesses.
- TOKEN (PREARM L1): market-hours-only lifecycle — connect ~08:55, disconnect 15:35;
  every connect loads the newest token from broker_credentials; the 03:00 rotation never
  crosses a live session. Any WS error → reconnect with fresh token load. Acceptance
  test, not assertion: connect-log timestamps vs rotation + a forced mid-session
  kill/reconnect drill.
- DEATH LOUDNESS: supervisor restart (seconds) + 5s heartbeat file; the 15-min bar cycle
  asserts heartbeat freshness in market hours → TICK_WATCHER_DOWN marker + Telegram via
  the ANCHOR_STALL notifier seam (one ping per streak). Detection ≤ one cycle; harm vs
  today = zero (additive property).
- STOP-LEVEL DECLARATION (the keystone): the bridge adds `stop_level` to every payload
  from day one. 🔴 CONDITION 1 SATISFIED 2026-08-11: `extra="ignore"` verified IN THE
  RUNNING CONTAINER (trading_bridge_backend, /app/app/schemas/strategy_webhook.py:74,
  image sha 421d844b… shared with celery_worker) — the live server drops the field
  harmlessly; production evidence of correct declaration accrues before any platform
  work exists. One contract amendment later unlocks the platform watcher AND item 7.

## 🔴 ARM GATE — MANDATORY, HIGHEST-VALUE FINDING (adversarial review, 2026-08-11)
A watcher that simply "watches ticks" FIRES BEFORE THE MARKET OPENS. Verified on real
recorded data (2026-08-11 session, independently reproduced): the first 191 packets of the
feed day (received 09:05:09-09:08:00) carry ltp = 3596.10 = the PREVIOUS DAY'S CLOSE,
trade-stamped 2026-08-10 15:59:57, with a garbage book (bid 3955.70 ABOVE ask 3236.50).
An ungated 2-tick rule fires at 09:05:10 — TEN MINUTES before the open — for any
L >= 3596.10 (tested L = 3600/3610/3620; legitimate first breach was 09:15:04-09:15:12).
This is a DESIGN bug caught pre-build, NOT a production bug (no watcher exists yet), and it
would have shipped. It is independent of which confirmation rule is chosen.

ARM GATE (evaluate first; packet discarded unless all hold):
  A1. wall-clock IST in [09:15:00, 15:25:00]  (matches the platform's market-hours guard)
  A2. date(ltt - 19800s) == today's trading date  (ltt carries a +19800s IST shift;
      this kills the previous-day-close block that A1 alone would not catch after 09:15)
PACKET VALIDITY (discard packet if any fail):
  V1. packet_type == 8 AND security_id == 19585
  V2. bid_price_1 > 0 AND ask_price_1 > 0   (use > 0: the feed emits a -0.01 sentinel for
      empty levels; 2 post-close packets carry bid = ask = 0)
  V3. bid_price_1 < ask_price_1  (STRICT: rejects all 192 crossed books — 191 of which are
      pre-open — and the locked closing-auction print)
  V4. (ts_recv - (ltt - 19800)) <= 5.0 s  (freshness; in-session median 0.85s, p99 3.90s)
  V5. volume >= volume_prev  (rejects cumulative-volume regressions; one occurs in-session
      at 15:20:00 where volume drops to 0. LOAD-BEARING — the distinct-trade test fails OPEN
      on a volume reset, and V5 is what closes it. Do not drop as cosmetic.)
BREACH B(k):  ltp[k] <= L + 0.05  (half-tick epsilon: float32 stores 336 of 845 distinct
      prices ABOVE their 2dp value, e.g. 3537.10009765625, so a bare <= silently misses
      exact touches. VERIFY tick size 0.10 from the scrip master before hard-coding.)
DISTINCT TRADE N(k): NOT (ltt[k] == ltt[p] AND volume[k] == volume[p]), p = previous valid
      packet — stops one trade being echoed across packets and counting as two.
FIRE iff: A1 AND A2 AND V(k) AND V(p) AND B(k) AND B(p) AND N(k)
WATCHDOG (alert only, NEVER auto-fires): B holds on a valid packet but no fire within
      3000 ms -> operator alert. Fail closed: an anomalous or stalled book is evidence
      AGAINST firing, never a reason to fall back to a weaker test.

## DEPTH-CONFIRM ON THE FIRST TICK: PROPOSED, MEASURED, **REFUTED** (2026-08-11)
Founder asked whether 5-level depth could confirm a breach on the FIRST packet (~900ms)
instead of requiring 2 ticks (~1800ms). Depth IS structurally available (packet_type=8
carries LTP + 5 levels in one packet, 100% populated). The proposed guard was
`bid1 > 0 AND bid1 <= ask1 AND |ltp - bid1| <= 10 bps`. Four independent adversarial
reviews against the raw file refuted it on three counts, all reproduced:
  1. THE GUARD IS A NO-OP IN-SESSION. Over 09:15:30-15:29 (23,849 packets) it rejects
     ZERO. The full in-session support of |ltp - bid1| is [-6.70, +8.45] bps — the 10 bps
     threshold lies outside the entire empirical range of the statistic it tests. My
     original 99.18%/0.8%-reject figure was contaminated by pre-open auction packets; the
     session gate above is the correct fix for those, not a bps filter.
  2. IT BLOCKS NONE OF THE FAILURE CLASS IT WAS INVENTED FOR. Sweeping 8,830 stop levels:
     186,692 isolated single-packet dips (ltp <= L for exactly one packet, then recovery —
     precisely the fires a 1-tick rule makes and a 2-tick rule cannot). The guard permits
     186,692 of 186,692 = 100.00%. 30.0% of levels have such a dip as their FIRST breach.
     After an isolated dip price is back above L one minute later 51.1% of the time — coin
     flips, not information.
  3. ITS ONLY IN-SESSION ACTION IS TO VETO GENUINE FAST DECLINES. Exactly 5 in-session
     packets fail the ±10 bps test; ALL FIVE are 09:15:04-09:15:09, the steepest four
     seconds in the file. Market makers pull the bid as price falls, so (ltp - bid1) is a
     DECLINE-SPEED METER, not a glitch detector. The filter is inert on calm packets and
     actively harmful on exactly the squeeze events that generate the ₹42,200/yr — its
     benefit is negatively correlated with its payoff.
ROOT CAUSE, why no volatile day would rescue it: the ~901ms throttle destroys the
print-vs-book separation before delivery. ltp lands exactly on bid1 or ask1 on 82.8% of
packets; lead-lag corr(Δltp, Δbid1) = 0.596 at lag 0 and |corr| < 0.03 at every other lag.
We receive two fields of ONE end-of-second converged snapshot, not a print and an
independent book. Sub-second divergence is smoothed away before it reaches us.
ALSO: bid1 is the wrong field to trust — it is the spoofable side (median 2 orders / 55
shares at the touch) and cash L1 depth cannot support the exit anyway (whole L1-L5 bid
stack ~411 shares median vs a 400-unit order; ~0.16% of total_buy_qty). Displayed depth is
never fillability evidence.

DECISION: **KEEP 2-TICK.** The hardening above is exactly free — measured against plain
2-tick across the level sweep it is identical at 100.0% of levels (median +0ms, max +0ms,
0 misses). It removes failure modes and costs no latency.

UPGRADE PATH, held not taken: `ask_price_1 <= L` on the first packet (the whole visible
spread below the level) blocks 87.7% of isolated dips, misses 0 of 883 levels where 2-tick
eventually fires, and fires FASTER than 2-tick at 93.0% of levels (median -898ms). It is
faster AND safer than the proposal — but it is still a ONE-tick rule producing 630
wrong-fire levels vs 0, on ONE session. Revisit only with multi-session data incl. a
squeeze. Merely tightening the refuted threshold does NOT work: 3 bps still allows 96.97%
of wrong fires, 1 bps still allows 83.91%, and both add ~+2,700ms median — slower than the
rule they would replace AND less safe.

## HONEST LATENCY CLAIM (supersedes earlier drafts)
- Versus PRODUCTION TODAY (bar close + ~75s, up to ~16 min): the 2-tick rule fires a
  median 910ms after the first breaching packet and recovers ~99.8% of the ₹42,200/yr.
  That is the entire prize, and 2-tick already captures it.
- MUST NOT be claimed: "~900ms end-to-end" (exchange-to-receipt lag is a median 0.86s that
  no rule change removes; honest exchange-event-to-fire is ~1.8s median), or "halves
  latency" (true only at the median: 2-tick delay vs first breach is median 910ms, p90
  8,058ms, p99 ~11 min — the tail is set by FEED STALLS, 32 in-session gaps >5s incl. a
  33.6s stall, which no confirmation rule fixes).
- The marginal value of 1-tick over 2-tick is ~899ms ≈ ₹40/yr pro-rata, or measured
  directly on this session ~₹240 median / ₹420 mean per event on 400 units. That is the
  entire benefit that would have been bought with a new unbounded failure class.

## CLAIMS LEDGER — WHAT MAY AND MAY NOT BE SAID ABOUT THIS FEATURE
Founder instruction 2026-08-11: these sentences live HERE, not only in a chat report,
because they are the ones that would otherwise be repeated back to Jayesh wrongly. Each
RETRACTED line was said by me during scoping and is now known to be false or misleading.

RETRACTED — do not repeat:
  ✗ "The watcher fires ~900ms-1s end to end."
  ✗ "Depth confirmation halves the latency."
  ✗ "The rules showed a 0% miss rate."
  ✗ "The book corroborates the print, so a glitch is exposed on the first tick."

SAY INSTEAD — verified, quotable:
  ✓ "Honest exchange-event-to-fire is ~1.8 s median. The ~0.86 s exchange-to-receipt lag
     is in the feed and NO rule change removes it."
  ✓ "Latency is halved only AT THE MEDIAN. The distribution's tail — p90 ~8 s, p99 ~11
     minutes — is set by FEED STALLS (32 in-session gaps >5 s, incl. a 33.6 s stall),
     which NO confirmation rule fixes."
  ✓ "A 0% miss rate is a property of THIS ONE DAY, not a property of the rules. One calm
     session, one instrument, no squeeze, no halt. Every rate in this spec is provisional
     until multi-session."
  ✓ "Depth cannot corroborate a print on this feed: the ~901 ms throttle delivers two
     fields of ONE converged end-of-second snapshot, so the divergence a glitch would
     create is smoothed away before it reaches us."
  ✓ "Versus production today the 2-tick rule recovers ~99.8% of the ₹42,200/yr. The last
     ~899 ms is worth ~₹240 median / ₹420 mean per event — that is the whole prize that a
     faster rule would buy, in exchange for a new wrong-fire class."
  ✓ "TrueData's 250 ms was measured on INDICES, and on indices Dhan is 249 ms — identical.
     250 ms is the index publication cadence, not a vendor advantage."
  ✓ "TrueData is not 5x slower on BSE: that compared its TRADE stream alone (4,472 msgs)
     against Dhan's combined packet. With its bidask stream merged (18,472 msgs) the gap
     is ~1.3x — and on exchange-to-receipt lag TrueData is actually BETTER (p99 1.0s vs
     Dhan's 5.28s on the traded name)."
  ✓ "The watcher subscribes to BSE CASH (19585), not the futures contract it closes,
     because the engine derives the stop level from cash bars. Watching futures would
     compare a futures price to a cash level and let basis (~22 bps front, ~55-71 next)
     silently move the stop — late for longs, EARLY for shorts."

STANDING RULE: any latency or safety number quoted outward carries its measurement basis
(which session, which sample size). "Measured on one calm session" is part of the number,
not a footnote to be dropped.

## THE ONE NEW RISK CLASS, AND ITS GATE
A bad tick firing a premature exit the model never takes (position-desync class) is the
watcher's ENTIRE novel risk surface — it can never send a wrong symbol, qty, or side,
because it only sends the payload the bar path itself would send.
GUARD: 2 consecutive ticks beyond the level + top-of-book confirmation (bid<level for
longs / ask>level for shorts) from the same feed.
🔴 CONDITION 2 (founder, hard gate): the guard ships TEST-DRIVEN — falsification twin:
synthetic bad-print fixture (single glitch tick through the level, never confirmed) →
guard removed = watcher fires and the test FAILS; guard restored = no fire, passes.
Same standard as the settlement guard (proven 2026-08-11) and the T-2 backstop.

## ACCEPTANCE — WHAT THE SHADOW CAN AND CANNOT PROVE (founder arithmetic, recorded
## the way E4's day-1 report was: "0 early means no entry occurred, not that it works")
Short stops run ~24/yr ≈ 2/month (154 over 6.5y). A 1-2 session DRY shadow therefore
catches ZERO short-stop events with ~82% probability (any stop at all: ~56% zero).
→ THE SHADOW CAN ONLY PROVE THE MACHINERY RUNS (feed up, levels loaded, heartbeat,
  zero false fires). A QUIET SHADOW WEEK IS NOT VALIDATION OF THE MONEY CASE and must
  never be reported as such.
→ TICK COVERAGE ON THE EXPENSIVE DAYS: ZERO (verified on the box 2026-08-11). The
  recorder's BSE ticks start 2026-07-09 (S3; local retention 10 days). ALL six ≥₹40k
  events (2024-07-31, 2024-10-08, 2025-05-07, 2025-05-09, 2025-08-21, 2026-02-01) and
  all sixteen ≥₹20k events predate it. THE REPLAY HARNESS THEREFORE PROVES THE DETECTOR
  ON ORDINARY TICK STREAMS ONLY — "replay validated" MUST NOT stand in for the money
  case (founder rule, 2026-08-11).
→ What validation actually consists of, in decreasing strength:
  (i)  the falsification-twin suite (signal_id identity, dedup end-to-end, kill-watcher
       fallback, bad-tick guard twin) — proves the SAFETY properties outright;
  (ii) real-tick replay (2026-07-09→now) with synthetic levels inside the day's range —
       proves the detector's mechanics on real microstructure. LABELLED TAPES (measured
       2026-08-12; the label is part of the artifact so the set is never oversold):
         * 2026-08-11 BSE_19585 — 24,076 pkts. Worst 1-min excursion **173 bps (62 pts)**,
           5-min 208 bps. Contains the sharpest SHORT-WINDOW move of the two (the 09:15
           opening decline: 5 consecutive packets at 11-19 bps each).
         * 2026-08-12 BSE_19585 — 24,052 pkts. Full-day range **2.86%** (3605.0 -> 3501.9)
           with a **-1.08% opening slide in ~14 min**, but worst 1-min excursion only
           **62 bps (22 pts)**, 5-min 90 bps: a sustained TREND day, not a violent one.
       🔴 NEITHER IS THE MONEY CASE. The >=Rs 40k events are ~2.9% moves at MINUTE scale
       (~290 bps in 60s). The gap is ~1.7x (11 Aug) and ~4.7x (12 Aug) on the statistic
       that actually matters — VELOCITY, not daily range. Note 12 Aug has the bigger daily
       move yet the calmer minute: magnitude and velocity are different axes, and only
       velocity stresses a confirm rule. Correction to an earlier framing in this file:
       11 Aug is NOT merely "ordinary microstructure" — at 1-minute scale it is the more
       demanding of the two.
  (iii) SQUEEZE-SHAPED SYNTHETIC streams reconstructed from the six events' actual 15m
       bars (monotone sweep through the recorded range at tick cadence, plus adversarial
       variants: opening gap print, lone glitch print, 100-points-in-a-minute ramp,
       and — founder addition 2026-08-11 — WHIPSAW: repeated crossings of the level
       inside one bar, because OHLC hides the intra-bar path and the single-direction
       variants only test the happy path; oscillation is what can delay or defeat a
       2-tick confirm). Whipsaw fixture asserts ALL of: (a) no fire when no crossing
       ever sustains 2 ticks + depth-confirm; (b) fire at exactly the first crossing
       that DOES confirm, not before; (c) when the guard rightly holds fire through an
       unconfirmed whipsaw, the BAR PATH still exits at bar close — the degradation is
       to TODAY, never to nothing (the additive property, asserted not assumed).
       Exercises the money-carrying SHAPE, clearly labeled synthetic microstructure;
  (iv) FORWARD ACCRUAL, the only real money-case evidence: ~2 short stops/month; every
       live short stop gets a post-hoc replay comparison (watcher's live behavior vs
       that day's recorded ticks). The money case is validated by accumulation, not by
       any pre-arming artifact.
Arming gate: machinery shadow clean (zero false fires) + twin suite green + (ii) and
(iii) green. A caught live short-stop during shadow is a bonus, never a requirement.
→ ADDED 2026-08-11 after the depth review, which found every candidate rule's 0% miss
  rate to be "a property of this day, not of the rules": capture and replay (a) a genuine
  fast-decline/squeeze session — all six ≥₹40k tail events are squeezes and NO session on
  file contains one — and (b) a stop-run-and-reverse day. Pathology rates here (crossed
  books, zero books, auction prints) are two contiguous regime BLOCKS observed once each,
  not independent draws: with n=1 session the 95% upper bound on any per-session pathology
  rate is ~97.5%. Treat every rate in this spec as provisional until multi-session.

## OPTIONS — DESIGN CONSTRAINT ONLY, NOT BUILT (founder order 2026-08-11)
Intra-bar stops are wanted for options too (options work comes next). Recorded here so
the futures build carries the constraint and the forks are never rediscovered:

1. THE CORE STAYS INSTRUMENT-AGNOSTIC. The two-layer factoring already guarantees it:
   `tick_watch/` core = feed client + breach detector + guards over (instrument_id,
   level, side, qty) with zero knowledge of what the instrument is. Nothing in the
   futures build may leak futures/cash assumptions into the core — an options adapter
   later is a new ADAPTER, never a core rewrite. Stated explicitly: the futures build
   BLOCKS NOTHING.

2. OPTION-SPECIFIC FORKS an options adapter must decide (recorded, NOT decided):
   - 🔴 PREMIUM STOP OR UNDERLYING STOP — the FIRST decision, before any other. A
     premium stop can be hit by IV collapse or theta with the underlying unmoved; an
     underlying stop is faithful to the strategy logic but means watching a DIFFERENT
     instrument than the one held. The choice changes the feed subscription, the
     detector's input series, and exit sizing. Not picked now; no default implied.
   - STRIKE-SPECIFIC SUBSCRIPTIONS, not one instrument — the watched leg changes with
     every position and expiries roll WEEKLY: 4-5x the boundary churn of the monthly
     futures case and materially heavier subscription management.
   - FAR WIDER SPREADS — a market exit on a triggered stop slips worse than futures;
     the fill-quality assumptions in this spec's rupee numbers do NOT transfer.
   - NOISIER PRINTS — thin strikes print erratically; the bad-tick guard becomes MORE
     load-bearing, not less, and its falsification fixtures need option-grade noise.

3. SEQUENCING, stated plainly: an options adapter is DOWNSTREAM of an options strategy
   existing and being CERTIFIED. Every certified number in this program today is
   futures-priced; the options pricing exam has not run. No options watcher work of any
   kind before that exists.

## SIZING & DAY-1 ORDER
~3 build days + 1-2 DRY shadow sessions + replay harness ≈ 1 week to armed. Slots after
the resolver deploy (Fri 14), ahead of E5 (founder priority: speed on the exit side).

DAY 1, in order (founder-approved 2026-08-11):
  1. FIRST COMMIT = THE ARM GATE + packet validity (A1/A2/V1-V5/B/N above), with its
     falsification twins: the pre-open fixture (191 stale previous-close packets — remove
     the gate → the test fires at 09:05:10 and FAILS), the float32 exact-touch fixture,
     and the volume-reset fixture. The gate is the highest-value item in the review and it
     ships before any firing logic exists.
  2. PIN THE DEPTH RECORDER to `connections:\n  max: 1` (founder: "one free slot with an
     unenumerable neighbour is not a margin"). Dhan cap 5; recorder 3 + depth 1 = 4 today,
     but the depth recorder's config PERMITS 3, so an unrelated instrument-list change
     could silently consume the watcher's only slot. Pin it on Day 1, not later. This is a
     platform-service config change → founder-gated, no code path touched.
  3. tick_watch core (feed client + 2-tick breach detector + guards) + unit suite incl.
     the bad-tick twin and the whipsaw fixture.
Day 2: bridge adapter (stop_state.json writer/reader, payload, signal_id identity, dedup
  end-to-end, heartbeat + TICK_WATCHER_DOWN escalation).
Day 3: replay harness + squeeze-shaped synthetics + supervisor unit + DRY-shadow flag.
