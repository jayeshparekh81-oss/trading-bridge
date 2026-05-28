#!/usr/bin/env python3
"""Dedup + case-normalise broker_credentials (Queue LL).

Production state: 38 rows in broker_credentials, of which 37 carry the
broker_name in UPPERCASE ('DHAN' / 'FYERS'). The ORM expects lowercase
('dhan' / 'fyers') — every read path 500s. Many users have duplicate
rows from OAuth reconnect flows; one user has BOTH 'dhan' and 'DHAN'
simultaneously, blocking the naive UPDATE that 002_fix_broker_name_case
tried (UniqueConstraint conflict if it actually exists).

This script discovers the live schema (FK tables + uniqueness constraints)
via information_schema at runtime, then plans:
    - rows to KEEP and UPDATE-case (FK-referenced rows + tie-break winner)
    - rows to DELETE (orphan duplicates with zero FK references)

The live BSE LTD strategy's broker_credential_id row is HARD-CODED as
sacred — if the plan would DELETE it, the script aborts with non-zero.

Default mode is --inspect (read-only). --apply requires both an explicit
flag and an interactive y/N confirmation, runs pg_dump before mutating,
performs all changes inside a single transaction, and rolls back on any
post-mutation verification failure.

Invocation (production EC2):
    docker compose exec backend python /app/scripts/dedup_brokers.py --inspect
    docker compose exec backend python /app/scripts/dedup_brokers.py --apply

Connection: env vars POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB,
default host `postgres` (Docker compose service name), default port 5432.
The script does NOT import any application module — it is a self-contained
psycopg2-only utility so failed imports in app/* can't break the fix.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor


# ─── Sacred constants ─────────────────────────────────────────────────────

# Live BSE LTD Dhan strategy's linked broker_credential. This row MUST
# survive the dedup as an UPDATE (case fix only). If the planner ever
# marks it for DELETE, the script aborts with non-zero. Verified manually
# by Jayesh before this script was authored.
SACRED_ROW_ID = "58b369a3-e590-475a-b687-de931c07c064"

# The strategy it's linked to — used only for sanity prints, not for
# guarding. The guard is on the broker_credential row id above.
SACRED_STRATEGY_ID = "89423ecc-c76e-432c-b107-0791508542f0"

# Valid post-fix broker_name values. Anything else surviving in the table
# at the end of the transaction is a verification failure → ROLLBACK.
ALLOWED_LOWERCASE = frozenset({"dhan", "fyers"})

# Table under operation.
TABLE = "broker_credentials"

# Backup file naming convention.
BACKUP_DIR = "/tmp"


# ─── Connection helpers ───────────────────────────────────────────────────


def _connect() -> PgConnection:
    """Open a psycopg2 connection from env vars. No SQLAlchemy, no app
    imports — keeps the failure surface tight to libpq + this script."""
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")

    missing = [k for k, v in [("POSTGRES_USER", user), ("POSTGRES_PASSWORD", password), ("POSTGRES_DB", db)] if not v]
    if missing:
        sys.exit(f"ABORT: missing required env vars: {', '.join(missing)}")

    conn = psycopg2.connect(
        user=user, password=password, dbname=db, host=host, port=port
    )
    # Stay in transaction-per-statement until --apply explicitly begins one.
    conn.autocommit = True
    return conn


def _dict_cursor(conn: PgConnection) -> PgCursor:
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ─── Schema discovery ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class FkRef:
    """One FK from another table pointing at broker_credentials.id."""

    table: str
    column: str
    on_delete: str  # 'r' = restrict, 'c' = cascade, 'n' = set null, 'a' = no action


@dataclass(frozen=True)
class UniqueConstraint:
    table: str
    name: str
    columns: tuple[str, ...]


def discover_fk_refs(conn: PgConnection) -> list[FkRef]:
    """Return every FK in any schema pointing at broker_credentials.id.

    Uses pg_catalog (more reliable than information_schema for
    cross-schema FKs + delete actions). Empty list means the table is
    orphan — deletes are free.
    """
    sql = """
        SELECT
            ns.nspname AS schema_name,
            cls.relname AS table_name,
            att.attname AS column_name,
            con.confdeltype AS on_delete
        FROM pg_constraint con
        JOIN pg_class cls       ON cls.oid = con.conrelid
        JOIN pg_namespace ns    ON ns.oid = cls.relnamespace
        JOIN pg_class ref_cls   ON ref_cls.oid = con.confrelid
        JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
        JOIN pg_attribute att   ON att.attrelid = cls.oid AND att.attnum = k.attnum
        WHERE con.contype = 'f'
          AND ref_cls.relname = %s
        ORDER BY cls.relname, att.attname;
    """
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (TABLE,))
        rows = cur.fetchall()
    return [
        FkRef(table=r["table_name"], column=r["column_name"], on_delete=r["on_delete"])
        for r in rows
    ]


def discover_unique_constraints(conn: PgConnection) -> list[UniqueConstraint]:
    """Return all UNIQUE / EXCLUSION constraints on broker_credentials.

    The brief asserts a `uniq_active_broker_per_user` on (user_id,
    broker_name) exists — but it's NOT in any migration file. It may have
    been added out-of-band, or named differently, or live as a partial
    unique index. We discover at runtime so the script doesn't depend on
    the brief's assertion.
    """
    sql = """
        SELECT con.conname AS name,
               array_agg(att.attname ORDER BY k.ord) AS columns,
               con.contype AS contype
        FROM pg_constraint con
        JOIN pg_class cls       ON cls.oid = con.conrelid
        JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
        JOIN pg_attribute att   ON att.attrelid = cls.oid AND att.attnum = k.attnum
        WHERE cls.relname = %s
          AND con.contype IN ('u', 'x')
        GROUP BY con.conname, con.contype
        ORDER BY con.conname;
    """
    # Plus partial unique indexes (which don't appear as pg_constraint rows).
    idx_sql = """
        SELECT idx.indexrelid::regclass::text AS name,
               array_agg(att.attname ORDER BY k.ord) AS columns,
               pg_get_expr(idx.indpred, idx.indrelid) AS where_clause
        FROM pg_index idx
        JOIN pg_class cls   ON cls.oid = idx.indrelid
        JOIN unnest(idx.indkey) WITH ORDINALITY AS k(attnum, ord) ON true
        JOIN pg_attribute att ON att.attrelid = cls.oid AND att.attnum = k.attnum
        WHERE cls.relname = %s
          AND idx.indisunique
          AND idx.indpred IS NOT NULL
        GROUP BY idx.indexrelid, idx.indpred, idx.indrelid;
    """
    out: list[UniqueConstraint] = []
    with _dict_cursor(conn) as cur:
        cur.execute(sql, (TABLE,))
        for r in cur.fetchall():
            out.append(UniqueConstraint(table=TABLE, name=r["name"], columns=tuple(r["columns"])))
        cur.execute(idx_sql, (TABLE,))
        for r in cur.fetchall():
            # Partial unique index — surface explicitly so the plan accounts for it.
            label = f"{r['name']} (partial: WHERE {r['where_clause']})"
            out.append(UniqueConstraint(table=TABLE, name=label, columns=tuple(r["columns"])))
    return out


# ─── Row inventory + FK-ref count per row ─────────────────────────────────


@dataclass
class BrokerRow:
    id: uuid.UUID
    user_id: uuid.UUID
    broker_name: str
    is_active: bool
    created_at: datetime
    # Filled by load_fk_ref_counts():
    fk_refs: dict[str, int] = field(default_factory=dict)

    @property
    def total_fk_refs(self) -> int:
        return sum(self.fk_refs.values())


def load_rows(conn: PgConnection) -> list[BrokerRow]:
    sql = f"SELECT id, user_id, broker_name, is_active, created_at FROM {TABLE} ORDER BY user_id, created_at"
    with _dict_cursor(conn) as cur:
        cur.execute(sql)
        return [
            BrokerRow(
                id=r["id"],
                user_id=r["user_id"],
                broker_name=r["broker_name"],
                is_active=r["is_active"],
                created_at=r["created_at"],
            )
            for r in cur.fetchall()
        ]


def load_fk_ref_counts(
    conn: PgConnection, rows: list[BrokerRow], fk_refs: list[FkRef]
) -> None:
    """For each FK table, fan out a COUNT(*) GROUP BY query and merge
    results into row.fk_refs. Single round-trip per FK table — N+1 free."""
    id_to_row = {r.id: r for r in rows}
    for fk in fk_refs:
        sql = f"SELECT {fk.column} AS bc_id, COUNT(*) AS n FROM {fk.table} GROUP BY {fk.column}"
        with _dict_cursor(conn) as cur:
            cur.execute(sql)
            for r in cur.fetchall():
                row = id_to_row.get(r["bc_id"])
                if row is None:
                    continue  # FK points at a broker_credential id that's not in our snapshot — odd but harmless
                row.fk_refs[fk.table] = int(r["n"])


# ─── Plan construction ────────────────────────────────────────────────────


@dataclass
class Plan:
    keep_and_case_fix: list[BrokerRow] = field(default_factory=list)  # UPDATE broker_name = lower(...)
    keep_unchanged: list[BrokerRow] = field(default_factory=list)     # already lowercase, no action
    delete: list[BrokerRow] = field(default_factory=list)             # orphan duplicates
    aborts: list[str] = field(default_factory=list)                   # reasons to refuse to --apply


def build_plan(rows: list[BrokerRow]) -> Plan:
    """Group rows by (user_id, lower(broker_name)); within each group pick
    one KEEP via the tie-break rules (FK refs > most recent > is_active).

    Tie-break rules (applied in order):
        1. Row with the most FK refs wins (loss of FK refs = data loss).
        2. Most-recently created (created_at DESC) wins (newer OAuth session).
        3. is_active=True wins.

    Sacred row guard: if the chosen KEEP for a group is NOT the sacred
    row but the sacred row IS in the group, override — sacred row always
    wins KEEP. If sacred row would otherwise be DELETED, abort.
    """
    plan = Plan()
    groups: dict[tuple[uuid.UUID, str], list[BrokerRow]] = {}
    for r in rows:
        groups.setdefault((r.user_id, r.broker_name.lower()), []).append(r)

    for (user_id, lower_name), grp in groups.items():
        if lower_name not in ALLOWED_LOWERCASE:
            plan.aborts.append(
                f"Unknown broker_name (lower)={lower_name!r} for user {user_id}; "
                f"expected one of {sorted(ALLOWED_LOWERCASE)}. Investigate manually."
            )
            continue

        # Sort by tie-break rules; the first element after sort is the KEEP candidate.
        grp_sorted = sorted(
            grp,
            key=lambda r: (-r.total_fk_refs, -r.created_at.timestamp(), 0 if r.is_active else 1),
        )
        keep = grp_sorted[0]
        rest = grp_sorted[1:]

        # Sacred row override — always keep, never delete.
        sacred_in_group = next((r for r in grp if str(r.id) == SACRED_ROW_ID), None)
        if sacred_in_group is not None and keep.id != sacred_in_group.id:
            # Override: the sacred row becomes the KEEP, the prior KEEP joins the DELETE candidates.
            rest = [r for r in grp if r.id != sacred_in_group.id]
            keep = sacred_in_group

        # KEEP row: case-fix if uppercase, leave alone if already lowercase.
        if keep.broker_name == lower_name:
            plan.keep_unchanged.append(keep)
        else:
            plan.keep_and_case_fix.append(keep)

        # The rest: delete IF zero FK refs, else abort (we'd lose audit data).
        for r in rest:
            if str(r.id) == SACRED_ROW_ID:
                plan.aborts.append(
                    f"FATAL: sacred row {SACRED_ROW_ID} marked for DELETE — "
                    f"planner bug. Aborting before any mutation."
                )
                continue
            if r.total_fk_refs > 0:
                plan.aborts.append(
                    f"Row {r.id} (user {r.user_id}, broker={r.broker_name!r}) "
                    f"has {r.total_fk_refs} FK refs across {sorted(r.fk_refs)}; "
                    f"refusing to DELETE. Manually re-link to the KEEP row "
                    f"{keep.id} first, then re-run."
                )
                continue
            plan.delete.append(r)
    return plan


# ─── Inspection (read-only) ───────────────────────────────────────────────


def print_inspection(
    conn: PgConnection,
    rows: list[BrokerRow],
    fk_refs: list[FkRef],
    uniques: list[UniqueConstraint],
    plan: Plan,
) -> None:
    print(f"\n=== {TABLE}: discovered schema ===")
    print(f"  rows total:          {len(rows)}")
    by_case: dict[str, int] = {}
    for r in rows:
        by_case[r.broker_name] = by_case.get(r.broker_name, 0) + 1
    for name, n in sorted(by_case.items()):
        marker = "" if name == name.lower() else "  ← will UPDATE"
        print(f"    {name!r:14s} x {n}{marker}")

    print(f"\n  FK tables referencing {TABLE}.id ({len(fk_refs)}):")
    for fk in fk_refs:
        on_del = {"r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "a": "NO ACTION"}.get(fk.on_delete, fk.on_delete)
        print(f"    {fk.table}.{fk.column}  (ON DELETE {on_del})")

    print(f"\n  Unique constraints / partial unique indexes ({len(uniques)}):")
    for u in uniques:
        print(f"    {u.name}  on ({', '.join(u.columns)})")
    if not uniques:
        print("    (none discovered — naive UPDATE is safe schema-wise)")

    print("\n=== Plan ===")
    print(f"  keep + case-fix (UPDATE):  {len(plan.keep_and_case_fix)}")
    print(f"  keep unchanged:            {len(plan.keep_unchanged)}")
    print(f"  delete (orphan dup):       {len(plan.delete)}")
    print(
        f"  net row count delta:       "
        f"{len(rows) - len(plan.delete)} (from {len(rows)}, -{len(plan.delete)})"
    )

    # Per-row plan
    if plan.keep_and_case_fix:
        print("\n  --- UPDATE (case fix) ---")
        for r in plan.keep_and_case_fix:
            sacred = "  ← SACRED" if str(r.id) == SACRED_ROW_ID else ""
            print(
                f"    {r.id}  user={r.user_id}  "
                f"{r.broker_name!r} -> {r.broker_name.lower()!r}  "
                f"FK={r.total_fk_refs}{sacred}"
            )
    if plan.delete:
        print("\n  --- DELETE (orphan duplicates, zero FK refs) ---")
        for r in plan.delete:
            print(
                f"    {r.id}  user={r.user_id}  "
                f"name={r.broker_name!r}  active={r.is_active}  "
                f"created={r.created_at.isoformat()}"
            )

    # Sacred-row verification
    sacred = next((r for r in rows if str(r.id) == SACRED_ROW_ID), None)
    print("\n=== Sacred-row check ===")
    if sacred is None:
        print(f"  WARNING: sacred row {SACRED_ROW_ID} NOT FOUND in {TABLE}. Investigate before --apply.")
    else:
        in_update = any(str(r.id) == SACRED_ROW_ID for r in plan.keep_and_case_fix)
        in_keep = any(str(r.id) == SACRED_ROW_ID for r in plan.keep_unchanged)
        in_delete = any(str(r.id) == SACRED_ROW_ID for r in plan.delete)
        verdict = (
            "UPDATE-case-only ✓" if in_update
            else "ALREADY-LOWERCASE-NO-CHANGE ✓" if in_keep
            else "DELETE ✗ FATAL" if in_delete
            else "MISSING FROM PLAN ✗ FATAL"
        )
        print(f"  sacred row {SACRED_ROW_ID}: {verdict}")
        print(f"    current broker_name = {sacred.broker_name!r}, FK refs = {sacred.total_fk_refs}")
        print(f"    target  broker_name = {sacred.broker_name.lower()!r}")

    if plan.aborts:
        print("\n=== ABORTS (--apply will refuse) ===")
        for msg in plan.aborts:
            print(f"  ✗ {msg}")
    else:
        print("\n=== ABORTS ===\n  (none — plan is apply-clean)")


# ─── Apply (mutating) ─────────────────────────────────────────────────────


def confirm_interactive() -> bool:
    """Block until the operator types 'yes' or 'no'. 'y'/'n' rejected."""
    try:
        ans = input("\nType 'yes' to apply, anything else to cancel: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\ncancelled.")
        return False
    return ans == "yes"


def run_pg_dump(db: str) -> str:
    """Dump the broker_credentials table to /tmp before any mutation.
    Returns the absolute path on success; aborts with non-zero on failure.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = f"{BACKUP_DIR}/broker_credentials_pre_dedup_{timestamp}.sql"

    pg_user = os.environ["POSTGRES_USER"]
    pg_host = os.environ.get("POSTGRES_HOST", "postgres")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    env = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}

    cmd = [
        "pg_dump",
        "-h", pg_host, "-p", pg_port, "-U", pg_user,
        "-t", TABLE,
        "--data-only",            # schema is in migrations; only data is at risk
        "--column-inserts",       # human-readable for emergency manual restore
        "-f", out_path,
        db,
    ]
    print(f"\nRunning pg_dump → {out_path}")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"\nABORT: pg_dump failed (exit {proc.returncode}):")
        print(proc.stderr)
        sys.exit(2)

    # Sanity: file exists and is non-zero
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        sys.exit(f"ABORT: pg_dump produced empty/missing file at {out_path}")
    print(f"  backup OK ({os.path.getsize(out_path)} bytes)")
    return out_path


