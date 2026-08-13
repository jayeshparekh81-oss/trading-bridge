# FEED_PHYSICS.md — the Dhan feed's DNA (measured, outcome-blind)

Measured on burned days 2026-07-16/17/20/21, NIFTY_FUT + BANKNIFTY_FUT (granularity audit,
2026-07-24) + tape source ground truth. This document contains NO outcome numbers (no net-R,
no PF, no win%) by construction — it describes what the feed physically delivers, and it BINDS
Round-2 pre-registrations that touch any physics-bounded family (§7).

## 1. FEED MODEL — what a packet is
A Dhan tick packet is a ~0.6–0.8s SNAPSHOT, not a trade event: NIFTY_FUT arrives at 1.21
packets/s (p50 gap 602–713ms), BANKNIFTY_FUT at 1.61 packets/s (p50 512–569ms); 43.9–46.0%
(NIFTY) / 23.1–28.8% (BANKNIFTY) of inter-packet gaps exceed 1s; max observed gap 6.6s.
- IRRECOVERABLE from this feed: the per-trade sequence inside a packet interval, true
  aggressor side per trade, individual order events (adds/cancels between snapshots).
  55–62% (NIFTY) / 35–47% (BANKNIFTY) of volume-advancing packets carry MORE volume than
  their last-trade-quantity (vol_inc > ltq) — i.e. ≥2 exchange trades collapsed into one
  packet, a LOWER bound since equal-size collapses are invisible. Max single-packet
  collapse observed: 74,230 contracts (NIFTY 07-17).
- EXACT in this feed: session-cumulative volume (monotone up to 8–13 tiny corrections/day
  of ~30–65 contracts, <0.1% of packets), per-tick OI, the LTP path at packet cadence, and
  the 5-level book per side.

## 2. BAR-CLOCK PHYSICS — tick_bar_size is a saturating PACKET clock
Ground truth (tape/bars.py:102, :81; TradeExtractor): one "trade" = one volume-advancing
PACKET, regardless of how many exchange trades collapsed into it. So `tick_bar_size` counts
snapshot-packets, and its ceiling is the packet cadence: NIFTY has only 7,613–13,136
vol-advancing packets/day, BANKNIFTY 4,317–9,001.

| size | NIFTY bars/day | NIFTY p50 dur | BANKNIFTY bars/day | BANKNIFTY p50 dur |
|---|---|---|---|---|
| 100 | ~80–95 | ~4–5 min | ~55–65 | ~6–7 min |
| 200 | 47 | 7.8 min | 31 | 11.9 min |
| 300 | 31 | 11.8 min | 21 | 18.1 min |
| 400 | 23 | 15.8 min | 15 | 23.7 min |
| 500 | 18 | 19.6 min | 12 | 30.8 min |
| 600 | 15 | 23.6 min | 10 | 38.8 min |
| 700 | 13 | 28.1 min | 8 | 45.2 min |
| 800 | 11 | 32.1 min | 7 | 54.8 min |
| 900 | 10 | 35.1 min | 6 | 42.1 min |
| 1000 | 9 | 38.8 min | 6 | 52.1 min |

NON-COMPARABILITY: a bar is N packets, and a packet at the open carries far more real
activity than a midday packet — open-15min collapse runs 64.5–86.2% (NIFTY) / 50.1–76.8%
(BANKNIFTY) vs 55–62% / 35–47% full-session, with open-window vinc p50 2–3× the session
median (NIFTY 195–390 vs 130). An "N-trade" bar at 09:20 therefore contains a materially
larger — and unequally compressed — slice of real market activity than the same-N bar at
13:00. Bars of equal tick_bar_size are NOT equal-information objects across the session.
S1000 RECONCILIATION: at size 1000 the p50 bar is 38.8–52.1 min against the 60-min
wall-clock sleeper — the exit engine acts on ~1–2 bars per position; large-size results
measure exit-machinery granularity as much as bar representation (HYPOTHESIS_LEDGER R2-15).

## 3. DELTA-FAMILY FLOORS — measured (volume-weighted, 2026-07-24 supplementary pass)
Packet-weighted zero-tick rate: 19.1–27.2% full-session. VOLUME-weighted zero-tick share w
(the honest mis-sign basis — zero-tick packets carry somewhat smaller volume):

