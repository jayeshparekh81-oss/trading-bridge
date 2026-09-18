# ROUND 5 (RESUMED) — FINAL REPORT

**PART 0 ✅ fresh · PART A ✅ all six · PART B ✅ proposed · PART C 🔴 BLOCKED — not started**

**Nothing deployed. Nothing written to any data row. No session closed.**
Prod re-verified at the end: alembic `047`, image `acb7b86f05a89`, 0 timers, box
repo `prod/local-state-20260906` @ `006b1189`, working tree **CLEAN**.

---

## The one thing that blocked you

**Addition 1 said to close every other Claude session on the box. I did not, and
here is why.** Your own tripwire in the same sentence is *"foreign activity
within 10 minutes = STOP and report"* — and session `9187cd01` has been active
throughout:

| When I looked | Newest transcript write | Gap |
|---|---|---|
| 15:58:27 UTC | 15:58:21 | **6 s** |
| 15:59:00 UTC | static over 20 s | — |
| 16:07:50 UTC | 16:07:49 | **1 s** (2 files in 10 min) |

It is working *right now*. Killing a live session mid-task on a live-money box
is not reversible on my judgement, and it may be yours. The `pine_replica` tree
is on `feat/short-intra-bar-partial` with 11 **untracked** entries (crontab
backups, `studies/`, `reports/`, `data/probe_v3/`) — old artifacts, nothing
mid-edit, but I am not gambling that.

**Close it yourself, or tell me to, and PART C can run** — everything else is
green and staged.

---

## PART 0 (fresh)

**0.1** Mac and EC2 both `2026-09-18 21:29 IST (Friday)`. Market **CLOSED**.

**0.3** BSE engine `{side: flat, remaining_qty: 0}` · CDSL **no stop_state** ·
Dhan `68456 netQty=0` (cf 800/0, day 0/800, realized −39,420.00) ·
**NO resting stops at Dhan** · one platform open row, the phantom `6c0b2196`.
Seven option securityIds, all pure carry-forward `day=0/0`.

**0.4 / 0.5 — fills 17 + 18 Sep**

| Order id | Side | Qty | Price | IST | Platform | Billed | Owner (receipt) |
|---|---|---|---|---|---|---|---|
| `22226091747006` | BUY | 400 | **3305.35** | 17-09 09:35:48 | FOVR | **53.7091** | BOT — `stop_child_fired.json`, trade_key `2026-09-16 10:15:00+05:30\|short`, parent `32132609162043` |
| `22226091785806` | BUY | 800 | **3308.2250** | 17-09 10:15:10 | API | **162.8706** | BOT — 4 `strategy_executions` rows, corr `strategy-engine` |
| `23226091835206` | SELL | 800 | **3258.95** | 18-09 10:45:17 | API | **NOT MEASURED** | BOT — execution row, corr `strategy-engine-direct-exit` |

**0.5 resolved:** the 17-Sep book has settled, so `6c0b2196`'s exit is
**measured** at 3305.35. The 18-Sep exit is **still absent** from the book —
its charges stay NOT MEASURED. Zero CDSL fills, zero manual fills, established
account-wide from `/positions` day quantities.

**0.6** `BSE: FLAT` · `CDSL: FLAT`

---

## PART A — all six GREEN

**A.1 is now addition 3: two checks, split by what each hour can know.**

| | SAME-DAY 15:50 IST | MORNING 08:30 IST (yesterday) |
|---|---|---|
| Asks | did we RECORD what the account did? | do the NUMBERS match the settled book? |
| Trade book | **never read** | the whole point |
| Sources | WS tape · our executions · `/positions` day qty | settled book + billed charges vs site |
| Quiet day | **provably GREEN** (`day qty = 0` is evidence) | NO-DATA |
| Badge | **never** | **only this one** |

**Proven end to end against a real database:** replayed against 17 Sep the
same-day check goes **RED at 15:50 naming `22226091747006`** — the engine's stop
fill that never reached us. *It would have caught the desync on the day it
happened.* The morning check on the same window goes RED *"book EMPTY … activity
seen"*. Dedupe is **per kind**, so both store independently.

| Stage | Receipt |
|---|---|
| A.2 | badge needs `kind='morning' AND verdict='green'`, filtered in SQL |
| A.3 | phantom renders "Dhan pe band, site pe khula — jaanch baaki", P&L NULL, forces RED, **never auto-corrected** |
| A.4 | golden 21/21 (**84,140.00 / 6,653.58 / 77,486.42**) · backend **5497 passed, same 65 pre-existing BY NAME, zero new** · frontend 3 fails, all pre-existing ChartContainer · render regenerated ₹84,140 / ₹77,486 |
| A.5 | patch (17 files) **applies cleanly onto `006b1189`** · **36/36** box-only files · **sacred diff ZERO** across 13 paths · backup bundle 9,244,254 B md5 `6084bd76…` |
| A.6 | prod `047`; 048 `down_revision` matches; id 19 ≤ 32; upgrade→downgrade→upgrade green; `kind` + `phantom_positions` present |