def apply_plan(conn: PgConnection, plan: Plan, rows_before: int) -> None:
    """Execute the plan inside ONE transaction. Verify pre-COMMIT; ROLLBACK
    on any verification failure."""
    if plan.aborts:
        print("\nABORT: plan has unresolved blockers (see --inspect output). No mutation performed.")
        sys.exit(3)

    # Switch out of autocommit for the duration of the transaction.
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # 1. DELETE orphan duplicates (zero FK refs verified by planner).
            if plan.delete:
                delete_ids = tuple(str(r.id) for r in plan.delete)
                # Defensive: re-assert sacred row not in delete list (planner check + here).
                if SACRED_ROW_ID in delete_ids:
                    raise RuntimeError(
                        f"DEFENSIVE ABORT: sacred row {SACRED_ROW_ID} present in DELETE list at apply time"
                    )
                cur.execute(
                    f"DELETE FROM {TABLE} WHERE id IN %s", (delete_ids,)
                )
                if cur.rowcount != len(plan.delete):
                    raise RuntimeError(
                        f"DELETE rowcount mismatch: expected {len(plan.delete)}, got {cur.rowcount}"
                    )
                print(f"  DELETE: {cur.rowcount} rows removed.")

            # 2. UPDATE remaining rows to lowercase. We do this in ONE
            #    statement covering every row whose broker_name != lower(broker_name),
            #    which is simpler than iterating per id and covers any
            #    row the planner missed.
            cur.execute(
                f"UPDATE {TABLE} SET broker_name = LOWER(broker_name) "
                f"WHERE broker_name <> LOWER(broker_name)"
            )
            print(f"  UPDATE: {cur.rowcount} rows case-normalised.")

            # 3. Verifications pre-COMMIT.
            # 3a. Only lowercase values remain.
            cur.execute(f"SELECT DISTINCT broker_name FROM {TABLE} ORDER BY broker_name")
            remaining = [r[0] for r in cur.fetchall()]
            non_lower = [n for n in remaining if n != n.lower()]
            if non_lower:
                raise RuntimeError(f"verification FAIL — non-lowercase remain: {non_lower}")
            unknown = [n for n in remaining if n not in ALLOWED_LOWERCASE]
            if unknown:
                raise RuntimeError(f"verification FAIL — unknown broker_name values: {unknown}")
            print(f"  verify 1/4: only lowercase values remain — {remaining}")

            # 3b. Sacred row still exists, broker_name='dhan'.
            cur.execute(
                f"SELECT broker_name FROM {TABLE} WHERE id = %s", (SACRED_ROW_ID,)
            )
            sacred = cur.fetchone()
            if sacred is None:
                raise RuntimeError(
                    f"verification FAIL — sacred row {SACRED_ROW_ID} missing post-mutation"
                )
            if sacred[0] != "dhan":
                raise RuntimeError(
                    f"verification FAIL — sacred row broker_name={sacred[0]!r}, expected 'dhan'"
                )
            print(f"  verify 2/4: sacred row intact, broker_name='dhan'")

            # 3c. Row count delta matches plan.
            cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
            rows_after = cur.fetchone()[0]
            expected_after = rows_before - len(plan.delete)
            if rows_after != expected_after:
                raise RuntimeError(
                    f"verification FAIL — row count {rows_after}, expected {expected_after}"
                )
            print(f"  verify 3/4: row count {rows_after} (was {rows_before}, -{len(plan.delete)})")

            # 3d. No strategy.broker_credential_id dangling (FK is SET NULL,
            #     so dangling means strategy has a non-null FK pointing at
            #     an id no longer in broker_credentials — should be impossible
            #     if planner refused to delete FK-referenced rows, but assert).
            cur.execute(
                f"""
                SELECT s.id, s.broker_credential_id
                FROM strategies s
                WHERE s.broker_credential_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM {TABLE} bc WHERE bc.id = s.broker_credential_id
                  )
                """
            )
            dangling = cur.fetchall()
            if dangling:
                raise RuntimeError(
                    f"verification FAIL — {len(dangling)} strategies have dangling broker_credential_id: "
                    f"{[(str(r[0]), str(r[1])) for r in dangling[:5]]}"
                )
            print(f"  verify 4/4: no dangling strategy.broker_credential_id refs")

        conn.commit()
        print("\nCOMMIT ✓ — all mutations applied.")
    except Exception as exc:
        conn.rollback()
        print(f"\nROLLBACK ✗ — {exc}")
        sys.exit(4)


