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

## 1. TRADETRI truth check — site vs Dhan, same day

| | |
|---|---|
| **Status** | **TESTED** — not armed, not live. Installing the timer is a deploy change (see below). |
| **Schedule** | Weekdays 15:50 IST (`OnCalendar=Mon-Fri 10:20` — the host runs UTC, measured `Etc/UTC`) |
| **Unit** | `deploy/systemd/tradetri-truth-check.{timer,service}` |
| **Script** | `deploy/bin/tradetri_truth_check.sh` → `/home/ubuntu/bin/` |
| **Code** | `app/domains/pnl_reconciler/truth_check.py` (pure) + `truth_check_runner.py` (I/O) |
| **Broker cost** | **ONE** trade-book GET per day. The book is pulled once to a file; the ingester and the check both read that file. |

### What it does
Compares what tradetri.com holds against what Dhan's own book says, for that
day, and sends **one** line:

```
TRADETRI = DHAN ✅ 2026-09-04 2 fills
MISMATCH 🔴 2026-09-04 PEHCHAAN NAHI 1: 99990001112223
```

It goes red on any of four things, each naming the fill it is about:

1. **unrecorded** — a Dhan fill we have no provenance row for;
2. **pehchaan nahi** — a fill that is neither ours nor demonstrably manual
   (never filed as manual: that would blame a human for the bot's own exit);
3. **manual** — a hand-placed trade on the bot's own symbol;
4. **duplicate exit** — two exits where one position closed once.

An empty tape beside actual fills is **one** red about the tape, never a
re-flagging of every fill.

### THE RECEIPT
Every run writes a row to `truth_check_runs` (`ran_at`, the window it covered,
`verdict`, `fills_checked`, `details`). Check the last one:

```bash
docker exec trading_bridge_postgres psql -U $POSTGRES_USER -d trading_bridge -c \
  "SELECT ran_at, verdict, fills_checked, details FROM truth_check_runs ORDER BY ran_at DESC LIMIT 5;"
```

and the timer's own view:

```bash
systemctl list-timers tradetri-truth-check.timer --no-pager
journalctl -u tradetri-truth-check.service --since today --no-pager
```

That table is also what licenses the **"Dhan se verified ✅"** badge on a
position: the badge may only be shown when a STORED run covers it, and must
show that run's date. No row, no badge.

### 🔴 IF IT STOPS
**No message on a weekday afternoon is the alarm.** This is why the green line
is sent every single day and not only on a red: if only failures spoke, a dead
timer and a clean day would look identical from the founder's phone, and the
silence would be indistinguishable from safety.

So:
* **No line by ~16:00 IST on a weekday** → the timer, the container, the
  credential or Telegram is down. Start with `systemctl list-timers`, then
  `journalctl -u tradetri-truth-check.service`.
* **A line every day but the same one forever** → check `fills_checked` is
  moving. A frozen count means it is reading a stale file, not the account.
* `Persistent=false` is deliberate: a missed run must not fire hours later
  carrying a verdict stamped with the wrong session.
* A red day exits 1; the unit declares `SuccessExitStatus=0 1` so systemd does
  not report a working check as a failed unit and mask a genuinely broken one.

### Dedupe
A retry, a restart or a second manual run does **not** re-send the same
sentence. Suppression is by **verdict**, not by day — a red arriving after a
green is news and still goes out. (Suppressing by day would swallow exactly
the message the founder most needs.)

### DEPLOY CHANGES NEEDED TO ARM IT
None of these have been made. All are listed for the founder's gate.

1. Copy `deploy/bin/tradetri_truth_check.sh` → `/home/ubuntu/bin/` (`chmod +x`).
2. Copy both units → `/etc/systemd/system/`, then
   `systemctl daemon-reload && systemctl enable --now tradetri-truth-check.timer`.
3. Apply migration **048_fill_provenance** (additive only: two new tables,
   nothing dropped, renamed or retyped).

**Rollback:** `systemctl disable --now tradetri-truth-check.timer`, remove the
two unit files and the script, `alembic downgrade -1`. The downgrade drops only
the two tables this migration created — proven against a scratch Postgres, with
the other 46 tables byte-identical in shape afterwards.

**No compose change and no container restart.** The backend container has zero
mounts (measured), so the tape is handed over with `docker cp` rather than by
adding a bind-mount, which would mean restarting the live web container.

### What is already true, and needs nothing
The alert transport is **live**: prod resolves `environment=production`, the bot
token is set and the operator chat id is `431466871`, so `send_alert` reaches
Telegram for real. ⚠️ Note that the setting named `telegram_enabled` is **dead
config** — declared in `app/core/config.py` and read nowhere. It resolves to
`False` while alerts nonetheless send. Do not read it as an on/off switch.
