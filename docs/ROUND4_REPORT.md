# ROUND 4 — REPORT. NOTHING DEPLOYED.

**Status: STOPPED before A1.** Not "stopped after A10" — I could not start A1.
Prod re-verified unchanged at the end: alembic `047`, image `acb7b86f05a89`, crontab md5
`ad7ec3fa…`, 0 new tables, 0 new timers, box HEAD `006b1189` (36 files) on
`prod/local-state-20260906`, working tree clean, `fix/ses-role-chain-20260917` = `b32eedd8`,
`itmgr/20260917-watchdog-html-escape` = `350fe579`. No data row was written.

---

## 1. WHY NOTHING RAN — four independent blockers

| # | Blocker | Receipt |
|---|---|---|
| **B-1** | **The mandate file does not exist.** `~/Downloads/TRADETRI_POSITIONS_TRUTH_ROUND4_DEPLOY.md` is absent; a full search of Downloads/Desktop/Documents/repo/scratchpad finds no ROUND4 file of any name. Only `TRADETRI_POSITIONS_TRUTH_ROUND3.md` is there. **I do not know what A1–A10 or B0–B9 are and will not invent them.** | `find` over 5 roots → 0 hits |
| **B-2** | **Rule 21 — open-position gate.** BSE 89423ecc holds an open position NOW. PART B necessarily touches containers, image and DB (migration 048 + rebuild + restart + timer), so rule 21 bars it. | `ops/kb/RULES.md:50`; `stop_state.json` → `remaining_qty: 800, side: long`; `strategy_positions` open rows = 2 |
| **B-3** | **Foreign session active on the box.** The tradetri-engineer session is live — `ccd-cli` PIDs started 17-09 14:42 and 19:50 IST, transcript `9187cd01-…jsonl` written within the last 30 min. Your rule 7: present ⇒ STOP. I did not touch it. | `ps -eo pid,lstart,cmd`; `find … -mmin -30` |
| **B-4** | **Date.** Your message says "TODAY 17 SEP". It is **Fri 18 Sep, 04:33 IST** on both this Mac and EC2. Your 15:45 IST gate is ~11 h away; if you meant 17 Sep, that window closed. | `date` on both hosts |

Rule 21's own text records it was decided *"when he said NA to a same-night restart with an
800-qty BSE long open (17 Sep)"* — that is the very position still open.

**Earliest lawful PART B window:** a weekday evening after 17:35 IST with **both lanes flat**,
else **Saturday daytime**. CDSL is already flat (no `stop_state.json`). BSE is not.

---

## 2. TODAY'S TRADES (17 Sep) — read-only, addition #2

### (a) Every fill

| Order id | Sec | Symbol | Side | Qty | Fill price | IST | Platform | Billed | Owner |
|---|---|---|---|---|---|---|---|---|---|
| `22226091747006` | 68456 | BSE-Sep2026-FUT | **B** | 400 | **3305.35** *(derived)* | 09:35:48 | FOVR | **absent** | **BOT** — BSE 89423ecc |
| `22226091785806` | 68456 | BSE-Sep2026-FUT | **B** | 800 | **3308.2250** | 10:15:10 | API | **absent** | **BOT** — BSE 89423ecc |

**Two fills, one instrument, nothing else.** Proven account-wide, not assumed: Dhan
`/positions` shows `dayBuy/daySell = 0/0` on **all seven option securityIds** — every one is
pure carry-forward. Total day activity on the account = 1200 buys on 68456. **Manual = 0.**

**Owner receipts.**
* `22226091785806` → four `strategy_executions` rows (qty 200 each, same broker order id,
  `leg_role=entry`, placed 17-09 10:15:11, strategy 89423ecc). Ours by our own record.
* `22226091747006` → tape `algoOrdNo` `32132609162043` → claimed in
  `pine_replica/executor/state/stop_child_fired.json` as
  `{trade_key: "2026-09-16 10:15:00+05:30|short", order_id: 32132609162043,
  status: PART_TRADED, at: 2026-09-17T09:35:48+05:30}` and in `BROKER_STOP_SPENT.json`.
  That `trade_key` **is** position `6c0b2196`. Ledger receipt, not shape inference.

⚠️ **On the 3305.35.** The tape's `tradedPrice` for that order is 3305.4, but that is its
LAST trade, not its average — proven by the sibling order, which shows `tradedPrice 3308.9`
vs `avgTradedPrice 3308.23`. 3305.35 is **derived** from Dhan's own aggregate
`(3307.2666667 × 1200 − 800 × 3308.2250) ÷ 400`. **No source reports the 400-order's average
directly.**

