# ROUND 5 — FINAL REPORT

**PART 0 ✅ · PART A ✅ (all six) · PART B ✅ proposed, nothing written · PART C 🔴 STOPPED AT C.3**

**Nothing was deployed. Nothing was written to any data row.** The box was restored to
exactly the state I found it in, verified line by line.

---

## PART 0 — MEASUREMENTS

**0.1 Clock.** Mac and EC2 both `2026-09-18 20:20 IST (Friday)`. Market **CLOSED**
(outside 09:15–15:30). *Note: your mandate says "Fri 18 Sep, 19:22 IST"; work began 20:20.*

**0.2 Foreign session.** At the start: newest transcript **13 h 10 m old**, every
claude/ccd process sleeping or zombie at ~0 % CPU, no repo edits. Judged **not active** →
PARTS A and B proceeded. **This changed later — see PART C.**

**0.3 Live position state.**

| | |
|---|---|
| `pine_replica/executor/state/stop_state.json` | `{side: flat, remaining_qty: 0, trade_key: ""}` |
| `pine_replica_cdsl/.../stop_state.json` | **no file** — lane flat/disarmed |
| Dhan `/positions` 68456 | **netQty 0**, buy 800 / sell 800, cf 800/0, day 0/800, realized −39,420.00 |
| Resting stops at Dhan (`/forever/orders`) | **NONE** — correct, nothing is open |
| Platform open/partial rows | **1** — `6c0b2196`, the phantom |

Seven short **option** positions exist (60319, 60321, 60322, 60425, 82377, 94173, 94176),
all pure carry-forward, `dayBuy=0/daySell=0`. Other instruments, not this strategy.

**0.4 Fills, 17 + 18 Sep.**

| Order id | Sym | Side | Qty | Price | IST | Platform | Billed | Owner (receipt) |
|---|---|---|---|---|---|---|---|---|
| `22226091747006` | 68456 | BUY | 400 | **3305.35** | 17-09 09:35:48 | FOVR | **53.7091** | **BOT** — `stop_child_fired.json` claims parent `32132609162043`, trade_key `2026-09-16 10:15:00+05:30\|short` |
| `22226091785806` | 68456 | BUY | 800 | **3308.2250** | 17-09 10:15:10 | API | **162.8706** | **BOT** — 4 `strategy_executions` rows, corr `strategy-engine` |
| `23226091835206` | 68456 | SELL | 800 | **3258.95** | 18-09 10:45:17 | API | **not in book yet** | **BOT** — execution row, corr `strategy-engine-direct-exit` |

**Zero CDSL fills, zero manual fills**, established account-wide from `/positions` day
quantities (every other securityId `day=0/0`), not from a missing log file.

**0.5 `6c0b2196`'s true fill price — RESOLVED, no longer NOT MEASURED.** The 17-Sep book
settled between Round 4 and now: `22226091747006` **BUY 400 @ 3305.35, billed 53.7091**,
straight from Dhan's trade book. My Round-4 *derived* 3305.35 was right, but it is now
**measured**, which is what counts. (Sources tried: trade book ✅; `/orders` book — empty,
day-scoped; `/orders/{id}` — returns nothing on this account.)

**0.6 GATE.**
```
BSE:  FLAT   (Dhan netQty=0, engine flat, no resting stops)
CDSL: FLAT   (no stop_state, no activity since 24-Jul)
```

---

## PART A — ALL SIX GREEN

| Stage | Verdict | Receipt |
|---|---|---|
| **A.1** false-green fix | ✅ | 17-Sep replayed ⇒ **RED** "book EMPTY … activity seen (WS tape frames=8, day quantity=1200, executions=4) — we are blind, not clean". Quiet day ⇒ **NO-DATA** (`DEKHA NAHI JA SAKA ⬜`), never green. 34 tests. |
| **A.2** badge only from GREEN | ✅ | `_AGREEING_VERDICTS = ("green",)`. ATTENTION and NO-DATA both excluded. 11 tests. |
| **A.3** phantom handling | ✅ | Renders "Dhan pe band, site pe khula — jaanch baaki", P&L NULL, truth check RED. **No auto-correction anywhere.** |
| **A.4** re-run | ✅ | Golden 21/21 (**84,140.00 / 6,653.58 / 77,486.42**). Backend 5482 passed, **same 65 pre-existing by name, zero new**. Frontend 3 fails, all pre-existing ChartContainer. Render regenerated: GROSS ₹84,140 / NET ₹77,486. |
| **A.5** deploy-base safety | ✅ | App patch (17 files) **applies cleanly onto `006b1189`**; **36/36** box-only files present; **sacred diff ZERO** across 13 paths vs the real base. Backup: bundle 9,244,254 B md5 `6084bd76…` ("records a complete history"), tar 142,104 B md5 `efb5710d…`, file list md5 `80aa159e…`, at `/home/ubuntu/backups/boxonly/`. |
| **A.6** migration 048 | ✅ | prod `alembic current` = `047_ledger_tracking_epoch`; 048's `down_revision` matches; id 19 chars ≤ 32; upgrade→downgrade→upgrade all green on scratch; `phantom_positions jsonb` present. |

