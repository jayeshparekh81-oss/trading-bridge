# Real-Dhan backend deploy — gated runbook (FOUNDER runs this, step by step)

**Purpose:** ship the backend bundle currently on `main` to the EC2 prod host so the historical-backfill drain (Queue CCC/FFF) can run against real Dhan. **Founder-gated; NOT autonomous.** Every 🔴 is a hard-stop where you confirm before proceeding.

**Status going in (verified 2026-06-16):**
- Prod backend = **`cutover-12` / `a63d5e8`** (NOT cutover-8 — older docs were stale). `git -C /home/ubuntu/trading-bridge describe --tags` → `release-cutover-12`.
- Prod DB alembic head = **`028_add_backtest_runs`**.
- Prod frontend = Vercel auto-deploys `main` (already current).
- `BACKFILL_ENABLED` defaults **OFF**; `STRATEGY_PAPER_MODE=true`, `WEBHOOK_REQUIRE_HMAC=false` on prod.
- BSE LTD `89423ecc` LIVE, `is_paper=FALSE` — **must stay untouched**.
- Backend API surface is byte-identical `cutover-12 ↔ main` (the merged HHH frontend pages call only already-live endpoints), so the deploy is **migrations + services**, not new HTTP behaviour.

**What this deploy lands** (the `cutover-12 → main` delta): historical_candles store + backfill jobs/orchestrator/rate-limit-guard + A5 credential factory + migrations 029/030, the test baseline, and (if its PR is merged first) the `users.py:387` webhook-URL fix. **Do NOT include `/alerts` (M10) or migration 031** unless you've separately reviewed + merged them.

---

## 0. Pre-flight (do the morning of, market CLOSED, ideally a weekend/holiday)
- [ ] Confirm IST time is **well outside 09:15–15:25** and ideally not a trading day.
- [ ] `ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@13.127.224.68` works.
- [ ] **Verify BSE LTD is flat:** `SELECT status, count(*) FROM strategy_positions WHERE strategy_id='89423ecc-c76e-432c-b107-0791508542f0' GROUP BY status;` → no `open`. If there's an open position, **🔴 STOP** — do not deploy with a live position at risk.
- [ ] Decide creds path: **β** (`BACKFILL_DHAN_USER_ID`) or **α** (`BACKFILL_DHAN_CLIENT_ID` + `BACKFILL_DHAN_ACCESS_TOKEN`). Have the values ready.
- [ ] `cd /home/ubuntu/trading-bridge && git fetch && git log --oneline origin/main -1` — note the target SHA.

## 1. 🔴 HARD-STOP #1 — DB BACKUP FIRST (before any migration)
- [ ] `docker exec trading_bridge_postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > ~/backup_pre_realdhan_$(date +%Y%m%d_%H%M).sql.gz`
- [ ] Verify the dump is non-empty: `ls -lh ~/backup_pre_realdhan_*.sql.gz` (should be MBs, not 0).
- [ ] Note the alembic head pre-deploy: `docker exec trading_bridge_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT version_num FROM alembic_version;"` → expect `028_add_backtest_runs`.
- **Confirm backup exists + is valid before continuing.**

## 2. Pull the new backend code (no restart yet)
- [ ] `cd /home/ubuntu/trading-bridge && git checkout main && git pull --ff-only` (or check out the target tag/SHA from step 0). If checkout refuses (local changes), **🔴 STOP** and investigate — never force.
- [ ] Confirm `git rev-parse --short HEAD` matches the target.

## 3. 🔴 HARD-STOP #2 — BEFORE MIGRATIONS
- [ ] Dry-run inspect: `docker compose run --rm backend alembic history | head` and `alembic current` → confirm current is `028` and the pending chain is `029 → 030` (additive new tables: `historical_candles`, `historical_backfill_jobs`).
- [ ] **Confirm 029/030 are net-new, additive (CREATE TABLE only, no ALTER/DROP on existing).** (Verified: they are.)
- [ ] **Confirm you are NOT applying `027` again** — prod is past it (the 027 uuid<>varchar issue is a fresh-DB bootstrap problem only; never re-runs on prod).
- **Confirm, then apply:** `docker compose run --rm backend alembic upgrade head`
- [ ] Re-check head: `SELECT version_num FROM alembic_version;` → expect `030_historical_backfill_jobs`. If it errored mid-way, **🔴 STOP**, restore from the step-1 backup.

## 4. Configure backfill credentials (env, not committed)
- [ ] Add to the celery_worker env (the prod `docker-compose.yml` env / `.env`): the chosen creds — **β** `BACKFILL_DHAN_USER_ID=<id>` OR **α** `BACKFILL_DHAN_CLIENT_ID=<id>` + `BACKFILL_DHAN_ACCESS_TOKEN=<token>`.
- [ ] **Leave `BACKFILL_ENABLED` OFF for now** (we flip it last, after a clean restart).

## 5. 🔴 HARD-STOP #3 — BEFORE CONTAINER RESTART
- [ ] The backend image is BAKED + SHARED by web+worker+beat. A code change needs a rebuild: `docker compose build backend` (TA-lib compile ~3–5 min) — do this BEFORE restarting so the live web isn't down during the build.
- [ ] **Restart workers WITHOUT touching the live web first** if you want zero web downtime: `docker compose up -d --no-deps --build celery_worker celery_beat`. Then, when ready, `docker compose up -d --no-deps --build backend` (brief web restart).
- [ ] **Confirm BSE LTD still LIVE + flat after restart:** re-run the position query from step 0. **🔴 STOP if anything changed on `89423ecc`.**
- [ ] Health: `curl -s localhost:8000/health` → 200. `curl -s localhost:8000/openapi.json | grep -c webhook` sanity.

## 6. Drain — SMALL first, never all 22 at once
- [ ] Flip `BACKFILL_ENABLED=true` on celery_worker env, restart **only** celery_worker (`up -d --no-deps celery_worker`).
- [ ] **Drain 1–2 symbols first** (e.g. one index), NOT all 22. Watch logs: `docker logs -f trading_bridge_celery_worker` — confirm real Dhan candle data lands in `historical_candles` (row counts climb, `quality_score` set, no auth/IP errors).
- [ ] If Dhan returns Invalid-IP, the EC2 elastic IP `13.127.224.68` needs whitelisting in the Dhan app — fix that, don't brute-force.
- [ ] Only after 1–2 symbols verify clean → let the rest drain (or enqueue them).

## 7. Post-deploy verification + close-out
- [ ] `SELECT version_num FROM alembic_version;` = `030...`.
- [ ] `SELECT count(*) FROM historical_candles;` climbing with real data.
- [ ] **Final BSE LTD check before next 09:15 IST:** `89423ecc` is `is_paper=f`, `is_active=t`, and the manual hedge (if any) is intact. **🔴 If not, STOP and reconcile before market open.**
- [ ] Tag the release: `git tag release-cutover-13 && git push --tags` (optional).
- [ ] Update `SESSION_HANDOFF.md` §2 to the new prod SHA + alembic head.

## Rollback (if anything goes wrong)
1. `docker compose run --rm backend alembic downgrade 028_add_backtest_runs` (029/030 are additive — safe to drop) **or** restore the step-1 `pg_dump` backup.
2. `git checkout release-cutover-12 && docker compose up -d --build` to revert code.
3. Re-verify `89423ecc` flat + live. The strategy webhook + paper path are unchanged by this deploy, so a code rollback is low-risk.

**Golden rule:** if any step's result contradicts this doc, or `89423ecc` shows any change you didn't make — **STOP**, don't improvise. Real money.
