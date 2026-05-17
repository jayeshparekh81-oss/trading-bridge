# Phase C Monday Deploy — Quick Reference (May 18, 2026)

Print or open as second monitor. Times IST. Full runbook: `docs/PHASE_C_MONDAY_DEPLOY_RUNBOOK.md`.

## TL;DR
- **What:** cherry-pick `strategy_webhook.py` (futures_resolver integration) and ship to EC2.
- **Why:** BSE futures symbols (`NSE:BSE`, `BSE1!`) normalized to canonical `BSE-<MMM>YYYY-FUT` before Dhan order placement — fixes silent reject-class for BSE F&O.
- **Outcome:** first BSE signal of the day logs `symbol_normalized`, Dhan accepts canonical symbol, zero non-canonical rows after close.

## Monday timeline
- **06:45** pre-flight pulls + segment verifier (`scripts/verify_bse_fut_segment.py` → GREEN)
- **07:00** cherry-pick + tests + push prep branch
- **07:15** merge to main, deploy on EC2
- **07:30** smoke webhook → verify both log lines
- **08:00** standby for first real signal
- **08:30** done; market opens at 09:15
- **Hard cut-off:** 08:45 — abort if not green by then.

## 07:00 — Cherry-pick (local)
```bash
git checkout feat/phase-c-prep && git pull --ff-only
git checkout origin/feat/dockerfile-talib -- backend/app/api/strategy_webhook.py
cd backend && .venv/bin/python -m pytest tests/services/test_futures_resolver.py -q   # 45 pass
git add app/api/strategy_webhook.py
git commit -m "feat(phase-c): integrate futures_resolver into strategy_webhook"
git push -u origin feat/phase-c-prep
```

## 07:15 — Merge + deploy
```bash
# Local
git checkout main && git pull --ff-only
git merge --no-ff feat/phase-c-prep -m "merge: feat/phase-c-prep — futures_resolver integration"
git push origin main

# EC2 (43.205.195.227)
ssh tradetri@43.205.195.227 'cd /opt/tradetri && \
  git pull origin main && \
  docker compose -f docker-compose.prod.yml build backend && \
  docker compose -f docker-compose.prod.yml up -d backend'
# No migration. Pure code change.
```

## 07:30 — Smoke verify (5 curls / log greps)
```bash
# 1. Health
curl -sf https://api.tradetri.com/health                              # → {"status":"ok"}

# 2. Tail backend logs (window A)
ssh tradetri@43.205.195.227 'docker logs -f tradetri_backend 2>&1 \
  | grep -E "futures_resolver|strategy_webhook.symbol_normalized"'

# 3. Fire test webhook (window B, test strategy/test token, min lot)
curl -X POST https://api.tradetri.com/strategy-webhook/<TEST_TOKEN> \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"NSE:BSE","action":"ENTRY","side":"BUY","quantity":75}'
# Expect: HTTP 202

# Window A MUST show both:
#   strategy_webhook.symbol_normalized   original=NSE:BSE  normalized=BSE-<MMM>YYYY-FUT
#   futures_resolver.continuous_future_resolved   original=NSE:BSE  resolved=BSE-<MMM>YYYY-FUT

# 4. Kill-switch reachable
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $JWT" https://api.tradetri.com/api/kill-switch/status   # → 200

# 5. Frontend loads
curl -s -o /dev/null -w "%{http_code}\n" https://tradetri.com/chart                  # → 200
```

## Rollback (if anything breaks)
```bash
ssh tradetri@43.205.195.227 'cd /opt/tradetri && \
  git log --oneline -5 && \
  git checkout <PREVIOUS_GOOD_SHA> && \
  docker compose -f docker-compose.prod.yml build backend && \
  docker compose -f docker-compose.prod.yml up -d backend'
# Locally revert the merge (no force-push):
git checkout main && git revert -m 1 <PHASE_C_MERGE_SHA> && git push origin main
```

## If something goes wrong — top 5 + fixes
1. **Both expected log lines missing after test webhook.** Resolver silently no-op'ing.
   `docker exec tradetri_backend python -c "from app.brokers.dhan import _SCRIP_MASTER; print(_SCRIP_MASTER.is_loaded(), len(_SCRIP_MASTER._by_symbol))"` — if 0/0, scrip-master didn't load: restart backend, recheck.
2. **Dhan responds REJECTED with `BrokerInvalidSymbolError`.** Resolver hit wrong segment. Re-run `scripts/verify_bse_fut_segment.py` — if RED, ABORT + rollback. If GREEN, capture the failing symbol + raw Dhan response and surface.
3. **Test suite shows NEW failure (not in baseline 11/24).** STOP at step 07:00. Do not push. Inspect traceback; the cherry-pick likely picked up a stale import.
4. **`git pull` on EC2 conflicts** (someone hot-edited `/opt/tradetri`). `git status` → `git stash` → pull → resolve manually. Do NOT `--force`.
5. **`docker compose build` fails** (TA-Lib / numpy compile). `docker compose -f docker-compose.prod.yml build --no-cache backend`. If still failing, rollback container is still running from prior `up -d` — production stays alive.

## Sign-off (tick before market open)
- [ ] 1.3 segment verifier = GREEN
- [ ] Test suite = 45 resolver pass, only baseline failures
- [ ] Smoke webhook logged both lines
- [ ] First real BSE signal at market open shows canonical symbol