🔴 **A.5 found something Round 3 got wrong.** Round 3 measured its sacred diff against
`fffc1bf3`. The real deploy base is `006b1189`, a **divergent line** (`fffc1bf3` is not its
ancestor; merge-base `1b5c3ffe`). A plain `git merge` produces **10 conflicts**. Measured
properly, the genuine overlap is only **5 files, all tests** — zero application-code
overlap — so the app patch applies cleanly. Re-measured against the correct base, the
sacred diff is still **ZERO**.

---

## PART B — PROPOSED (nothing written)

**1–16 Sep — UNCHANGED, not adjusted to fit anything:**

| Row | before `final_pnl` | gross | billed | **after** |
|---|---:|---:|---:|---:|
| `844b8037` | 78,767.7100 | 80,360.00 | 2,302.2784 | **78,057.7216** |
| `a13ddeb0` | −62,605.3900 | −61,020.00 | 2,602.9570 | **−63,622.9570** |
| `9165ebbe` | NULL | 69,160.00 | 1,615.2172 | **67,544.7828** |
| dup-exit | (history only) | −4,360.00 | 133.1296 | **−4,493.1296** |
| **TOTAL** | | **84,140.00** | **6,653.58** | **77,486.42** |

`d0086394`: **41,769.7100 / operator_estimate → NULL / human_interfered**, "manual se band"
(closed by FAST order `35226091145606`).

**17 Sep — `6c0b2196`, now fully measured:**
* entry SELL 400 @3251.55, `34226091617106`, billed 703.0891
* exit BUY 400 @3305.35, `22226091747006`, billed 53.7091
* gross **−21,520.00**, charges **756.7982**, net **−22,276.7982**
* before: `status open, remaining 400, final_pnl NULL` → after: `closed, remaining 0`

**18 Sep — `62ff7a0f`:** entry BUY 800 @3308.2250 (billed 162.8706), exit SELL 800 @3258.95
(`23226091835206`). Gross **−39,420.00** — matches Dhan `realizedProfit` exactly. Exit
charges **not in the book yet** ⇒ charges baaki, **net NULL**.

**The page after correction:**
```
1-16 Sep set     gross  +84,140.00   charges 6,653.58   net  +77,486.42
17 Sep 6c0b2196  gross  −21,520.00   charges   756.80   net  −22,276.80
18 Sep 62ff7a0f  gross  −39,420.00   charges    baaki   net       NULL
─────────────────────────────────────────────────────────────────────
TOTAL GROSS      +23,200.00
TOTAL NET        NULL — one row's charges are not yet billed
                 (billed part alone: 77,486.42 − 22,276.80 = 55,209.62)
```

---

## PART C — 🔴 STOPPED AT C.3

**C.1 ✅** baselines captured (below). **C.2 ✅** `pg_dump` 365,128 B, md5
`db6d63ad90dd6cfe8951674e8c0119bf`, `pg_restore --list` **exit 0**, 355 entries / 46 table
data, at `/home/ubuntu/backups/predeploy/`. Disk **20 G free (80 %)**. **C.3 ✅** image
tagged `trading_bridge_backend:pre-positions-truth-20260918` (`acb7b86f05a8`).

**Then the gate broke under me.** While staging the code I re-checked 0.2 and found a
subagent transcript under the engineer's session `9187cd01` written **105 seconds earlier**
(15:08:10 UTC vs 15:09:55 now). At 14:50 the newest write had been 01:40. Processes read
idle *now*, but something worked within the last two minutes and **the box's checkout is
shared**.

Your rule: *active ⇒ PART C cannot run*. **I stopped and rolled back.**

