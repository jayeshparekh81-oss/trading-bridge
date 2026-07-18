# orderflow_engine — MASTER HANDOFF

**Consolidated entry point.** Paste this into any new chat to reconstruct state. It links and
summarizes the platform handoff + the orderflow build (R0→R8) + fences + pending work. It is a
**reference index** — the source docs below are authoritative; this file points at them.

_Last updated: 2026-07-18. Branch `feat/orderflow-r7-alerts` @ `b2fc49a`._

---

## 0. TL;DR — current state (2026-07-18)

- **Branch / HEAD:** `feat/orderflow-r7-alerts` @ `b2fc49a` (tip; `main` is behind — nothing merged to main).
- **Everything is INERT.** The engine ships fenced off: no signal fires, no order routes, no alert
  sends. See §3.
- **Frozen research baseline:** 17 clean trades, **+2.017R gross** (in-sample, in-memory OFI-on /
  threshold-40, 07-15/16/17). This is the locked reference — do NOT let any change move it.
- **The core finding:** the confluence scorer does **not** rank winners yet (score≠outcome, proven 3
  independent ways). The 15-day calibration set (~**31 Jul 2026**) exists to answer "does ANY signal
  rank out-of-sample?" *before* any weight/threshold is tuned. See §5.
- **Menu is CLOSED:** no component/weight/threshold is activated without an explicit gate.

---

## 1. Platform state (separate track — customer platform / LIVE money)

Authoritative: [`../docs/SESSION_HANDOFF.md`](../docs/SESSION_HANDOFF.md) — last modified **2026-07-06**,
newest content dated **2026-06-26**. Does **not** cover orderflow (predates it).

- Customer platform (TRADETRI) is a **different track**; **BSE Ltd strategy (89423ecc) is LIVE REAL
  MONEY on Dhan**. Sacred files (is_paper, strategy_executor, direct_exit, webhook, kill_switch,
  broker adapters, migrations) — never modify without an explicit `is_paper=false confirmed` gate.
- Last platform one-line state (SESSION_HANDOFF §8): Queue CCC Sprint 2 + Phase 3 skeleton pushed on
  `feat/queue-ccc-historical-candles-skeleton`; migration 030 applied; 22 backfill jobs enqueued;
  main merge deferred to founder.
- **orderflow_engine is isolated** from that live path (offline/record-only; the tape/signals layer
  never runs in the live recorders). Zero runtime risk to R0/R1 or to the live strategy.

---

## 2. Orderflow build — module lineage R0 → R8

| Mod | What | Status | Doc |
|---|---|---|---|
| **R0** | Tick recorder (spot + near-month fut + ATM±20 CE/PE + INDIA VIX; per-tick incl. OI) | LIVE (record-only) | [`README.md`](README.md) |
| **R1** | 20-level market-depth recorder (separate container, journal-only) | DEPLOYED — built 2026-07-11 | [`OPS_NOTES.md`](OPS_NOTES.md) §5 |
| **R2** | Deterministic replayer (consumer contract; G1 hash `faf6d8b8…` on 07-09) | built | — |
| **R3** | Tape engine (bars/CVD/velocity/OFI/big-print/footprint) | built 2026-07-11 | [`TAPE_NOTES.md`](TAPE_NOTES.md) |
| **R4** | Levels & context (VWAP±SD / value-area intraday; pivots+PDH/PDL daily) | built | `TAPE_NOTES.md` |
| **R5** | Option-chain analytics (offline BSM IV/Greeks + PCR / max-pain / GEX / buildup) | built | `TAPE_NOTES.md` |
| **R6** | Confluence signal engine — "the brain" (9 components, gates, exits, glass-box) | built | `TAPE_NOTES.md` |
| **R7** | Alerts (SIGNAL alerts + Daily Pulse) | built | `TAPE_NOTES.md` |
| **R8** | Paper executor (sizing / risk / ledger / TCA) | built, **INERT** | `TAPE_NOTES.md` |

Ops/incidents: `OPS_NOTES.md` §3 — 07-09 disk-full, 07-10 host-hang (OOM), 07-13 partial (DISK_FULL
14:33). The full calibration narrative + all findings live in `TAPE_NOTES.md` (large; see §5).

---

## 3. Config fences (verified on disk, 2026-07-18)

Everything that could act is off. `tape_config.yaml` + `signals/config.py`:

