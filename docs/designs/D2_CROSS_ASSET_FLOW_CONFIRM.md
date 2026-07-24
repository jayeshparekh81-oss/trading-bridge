# D2 — CROSS-ASSET FLOW CONFIRM (futures ↔ options razamandi), minutes scale
DESIGN-ONLY DRAFT — pre-Market-DNA. Zero outcome numbers. Nothing enabled.

## Idea (mechanical, no discretion)
A frozen AGREEMENT rule between the futures-side flow state and the option-side state,
used ONLY as a CONFIRM/VETO overlay on an existing (separately pre-registered) entry —
never as its own trigger. "Razamandi" = both sides of the market telling the same
story at the minutes scale.

## The two sides
- FUTURES-SIDE STATE (per bar): sign of bar delta + price-vs-VWAP side (the surviving
  pair) — PHYSICS-BOUNDED per FEED_PHYSICS §3 (~8-10% expected mis-signed-volume
  floor at any intraday bar size; cite in any exam).
- OPTION-SIDE STATE (per chain grid, R5 sensors, all PHYSICS-CLEAN per FEED_PHYSICS
  §6 — per-tick OI is exact): direction votes from (i) dOI_w2 (5-min) sign at ATM±K
  CE vs PE, (ii) PCR-OI change sign over the same window, (iii) buildup-matrix
  majority label ONCE the fuel fix lands (prerequisite: R2-03's first-grid ltp=None
  repair), (iv) max-pain-side of price. NOTE: R2-03 probe evidence (NIFTY inverse @0.1st
  pctile, BANKNIFTY sign-flip = noise signature) stands as PRIOR AGAINST the
  max-pain vote; retained deliberately — the bundle exam adjudicates.

## Frozen rule shape
CONFIRM if >= M of the 4 option votes agree with the futures-side state within the
same W-minute window; VETO if >= M agree AGAINST it; else NEUTRAL (no effect).

## Parameters-to-freeze (before ANY data)
M (votes required, propose 3-of-4), W (window minutes, propose 5), K (ATM±K strikes
pooled, propose 5), the exact vote definitions above (each one sentence, no
alternatives), tie behavior (exact-zero dOI/PCR change = abstain, not a vote),
and the host rule: overlay applies to ALL fired candidates of the frozen baseline config.

## Ledger binding-format entry
- id: R2-16 (new)
- observation: futures-side flow signals and option-side OI/positioning sensors are
  recorded on independent feeds with different physics classes; no exam has tested
  their AGREEMENT as information.
- mechanical rule: the M-of-4 agreement CONFIRM/VETO overlay above, frozen shape.
- parameters-to-freeze: M, W, K, vote definitions, tie behavior, host entry rule.
- exam design: Round-2, FRESH BLIND DATA ONLY (post-window sessions never seen by
  any prior study); per-instrument; full harness (permutation null on the
  confirm/veto labels, DSR with the trial count of {M,W,K} if more than one set is
  ever run — prefer exactly ONE frozen set).
- what-would-kill-it: confirm-set vs veto-set outcomes indistinguishable from a
  shuffled-label null; or the overlay's effect fully explained by trading-less cost
  mechanics (must run the random-removal null per the NEG-01 precedent).

## Physics note (mandatory citation in the exam)
Futures delta-family input is PHYSICS-BOUNDED (mis-sign floor ~8-10% expected);
option-side OI family is PHYSICS-CLEAN. The exam must therefore attribute any failure
mode correctly: a dead futures side is expected physics; a dead option side is not.
