# Milestone 1 Deploy — Tonight

> Jayesh's manual steps after CC pushes `feat/milestone-1-ship`. No
> migration required. Tested locally on aiosqlite; production path uses
> Postgres + existing trade_markers schema (no new tables).

---

## Step 1 — Merge to `main` locally (5 min)

```bash
cd /Users/jayeshparekh/trading-bridge-chart

git fetch origin
git checkout main && git pull origin main

git merge --no-ff origin/feat/milestone-1-ship \
  -m "merge: Milestone 1 — translator wired + /api/backtest mounted + trade markers persist"

git push origin main
```

## Step 2 — Deploy to EC2 (15 min, post-4 PM IST)

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227

cd /home/ubuntu/trading-bridge
git fetch origin
git checkout main
git pull origin main

# Backend + Celery worker rebuild — celery_tasks.py changed
docker compose build backend celery_worker celery_beat

# Restart in order: workers first (so they pick up the new task code
# before the API can dispatch to them), then backend
docker compose up -d celery_worker celery_beat
docker compose up -d backend
```

## Step 3 — Verify routes are live (2 min)

```bash
# From local terminal
curl -s https://api.tradetri.com/openapi.json | jq '.paths | keys[] | select(contains("backtest"))'
# Expect:
#   "/api/backtest"
#   "/api/backtest/{run_id}"
#   "/api/backtest/{run_id}/trades"
#   "/api/backtest/{run_id}/markers"
#   "/api/strategies/{strategy_id}/backtest"   (pre-existing sync endpoint)
```

## Step 4 — End-to-end smoke test (10 min)

```bash
# Get a JWT (use your usual login flow, then capture from browser devtools)
TOKEN="<your-bearer-token>"

# Clone a PASS template — should produce a Strategy with strategy_json populated
CLONE_RESP=$(curl -s -X POST https://api.tradetri.com/api/templates/ema-crossover-9-21/clone \
  -H "Authorization: Bearer $TOKEN")
STRATEGY_ID=$(echo "$CLONE_RESP" | jq -r '.id')
echo "Cloned strategy: $STRATEGY_ID"

# Confirm the strategy has strategy_json (the new translator path)
curl -s https://api.tradetri.com/api/strategies/$STRATEGY_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.strategy_json | length'
# Expect: >0 (translator populated it on clone). If 0/null → translator
# failure path fired; check backend logs for ``template.translation.skipped``.

# Enqueue an async backtest via the NEW route
ENQUEUE_RESP=$(curl -s -X POST https://api.tradetri.com/api/backtest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"strategy_id\":\"$STRATEGY_ID\",\"timeframe\":\"5m\"}")
RUN_ID=$(echo "$ENQUEUE_RESP" | jq -r '.run_id')
echo "Run id: $RUN_ID"

# Poll until SUCCEEDED (Celery picks up + runs; ~30-60s typically)
for i in 1 2 3 4 5 6 7 8 9 10; do
  STATUS=$(curl -s https://api.tradetri.com/api/backtest/$RUN_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "  attempt $i: status=$STATUS"
  if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
  sleep 5
done

# Markers endpoint
curl -s https://api.tradetri.com/api/backtest/$RUN_ID/markers \
  -H "Authorization: Bearer $TOKEN" | jq '.markers | length'
# Expect: 2 × total_trades (1 entry + 1 exit per trade). If 0 with
# total_trades > 0, check logs for ``backtest.markers.persist_failed``.
```

## Step 5 — Tail logs for 15 minutes

```bash
docker compose logs -f --since 5m backend celery_worker | grep -E '(template.translation|backtest.markers|backtest.run)'
```

Watch for:
- `template.translation.skipped` — non-PASS template was cloned (expected for the 21/29 unsupported templates).
- `backtest.markers.persist_completed` — markers wrote successfully.
- `backtest.markers.persist_failed` — needs investigation (marker write failed but backtest succeeded; chart will be empty).
- `backtest.run.completed` — happy-path completion.

---

## Rollback procedure (if anything misbehaves)

```bash
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@43.205.195.227

cd /home/ubuntu/trading-bridge
git checkout main^   # one commit back = pre-merge state
docker compose build backend celery_worker celery_beat
docker compose up -d celery_worker celery_beat
docker compose up -d backend
```

Then locally:
```bash
git checkout main
git reset --hard origin/main^
git push origin main --force-with-lease   # DANGER: only if absolutely needed
```

NO data migration was applied — rollback is purely code.

---

## Pre-flight safety
- ✅ No alembic migration in this branch
- ✅ Live BSE LTD Dhan strategy untouched (no execution code modified)
- ✅ No live-trading code paths modified (`strategy_executor.py`, `order_router.py`, `direct_exit.py`, `live_orders/*`, broker connectors — all clean)
- ✅ Existing `/api/strategies/{id}/backtest` synchronous endpoint coexists with the new async `/api/backtest`
- ✅ Pre-existing template-clone path remains functional for templates the translator can't handle (strategy_json stays NULL, frontend UI fallback fires)
