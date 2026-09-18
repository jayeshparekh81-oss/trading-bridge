# WORKING INVENTORY — what runs unattended, and how you know it still does

One entry per scheduled job. Each says **when** it runs, **the receipt** that
proves it ran, and **IF IT STOPS** — the observable signal that it has died.

A job with no receipt is not a job; it is a hope. A job whose failure looks
exactly like its success is worse than no job, because it buys confidence it
has not earned.

> **STATUS WORDS ARE NOT INTERCHANGEABLE.**
> **BUILT** — the code exists and its tests pass.
> **TESTED** — it has been proven to do the thing, including the failure case.
> **ARMED** — the schedule is installed and enabled on the box.
> **LIVE** — its first *unattended* fire has landed on the founder's phone.
> A timer is not ARMED because a unit file exists, and not LIVE because it
> fired once when someone was watching it.

---

## 1. TRADETRI truth check — TWO timers, split by what each hour can know

**Status: BUILT + TESTED. Not armed, not installed.**

Dhan's trade book does not settle in time. **MEASURED:** the 17-Sep session was
absent from `/trades` at 18-Sep 04:33 IST and present by 20:20 — roughly forty
hours. One check could not do both jobs, and trying made it lie: a 15:50 run
that needed the book returned `TRADETRI = DHAN ✅ 0 fills` on the day a live
position silently desynced.

So the work is split by what each hour can actually know.

### 1a. SAME-DAY — weekdays 15:50 IST (`Mon-Fri 10:20` UTC)

| | |
|---|---|
| Asks | *Did we RECORD what the account did today?* |
| Sources | WS tape · our own `strategy_executions` · Dhan `/positions` day quantities |
| Trade book | **Not read.** It is silent about the session that just ended. |
| Broker cost | ONE `/positions` GET |
| Unit / script | `tradetri-truth-check-sameday.{timer,service}` → `/home/ubuntu/bin/tradetri_truth_check_sameday.sh` |
| Badge | **Never.** It has seen no settled price and no billed charge. |

Green when the record matches the day's activity — and a **quiet day is provably
green**, because `/positions` day quantities are positive evidence that nothing
traded, unlike an empty book. RED when the tape saw a fill we did not record, a
position is open here while the broker is flat, or the tape loads empty beside
real activity. NO-DATA only when the broker could not be reached at all.

**Replayed against 17 Sep it goes RED, naming `22226091747006`** — the engine's
stop fill that never reached us. It would have caught that desync the same day.

### 1b. MORNING — weekdays 08:30 IST (`Mon-Fri 03:00` UTC), for YESTERDAY

| | |
|---|---|
| Asks | *Do the NUMBERS match Dhan's settled book?* |
| Sources | the settled trade book + its **billed** charges, against what the site stored |
| Broker cost | ONE trade-book GET, pulled once to a file the ingester and the check share |
| Unit / script | `tradetri-truth-check-morning.{timer,service}` → `/home/ubuntu/bin/tradetri_truth_check_morning.sh` |
| Badge | **Only this run** licenses "Dhan se verified ✅" |

If the book is STILL empty for that session while a witness saw activity ⇒ RED
*"book empty, activity seen"*, never green.

### THE RECEIPT
Both write to `truth_check_runs`, each stamped with its `kind`, and dedupe is
**per kind** — one session legitimately has one of each, and without the scope
the morning verdict would be swallowed as a duplicate of the afternoon's.

```bash
docker exec trading_bridge_postgres psql -U $POSTGRES_USER -d trading_bridge -c \
  "SELECT ran_at, kind, verdict, fills_checked, details FROM truth_check_runs ORDER BY ran_at DESC LIMIT 10;"
systemctl list-timers 'tradetri-truth-check-*' --no-pager
journalctl -u tradetri-truth-check-sameday.service -u tradetri-truth-check-morning.service --since today --no-pager
```

The badge on a position may render **only** from a stored run with
`kind='morning' AND verdict='green'` whose window covers that position's close,
and it shows that run's date. No row, no badge.

### 🔴 IF IT STOPS
**Silence on a weekday is the alarm** — which is why the green line is sent every
day, from both checks. A dead timer and a clean day must not look alike.

* **No same-day line by ~16:10 IST** → timer, container, credential or Telegram.
* **No morning line by ~08:50 IST** → same, plus check the book actually pulled.
* **Lines arriving but `fills_checked` frozen** → it is reading a stale file, not
  the account.
* `Persistent=false` on both: a missed run must not fire hours later carrying a
  verdict stamped with the wrong session.
* A red exits 1; both units declare `SuccessExitStatus=0 1` so a working check is
  not reported as a failed unit.

