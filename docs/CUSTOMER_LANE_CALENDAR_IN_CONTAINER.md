# The calendar is not in the deployed image — options

**Status: NEEDS FOUNDER DECISION. Nothing here has been implemented.**
Every option below requires an image rebuild or a container recreate, which this
run was not permitted to do.

## The finding (run G, read-only, verified inside the running containers)

```
$ docker exec trading_bridge_backend sh -c 'ls /app'
alembic.ini  app  data  migrations  scripts

$ docker exec trading_bridge_backend sh -c 'find / -name "holidays.yaml" ...'
(nothing)

$ docker exec trading_bridge_celery_worker sh -c 'find / -name "holidays.yaml" ...'
(nothing)

candidate 1 : /orderflow_engine/holidays.yaml                          -> exists: False
candidate 2 : /home/ubuntu/trading-bridge/orderflow_engine/holidays.yaml -> exists: False

$ docker inspect -f '{{range .Mounts}}...' trading_bridge_backend
(no mounts)
```

**Verdict: NOT RESOLVABLE inside the deployed image.**

**Why, structurally:** `docker-compose.yml` builds the backend with
`context: ./backend`. `orderflow_engine/` is a *sibling* of `backend/`, so it is
outside the build context and Docker cannot `COPY` it in. This is not an
oversight in the Dockerfile — it is a consequence of the context boundary.

**Consequence today:** `is_trading_day()` raises `CalendarUnavailable` in
production. That is the correct fail-loud behaviour, but it means the ladder
would never run. The lane therefore now **refuses to arm** at beat registration
(`app/domains/customer_lane/preflight.py`) rather than arming and failing every
morning at 07:45 in a worker log.

## What must NOT be done

**Do not vendor a copy of `holidays.yaml` into `backend/`.** The founder ruling of
13 Aug 2026 makes `orderflow_engine/holidays.yaml` the single source of record,
and `pine_replica/executor/session_calendar.py` already reads that same file
cross-repo rather than copying it. Two calendars that drift is a worse failure
than no calendar, because it fails silently.

## Options

### A — bind-mount the file read-only (least invasive)

```yaml
# docker-compose.yml, backend + celery_worker + celery_beat
volumes:
  - ./orderflow_engine/holidays.yaml:/app/orderflow_engine/holidays.yaml:ro
```

- **For:** no image rebuild; the file stays the one source; read-only, so a
  container cannot corrupt it; the resolver's candidate 1 then hits, since
  `/app/app/domains/customer_lane/calendar.py`'s `parents[4]` is `/` — so the
  mount destination must be `/orderflow_engine/holidays.yaml`, **not**
  `/app/orderflow_engine/...`. Set `CUSTOMER_LANE_HOLIDAYS_FILE` instead if a
  tidier destination is wanted.
- **Against:** requires a container recreate to take effect; these containers
  currently have **no mounts at all**, so this introduces the first one; the file
  must exist on the host at the deploy path (it does — the deploy dir is
  `/home/ubuntu/trading-bridge`).

### B — widen the build context to the repo root

```yaml
build:
  context: .
  dockerfile: backend/Dockerfile
```
plus `COPY orderflow_engine/holidays.yaml ./orderflow_engine/holidays.yaml`.

- **For:** the calendar ships *with* the image, so the image is self-contained
  and a container started anywhere behaves identically.
- **Against:** every `COPY` path in the Dockerfile must gain a `backend/` prefix;
  the build context grows from `backend/` to the whole repo (slower builds, and
  `.dockerignore` becomes load-bearing); it bakes a point-in-time copy into each
  image, so refreshing the calendar for a new year needs a rebuild — which
  partially defeats "one live file".

### C — explicit path config (complement, not an alternative)

`CUSTOMER_LANE_HOLIDAYS_FILE=/some/path/holidays.yaml` is already supported by
`calendar.py`. On its own it solves nothing: without A or B the file is still not
in the container. Useful **with** A to decouple the mount destination from the
resolver's default candidates.

### D — a sync job that copies the file in

**Rejected.** It creates the second calendar the 13 Aug ruling forbids, and a
stale copy fails silently — the worst failure mode of the four.

## DECISION (founder, run H): **A + C — read-only mount plus the env var**

The env var is the **primary** mechanism because the resolver's `parents[4]` path
arithmetic is brittle and breaks if the file or the module moves. The mount is what
makes the file present. It is **read-only** so no container can ever write to the
single source of record.

### PREPARED, NOT APPLIED

The compose change is **committed on `feat/customer-lane-full` and deliberately not
applied**. It requires a container recreate, which no run so far has been permitted
to do. Verified still unapplied at the time of writing: `docker inspect` reports 0
mounts on backend, 0 on celery_worker and 1 on celery_beat (the pre-existing
`celery-data`), and `/opt/tradetri/holidays.yaml` does not exist in the container.

Mounted on all three services that could run lane code:

```yaml
    volumes:
      - ./orderflow_engine/holidays.yaml:/opt/tradetri/holidays.yaml:ro
```

### APPLY PROCEDURE (one page)

1. **Founder go.** This recreates containers; do it outside market hours.
2. Add to `backend/.env` on the box:
   ```
   CUSTOMER_LANE_HOLIDAYS_FILE=/opt/tradetri/holidays.yaml
   ```
3. Confirm the source file exists on the host at the deploy path:
   ```bash
   ls -l /home/ubuntu/trading-bridge/orderflow_engine/holidays.yaml
   ```
4. Recreate ONLY the services that need it. `celery_worker` first — it runs the
   ladder — then `celery_beat`, then `backend`:
   ```bash
   cd /home/ubuntu/trading-bridge
   docker compose up -d --no-deps celery_worker celery_beat backend
   ```
5. **Verify inside the container before believing it:**
   ```bash
   docker exec trading_bridge_celery_worker ls -l /opt/tradetri/holidays.yaml
   docker exec trading_bridge_celery_worker python -c \
     "from app.domains.customer_lane import preflight; print(preflight.check())"
   ```
   Expect `ready=True` (or `rung_transport_missing`, which is the separate voice
   blocker — the calendar half is then proven).
6. **Verify it is read-only** — this must FAIL:
   ```bash
   docker exec trading_bridge_celery_worker sh -c 'echo x >> /opt/tradetri/holidays.yaml'
   ```
7. Roll back by reverting the compose change and recreating the same three services.

### Why not B

B (widen the build context to the repo root) is defensible if self-contained images
are wanted, but every `COPY` path gains a `backend/` prefix, the build context grows
to the whole repo, and it bakes a point-in-time copy into each image — so refreshing
the calendar for a new year would need a rebuild, partially defeating "one live
file".

## Until a decision is made

The lane stays disarmed. `CUSTOMER_LANE_BEAT_ENABLED` is false, and even if it
were flipped, `register_beat_entries` raises `CustomerLaneNotReady` naming the
subsystem and the missing file. Check the state any time with:

```bash
cd backend && .venv/bin/python -c "from app.domains.customer_lane import preflight; print(preflight.check())"
```
