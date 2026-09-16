# ROUND 3 — FOUNDER TABLE
**Branch** `fix/positions-orders-truth` @ `59cc6805` · cut from PROD `fffc1bf3`
**Nothing deployed. Nothing on prod changed.** Stopping here, before `HAAN DEPLOY`.

---

## 1. STAGE TABLE

| Stage | Verdict | Receipt |
|---|---|---|
| **R0** baseline | 🟢 | crontab md5 `ad7ec3fa…`, 102 lines · image `acb7b86f05a89` · prod alembic **047** (048 NOT applied) · 0 new tables · 0 new timers · 17 BSE rows unchanged |
| **R1.1** one clock | 🟢 | `ist_display()` → `04/09/26, 01:11 pm`. Injection: drop `astimezone` → 5 of 6 IST tests red |
| **R1.2** earned badge | 🟢 | `covering_truth_runs()` needs a STORED run covering the close, shows that run's date. 11 tests. 3 injections red |
| **R1.3** manual se band | 🟢 | `d0086394` reads "manual se band", not "verify baaki" |
| **R1.4** plain names, 2dp | 🟢 | `leg_label()` + `price_display()` (HALF_UP). 19 tests |
| **R1.5** legs must balance | 🟢 | `legs_balanced` in `writable`. Injection: drop it → primary red, twin green |
| **R2** fill ingester (+A) | 🟢 | `ingest.py`, migration **048**, 11 + 6 tests. Tape DELETED after ingest → answer unchanged (real Postgres) |
| **R3** same-day alerts (+B,C) | 🟢 **BUILT + TESTED, NOT ARMED** | 22 tests. Green day, red day, dedupe and a changed verdict all proved end-to-end against a real DB. 3 injections red |
| **D** no modelled costs | 🟢 | Cost model unreachable from the live-record surfaces (AST-proven). 13 tests. 3 injections red |
| **E** golden replay | 🟢 | **TOTAL CHARGES 6,653.58 · TOTAL NET 77,486.42**, exact, through the production loader. 21 tests |
| **R4** React frontend | 🟢 | Legs, duplicate exit, both totals, 3-state badge. 29 render tests. Render file produced |
| **R5** Vercel | 🟢 **MEASURED** | prod = `fffc1bf3` = main HEAD, deployment `6384487209`. Push to main ⇒ PRODUCTION. No login, no token |
| **R6** full verify | 🟢 | Sacred diff **ZERO** across 13 paths · backend 5470 pass / same 65 pre-existing · frontend 1661 pass, 3 fail (was 7) · C4 green · scratch torn down |

---

## 2. THE RECORD, WITH ITS ARITHMETIC

