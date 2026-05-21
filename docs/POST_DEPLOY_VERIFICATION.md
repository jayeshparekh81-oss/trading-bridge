# Post-Deploy Verification Runbook — Milestone 1 + 3

> Companion to `docs/MILESTONE_1_DEPLOY.md`. That doc is the canonical
> deploy sequence; this doc is the paste-able **verification** layer
> Jayesh runs before, during, and after the deploy.
>
> **Branch SHA at session prep:** `feat/milestone-1-ship` HEAD `3c701a0`
> (Queue HH verification time: 2026-05-21 11:35 IST).
>
> **Two corrections vs Queue HH brief** (use values in THIS file, not the
> brief): EC2 IP is `43.205.195.227` (not `13.127.224.68`); clone endpoint
> is `POST /api/templates/{slug}/clone` (not `POST /api/strategies/clone-template`).

---

## §A. Pre-merge verification (local, before `git push origin main`)

```bash
cd /Users/jayeshparekh/trading-bridge-chart

# A1 — Confirm the merge target SHA matches Queue FF's final SHA.
git log feat/milestone-1-ship --oneline -5
# Expected first line: 3c701a0 docs(queue-ff): final report ...

# A2 — Confirm 'main' is current.
git fetch origin
git rev-parse origin/main
git log main..feat/milestone-1-ship --oneline | wc -l
# Expected: a small number (the Milestone 1 + 3 commits).

# A3 — Confirm NO live-trading code in the delta.
git diff main..feat/milestone-1-ship --stat -- \
  'backend/app/strategy_engine/live_orders/' \
  'backend/app/api/webhook*.py' \
  'backend/app/services/order_router*.py' \
  'backend/app/services/broker*.py' \
  'backend/app/strategy_engine/paper_trading/' \
  'backend/app/api/kill_switch*.py'
# Expected: empty output (or only test files). NON-empty = STOP, audit each line.

# A4 — Confirm NO seed-file changes (Queue GG/Queue HH guardrails).
git diff main..feat/milestone-1-ship --stat -- 'backend/data/strategy_templates_seed.json'
# Expected: empty output.

# A5 — Confirm no migrations (deploy assumes no alembic upgrade).
git diff main..feat/milestone-1-ship --name-only -- 'backend/alembic/versions/' | wc -l
# Expected: 0
```

If any of A3/A4/A5 surfaces unexpected files → **STOP and audit before pushing.**

---

## §B. Deploy execution (paste-block, post-4 PM IST)

> See `docs/MILESTONE_1_DEPLOY.md` for the authoritative sequence. The
> below is the same flow consolidated for fast paste.

```bash
# B1 — Local: merge + push to main
cd /Users/jayeshparekh/trading-bridge-chart
git checkout main && git pull origin main
git merge --no-ff origin/feat/milestone-1-ship \
  -m "merge: Milestone 1 + 3 — translator + async backtest API + chart panel"
git push origin main

# B2 — EC2: pull + rebuild containers
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227

cd /home/ubuntu/trading-bridge
git fetch origin && git checkout main && git pull origin main
git log --oneline -5    # confirm Milestone 1 + 3 commits present

# Backend + Celery rebuild — celery_tasks.py changed in Milestone 1.
docker compose build backend celery_worker celery_beat

# Workers first (so they have the new task code before API dispatches), then API.
docker compose up -d celery_worker celery_beat
docker compose up -d backend

docker compose ps    # expect 5+ running containers; backend Up; workers Up
```

---

## §C. Smoke tests — five curls in order

Each curl shows the expected success signal and the typical failure shape.

### C1 — Health check (sanity, NOT a Milestone 1 test)

```bash
curl -s https://api.tradetri.com/health | jq .
```
- **Expected:** `{"status": "ok", ...}` HTTP 200.
- **Failure:** `502` = backend not booted. Run `docker compose logs backend --tail 200`. Common cause: env var missing in `.env.production`.

### C2 — OpenAPI shows the 4 new backtest routes are mounted

```bash
curl -s https://api.tradetri.com/openapi.json | jq '.paths | keys[] | select(contains("backtest"))'
```
- **Expected (exactly these 5):**
  ```
  "/api/backtest"
  "/api/backtest/{run_id}"
  "/api/backtest/{run_id}/markers"
  "/api/backtest/{run_id}/trades"
  "/api/strategies/{strategy_id}/backtest"
  ```
- **Failure:** any of the first 4 missing = router not registered. Check `docker compose logs backend --tail 100 | grep -i 'include_router\|ImportError'`.

### C3 — Clone a translator-PASS template (Milestone 1 happy path)

```bash
# Capture your JWT from browser devtools (Application → Local Storage → tb_access_token).
TOKEN="<paste-jayesh-token-here>"

CLONE_RESP=$(curl -s -X POST \
  "https://api.tradetri.com/api/templates/ema-crossover-9-21/clone" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")
STRATEGY_ID=$(echo "$CLONE_RESP" | jq -r '.id')
echo "Cloned strategy: $STRATEGY_ID"

# Confirm strategy_json is populated (translator fired on clone path).
curl -s "https://api.tradetri.com/api/strategies/$STRATEGY_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '.strategy_json | length'
```
- **Expected:** `STRATEGY_ID` is a UUID; final number > 0 (translator populated `strategy_json`).
- **Failure modes:**
  - `STRATEGY_ID` is `null` → clone endpoint returned an error; check `echo "$CLONE_RESP"`.
  - Final number is `0` or `null` → translator FAILURE on a known-PASS template; check `docker compose logs backend | grep template.translation`. Surface IMMEDIATELY.