| Fence | Value | Meaning |
|---|---|---|
| `signal.fire_threshold` (long/short) | **999 / 999** | INERT — nothing fires live |
| `tape.depth.ofi_enabled` | **false** | OFI off by default (on only via in-memory research override) |
| `tape.bigprint.mode` / `notional_threshold` | **fixed / 0** (all classes) | big_print INERT (percentile machinery built, not armed) |
| `signal.components.queue_imbalance.weight` | **0.0** | wired (value plumbed) but INERT — changes no trade |
| `signal.r8.enabled` | **false** | paper executor dormant (no sizing/exec) |
| `alerts.enabled` / `alerts.pulse_enabled` | **false / true** | no signal sends; only ops Pulse |

Rule: **no fence flips without an explicit gate.** big_print was measured ON and it *hurt*
(−4.879R via winner crowd-out) — stays inert. See `TAPE_NOTES.md` "DNA of the DEAD COMPONENTS".

---

## 4. Branch / recent history

`feat/orderflow-r7-alerts` tip commits:
```
b2fc49a  pre-register bar-representation + noise-efficiency study (15-day set)
ee0d2e3  Merge feat/orderflow-queue-wire: queue_imbalance wiring (INERT, weight 0) + DNA log
e4600a1  log DNA of dead components + big_print WORSE-when-on evidence + the path
d2dd54e  wire queue_imbalance into tape bars + signal context (INERT, weight 0)
4a3ee75  log THE REFRAME — does any signal rank at all?
```
Full suite: **561 passed, 2 skipped**. Nothing merged to `main`.

---

## 5. The core finding + THE REFRAME (why the 15-day set matters)

Proven **3 independent ways** that SCORE ≠ OUTCOME on the N=17 baseline:
1. Winner-separation ≈ 0 at N=17; 2. all 17 trades are structurally the *same* trade (OFI+CVD+regime
are collinear → 40 of 65 points is one idea, big_print/queue contribute nothing); 3. score vs gross R
Spearman **−0.140** (faintly negative — the top-scorer, 50.6, lost).

**THE REFRAME (TAPE_NOTES lead entry):** the only predictor that ranks is **stop-width**
(R-unit% Spearman **+0.777**, the one number clearing significance) — and even that is mechanically
"tight stops get noised out" (trade *structure*, not tape-reading). Every flow signal ranks ≈ zero
(|OFI| ρ=+0.120, score ρ=−0.140). So the 15-day set's FIRST question is **"does ANY signal rank
out-of-sample?"** — establish that *before* tuning any weight/threshold. If nothing ranks, no
calibration saves it.

---

## 6. Pending items / the sequenced path (all post-15-day, harness-gated)

1. **queue_imbalance — WIRED ✅** (INERT, weight 0). Value now flows to bars + context for calibration.
2. **big_print — stays INERT.** Do NOT flip to percentile (measured −4.879R via gate crowd-out). Real
   path = required-confirmer + loss-aware gate (design), not a switch.
3. **OFI percentile-rank** experiment (it saturates in the firing region; percentile-rank like
   big_print got) — 15-day experiment.
4. **Decorrelate** OFI/CVD/regime + make **location a gate/multiplier** (design).
5. **🔬 Bar-representation + noise-efficiency study** (pre-registered): tick sweep 100/200/300/500/1000
   + event bars; Kaufman Efficiency Ratio as diagnostic + chop-gate; plateau + Deflated-Sharpe gated.
6. **Gate hygiene:** cooldown is loose/outcome-blind (300s allows 3 same-direction entries in 14 min;
   no loss-aware cooldown / re-entry lock) — candidate GATE change, not a signal change.

Discipline for all: replay/research only; frozen baseline untouched; every sweep through
walk-forward OOS + permutation null + Deflated Sharpe + plateau; pay the N-trials burden. Menu CLOSED.

---

## 7. Doc index (authoritative sources)

- Platform / live money: [`../docs/SESSION_HANDOFF.md`](../docs/SESSION_HANDOFF.md)
- Orderflow ops + incidents + R1: [`OPS_NOTES.md`](OPS_NOTES.md)
- Orderflow R0 recorder: [`README.md`](README.md)
- Calibration findings + REFRAME + DNA + pre-registered studies (the big one): [`TAPE_NOTES.md`](TAPE_NOTES.md)
- Repo rules: [`../CLAUDE.md`](../CLAUDE.md)

_This is a reference index only — no code, config, or component changed to create it._
