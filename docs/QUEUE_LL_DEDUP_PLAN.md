# Queue LL — broker_credentials Dedup + Case-Fix Plan

**Branch:** `fix/broker-case-dedup` (NOT merged to main)
**Script:** `scripts/dedup_brokers.py` (self-contained, psycopg2-only)
**Date authored:** 2026-05-21
**Deadline:** Tomorrow 2026-05-22 09:15 IST — BSE LTD Dhan strategy must
execute on market open. Tonight (post-20:00 IST) is the safe operating
window.

---

## §0 — Problem statement (verbatim from Queue LL brief)

Production DB has **38 broker_credentials rows**. SQLAlchemy enum expects
lowercase (`'dhan'`, `'fyers'`) but **37 rows are UPPERCASE** (`'DHAN'`=34,
`'FYERS'`=3). This causes:

- 500s on `GET /api/users/me/brokers`
- `reconciliation_loop` `tick_failed` every 60s
- Strategy editor "Save Changes" → 500

Direct `UPDATE broker_credentials SET broker_name = LOWER(broker_name)`
is blocked by a unique constraint `uniq_active_broker_per_user` on
`(user_id, broker_name)` — one user has BOTH `'dhan'` and `'DHAN'` rows
simultaneously, plus 13+ stale OAuth-reconnect duplicates per user.

> **Schema-discovery footnote.** Migration `002_fix_broker_name_case`
> attempted exactly the naive `UPDATE ... LOWER(broker_name)` in 2024,
> which means it succeeded then but the prod table re-acquired uppercase
> rows afterwards (almost certainly: OAuth-reconnect code path
> inserting uppercase post-migration). The constraint name
> `uniq_active_broker_per_user` is **NOT** in any migration in
> `backend/migrations/versions/` — it must have been added out-of-band
> via direct SQL on prod, or it lives as a partial unique index. The
> script **discovers actual constraints at runtime** from `pg_constraint`
> + `pg_index` rather than depending on the brief's name.

## §1 — Sacred row (must survive)

| Field | Value |
|---|---|
| broker_credentials.id | **`58b369a3-e590-475a-b687-de931c07c064`** |
| broker_name (current) | `'DHAN'` (uppercase — needs case fix) |
| broker_name (post-fix) | `'dhan'` (UPDATE only — never DELETE) |
| Linked from | `strategies.broker_credential_id` for live strategy `89423ecc-c76e-432c-b107-0791508542f0` |

Script hard-codes both UUIDs at the top. The planner has THREE guards:

1. **Tie-break override:** if the sacred row is in any duplicate group,
   it always wins KEEP regardless of FK count / recency / is_active.
2. **Sanity assertion:** if the sacred row ends up in `plan.delete`, the
   planner appends a FATAL message to `plan.aborts` instead of executing.
3. **Defensive re-check at apply time:** the DELETE statement
   re-verifies `SACRED_ROW_ID not in delete_ids` and raises a `RuntimeError`
   that triggers `ROLLBACK` if the planner ever drifted.

## §2 — Algorithm

### Inspection (--inspect, default mode — read-only)