**Rolled back, verified:**
```
branch prod/local-state-20260906 · HEAD 006b1189 · working tree CLEAN
36/36 files · fix/ses-role-chain-20260917 b32eedd8 · itmgr/…watchdog 350fe579
alembic 047 · all 3 images acb7b86f05a89 · 7 containers up
crontab md5 ad7ec3fa… · timers 0 · new tables 0 · BSE rows 18 unchanged
```
The 6 files my patch *added* survived `git reset --hard` as untracked; I removed them **by
name**, never a blanket `git clean`, because untracked files on that box may be the
engineer's. C.4–C.9 never ran: no build, no restart, no migration, no data write.

**Deploy window: Saturday 19 Sep daytime** (both lanes flat, market closed, no session).

---

## TODAY'S TRADES — plain answer

Two bot trades on 17 Sep, one bot exit on 18 Sep, all on BSE-SEP2026-FUT. No CDSL order —
that lane still has not placed its first. No manual fills. Legs balance on `62ff7a0f`
(platform and Dhan agree). `6c0b2196` is the one break: closed at Dhan on 17-09, still open
here, **no exposure behind it**. The engine already knew — it recorded EXIT SUPPRESSION and
cancelled its stop reasoning *"A closing order now would OPEN the opposite position from
flat."*

---

## SELF-CHECK — found X, fixed by Y

1. **Round 3 measured the sacred diff against the wrong base** (`fffc1bf3`, not the box's
   `006b1189`). Re-measured against the real base — still zero, now correctly grounded.
2. **A `git merge` onto the deploy base yields 10 conflicts.** Measured the true overlap
   (5 files, all tests) and used an app-only patch, which applies cleanly.
3. **My own `&&` check printed ✅ from `head`'s exit, not `git apply`'s** — same class as
   the Round-4 false green. Re-ran with real exit codes.
4. **A patch test "failed" against a dirty scratch tree** I had not cleaned. Reset and redone.
5. **The badge test's fake session ignored the SQL verdict filter**, so it would have passed
   whatever `_AGREEING_VERDICTS` held. The fake now honours it; the injection fails against it.
6. **An old test encoded the false green** ("a day with no fills is green"). Corrected in
   place, with its history recorded.
7. **Round 4's unverifiable env md5s** were my wrong path: they live in `~/.config/tradetri/`,
   and both are **unchanged** (`21ad17b5…`, `ce3cb4e5…`).

---

## ROLLBACK COMMANDS (valid, unused)

```bash
# backend image (tag already created)
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker tag trading_bridge_backend:pre-positions-truth-20260918 trading_bridge_backend:latest && docker compose up -d --no-deps backend celery_worker celery_beat'
# migration
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker compose run --rm backend alembic downgrade 047_ledger_tracking_epoch'
# database
#   /home/ubuntu/backups/predeploy/trading_bridge-predeploy-20260918-2045.dump  (md5 db6d63ad…)
# box-only code
#   /home/ubuntu/backups/boxonly/trading-bridge-006b1189-20260918-2020.bundle   (md5 6084bd76…)
# timer
ssh ubuntu@13.127.224.68 'sudo systemctl disable --now tradetri-truth-check.timer'
# frontend: merging to main IS the deploy -> git revert the merge on main + push
```

---

## STATUSES

| Item | Status |
|---|---|
| A.1/A.2/A.3 fixes | **BUILT + TESTED** (`f09c206e`) — not deployed |
| Migration 048 (+ `phantom_positions`) | **BUILT + TESTED** — prod still 047 |
| 15:50 truth-check timer | **BUILT + TESTED** — **not ARMED** |
| Frontend R4 render | **BUILT + TESTED** — not deployed |
| PART B corrections | **PROPOSED** — nothing written |
| `6c0b2196` | **REPORTED, UNTOUCHED** |
| Backups | **DONE** — DB dump + box-only bundle, both checksummed |

---

## NOT MEASURED

1. **`62ff7a0f`'s exit charges** — the 18-Sep fill is not in the trade book yet. Net stays
   NULL. Re-pull `/trades/2026-09-18` after settlement (17-Sep took ~40 h to appear).
2. **Why the book lags.** Measured: 17-Sep absent at 18-Sep 04:33, present at 20:20. **A
   15:50 check will therefore often see an empty book for the current session** — under
   A.1 that is now a RED rather than a false green, but you may want the timer moved to the
   next morning instead. Your call; I did not change the schedule.
3. **Whether the engineer session is mid-task.** I saw a write 105 s old and stopped; I did
   not inspect its transcript.
4. **Whether the WS tape is account-wide or contract-scoped.** No sequence numbers, no gap
   detection.
5. **C.4–C.9** — never ran.