# ─── Main ─────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Read-only inspection (default if neither flag passed).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the plan after pg_dump backup + interactive 'yes' confirmation.",
    )
    args = parser.parse_args(argv)

    # Default to --inspect when neither flag is set.
    if not args.apply and not args.inspect:
        args.inspect = True

    if args.apply and args.inspect:
        sys.exit("ABORT: pass either --inspect OR --apply, not both.")

    db = os.environ.get("POSTGRES_DB") or ""
    if args.apply and not db:
        sys.exit("ABORT: POSTGRES_DB env var required for --apply (pg_dump target).")

    conn = _connect()
    try:
        fk_refs = discover_fk_refs(conn)
        uniques = discover_unique_constraints(conn)
        rows = load_rows(conn)
        load_fk_ref_counts(conn, rows, fk_refs)
        plan = build_plan(rows)
        print_inspection(conn, rows, fk_refs, uniques, plan)

        if args.inspect:
            print("\n(--inspect only — no mutations performed)")
            return 0

        # --apply path
        if plan.aborts:
            print("\nABORT: plan has aborts. Resolve manually and re-run --inspect.")
            return 3

        sacred_in_plan = (
            any(str(r.id) == SACRED_ROW_ID for r in plan.keep_and_case_fix + plan.keep_unchanged)
        )
        if not sacred_in_plan:
            sys.exit(
                f"\nABORT: sacred row {SACRED_ROW_ID} not in keep-list. "
                f"Refusing --apply for safety. Investigate manually."
            )

        if not confirm_interactive():
            print("--apply cancelled by operator.")
            return 0

        run_pg_dump(db)
        apply_plan(conn, plan, rows_before=len(rows))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
