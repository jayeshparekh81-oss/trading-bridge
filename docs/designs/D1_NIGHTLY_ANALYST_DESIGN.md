# D1 — NIGHTLY ANALYST DESIGN (Layer-2; live-LLM stays EXCLUDED)
DESIGN-ONLY DRAFT — written before any Market-DNA number exists. Zero outcome numbers.
Nothing enabled anywhere; window-safe.

## What it is
A post-session AI ritual: every evening AFTER close (post-pipeline, ~17:00+ IST), an
analyst pass READS that day's recorded artifacts and WRITES a dated, observations-only
diary. It may PROPOSE hypotheses — every proposal must be written as a ledger-format
entry and must earn its own fresh pre-registered exam before anything else happens.
It can NEVER touch config, thresholds, or live code. It is a diary + proposal
generator, not an actor.

## Inputs (read-only, that day only)
ticks + depth parquets; chain snapshots (R5 sensors: dOI windows, PCR, buildup,
max-pain, IV); shadow component activations (qi, pain_map, book_ofi from the
breakdown); health metrics (watchdog v2 verdict, report.json coverage, depth verify);
FEED_PHYSICS + HEALTH_CARD bounds as standing context.

## Output format (one file per session day)
research_scratch/nightly/<date>.md with EXACTLY three sections:
  1. OBSERVATIONS — dated, numbers-with-provenance, no interpretation verbs beyond
     "measured/counted/ranked".
  2. ANOMALIES — deviations from standing bounds (FEED_PHYSICS/HEALTH_CARD), each
     with the bound cited.
  3. PROPOSALS (0..n) — each in ledger binding format (below); no proposal may
     reference outcome/PnL of any live or frozen-window day.

## Hard fences
- ACTIVATION: post-window only — first run AFTER the 12-Aug window's eval;
  never runs on frozen-window days pre-eval.
- Runs POST-CLOSE only; never during 09:00-15:45 IST.
- Read-only on data/; writes only its own diary file (+ ledger drafts for review).
- May not read the frozen OOS window's evaluator outputs until window closes.
- May not edit HYPOTHESIS_LEDGER/TAPE_NOTES itself — proposals are pasted for founder
  review, founder commits.
- No config/threshold/live-code writes, ever. No orders, no alerts beyond its diary.

## Ledger binding-format entry (this design itself)
- id: R3-02 (EXPANDED — replaces the one-line "Nightly Analyst ritual" stub)
- observation: post-close artifacts are rich (ticks/depth/chain/shadows/health) but
  nothing systematically reads them nightly; hypothesis generation is ad-hoc.
- mechanical rule: nightly diary with the 3-section format above; proposals only in
  binding format; founder gate on every ledger admission.
- parameters-to-freeze: run time (post-close trigger), input list (above), diary
  format version, proposal quota cap per night (propose: <=3).
- exam design (its own Round-2 exam): binding metric = SURVIVAL rate — proposals
  passing their own later pre-registered exams vs null proposals passing theirs
  (null = random-plausible proposals, same count, pre-listed space). Admission rate
  = descriptive only (founder-gated => circular). Pre-register N before the first
  scored night.
- what-would-kill-it: proposals that are re-skins of already-burned hypotheses;
  admission rate indistinguishable from the random-proposal null; any fence breach
  (config touch / in-window read) = immediate retirement.

## Explicitly excluded
Layer-3 (live-LLM in the loop) stays excluded — no in-session AI anywhere.