| inst-day | full-session w | open-15min w |
|---|---|---|
| 07-16 NIFTY / BANKNIFTY | 17.4% / 17.4% | 25.8% / 15.5% |
| 07-17 NIFTY / BANKNIFTY | 18.2% / 16.0% | 12.8% / 11.5% |
| 07-20 NIFTY / BANKNIFTY | 19.7% / 15.7% | 9.8% / 10.3% |
| 07-21 NIFTY / BANKNIFTY | 16.3% / 18.5% | 15.0% / 13.0% |
| BAND | NIFTY 16.3–19.7%, BANKNIFTY 15.7–18.5% | NIFTY 9.8–25.8%, BANKNIFTY 10.3–15.5% |

FORMULA (worst measured w per instrument):
  worst-case mis-signed volume share per bar  W = w      (every zero-tick unit wrong)
  expected-case (zero-tick signs independent) E = w/2
  per-bar 95% fluctuation ≈ E ± 1.96·sqrt(E(1−E)/N_pkts)   (N_pkts = tick_bar_size)
  minimum tick_bar_size at band B: smallest N with E + 1.96·sqrt(E(1−E)/N) ≤ B
Bands B ∈ {10%, 20%} were fixed before measurement (presentation choices, not outcome-tuned):
  B=10%: NIFTY N ≥ 135,222 packets (E=9.8% sits ~at the band) — UNREACHABLE intraday
         (>13 sessions of packets in one bar); BANKNIFTY N ≥ 6,027 — also unreachable
         intraday (~1.2 sessions). A 10% expected mis-sign floor cannot be bought with bar
         size on this feed.
  B=20%: NIFTY N ≥ 34, BANKNIFTY N ≥ 29 — every menu size (100..1000) satisfies it.
Reading: the delta family carries an irreducible ~8–10% expected (16–20% worst-case)
mis-signed-volume floor at ANY intraday bar size; bar size only tames per-bar fluctuation.

## 4. OPEN-WINDOW RULE — quantified options (decision = ledger R2 item; spec only bounds)
 (a) EXCLUDE 09:15–09:30 from delta-family features: removes the window where collapse
     peaks (64.5–86.2% NIFTY / 50.1–76.8% BANKNIFTY) and where w is most unstable
     (NIFTY open w ranged 9.8→25.8% across 4 days vs 16.3–19.7% full-session).
 (b) COARSER FLOOR in-window: apply §3 with the open-window worst w (NIFTY 25.8% →
     W=25.8%, E=12.9%; B=20% then needs N ≥ 67 open-window packets — but only ~580–1,035
     vol-advancing packets exist in the whole 15-min window, so at most ~8–15 such bars).

## 5. CADENCE CONSTRAINTS
No sub-second or per-packet logic anywhere in strategy space: the feed's p50 inter-packet
gap is 0.5–0.7s and 23–46% of gaps exceed 1s, so any signal defined on sub-second timing
reads noise. Inter-packet timing below 1s = noise floor. (Velocity/duration features must
treat <1s deltas as unresolved.)

## 6. COMPONENT CLASSIFICATION
| component / family | class | why |
|---|---|---|
| P6 depth proxies (refill/cancel/wall) | PHYSICS-CLEAN | book snapshots are exact per packet |
| queue_imbalance (shadow) | PHYSICS-CLEAN | 5-level qtys exact per packet |
| pain_map / buildup (OI) | PHYSICS-CLEAN | per-tick OI exact |
| volume totals / vol profile | PHYSICS-CLEAN | cumulative volume exact (≤0.1% corrections) |
| price path / VWAP / SD bands | PHYSICS-CLEAN | LTP path exact at packet cadence |
| levels / regime (MA, VIX) | PHYSICS-CLEAN | derived from exact inputs at bar scale |
| cvd_confirm (CVD slope) | PHYSICS-BOUNDED | tick-rule signing; bounded per §3 |
| delta gate (delta+VWAP rule's delta_al) | PHYSICS-BOUNDED | same signing bound (§3) |
| tick-rule OFI (trade-side OFI) | PHYSICS-BOUNDED | §3; (book-OFI from depth = clean) |
| big_print sizing (notional per packet) | PHYSICS-BOUNDED | collapse inflates single-packet notional (§1) |
| **BAR CLOCK (tick_bar_size)** | **PHYSICS-BOUNDED** | saturating packet clock, unequal information per bar (§2) |

## 7. BINDING
Any Round-2 pre-registration touching a PHYSICS-BOUNDED family MUST cite this spec's ranges:
- R2-13 (bar-size exam): must state §2's packet-clock ceiling + non-comparability and §3's
  minimum-size table in its design; size choices below the B-band minimums require explicit
  justification against the measured w.
- Open-window ledger item (new, this spec): the §4 option chosen must cite the open-15min
  w and collapse numbers.
- Delta/CVD/OFI/big_print exams: must state the §3 floor for their bar size.