### (b) Legs, balance and net

* `6c0b2196` (SELL 400): **legs do NOT balance** — entry 400, exits recorded **0**, while 400
  left the position at the broker. **A bot fill is missing on the platform.**
* `62ff7a0f` (BUY 800): balanced — entry 800, open, no exit expected yet.
* **Broker net vs bot net: `+800` vs `+400`.** The platform carries a **phantom SHORT of 400
  the broker does not have.** Manual term = 0.
* **No duplicate-exit shape.** One 400 exit against one 400 entry; no exit qty exceeds entry
  qty anywhere today.

### (c) CDSL — does not arise

**Zero CDSL fills.** Not argued from a missing log file (that was the old CDSL-blindness
error) but from the account: every non-68456 securityId shows `dayBuy=0/daySell=0`.
CDSL 0252e82c has 8 position rows, newest **2026-07-24**. Its lane is flat/disarmed
(no `stop_state.json`). **The CDSL lane has still not placed its first real order.**

### (d) Charges

**Worse than "baaki", and I had this wrong at first.** Dhan's `/trades` returns **0 rows for
2026-09-17 — all pages, unfiltered** — while returning 4 rows for 15 Sep and 3 for 16 Sep
through the same endpoint. So it is not that the bill is pending; **the fill-of-record does
not exist**. "Baaki" means the fill is in the book and only the bill is outstanding — the
milder state, and claiming it would err in the flattering direction.

Charge fields **do** populate on this account (all 7 settled rows carry all six). Notably
`34226091617106` — `6c0b2196`'s own **entry** leg — is billed **703.0891**. So the exit's
charges should appear when 17-Sep settles. **Re-pull `/trades` for 2026-09-17 then; until it
returns rows, this trip stays unpriced.**

---

## 3. TWO REDs ON LIVE STATE

**RED-1 — `6c0b2196` is a phantom short.** Section 2(b). Independently confirmed: Dhan
`realized −22,286.67 = (3251.55 − 3307.266667) × 400` matches to the paisa, and `cfSell=400,
dayBuy=1200, daySell=0` shows the carried short was covered by a day buy. The platform's own
`reconciliation_loop.py:321` detects exactly this shape and is **observer-only** — nothing
will self-heal it.

**Mitigating, and good news:** pine_replica already noticed. At 09:45 IST it recorded
`EXIT SUPPRESSION … for 2026-09-16 10:15:00+05:30|short` and cancelled the stop on confirmed
flat, reasoning *"A closing order now would OPEN the opposite position from flat."* So the
engine will not act on the phantom.

**Per your rule 9 I changed nothing.** Reporting and waiting for your haan.

**RED-2 — the 15:50 truth check would have reported a FALSE GREEN for 17 Sep.**
Reproduced locally:

```
evaluate([], stored={}, tape_covered=set())
  verdict green · fills_checked 0
  "TRADETRI = DHAN ✅ 2026-09-17 0 fills"
```

On the very day a live position silently desynced. Addition B's guard cannot catch it —
it reads `if fills and not tape_loaded`, and `fills` is empty. It is also worse than a missed
alert: the green would be **stored**, and a stored agreeing run is exactly what licenses the
"Dhan se verified ✅" badge. **This blocks arming the timer.** The fix must cross-check an
independent witness (the tape had 8 frames; `/positions` day quantities moved) — book empty +
tape non-empty ⇒ RED. Note `dhan.py:944` already says `/trades` "can be paginated/incomplete
and must NOT be used" as ground truth; my check trusted it anyway.

---

## 4. WHAT I GOT WRONG (caught by an adversarial pass over my own findings)

1. **"charges baaki, net NULL"** — wrong state, in the flattering direction. Correct:
   **not priced / unpriceable**, because the fill is absent from the settled book entirely.
2. **"bought 400 @3305.40"** — that is the tape's last-trade price, not the fill average.
   Derived average is **3305.35**.
3. **"gross −21,540.00"** — follows from the wrong price. See section 5.
4. **"FOVR + algoOrdNo ⇒ the engine's stop"** — a shape inference this repo forbids twice in
   words (`__main__.py:172`, `service.py:681`), and two existing tests pin it as wrong. A
   hand-placed Dhan GTT also fires FOVR with an algoOrdNo. I then ran the ledger grep and
   **did** find the receipt, so the conclusion stands — but it stands on the ledger, not the shape.
