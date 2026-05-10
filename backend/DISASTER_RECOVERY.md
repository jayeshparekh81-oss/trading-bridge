# TRADETRI — Disaster Recovery Runbook

This is the single source of truth for getting TRADETRI back online
after a data-plane failure. Treat it as a living doc; every infra
commit that changes backup / restore behavior must update the
relevant section.

## Objectives

| Metric | Target | Notes |
| --- | --- | --- |
| **RTO** (Recovery Time Objective) | **4 hours** | From "we have decided to restore" to "traffic is being served." Lower bound is dominated by `pg_restore` time on a 50 GB dump (~30 min) plus DNS / app rollout (~15 min). |
| **RPO** (Recovery Point Objective) | **1 hour** | Worst case is a failure at 3:59 AM IST, one minute before the daily dump — the prior day's dump plus RDS PITR within the 7-day window covers anything closer than 1 hour. |

## Backup tiers (Phase 1, locally orchestrated)

| Tier | Frequency | Mechanism | Retention | Restore latency |
| --- | --- | --- | --- | --- |
| **Daily logical** | 03:00 IST | `backup_postgres.sh` → encrypted pg_dump → S3 | 30 days | minutes |
| **Hourly PITR** | continuous | RDS automated snapshots | 7 days | tens of minutes |
| **Weekly archive** | Sunday 04:00 IST | mirror to `tradetri-archive/` prefix → S3 lifecycle → Glacier | 1 year | 3–5 hours (Glacier retrieval) |

Critical restore order, when restoring table-by-table is needed:

1. `users` — every other surface depends on FK to user_id.
2. `strategies` + `indicator_versions`.
3. `ledger_snapshots` — immutable, never overwrite during partial restore.
4. `paper_sessions` + `paper_trades`.
5. `audit_logs`.
6. `marketplace_listings` + `marketplace_subscriptions`.
7. `support_tickets`.
8. `alembic_version` — restore last (otherwise migrations re-run on a partially-restored schema).

## Decision tree

```
                   ┌─── data is wrong/missing ───┐
   Symptom?  ─────┤                             ├─── infra is gone ───┐
                   └─── DB unreachable ──────────┘                     │
                              │                                        │
            ┌─────────────────┼─────────────────┐         ┌────────────┴────────────┐
            │                 │                 │         │                         │
       single bad        whole table        whole DB    region        whole AWS
        record           corrupted         is gone      down          account gone
            │                 │                 │         │                         │
            ▼                 ▼                 ▼         ▼                         ▼
    Scenario A          Scenario B        Scenario C   Scenario D            Scenario E
    PITR + repair       Logical restore   Snapshot     Cross-region          Glacier
    via SQL             of one table      restore      replica failover      pull-and-rebuild
                                          (PITR)
```

---

## Scenario A — Bad migration / data corruption (single-table or row-level)

**Likelihood:** medium. **Impact:** medium. **Time-to-restore:** 30 min – 2 hr.

1. **Stop writes** to the affected table.
   ```sh
   # Toggle the kill switch — stops all order placement immediately
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
        https://api.tradetri.in/api/admin/kill-switch \
        -d '{"reason":"investigating data corruption"}'
   ```
2. **Identify scope** — `audit_logs` is your friend.
   ```sql
   SELECT * FROM audit_logs
   WHERE created_at > NOW() - INTERVAL '4 hours'
     AND entity_type = '<affected_table>'
   ORDER BY created_at;
   ```
3. **Decide the restore source:**
   - Last 7 days → RDS PITR to a parallel instance.
   - Older → daily S3 dump (`backup_postgres.sh` output).
4. **Restore to a *parallel* DB**, never directly over production.
   ```sh
   BACKUP_RESTORE_TARGET="postgres://tradetri@scratch.<rds-host>/tradetri_restore" \
     ./scripts/restore_postgres.sh tradetri-20260509T213000Z --confirm tradetri_restore
   ```
5. **Diff + cherry-pick** the rows that need to come back.
   ```sql
   -- in the scratch DB
   COPY (SELECT * FROM <table> WHERE <predicate>) TO STDOUT;
   -- pipe into prod
   psql $PROD_URL -c "COPY <table> FROM STDIN;"
   ```
6. **Reverse the bad migration** if it was a schema change.
   ```sh
   alembic downgrade -1
   ```
7. **Re-enable writes**, run smoke tests, post all-clear.

---

## Scenario B — Whole-table loss

**Likelihood:** low. **Impact:** high. **Time-to-restore:** 1–2 hr.

1. Engage admin oncall (see escalation chain below).
2. Stop writes via kill-switch as in Scenario A.
3. `pg_restore` only the affected table from the latest dump:
   ```sh
   pg_restore --dbname=$BACKUP_RESTORE_TARGET \
              --table=<table_name> \
              --data-only --no-owner --no-acl \
              /var/backups/tradetri/tradetri-<TS>.dump
   ```
4. Verify row counts match expected pre-incident value (cross-reference `audit_logs`).
5. Re-enable writes, smoke-test, post all-clear.

---

## Scenario C — Whole-DB loss (instance crashed, disk corrupted, accidental DROP DATABASE)

**Likelihood:** low. **Impact:** critical. **Time-to-restore:** 2–4 hr (within RTO).

1. Open the AWS RDS console, identify the latest healthy automated snapshot.
2. **Restore-from-snapshot** to a NEW instance (do NOT replace the original — keep it for forensics).
3. Update the app's `DATABASE_URL` env var to point at the new instance.
4. Roll the app pods (preserves cache warmth where possible):
   ```sh
   kubectl -n tradetri rollout restart deployment/api deployment/worker
   ```
