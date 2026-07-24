# MACHINE HEALTH CARD — DRAFT (outcome-blind; no PnL/R numbers anywhere)

Phase 1(A) measured 2026-07-25 on burned days. Data reality: depth retention (5-day
window) had already pruned 2026-07-15/16/17 depth locally → those days SKIPPED
(restore out of scope in a read-only session); 2026-07-14 EXCLUDED (degraded).
Audited units: {2026-07-20, 2026-07-21} × {NIFTY_FUT, BANKNIFTY_FUT}, 5-level book
as recorded (of the 20-level feed), raw parquets, NO replay. Peak RSS 205MB.
Raw per-unit JSONs: scratchpad/healthcard/A_<day>_<inst>.json.

FEED_PHYSICS §1 spec line (drafted, approved): "DEPTH CLOCK = fixed-cadence ~8.33
snaps/s frame publisher; frame diffs collapse book events (47-65% of changed frames
touch >=3/5 levels)."

PRE-DECLARED REPORTING BANDS (fixed before measurement): staleness 1s/5s; crossed
material line >0.1% of snapshots OR any episode >=1s; LTP-outside material line >2%
of volume-advancing packets after +/-1-snapshot tolerance.

## A. DEPTH / BOOK-STATE INTEGRITY — FILLED

### A1. Update rate
~8.33 snapshots/s on every unit, and REMARKABLY flat across buckets (09:15-10:30 /
10:30-13:00 / 13:00-15:30 all 8.31-8.35/s — the depth feed is a fixed-cadence
publisher, unlike the trade-rate-driven tick feed). Inter-update gaps: p50 0ms
(bid+ask arrive paired at the same ts), p90 ~335-337ms, p99 ~407-410ms, max 3.6s
(07-20 both insts) / 0.8s (07-21).

### A2. Staleness (book-CHANGE age)
Change-gap p50 ~0.20s, p90 ~0.40s, p99 0.9-1.2s. % of session time with book age
>1s: NIFTY 2.87/2.12%, BANKNIFTY 1.82/1.36%. Age >5s: <=0.046% everywhere.
Longest identical-book span: 12.01s @ 12:16:17 (07-20 NIFTY); others 5.4-6.2s.

### A3. Crossed / locked
Crossed snapshots: 0.0502-0.1156% — TWO of four units marginally exceed the 0.1%
material line (07-20 BANKNIFTY 0.1063%, 07-21 NIFTY 0.1156%). Episodes 94-214/day,
ALL sub-250ms (max episode 0.202s @ 10:43:57 07-21 NIFTY) — far under the 1s episode
line. Locked: 0.03-0.32%. Note: the tape's book_ok guard already skips crossed/locked
books in the OFI path, so these transients never enter accumulated features.

### A4. Level integrity
Monotonicity violations: 0 of ~187k snapshots on every unit. Zero/negative qty: 1
snapshot total (07-20 NIFTY) across ~750k audited snapshots. Short books (<5 levels):
0. The recorded book structure is essentially perfect.

### A5. LTP <-> book coherence  ** BREACHES THE PRE-DECLARED 2% LINE **
% of volume-advancing tick packets with LTP outside [best_bid, best_ask] even with
+/-1-snapshot tolerance: 19.2-26.0% (all four units; line was 2%). |LTP - mid|:
p50 31-33 ticks (~1.6 pts) NIFTY, 96-132 ticks (~5-7 pts) BANKNIFTY; p95 97-105 /
300-318 ticks. Reading: this is CROSS-FEED ASYNCHRONY, not book corruption — the
tick feed is a ~0.6-0.8s snapshot (FEED_PHYSICS §1) whose LTP is up to several
book-updates stale against an 8.3/s depth feed; on a moving market the trade price
legitimately sits outside the CURRENT book. The book itself is internally clean (A4).
Consequence: any feature that JOINS tick-LTP to the book at packet precision
inherits this skew. Book-only features (P6, qi) are unaffected.

