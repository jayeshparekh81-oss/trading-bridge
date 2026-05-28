# PATCH INSTRUCTIONS — Phase F Component 1 (BB fix + Phase B adapter)

**Branch:** `feat/phase-f-indicator-audit` (8+ commits ahead of `main`)
**Sprint date:** 2026-05-17 (1 day before paper-launch)
**Deploy target:** AWS Mumbai EC2 `43.205.195.227` (production backend)

## What this sprint ships

1. **BB stddev math fix** (authorized override on `bb.py:67-72`) — removes the wrong-direction `sqrt(N/(N-1))` Bessel correction. Post-fix BB output matches Pine `ta.bb` to float64 epsilon. Empirical evidence: `PHASE_F_DEVIATION_ANALYSIS.md`.
2. **Phase B adapter** (new files only) — `backtest_adapter.py` + `_types.py` provide a functional `rsi(close, period) -> ndarray` API for the upcoming Phase F backtest engine (Component 4). Pure composition over the existing class-based API; zero math reimplementation.
3. **Independent reference tests** — `test_indicators_phase_f_reference.py` validates all 5 MVP indicators against pandas-ta-classic-derived Pine fixtures. Breaks the prior TA-Lib-self-referential tautology that masked the BB bug.

## Before deploy

- [ ] **Verify pyproject pin** of `ta-lib==0.6.4` is present (it is, line 67 of `backend/pyproject.toml`). No version change required.
- [ ] **No new runtime deps.** Phase B adapter uses only `numpy`, `pydantic` (transitive), and the existing project imports. No `pandas-ta` runtime dependency — it's used only at fixture-generation time and runs in a throwaway dev venv.
- [ ] **Rebuild backend Docker image** to pick up the `bb.py` and `_types.py` / `backtest_adapter.py` changes:
  ```bash
  docker compose build backend
  ```
- [ ] **Confirm test suite passes in CI** before promoting to prod:
  ```bash
  cd backend
  pytest tests/services/indicators/ tests/api/test_indicator.py -v
  # Expected: 64 passed, 1 xfailed (test_macd_matches_pine_reference)
  ```

## Deploy steps (EC2)

```bash
# 1. SSH to EC2
ssh ubuntu@43.205.195.227

# 2. Pull latest from main (after Jayesh merges + pushes the branch)
cd /home/ubuntu/trading-bridge
git fetch origin main
git checkout main
git pull --ff-only

# 3. Rebuild + restart backend container
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend

# 4. Smoke test BB endpoint (paper-mode user, NIFTY 5m):
curl -s -H "Authorization: Bearer $JAYESH_TOKEN" \
  -X POST https://api.tradetri.com/api/chart/indicator \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NIFTY",
    "exchange": "IDX",
    "timeframe": "5m",
    "params": {"indicator": "bb", "length": 20, "stddev_multiplier": 2.0},
    "from_ts": "2026-05-16T03:45:00+00:00",
    "to_ts": "2026-05-16T10:00:00+00:00"
  }' | jq '.series.upper[-1], .series.middle[-1], .series.lower[-1]'

# Expected post-deploy: upper - middle should be ~2.6% SMALLER than
# the pre-deploy value on the same window. (E.g. if pre-deploy
# upper-middle was ~50, post-deploy should be ~48.7.)
```

## Override scope

ALLOWED edits to existing files (one-time, this sprint only — see `PHASE_F_OVERRIDE_LOG.md`):

| File | Change | Lines | Reason |
|---|---|---|---|
| `backend/app/services/indicators/bb.py` | Remove Bessel correction | 67-72 + docstring 1-26 | Wrong-direction correction inflated BB bands +2.60% vs Pine |
| `backend/tests/services/indicators/fixtures/bb_expected.csv` | Regenerate | (full file) | Old CSV was generated from buggy output; new CSV matches Pine via post-fix output |
| `backend/tests/services/indicators/test_bb.py` | Delete `test_pine_compat_correction_applied` | 82-101 | Test explicitly asserted the bug was present; obsolete after fix. Coverage preserved by new `test_bollinger_matches_pine_reference`. |

NEW files added (no doctrine override needed):

| File | Purpose |
|---|---|
| `backend/app/services/indicators/_types.py` | NamedTuple result types for adapter |
| `backend/app/services/indicators/backtest_adapter.py` | Functional adapter for backtest engine |
| `backend/app/services/indicators/BACKTEST_USAGE.md` | Adapter usage guide |
| `backend/tests/services/indicators/test_indicators_phase_f_reference.py` | Independent Pine-reference tests |
| `backend/tests/services/indicators/fixtures/_generate_phase_f_fixtures.py` | Fixture generator (pandas-ta-classic + hand-roll) |
| `backend/tests/services/indicators/fixtures/nifty_100_bars_5m.csv` | Deterministic 100-bar OHLCV input |
| `backend/tests/services/indicators/fixtures/{rsi_14,sma_20,ema_20,macd_12_26_9,bollinger_20_2}_pine_expected.csv` | Pine-reference expected CSVs |

## Rollback

The BB math fix and the `bb_expected.csv` regen + the `test_bb.py` deletion are logically coupled. To roll back:

```bash
git revert a0bced4   # test_bb.py deletion
git revert 333b675   # bb_expected.csv regen
git revert 63932b0   # bb.py math fix
git push origin main
# Then redeploy via the EC2 steps above.
```

The Phase B adapter infrastructure (commit `c845b3a`), reference tests (`c845b3a` + `daad5e7`), and all docs commits are **independent of the BB fix** — they can stay merged even if the BB fix is reverted. The reference tests would then go red on `test_bollinger`, surfacing the bug again in CI exactly as designed.

## Customer impact (post-deploy)

- **BB band overlays on chart UI**: bands will appear ~2.6% NARROWER than before. Customers comparing TRADETRI BB to TradingView BB at length=20 will now see matching values.
- **Strategy P&L on BB-touch entries**: signal timing may shift by 1-2 bars per 100-bar window. On a 5K-bar backtest, expect 50-150 entry-signal differences vs the pre-fix run. This is the *correct* behaviour matching Pine; pre-fix runs were inflated.
- **No API contract changes**, no schema changes, no router changes. Drop-in deploy.

## Verification post-deploy

1. **Smoke test** (curl above) — BB upper-middle distance should drop ~2.6%.
2. **Customer-facing chart** — load NIFTY 5m with BB(20,2) overlay; visually confirm bands moved closer to price (tighter).
3. **No customer-reported regressions** in paper-mode strategies for 24h post-deploy. Both LIVE customers in paper_mode currently use NIFTY-based strategies; monitor their dashboards for any signal-firing anomalies.

## Open follow-up (post-launch)

**MACD seeding convention** — TA-Lib `MACD` uses aligned EMA seeding (industry standard) while Pine docs describe independent SMA seeding. Empirical TradingView UI verification is deferred to **2026-05-25** per `PHASE_F_OVERRIDE_LOG.md` entry #2. The Phase F reference test for MACD is currently `xfail`'d with strict=False; un-xfail (or fix `macd.py`) after the TV check.

## Total scope summary

- 3 existing files edited (all authorized): `bb.py`, `bb_expected.csv`, `test_bb.py`
- ~12 new files added (Phase B infra + tests + fixtures + docs)
- 9 commits on `feat/phase-f-indicator-audit` ahead of `main`
- 0 unauthorized scope expansions
- 0 customer-facing docs touched (per α-modified decision: no premature MACD footnote)