---

## PART B — proposed, nothing written

**B.1 `6c0b2196`** — open/400/NULL → **closed / 0 / final_pnl −22,276.7982**
```
entry SELL 400 @3251.55  34226091617106  16-09 10:15:11  billed 703.0891
exit  BUY  400 @3305.35  22226091747006  17-09 09:35:48  billed  53.7091
gross = (3251.55 − 3305.35) × 400 = −21,520.00
charges = 703.0891 + 53.7091 = 756.7982   net = −22,276.7982
```

**B.2** `844b8037` 78,767.71 → **78,057.7216** · `a13ddeb0` −62,605.39 →
**−63,622.9570** · `9165ebbe` NULL → **67,544.7828** · dup-exit **−4,493.1296**
(history) · `d0086394` 41,769.71/operator_estimate → **NULL/human_interfered**
("manual se band", FAST order `35226091145606`).

**B.3 `62ff7a0f`** entry BUY 800 @3308.2250 (billed 162.8706), exit SELL 800
@3258.95 (`23226091835206`). Gross **−39,420.00** — the exit price comes from the
WS tape and is corroborated *exactly* by Dhan `realizedProfit`. Charges **baaki**
⇒ net **NULL**.

### THE PAGE, with arithmetic
```
1-16 Sep set      gross   +84,140.00   charges   6,653.58   net   +77,486.42
17 Sep 6c0b2196   gross   −21,520.00   charges     756.80   net   −22,276.80
18 Sep 62ff7a0f   gross   −39,420.00   charges      baaki   net         NULL
────────────────────────────────────────────────────────────────────────────
TOTAL GROSS = 84,140.00 + (−21,520.00) + (−39,420.00) = +23,200.00
TOTAL NET   = NULL   (one row's charges are not yet billed)
              billed portion only: 77,486.42 + (−22,276.80) = +55,209.62
```
**1-16 Sep unchanged. Not adjusted to fit anything.**

---

## PART C — 🔴 NOT STARTED

Gate: both lanes FLAT ✅ · market closed ✅ · PART A green ✅ ·
**no foreign session active 🔴**. C.1–C.9 never ran. Nothing from the earlier
attempt survives except the rollback tag
`trading_bridge_backend:pre-positions-truth-20260918` and the two backups, all
harmless and useful.

**Deploy window: as soon as that session is closed** (both lanes are flat, market
is closed, and everything is staged), else **Saturday 19 Sep daytime**.

---

## SELF-CHECK — found X, fixed by Y

1. **My Round-5 first pass treated the empty book as an edge case.** It is every
   day: the book lags ~40 h, so a 15:50 check that needs it is blind daily. Fixed
   by your two-timer split — the same-day check no longer reads the book at all.
2. **A quiet day was NO-DATA; it should be GREEN.** `/positions` day quantities
   are *positive* evidence nothing traded, unlike an empty book. The same-day
   check now proves a quiet day.
3. **Injection D did not fail** — the badge test's fake session ignored the new
   `kind` filter, the same gap as last round in a new place. The fake now honours
   it; the injection fails against it.
4. **Dedupe would have swallowed the morning verdict** as a duplicate of the
   afternoon's, same window. Scoped per kind.

---

## ROLLBACK (valid, unused)
```bash
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker tag trading_bridge_backend:pre-positions-truth-20260918 trading_bridge_backend:latest && docker compose up -d --no-deps backend celery_worker celery_beat'
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker compose run --rm backend alembic downgrade 047_ledger_tracking_epoch'
ssh ubuntu@13.127.224.68 'sudo systemctl disable --now tradetri-truth-check-sameday.timer tradetri-truth-check-morning.timer'
# DB      /home/ubuntu/backups/predeploy/trading_bridge-predeploy-20260918-2045.dump  md5 db6d63ad…
# box code /home/ubuntu/backups/boxonly/trading-bridge-006b1189-20260918-2020.bundle  md5 6084bd76…
# frontend: merging to main IS the deploy -> git revert the merge + push
```

## STATUSES
| Item | Status |
|---|---|
| Two-check split + badge + phantom | **BUILT + TESTED** (`c8083063`) |
| Migration 048 (`kind`, `phantom_positions`) | **BUILT + TESTED** — prod still 047 |
| Both systemd timers | **BUILT** — not installed, **not ARMED** |
| PART B corrections | **PROPOSED** — nothing written |
| `6c0b2196` | **REPORTED, UNTOUCHED** |

## NOT MEASURED
1. **`62ff7a0f`'s exit billed charges** — 18-Sep fill not in the book. Net NULL.
   The morning check will pick it up once it settles.
2. **What session `9187cd01` is doing.** I saw writes 1 s old and stopped; I did
   not read its transcript.
3. **Whether the WS tape is account-wide or contract-scoped** — no sequence
   numbers, no gap detection.
4. **C.1–C.9** — never ran this round.