### DEPLOY CHANGES TO ARM (none made)
1. Copy both scripts → `/home/ubuntu/bin/` (`chmod +x`).
2. Copy all four units → `/etc/systemd/system/`, `systemctl daemon-reload`,
   `systemctl enable --now tradetri-truth-check-sameday.timer tradetri-truth-check-morning.timer`.
3. Apply migration **048** (additive: two tables, plus nullable `kind` and
   `phantom_positions` on a table it creates).

**Rollback:** `systemctl disable --now` both timers, delete the units and
scripts, `alembic downgrade 047_ledger_tracking_epoch`.

**No compose change, no container restart.** The backend container has zero
mounts (measured), so the tape is handed over with `docker cp`.

## 2. 🔴 BLOCKING PRE-CONDITION — the ledger snapshot's `pnl_basis` is now stale

**Not a live defect today, and that is the only reason this is a note rather
than a red.** Measured on prod 2026-09-16:

```
ledger_snapshots rows: 0
distinct pnl_basis  : (none)
LEDGER_DAILY_SNAPSHOT_ENABLED=false
```

Nothing has been written and nothing is scheduled, so no customer sees a wrong
basis.

**The trap.** `create_daily_snapshot` stamps every live-strategy snapshot with
`pnl_basis = "reconciled_net_estimated_costs"`
(`app/strategy_engine/ledger/snapshots.py:341`), and the marketplace panel
faithfully renders that as "net of modelled charges". That label was true when
the reconciler modelled its charges. **It is no longer true:** since the
founder's ruling of 2026-09-16, `final_pnl` is net of what Dhan BILLED.

So the first snapshot taken would stamp a false basis onto an **append-only,
hash-chained** record — the one kind of row that cannot be corrected afterwards.

**Why it is not fixed in this train.** The ledger is a separate, founder-gated
lane, and changing what reaches a hash chain is not a change to make unasked.
Two further questions need the founder's answer first:

1. A new basis literal (e.g. `reconciled_net_billed_charges`) — what should it
   be called on the chain?
2. Archive rows priced under the OLD modelled path are still in the table. A
   snapshot summing both is **mixed-basis**, and one literal cannot describe it
   honestly. Either the archive is excluded, or the basis has to say "mixed".

**Do not take the first snapshot until this is decided.**

---

## 3. The frontend deploy route — MEASURED, not assumed (R5)

Everything below was read from GitHub's own deployment records with the `gh`
CLI. **No Vercel login, no token, nothing handled.**

### What is live right now

| | |
|---|---|
| **Production commit** | `fffc1bf3` |
| **GitHub deployment id** | `6384487209` |
| **Deployed at** | 2026-09-11 01:25:21 UTC |
| **State** | success |
| **URL** | `https://trading-bridge-l8ht953hh-jayeshparekh81-9555s-projects.vercel.app` |

**`fffc1bf3` is also `main`'s current HEAD, and it is the same commit the
backend's sacred diff is measured against.** Frontend and backend production
are in lockstep on one commit — which is why the C4 contract test pins that
exact sha: it is really what a customer's browser is running.

### How the deploy happens — evidence, not assumption

* **A push to `main` auto-deploys to PRODUCTION.** Every one of the last 10
  Production records was created by `vercel[bot]`, and every `ref` is a commit
  on `main` (checked with `git merge-base --is-ancestor`).
* **A push to any other branch deploys a PREVIEW**, not production. All 10
  most recent records for this branch are `env=Preview` — including every
  commit of this train.
* **No GitHub Action does it.** Nothing under `.github/workflows/` mentions
  Vercel, so this is the Vercel↔GitHub git integration.

⚠️ **This means merging this branch to `main` IS the frontend deploy.** There is
no separate button and no second gate. Treat the merge itself as the deploy.

### (a) Note the current production deployment BEFORE deploying

Run this and keep the output. It needs only the `gh` login that already exists:

```bash
gh api "repos/jayeshparekh81-oss/trading-bridge/deployments?environment=Production&per_page=1" --jq '.[0] | "deployment id: \(.id)\ncommit: \(.sha[0:8])\ncreated: \(.created_at)"'
```

That commit is what you roll back TO.

### (b) Rolling back — the founder's step, in simple words

Claude cannot do this part: it needs a logged-in Vercel session, and no token
should be handled for it.

1. Open **vercel.com** and sign in.
2. Pick the **trading-bridge** project (team *jayeshparekh81-9555s-projects*).
3. Click the **Deployments** tab.
4. Find the row whose commit matches the sha you saved in step (a) — for the
   deployment live today that is **`fffc1bf3`**.
5. Click the **⋯** menu at the right of that row.
6. Choose **"Promote to Production"** (some plans label it **"Instant
   Rollback"**). Confirm.

The site returns to that commit within seconds; it re-serves a build that
already exists rather than rebuilding.

**To check it worked**, re-run the command in (a): the commit it prints should
be the one you rolled back to.