### A6. P6 diff-jump pressure
Among book-changing updates, >=3-of-5 levels change at once in 47.0/57.4% (NIFTY
07-20/21) and 65.0/64.4% (BANKNIFTY) of updates; single-level changes are only
17-33%. Multi-level jumps are the NORM on this feed, not the exception — P6's
by-price diff semantics remain valid, but "surgical" single-level reads are the
minority regime. Existing P6 gap-guard fire rate: NOT-MEASURED (no new plumbing).

### A. VERDICT TABLE
| subsystem | verdict | evidence line |
|---|---|---|
| DEPTH_UPDATE_RATE | SOUND | 8.33/s, flat 8.31-8.35 across all buckets/units; p99 gap ~0.41s |
| BOOK_STALENESS | SOUND | age>1s only 1.4-2.9% of session, >5s <=0.046%; worst span 12s once |
| CROSSED_LOCKED | CEILING-BOUNDED | 0.05-0.12% (2/4 units marginally over the 0.1% line) but ALL episodes <0.25s vs the 1s line; book_ok already filters them from OFI |
| LEVEL_INTEGRITY | SOUND | 0 monotonicity violations, 1 zero-qty snapshot in ~750k, 0 short books |
| LTP_BOOK_COHERENCE | CEILING-BOUNDED | 19-26% outside-book (line: 2%) — cross-feed asynchrony (tick ~0.7s snapshots vs 8.3/s book), not book corruption; binds LTP-to-book joins only |
| P6_DIFF_JUMPS | CEILING-BOUNDED | 47-65% of changes touch >=3/5 levels — multi-level jumps are the norm; by-price diffs valid, single-level reads minority; guard rate NOT-MEASURED |

### Drafted caveat lines (for review — FEED_PHYSICS.md NOT edited)
1. FEED_PHYSICS §6 caveat (new row/footnote): "LTP-to-BOOK JOINS = PHYSICS-BOUNDED:
   the tick feed (~0.6-0.8s snapshots) and the depth feed (8.3 updates/s) show
   cross-feed STALENESS-dominant — clock bases aligned (offset ≈0 ±5ms, B4), outside-book
   share unchanged under offset correction (B5) → permanent asynchrony bound, not
   repairable skew — with
   19-26% of volume-advancing packets printing LTP outside the concurrent best
   bid/ask even with +/-1-snapshot tolerance (|LTP-mid| p50 ~31-33 ticks NIFTY /
   ~96-132 ticks BANKNIFTY, measured 07-20/21). Book-only depth features stay
   PHYSICS-CLEAN; any feature joining tick-LTP to the book at packet precision
   inherits this bound. Signed Lee-Ready P5 inherits this bound; unsigned
   response-efficiency variant does not."
2. FEED_PHYSICS §1 footnote (minor): "crossed book snapshots 0.05-0.12% of updates
   (all episodes <0.25s; book_ok skips them); 47-65% of book updates change >=3 of 5
   levels at once — multi-level jumps are the feed's normal regime."
No REPAIR->ledger rows; no ledger item required from Section A.

## B. TIMESTAMP / ORDERING — FILLED (Phase 1(B), measured 2026-07-25)
Tick-side: 07-15..21 (5 days x 2 insts, all local). Cross-feed: 07-20/21 (Section-A days).
Peak RSS 183MB. Raw JSON: scratchpad/healthcard/B_all.json.

### B1. TS inventory
TICKS: ts_recv_ns (LOCAL receive, TRUE-ns jitter — no ms/us padding) + ltt (EXCHANGE
last-TRADE-time, SECONDS resolution). DEPTH: ts_recv_ns (LOCAL, true-ns) + msg_seq = DEAD field (all zeros, all audited
files) — the earlier 'monotone exchange sequence / ordering witness' claim is
RETRACTED (trivially true on zeros); truth-order verification in B2-VERIFY was
content-based. No fine exchange sequence exists on either feed. + seq_local. NO exchange wall-clock exists on the depth feed and only seconds-resolution
trade-time on ticks => Section B measures RELATIVE inter-feed offset only; both feeds
stamp on the SAME host clock. TRAP FOUND: ltt's epoch base is IST-SHIFTED (+19,800s) —
raw recv-ltt sits at ~-19,797.6s; after base correction, recv - ltt_utc p50 ~ +2.4s,
an UPPER bound on feed delay (ltt is last-trade age, inflated on quiet stretches).
Session-bound sanity OK (ticks 09:05->15:30). Join-key ts_ns derives from ts_recv_ns.