| Row | Gross | Charges (Dhan's bill) | Net |
|---|---:|---:|---:|
| `844b8037` | +80,360.00 | 2,302.2784 | **+78,057.72** |
| `a13ddeb0` | −61,020.00 | 2,602.9570 | **−63,622.96** |
| `9165ebbe` | +69,160.00 | 1,615.2172 | **+67,544.78** |
| `dup-exit` *(system galti)* | −4,360.00 | 133.1296 | **−4,493.13** |
| **TOTAL** | **+84,140.00** | **6,653.58** | **+77,486.42** |

`84,140.00 − 6,653.58 = 77,486.42` ✅ — the founder's headline, to the paisa.

* `d0086394` — **P&L not counted**. Closed by manual Dhan-app order `35226091145606`
  (BUY 200 @3215.40, 11-09 09:31). Reads "manual se band".
* `6c0b2196` — open, entered 16-09. **Charges baaki**: today's fills come back from
  Dhan with no charge fields at all, so net is NULL, never a flattering zero.

**Provenance of all 17 fills in the window: 12 bot · 4 manual · 0 pehchaan nahi.**

**Render:** `frontend/tests/render-snapshot/positions.html` (mounts the real component;
its TOTAL GROSS 84,140 / TOTAL NET 77,486 are the page's own arithmetic, asserted).

---

## 3. NEW TIMER / ALERTS — sandbox receipts

**One timer**, `tradetri-truth-check` — weekdays **15:50 IST** (`Mon-Fri 10:20` UTC;
the host runs Etc/UTC, measured). systemd, never the crontab.

| Proved in sandbox | Receipt |
|---|---|
| GREEN day | `TRADETRI = DHAN ✅ 2026-09-04 2 fills` + stored run |
| RED day | `MISMATCH 🔴 … 1 fill(s) not in our record: 99990001112223` + stored run |
| DEDUPE | same verdict again → suppressed, **no new row, no send** |
| Changed verdict | green→red **does** get through (dedupe is by verdict, not by day) |
| PEHCHAAN NAHI on real data | ledger removed → the two FOVR stops go `unknown`, day RED, never "manual" |
| Manual trade | `TRADETRI = DHAN ✅ … — HAATH SE TRADE ⚠️ …`, severity WARNING not CRITICAL |
| Severity/dedupe delivery | asserted at the transport boundary (a test that really sent would buzz his phone every CI run) |

**IF IT STOPS:** no line by ~16:00 IST on a weekday **is** the alarm — which is why the
green line goes out every day. A dead timer and a clean day must not look alike.

⚠️ **NOT ARMED.** A timer is armed only when its first unattended fire lands on your
phone. The transport itself is already live (prod is `environment=production`, token set,
chat `431466871`).

---

## 4. DEPLOY CHANGES — each with its rollback

| # | Change | Rollback |
|---|---|---|
| 1 | **Migration 048** (2 new tables, additive only — proven on a scratch DB, and its downgrade leaves the other 46 tables byte-identical) | `alembic downgrade -1` |
| 2 | Copy `deploy/bin/tradetri_truth_check.sh` → `/home/ubuntu/bin/` (`chmod +x`) | delete the file |
| 3 | Install both units → `/etc/systemd/system/`, `systemctl enable --now tradetri-truth-check.timer` | `systemctl disable --now tradetri-truth-check.timer` + delete the units |
| 4 | Backend image rebuild (code) | retag the saved image (below) |
| 5 | Frontend: **merging to main IS the deploy** | Vercel dashboard → Promote (below) |

**NO bind-mount and NO compose change.** The backend container has **zero mounts**
(measured), so the tape is handed over with `docker cp` — no restart of the live web
container. The copies are ephemeral; the verdict lives in the database, which is the
whole point of addition A.

### Backend: tag BEFORE building
```bash
ssh ubuntu@13.127.224.68 'docker tag trading_bridge_backend:latest trading_bridge_backend:pre-truth-check-20260917'
```
### Backend rollback
```bash
ssh ubuntu@13.127.224.68 'cd /home/ubuntu/trading-bridge && docker tag trading_bridge_backend:pre-truth-check-20260917 trading_bridge_backend:latest && docker compose up -d --no-deps backend celery_worker celery_beat'
```
(+ `alembic downgrade -1` if 048 was applied. The image is shared by backend, worker and beat.)

### Frontend rollback — your step, in simple words
Claude cannot do this: it needs a logged-in Vercel session and no token should be handled.
1. **vercel.com** → sign in → project **trading-bridge**
2. **Deployments** tab → find the row for commit **`fffc1bf3`**
3. **⋯** → **"Promote to Production"** (some plans: "Instant Rollback") → confirm

Note today's production first:
```bash
gh api "repos/jayeshparekh81-oss/trading-bridge/deployments?environment=Production&per_page=1" --jq '.[0] | "id: \(.id)  commit: \(.sha[0:8])  at: \(.created_at)"'
```

---

## 5. SELF-CHECK — what I found and fixed

1. **Migration 048 would have gone RED on your deploy.** Its revision id was 36 chars;
   `alembic_version.version_num` is `varchar(32)`. It created both tables and then failed
   on the stamp. An AST check calls it "additive" and passes — only a live apply finds it.
2. **Addition B guarded the ingester but not the CLI.** `apply_provenance` on an empty tape
   silently returns every fill with no platform ⇒ the whole record reads "pehchaan nahi".
   That is exactly the 16-Sep incident shape. The CLI now refuses.
3. **The page was serving MODELLED charges.** Not a wording problem — `derived_realised_pnl`
   was gross minus a modelled stack on every row without a `final_pnl`. Replaced with Dhan's
   bill; unbilled rows show gross + "baaki" + net NULL.
4. **The duplicate exit's charges were being ignored** — its gross was added into a NET
   total and the headline came out **133.13 too high**. Found by mounting the page, not by
   reading the code.
5. **My own R4 test was worthless.** It asserted `p.legs.map` appeared in the SOURCE;
   disabling the section left that string intact and all 16 assertions passed. Replaced
   with a render test — the same injection fails 5 of its assertions.
6. **My first sacred-diff check was a FALSE GREEN.** A heredoc collapsed the file list into
   one string, so it measured nothing and printed ✅. Redone properly: zero across 13 paths.
7. `/trades` had **no label for `broker_stop`** and excluded it from `EXIT_ROLES` —
   the fill that closed two of the four round trips rendered as raw text and was uncounted.
8. The reconciler task logged `total_costs_estimated`, which now resolves to **0** on the
   live path — a flattering zero in your own operator log.
9. A comment I wrote named a month and tripped ADR 0003's single-owner guard. Reworded.
10. **Today's fills come back with no charge fields at all** — so net is NULL, not zero.
    This is the rule working; the golden fixture caught it live.

## 6. THINGS YOU SHOULD DECIDE (not fixed here, on purpose)

1. 🔴 **The ledger snapshot would stamp a now-false basis.** `create_daily_snapshot` writes
   `pnl_basis = reconciled_net_estimated_costs`, but `final_pnl` is now net of Dhan's bill —
   onto an **append-only, hash-chained** row. Measured: **0 snapshots, beat disabled**, so it
   is latent. Needs your call on the new literal, and on archive rows priced the old way
   (a snapshot summing both is mixed-basis). **Do not take snapshot #1 until this is settled.**
2. **Two migrations are numbered 047.** `047_customer_lane` lives on `feat/customer-lane-full`
   and chains off the same parent as `047_ledger_tracking_epoch`. If those lanes ever merge,
   alembic has **two heads** and `upgrade head` fails.
3. **`telegram_enabled` is dead config** — declared once, read nowhere, resolving `False`
   while alerts nonetheless send. Don't trust it as a switch.
4. ⚠️ **Two R0 md5s cannot be verified as recorded.** `pine_replica/bridge.env` and the CDSL
   equivalent **do not exist** — no `*.env` file exists anywhere in either tree. What is
   measured instead: by mtime, nothing in either tree changed except engine-written logs.
5. 🔴 **Another Claude session is live on the EC2 box.** It wrote three loose git objects into
   `pine_replica/.git` at 18:28:13 UTC (no commit, index untouched). Not this session — every
   command here reads. Two sessions on one box already caused a wrong-branch commit once.

---

## 7. STOP

Waiting for exactly: **`HAAN DEPLOY`**