### C4 — Enqueue async backtest

```bash
ENQUEUE_RESP=$(curl -s -X POST https://api.tradetri.com/api/backtest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"strategy_id\":\"$STRATEGY_ID\",\"symbol\":\"NIFTY\",\"timeframe\":\"5m\",\"start\":\"2026-05-01T00:00:00Z\",\"end\":\"2026-05-20T00:00:00Z\",\"initial_capital\":100000,\"quantity\":1}")
RUN_ID=$(echo "$ENQUEUE_RESP" | jq -r '.run_id')
echo "Run id: $RUN_ID  (cached=$(echo "$ENQUEUE_RESP" | jq -r '.cached'))"
```
- **Expected:** HTTP 202 (new) or 200 (cache hit); `run_id` is a UUID; `cached` is boolean.
- **Failure modes:**
  - `422` → schema mismatch on request body; check the field names against `BacktestEnqueueRequest`.
  - `429` → rate-limited (`BACKTEST_RATE_LIMIT_PER_HOUR=30`). Wait + retry.
  - `500` → Celery dispatch failure; check `docker compose logs backend | grep enqueue`.

### C5 — Poll until SUCCEEDED + fetch markers

```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  STATUS=$(curl -s "https://api.tradetri.com/api/backtest/$RUN_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "attempt $i: status=$STATUS"
  if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
  sleep 5
done

# Markers — should match the trade count produced by the engine.
curl -s "https://api.tradetri.com/api/backtest/$RUN_ID/markers" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.markers | length), sample: .markers[0:2]}'
```
- **Expected:** `STATUS=SUCCEEDED` inside 10 attempts; markers count ≈ 2 × trade count (one entry + one exit per trade). For `ema-crossover-9-21` on Queue BB's synthetic harness: ~22 markers from 11 trades.
- **Failure modes:**
  - Stays `PENDING` 10× → Celery worker not consuming. `docker compose logs celery_worker --tail 100 | grep -E "(ERROR|backtest)"`.
  - `FAILED` → check `curl .../api/backtest/$RUN_ID | jq .error` for traceback.
  - Markers count `0` despite SUCCEEDED → check `docker compose logs backend | grep backtest.markers.persist`. Could be the celery post-success hook silently failed.

---

## §D. Live BSE LTD Dhan health (THE most important verification)

The live BSE LTD Dhan strategy `89423ecc-c76e-432c-b107-0791508542f0` must
keep functioning after deploy. Run this within 30 min of the deploy:

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227 \
  "docker compose logs backend celery_worker --since 30m | grep -iE '(89423ecc|order_router|webhook|live_orders|kill_switch)' | grep -iE '(error|exception|traceback|fail)' | head -50"
```
- **Expected:** empty output (no errors mentioning the live strategy / order paths in the last 30 min).
- **NON-empty:** investigate IMMEDIATELY before market close (3:30 IST window).

### Quick "is the engine still ticking?" check

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227 \
  "docker compose logs backend --since 5m | grep -E '(broker|tick|candle|heartbeat)' | wc -l"
```
- **Expected:** > 0 (broker traffic flowing in the last 5 min — assumes market open).
- **Zero:** broker disconnected. Cross-check from chart UI (`StatusPill`) before declaring an incident.

---

## §E. Rollback plan (if smoke fails irrecoverably)

```bash
# On EC2:
cd /home/ubuntu/trading-bridge

# Find the previous known-good main SHA (commit before the merge).
git log main --oneline -10
PREV_GOOD="<sha-of-pre-milestone-1-main>"   # tag manually before deploy

git checkout "$PREV_GOOD"
docker compose build backend celery_worker celery_beat
docker compose up -d celery_worker celery_beat backend
docker compose ps

# Verify health restored
curl -s https://api.tradetri.com/health | jq .
```

> **Pre-deploy tip:** before merging to `main` tonight, tag the current
> `main` HEAD: `git tag pre-milestone-1-main && git push origin pre-milestone-1-main`.
> Rollback then becomes `git checkout pre-milestone-1-main`.

---

## §F. Verification checklist (paste into deploy chat)

- [ ] §A pre-merge guards: A3 (no live-trading diff), A4 (no seed diff), A5 (no migrations) all empty
- [ ] §B deploy executed: `docker compose ps` shows backend + workers Up
- [ ] §C1 health: 200
- [ ] §C2 OpenAPI: 4 new backtest routes mounted
- [ ] §C3 clone: `strategy_json` populated
- [ ] §C4 enqueue: `run_id` returned
- [ ] §C5 markers: SUCCEEDED + non-zero marker count
- [ ] §D live BSE LTD: zero errors in last 30 min
- [ ] §F (this checklist) marked complete in deploy notes