1. **Discover schema** via `pg_constraint` + `pg_index`:
   - All tables with FK → `broker_credentials.id` (and their ON DELETE action)
   - All UNIQUE / EXCLUSION constraints on `broker_credentials`
   - All partial unique indexes on `broker_credentials` (these don't appear as `pg_constraint` rows)
2. **Snapshot rows** ordered by `(user_id, created_at)`.
3. **Count FK refs per row** via one `SELECT COUNT(*) GROUP BY` per FK table (no N+1).
4. **Group by `(user_id, LOWER(broker_name))`** to identify duplicate groups.
5. **For each group, pick KEEP via tie-break:**
   1. Most FK refs (loss of FK refs = data loss)
   2. Most recent `created_at` (newer OAuth session)
   3. `is_active = TRUE`
6. **Sacred-row override** (per §1).
7. **Plan:**
   - **KEEP + case-fix:** row stays, `broker_name` UPDATE to lowercase
   - **KEEP unchanged:** row stays, already lowercase
   - **DELETE:** orphan duplicate, zero FK refs
   - **ABORT:** any row marked DELETE that has FK refs → manual re-link required
8. **Print everything.** Per-row plan, sacred-row verdict, summary counts.

### Apply (--apply, requires explicit flag + `yes` typed)

Single transaction:

1. **pg_dump backup** to `/tmp/broker_credentials_pre_dedup_YYYYMMDD_HHMMSS.sql`. If `pg_dump` exits non-zero or file is empty → `sys.exit(2)`.
2. **BEGIN** (`conn.autocommit = False`).
3. `DELETE FROM broker_credentials WHERE id IN (plan.delete)`. Rowcount must equal `len(plan.delete)`.
4. `UPDATE broker_credentials SET broker_name = LOWER(broker_name) WHERE broker_name <> LOWER(broker_name)`. (One statement; defensive — covers any rows the planner missed.)
5. **Verifications (4 of them) — any failure raises and triggers `ROLLBACK`:**
   - V1: `SELECT DISTINCT broker_name` returns only `{'dhan', 'fyers'}`.
   - V2: Sacred row still exists; `broker_name = 'dhan'`.
   - V3: Row count delta matches plan (`before - len(delete)`).
   - V4: No `strategies.broker_credential_id` dangling (would only happen if planner deleted an FK-referenced row, which it refuses to do — still asserted as belt + braces).
6. **COMMIT** only if all 4 verifications pass. Otherwise `ROLLBACK` + non-zero exit.

## §3 — Mode matrix

| Mode | `--inspect` (default) | `--apply` |
|---|---|---|
| Reads | yes | yes |
| Writes | no | yes (single transaction) |
| pg_dump | no | **required** before any mutation |
| Interactive confirm | no | `yes` typed required |
| Exit non-zero on planner abort | yes (prints aborts; rc=0) | yes (rc=3) |
| Exit non-zero on pg_dump fail | n/a | yes (rc=2) |
| Exit non-zero on verification fail | n/a | yes (rc=4, ROLLBACK first) |
| Exit non-zero on sacred row not in keep-list | n/a | yes |

`--inspect` is the default — running the script with NO flags is safe.

## §4 — Invocation (production EC2)

```bash
# Dry-run (safe to run anytime):
docker compose exec backend python /app/scripts/dedup_brokers.py --inspect

# Apply (requires interactive 'yes'):
docker compose exec backend python /app/scripts/dedup_brokers.py --apply
```

The backend container is the one with all `POSTGRES_*` env vars set and
where the `postgres` service hostname resolves. The script does NOT
import any `app.*` module — purely psycopg2 + standard library.

## §5 — Pre-execution checklist (Jayesh)

Before running `--apply` on prod tonight:

- [ ] Confirm market is closed (post-20:00 IST). ✓ at time of writing.
- [ ] Verify the script SHA matches what's on `fix/broker-case-dedup`:
      `docker compose exec backend sha256sum /app/scripts/dedup_brokers.py`
- [ ] Run `--inspect` first. Read the per-row plan. Confirm:
      - Sacred-row verdict is **UPDATE-case-only ✓**
      - No `ABORT` entries
      - Net row count delta is sane (~20 deletes expected per brief's count)
- [ ] Verify free space in `/tmp` for the pg_dump file (`df -h /tmp`).
- [ ] Confirm the `POSTGRES_USER` you're running as has DELETE + UPDATE
      perms on `broker_credentials` (production runs as the same app user
      that already inserts there, so this should be a no-op).

## §6 — Failure modes + recovery

| Failure | What you see | Recovery |
|---|---|---|
| Planner aborts (FK-referenced dup, unknown broker_name, etc.) | `--inspect` prints `ABORT` entries; `--apply` refuses with rc=3 | Manually re-link the FK-referenced row to the KEEP candidate (UPDATE in another table), then re-run `--inspect`. |
| `pg_dump` fails | `ABORT: pg_dump failed (exit N)` + stderr, rc=2 | Don't proceed. Investigate pg_dump binary path / perms / disk space. Re-run `--inspect` to confirm DB is untouched. |
| Verification V1-V4 fails post-mutation | `verification FAIL ...` then `ROLLBACK ✗`, rc=4 | DB is unchanged (rollback completed). Re-run `--inspect`, surface the failure mode for code review before retry. |
| Operator cancels at `yes` prompt | `--apply cancelled by operator.`, rc=0 | DB is unchanged. Re-run when ready. |
| Sacred row missing from KEEP list at apply time | `ABORT: sacred row ... not in keep-list` rc=non-zero | DB is unchanged (apply refused before pg_dump). Investigate why planner excluded it. |

### Emergency manual restore

If something catastrophic happens AFTER `COMMIT`:

```bash
# 1. Find the pg_dump file the script printed:
ls -lt /tmp/broker_credentials_pre_dedup_*.sql | head -1

# 2. Restore (DROP + recreate the table data — schema untouched):
docker compose exec backend bash -c "
  PGPASSWORD=\$POSTGRES_PASSWORD psql -h postgres -U \$POSTGRES_USER -d \$POSTGRES_DB <<SQL
    BEGIN;
    DELETE FROM broker_credentials;
    \\i /tmp/broker_credentials_pre_dedup_<TIMESTAMP>.sql
    COMMIT;
  SQL
"

# Note: the pg_dump uses --data-only + --column-inserts so it's safe to
# replay over an empty table without conflicting with the migration-owned
# schema.
```

## §7 — What the script does NOT do (out of scope)

- **Does not fix the upstream OAuth code** that inserts uppercase rows.
  That's a separate fix in `backend/app/api/auth.py` or the broker
  connector callback — recommended as a follow-up Queue. Without that
  fix, the table will accumulate uppercase rows again over time.
- **Does not modify any application code.** This script is a one-shot
  data fix; the SQLAlchemy enum at `backend/app/db/models/broker_credential.py:38`
  already uses `values_callable=lambda obj: [e.value for e in obj]` to
  validate against lowercase values, so once the data is fixed, reads
  will succeed.
- **Does not run on EC2 by itself.** Branch `fix/broker-case-dedup`
  is NOT merged. Jayesh decides when + reviews `--inspect` output
  before running `--apply`.
- **Does not touch any other table.** Only `broker_credentials`.
- **Does not bypass the unique constraint.** If the constraint exists,
  DELETE-then-UPDATE happens to side-step it because the orphan duplicate
  is gone before the case fix runs.

## §8 — Sign-off

- ✅ No code edits in `backend/app/**` or `frontend/src/**`
- ✅ Deliverable: `scripts/dedup_brokers.py` + this plan doc (2 files)
- ✅ Default mode = `--inspect` (read-only)
- ✅ `--apply` requires explicit flag + interactive `yes`
- ✅ Single transaction with `ROLLBACK` on verification failure
- ✅ pg_dump mandatory before any mutation
- ✅ Hard-coded protection for row `58b369a3-...` (THREE guards: tie-break override, planner abort, apply-time defensive check)
- ✅ Branch `fix/broker-case-dedup` — do NOT merge to main