### B2. Ordering
TICKS: PERFECT — 0 out-of-order, 0 duplicate-ts, all 10 unit-days (27.4k/36.4k rows).
DEPTH: dup-ts 50.01% BY DESIGN (bid+ask frames share one ts; longest run 4 = two
pairs). Out-of-order 0.0202-0.0208% (~39 rows/file) BUT max backwards jump ~20,440s
(~5.7h) — one DISPLACED BLOCK per consolidated file (file tail stamps 15:16 while
later-timed rows sit earlier) => the depth EOD consolidation does NOT guarantee
global ts order. Breaches the pre-declared 'any backwards jump >1s' line => material.
Consumers that assume per-file sorted order (ReplaySource heap-merge) could emit
out-of-order depth for that block; Section A sorted before measuring, so A-metrics
are unaffected.
Determinism note (B2-VERIFY resolved): ReplaySource emits ts-sorted with zero
backwards events — frozen hashes, probe results AND replayed book state all STAND;
the file-order anomaly has NO replay-level effect.

### B3. Cadence self-check
Ticks reproduce FEED_PHYSICS exactly: 1.21 (NIFTY) / 1.61 (BANKNIFTY) pkts/s on all
5 days. Depth naive rate reads 8.63-8.65/s vs A1's sorted 8.33/s — the difference is
itself the B2 displaced block (unsorted span shorter) => A1's 8.33/s stands; the
discrepancy corroborates B2, ts fields otherwise believable.

### B4. Cross-feed offset (two methods)
(i) EVENT ALIGNMENT (authoritative): signed delta median -0.001 to -0.004s (~0),
IQR 0.147-0.151s, bucket medians stable within +/-6ms across all three buckets, both
days both insts; unmatched 3.1-4.6%. 3/4 units met the constant-skew label; 1 unit IQR 151ms marginally over the 150ms
line; conclusion rests on B4 median (~0) + B5 re-score, not the label. Skew ~= ZERO.
(ii) LAGGED XCORR: argmax +0.2..+0.5s but peak corr only 0.011-0.028 and
peak/2nd-best 1.0-1.6 => NO sharp peak — method uninformative on a 100ms grid vs a
1.2-1.6 pkt/s tick feed (expected). Weakly consistent in sign with (i).
CONVERGED CONCLUSION: clock bases are ALIGNED (offset ~ 0 +/- 5ms, constant).

