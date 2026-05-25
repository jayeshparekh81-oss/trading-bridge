# Deploy Runbook — Exit-Class Symbol Re-resolution Fix (2026-05-26)

**Branch:** `fix/exit-skip-reresolve-20260526` (off `deploy/3fixes_20260524_2121` @ aebe07d) · **Status:** LOCAL ONLY, not pushed · **Founder executes deploy after review.**

## What this fixes
Pine-driven exit actions (`EXIT` / `SL_HIT` / `PARTIAL`) were re-resolved through `futures_resolver` in the webhook. On an F&O **expiry day** in the **14:30–15:30 IST** window the resolver rolls the ticker to next month, so the symbol-keyed exit lookup misses the still-open current-month position → the exit **silently no-ops** (`status='ignored'`), leaving the position to auto-settle. Fix: exit-class actions now **pin to the open position's stored entry-time symbol** (no re-resolution); ENTRY is unchanged. Internal exits (position_manager / kill_switch) were already safe.

**Diff:** `app/api/strategy_webhook.py` (+~30, exit branch only — ENTRY path byte-identical), NEW `app/services/position_lookup.py`, NEW `tests/integration/test_exit_skip_reresolve.py`. No changes to dhan.py / futures_resolver / position_manager / kill_switch / migrations / compose / .env.

---

## 1. Pre-deploy checklist
- [ ] **Push the branch first** — it is local-only. Either push `fix/exit-skip-reresolve-20260526`, or merge it into `deploy/3fixes_20260524_2121` and push that. (EC2 cannot `git fetch` a local branch.)
- [ ] 89423ecc `is_active = f` (verify: `SELECT id, is_active FROM strategies WHERE id = '89423ecc-...';`)
- [ ] No open rows for any live strategy: `SELECT strategy_id, symbol, status FROM strategy_positions WHERE status IN ('open','partial');` → expect 0 for live strategies.
- [ ] Market closed (> 15:30 IST) — deploy outside trading hours.
- [ ] Fix-branch commit SHA recorded.
- [ ] All 12 new tests + full suite locally green (0 new failures vs the 44 pre-existing baseline — verified this session).
- [ ] Founder code review complete.

## 2. Deploy sequence (manual — founder executes)
> Assumes the fix is merged into / available on the deploy branch on the remote.
```
ssh -i ~/Documents/aws-ssh-keys/tradedeskai-aws-key.pem ubuntu@13.127.224.68
cd /home/ubuntu/trading-bridge
git fetch origin
git checkout <deploy-branch-with-fix>        # e.g. deploy/3fixes_20260524_2121 after merge
git log -1 --format='%h %s'                  # confirm the exit-fix commit is HEAD
docker compose build backend
docker compose up -d backend                 # backend only; do NOT touch postgres/redis
curl -fsS http://localhost:8000/health       # or the public health URL
docker compose logs --tail=100 -f backend    # watch ~2 min for import errors / crash loops
```

## 3. Post-deploy verification
- [ ] Backend starts clean (no ImportError, no crash loop, container healthy).
- [ ] Webhook endpoint responds — POST a **dummy paper** signal (a disposable paper strategy token) and confirm 202 + a `strategy_signals` row.
- [ ] DB connection healthy (the health endpoint / a trivial read).
- [ ] Telegram test alert delivers (note: alerts are HTML — confirm rendering).
- [ ] Grep logs for the new markers on a test exit: `strategy_webhook.exit_symbol_pinned_to_position` (pinned) and absence of `symbol_normalized` for that exit.

## 4. Rollback
```
cd /home/ubuntu/trading-bridge
git checkout deploy/3fixes_20260524_2121     # back to aebe07d (pre-fix)
docker compose up -d --build backend
curl -fsS http://localhost:8000/health
```
The change is additive + behind an action-type branch, so rollback is a clean revert to aebe07d.

## 5. Re-enable 89423ecc (only after deploy is verified stable ≥ 30 min)
- [ ] Confirm `strategy_positions` open count for 89423ecc is still 0.
- [ ] `UPDATE strategies SET is_active = true WHERE id = '89423ecc-...';`
- [ ] Verify `SELECT is_active FROM strategies WHERE id = '89423ecc-...';` → `t`.
- [ ] Watch the first signal/heartbeat in logs; on the next exit, confirm the pinned-symbol log line and that the exit closes the held contract.

## Notes / open items for founder
- **No-position exit behavior:** this fix logs a **WARNING** (`strategy_webhook.exit_no_open_position`) and returns a benign 202 (no HTTP error, no Telegram) for an exit with no open position — chosen to avoid TradingView retry storms and false alarms on benign duplicate/already-closed exits. If you'd rather have a hard error + Telegram alert, that's a one-line change — flagging for your call.
- **Pre-existing lint debt** in `strategy_webhook.py` (`I001` import-sort at line ~27, `B008` FastAPI `Depends`) was left untouched (surgical hotfix; not introduced by this change).
- This is the **futures** exit path. The same stored-symbol principle is documented for the options path in `PHASE_3B_IMPLEMENTATION_PLAN.md`.