5. Run the verify script against the restored DB before re-enabling traffic:
   ```sh
   BACKUP_VERIFY_TARGET="$NEW_DB_URL" \
     ./scripts/verify_backup.sh
   ```
6. If RDS PITR window has elapsed, fall through to logical restore (Scenario E procedure with a fresh RDS instance).
7. Post-incident: write up the timeline + root cause within 48 hr.

---

## Scenario D — Region failure

**Likelihood:** very low. **Impact:** critical. **Time-to-restore:** 1 hr (cross-region replica).

> **Phase 1 status:** cross-region replication is **not yet provisioned**.
> Until Phase 2 ships, a region failure degrades to Scenario C with
> a longer RTO (tens of minutes added for Glacier retrieval if the
> daily-dump bucket is region-pinned).

When Phase 2 lands, this section will document:

- Promoting the read replica in `ap-south-2` to primary.
- DNS cutover via Route 53 health-check.
- Reconciling sequences / autoincrement counters post-promotion.

---

## Scenario E — Total AWS account compromise / loss

**Likelihood:** ~zero. **Impact:** existential. **Time-to-restore:** 4–8 hr.

1. Spin up a fresh AWS account.
2. Pull the most recent Glacier archive (3–5 hr retrieval window).
3. Run `restore_postgres.sh` with that archive into a fresh RDS instance.
4. Restore IAM, secrets, container registry from the off-site snapshot
   stored in the founder's encrypted offline vault.
5. Stage app re-deploy + DNS cutover.

---

## Communication template (status page)

Post the relevant variant within 5 minutes of scenario confirmation.

> **Investigating** — *2026-XX-XX HH:MM IST* —
> We are aware of an issue affecting `<surface>`. Trading is paused
> while we investigate. We will post the next update by `<HH:MM>`.

> **Identified** — *2026-XX-XX HH:MM IST* —
> Root cause identified: `<one-line summary>`. ETA to recovery:
> `<HH:MM>`. Trading remains paused. No customer funds are at risk.

> **Resolved** — *2026-XX-XX HH:MM IST* —
> Service restored. Trading resumed at `<HH:MM>`. Full incident
> report within 48 hours.

---

## Post-incident checklist

Within **24 hours** of resolution:

- [ ] Timeline captured (every key timestamp + decision)
- [ ] Root cause identified (5-whys)
- [ ] Customer-impact estimate (count of users / orders affected)
- [ ] Refund / compensation list compiled if applicable

Within **48 hours**:

- [ ] Public post-mortem published to `/changelog` (no PII, no secrets)
- [ ] Action items filed as GitHub issues with explicit owners
- [ ] Runbook updated with anything we'd do differently next time

Within **7 days**:

- [ ] Action items either landed or have a tracked schedule
- [ ] Tabletop exercise run if the scenario is novel (worth burning a Saturday)

---

## Escalation chain

| Tier | Role | Window |
| --- | --- | --- |
| L1 | On-call engineer (rotates weekly) | 24×7, Slack `#oncall-pager` |
| L2 | Founder / CTO (Jayesh) | 24×7, phone tree |
| L3 | AWS Premium Support | Severity-Critical case, ~15 min ack |
| L4 | RDS Database Engineer (paid escalation) | open via L3 |

**Phone tree:** maintained in 1Password vault `infra/oncall-rotation`.
**AWS account:** root credentials in offline encrypted vault — DO NOT
use the root account for routine ops; only for IAM recovery.

---

## Phase 2 deferred items

These are documented here so the runbook reads as a complete
target-state rather than a partial one:

- **Real S3 integration** — currently the scripts run in stub mode on
  any host that hasn't set `BACKUP_S3_BUCKET`. Provision the bucket +
  IAM role when AWS account is active.
- **Cross-region replica** — secondary in `ap-south-2`, async streaming.
- **Encryption-key rotation** — quarterly rotation policy with re-encrypt
  of in-flight Glacier archives.
- **Glacier lifecycle rule** — tagged-prefix transition policy on the
  bucket (currently the cron just mirrors under the archive prefix
  and trusts the rule to handle the rest).
- **Monitoring** — Datadog / CloudWatch alarms on
  `/api/health/backups` `last_backup_age_hours > 25` and
  `last_verification_status != "ok"`.

---

## Quick-reference runbook commands

```sh
# Run a manual backup right now (dev / lab):
BACKUP_DB_URL="$DEV_DB_URL" \
BACKUP_LOCAL_DIR="$HOME/.cache/tradetri-backups" \
  ./backend/scripts/backup_postgres.sh

# Restore a specific dump into a scratch DB:
BACKUP_RESTORE_TARGET="$SCRATCH_DB_URL" \
BACKUP_LOCAL_DIR="$HOME/.cache/tradetri-backups" \
  ./backend/scripts/restore_postgres.sh tradetri-20260510T030000Z \
    --confirm <db_name_in_scratch_url>

# Verify the latest dump (pg_restore + sanity queries):
BACKUP_VERIFY_TARGET="$SCRATCH_DB_URL" \
BACKUP_DB_URL="$DEV_DB_URL" \
BACKUP_LOCAL_DIR="$HOME/.cache/tradetri-backups" \
  ./backend/scripts/verify_backup.sh

# Read the current backup health (admin token required):
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.tradetri.in/api/health/backups | jq
```