5. **"No CDSL fill (no tape file)"** — absence of a log is not absence of activity. Re-grounded
   on `/positions` day quantities.

---

## 5. TOTALS — addition #3

**1–16 Sep is UNCHANGED, and was not adjusted to fit anything:**

```
GROSS 84,140.00 − CHARGES 6,653.58 = NET 77,486.42
```
Golden replay 21/21 pass. `6c0b2196` was OPEN in that set and contributed nothing; its close
belongs to 17 Sep, so the set is untouched by construction.

**17 Sep, reported separately:**

| | |
|---|---|
| `6c0b2196` closed | gross **NOT MEASURED** — no trade-book row exists |
| — indication only, leg-matched | (3251.55 − 3305.35) × 400 = **−21,520.00** |
| — Dhan average-cost realised | **−22,286.67** (blends the still-open 800's entry; a different quantity, not this trade's P&L) |
| — charges | absent from the book |
| — net | **NULL** |
| `62ff7a0f` open | BUY 800 @3308.2250, no exit, no P&L |

**Live page total today would be: 1–16 Sep set + one unpriced row.**
`GROSS 84,140.00 + (not measured)`, `NET 77,486.42 + NULL = NULL`.
Neither indication above may be published as the trade's P&L.

---

## 6. ROLLBACK COMMANDS — still valid, unused

```bash
# BEFORE any build (tag the running image first)
ssh ubuntu@13.127.224.68 'docker tag trading_bridge_backend:latest trading_bridge_backend:pre-truth-check-20260918'

# Backend rollback
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker tag trading_bridge_backend:pre-truth-check-20260918 trading_bridge_backend:latest && docker compose up -d --no-deps backend celery_worker celery_beat'
#  + alembic downgrade -1   (only if 048 was applied)

# Timer rollback
ssh ubuntu@13.127.224.68 'sudo systemctl disable --now tradetri-truth-check.timer'

# Frontend: merging to main IS the deploy. Roll back at vercel.com ->
#   trading-bridge -> Deployments -> the row for the target commit -> ... -> Promote to Production
```

⚠️ **Rule 8 changes my Round-3 deploy plan.** Box HEAD `006b1189` (36 files, on **no remote**)
must be the build base. A build that checked out `main` would silently drop all 36. Verified
now: HEAD **is** `006b1189`, tree clean, and both engineer branches contain it. Any future
build must re-verify the 36 files are present in the image afterwards.

---

## 7. STATUSES

| Item | Status |
|---|---|
| Round-3 code (R1–R6) | **BUILT + TESTED** — not deployed, not armed |
| Migration 048 | **BUILT** — not applied (prod still `047`) |
| 15:50 truth check | **BUILT + TESTED, BLOCKED** — false-green defect must be fixed before ARMED |
| Frontend R4 render | **BUILT + TESTED** — not deployed |
| A1–A10 / B0–B9 | **NOT STARTED** — mandate file missing |
| `6c0b2196` desync | **REPORTED, UNTOUCHED** — awaiting your haan |

---

## 8. NOT MEASURED

1. **The 400-order's true average fill price.** Derived (3305.35), never directly reported.
   Settles when the 17-Sep book appears.
2. **Why the 17-Sep book is empty.** Not settlement-dating — a 14→18 Sep window also returns
   nothing for 17 or 18.
3. **Whether the WS tape is account-wide or contract-scoped.** It has no sequence numbers and
   no gap detection, so "8 frames = the whole day" is unproven. `/positions` day quantities
   corroborate it for 17 Sep, but that is a second source, not a completeness proof.
4. **Whether anything alerted on 17 Sep.** The truth check is not armed; whether the
   reconciliation loop's drift alert fired and reached you is unverified.
5. **What the platform would do with the phantom short** if an exit-class signal, kill-switch
   sweep or expiry backstop touched it. The engine has suppressed its side; the platform side
   is untraced.
6. **A1–A10 / B0–B9 content.**

---

## 9. WHAT I NEED FROM YOU

1. **The Round-4 mandate** — paste it, or re-save the file. I will not guess the stages.
2. **The date** — "today 17 Sep" vs the clock's 18 Sep, and whether 15:45 IST means today.
3. **`6c0b2196`** — say the word and I will propose (not apply) the smallest correction.
4. Acknowledge that **PART B cannot run while BSE holds the 800 long** (your rule 21).