### B5. A5 re-score with measured offset
Offset applied as pure ts-shift (-1 to -4ms): outside-book % UNCHANGED — 22.7 / 22.8 /
25.96 / 19.23 vs 22.7 / 22.8 / 25.96 / 19.21 before. Per the pre-declared band
(>10%) => ** ASYNCHRONY-DOMINANT — a PERMANENT bound **. The A5 phenomenon is
cross-feed STALENESS (the tick packet's LTP is old news vs an 8.3/s book), not a
repairable clock skew. No offset-repair ledger item (nothing to repair by shifting).

### B6. Join-key safety (raw feeds)
TRADES: ts_ns is a SAFE unique key per instrument-day (0 duplicates in 10 unit-days).
DEPTH: ts_ns alone is NOT unique (50% paired duplicates, runs to 4) — any depth-row
join needs (ts_ns, side)-style disambiguation. Bar-level signal joins (ts_ns = bar
end) are tick-derived and unaffected.

### B. VERDICT TABLE
| subsystem | verdict | evidence line |
|---|---|---|
| TS_BASE_INVENTORY | CEILING-BOUNDED | only LOCAL ns clock is fine-grained (exchange side: seconds ltt + seq); relative offsets only; ltt epoch is IST-shifted (+19,800s) — documented trap |
| ORDERING_MONOTONICITY | REPAIR->ledger (depth) / SOUND (ticks) | ticks 0/0 everywhere; depth has one displaced block/file (0.02% rows, max backwards jump ~5.7h vs the 1s line) — consolidation lacks a global-sort guarantee |
| TS_RESOLUTION_DUPES | CEILING-BOUNDED | true-ns resolution both feeds; tick dupes 0%; depth dupes 50.01% BY DESIGN (paired frames) — structural, binds join keys (B6), not fan-out corruption |
| CROSS_FEED_OFFSET | SOUND | event-align median ~0 (-1..-4ms), IQR ~0.15s, bucket-stable +/-6ms; xcorr flat (no sharp peak) but sign-consistent |
| A5_MECHANISM | CEILING-BOUNDED (ASYNCHRONY-DOMINANT) | outside-book unchanged (19.2-26.0%) after offset shift => staleness, not clock skew; permanent bound on LTP<->book joins |
| JOIN_KEY_SAFETY | SOUND (trades) / statement (depth) | trades ts_ns unique; depth requires (ts_ns, side) |

### Drafted lines (for review — nothing applied)
R-depth-sort — B2-VERIFY MEASURED (2026-07-25): msg_seq is DEAD (all-zero, all files) —
exchange-sequence verification impossible; truth-order established by CONTENT instead
(stray rows' prices match their OWN ts's market, not their file neighborhood's —
exemplar 07-20 NIFTY 24158.1 @09:51 vs tail 24259 @15:16). Structure: the session-TAIL
segment (15:16-15:33) was consolidated EARLY (~7.4k rows mid-file), interleaved ~every
200 rows with resuming morning rows -> 38-39 file-order backwards transitions/file;
timestamps and content are individually CORRECT. ReplaySource emitted ZERO out-of-order
depth events (187k/file, all four files) — heap-merge fully heals file order at read
time; replayed book provably clean. VERDICT per pre-declared bands: TAIL-CONFINED (all
four files; displaced rows' ts all 15:16-15:33; replay anomalies = zero). The 90.4%
positional book-diff from the first pass was a comparison ARTIFACT (positional compare
vs the wrong reference order) — discarded. R-depth-sort DE-ESCALATES to cosmetic
file-order hygiene: optional sort-on-write in recorder EOD consolidation at a future
maintenance cycle; NO replayer change needed; no correctness repair outstanding.
FEED_PHYSICS §6 caveat RESOLUTION (updates the Phase-1(B) placeholder wording):
"...cross-feed STALENESS-dominant — clock bases aligned (offset ~0 +/- 5ms, B4) and
the outside-book share is unchanged under offset correction (B5) => permanent
asynchrony bound, not repairable skew."

## C. EXIT-ENGINE LIFECYCLE AUTOPSY — FILLED (Phase 1(C), 2026-07-25)
OUTCOME-DESCRIPTIVE ON BURNED DAYS ONLY (R/MFE/MAE permitted in this section alone).
Sources: cached artifacts only — netr_trades.json (baseline-17), v2 export exits arrays
(14/17 trades; the three 07-15 NIFTY trades' exits are NOT-CACHED — excluded from
C1-C3, included in C4), veto_perfire (delta+vwap per-fire gross/net). 1-min bar paths
from local ticks. NO new replays. Peak RSS 84MB.
COVERAGE NOTE: the delta+vwap set has NO cached exit reasons/timestamps => C1-C3 for
that set = NOT-CACHED (skipped, labeled); C4 computable from cached gross/net.

### C1. Exit-leg census (baseline-17, 14 cached; per instrument, sets NEVER pooled)
NIFTY: stop_hit 4, trail_hit 2 (of 6 cached). BANKNIFTY: stop_hit 3, trail_hit 3,
signal_exit 2 (of 8 cached). Partial (T1) taken on 7/14. Legs NEVER used: sleeper 0,
session-flatten 0. delta+vwap set: NOT-CACHED.

### C2. Wall-clock share
Time-driven exits: 0/14 — every cached exit is price-driven. Median time-in-trade:
stop_hit 3.2 min, signal_exit 8.1 min, trail_hit 9.1 min. The 60-min sleeper NEVER
engaged at size-100 (median holds are minutes; a size-100 tick-bar itself spans
~4.7 min). Ties to R2-15: sleeper-dominance is a LARGE-bar-size phenomenon only.

### C3. MFE/MAE (bar-approximate, 1-min paths entry->exit; n=14)
Full-window:  MFE median 1.14R, quartiles [0.59, 1.14, 2.60]; MAE median -1.27R,
quartiles [-2.37, -1.27, -0.64]. Interior-bars-only (entry/exit bars excluded):
MFE 1.07R [0.58, 1.07, 2.59]; MAE -1.22R [-2.08, -1.22, -0.33] — the contamination
correction barely moves it. MAE<= -0.8R before MFE>=+0.5R: 5/14.
STRUCTURE FOUND (stop-fill realism): stop-out trades book gross ~-1.01R (stop + flat
2-tick slip) while their 1-min paths show -1.2..-4.1R adverse excursion WITHIN the
triggering tick-bar step — at size-100 one tick-bar ~4.7 min, so stops resolve inside
a single sim step and the flat-slip fill assumption is OPTIMISTIC on sweep bars.
Winners' giveback: trail exits book +0.5..+1.0R against bar-path MFE medians ~2.5R.

### C4. Tail concentration (descriptive; central-reframe)
baseline-17 NIFTY: n=9, net total -1.32R; top-1 +2.48, top-2 sum +4.50; -1R cluster
5/9. baseline-17 BANKNIFTY: n=8, net -1.52R; top-1 +0.92, top-2 +1.58; cluster 3/8.
delta+vwap NIFTY: n=177, net -83.99R; top-1 +6.82, top-2 +10.36; -1R cluster 50.3%.
delta+vwap BANKNIFTY: n=185, net -33.21R; top-1 +9.68, top-2 +16.50; cluster 50.3%.
In every set the positive mass concentrates in the top 1-2 fires; roughly half of all
fires end at the hard stop.

### C. VERDICT ROWS
| subsystem | verdict | evidence line |
|---|---|---|
| EXIT_ENGINE_MIX | SOUND (machinery) | legs fire as designed; in practice 3 of 5 legs carry everything (stop 50%, trail 36%, signal 14% of cached exits); sleeper+flatten unused at size-100 |
| SLEEPER_DOMINANCE | SOUND at size-100 / R2-15-bound at large sizes | 0/14 sleeper exits; median holds 3-9 min vs 60-min sleeper; s1000 near-degeneracy remains the R2-15 concern |
| TAIL_CONCENTRATION | CEILING-BOUNDED | top-2 fires carry the positive mass in all four sets; ~50% of fires stop out at -1R (both families) |
| MFE_MAE_SHAPE | CEILING-BOUNDED | booked -1.01R stops sit inside measured -1.2..-4R 1-min excursions (flat-slip optimism on sweep bars); winners book 0.5-1.0R against ~2.5R path MFE (trail giveback). Bar-approx, labeled (model-realism bound, not feed physics) |

### Drafted ledger-note lines (for review — ADOPT NOTHING)
C-note-1 (-> R2-15/R2-14 context): "sleeper leg unused at size-100 (0/14 cached
exits; median hold 3-9 min vs 60-min sleeper) — bar-scaled sleeper is a large-size
concern only; exit-variant exams should treat sleeper as inert at baseline size."
C-note-2 (-> R2-14 input): "trail giveback structure: winners book +0.5..+1.0R
against bar-path MFE median ~2.5R (burned days, bar-approx, descriptive).
Path-MFE is not capturable by construction (clairvoyance); informs R2-14 exit
variants only — no promise of capture."
C-note-3 (standing-reframe corroboration): "~50% of fires end at the hard stop in
BOTH families; positive mass sits in the top-2 fires per set."
C-note-4 (NEW, cost-model realism): "stop fills are modeled at stop+2 ticks, but
size-100 stops resolve inside one ~4.7-min tick-bar whose 1-min path shows
-1.2..-4R excursion — flat-slip is optimistic on sweep bars; any Round-2 exam
should carry a stop-slip stress variant (existing slippage_multiplier knob covers
the mechanics; the ledger item is to REQUIRE it in exit-family exams). Path
excursion = UPPER BOUND on fill damage, not expected fill; the stress variant
spans flat-slip -> excursion-scaled slip."

## PHASE 2 — placeholder
