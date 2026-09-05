#!/usr/bin/env bash
# Create + migrate the customer-lane scratch database.
#
# tests/customer_lane/* run against a throwaway Postgres (docker-compose-test.yml,
# localhost:5433). The database is deliberately NOT the shared trading_bridge_test:
# these tests write and roll back constantly, and a private database keeps that
# blast radius at zero.
#
# Idempotent. Safe to re-run. Creates nothing outside localhost:5433.
#
#   ./scripts/cl_test_db.sh            uses the default name cl_scratch
#   CL_DB=other ./scripts/cl_test_db.sh
set -euo pipefail

CONTAINER="${CL_TEST_CONTAINER:-trading_bridge_postgres_test}"
DB="${CL_DB:-cl_scratch}"
USER_="${CL_TEST_USER:-trading_bridge_test}"
PASS="${CL_TEST_PASSWORD:-test_password_do_not_use_in_prod}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker exec "$CONTAINER" pg_isready -U "$USER_" >/dev/null 2>&1; then
  echo "ERROR: test postgres container '$CONTAINER' is not running." >&2
  echo "  start it with:  docker start $CONTAINER" >&2
  echo "  (or bring the compose test stack up)" >&2
  exit 1
fi

if docker exec "$CONTAINER" psql -U "$USER_" -d postgres -tAc \
     "SELECT 1 FROM pg_database WHERE datname='$DB';" | grep -q 1; then
  echo "database '$DB' already exists"
else
  docker exec "$CONTAINER" psql -U "$USER_" -d postgres -c "CREATE DATABASE $DB;" >/dev/null
  echo "created database '$DB'"
fi

export DATABASE_URL="postgresql+asyncpg://${USER_}:${PASS}@localhost:5433/${DB}"
cd "$HERE"
.venv/bin/python -m alembic upgrade head >/dev/null
echo "migrated '$DB' to $(.venv/bin/python -m alembic current 2>/dev/null | tail -1)"
echo
echo "now run:"
echo "  cd backend && CL_SCRATCH_URL=\"\$DATABASE_URL\" DATABASE_URL=\"\$DATABASE_URL\" .venv/bin/python -m pytest tests/customer_lane/ -q --no-cov"
