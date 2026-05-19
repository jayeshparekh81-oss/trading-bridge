# Queue X — Phase D2: feat/dockerfile-talib (LIVE-TRADING AUDIT, READ-ONLY)

**Status:** ⚠️ NEEDS_DEEP_REVIEW + PR_SPLIT — branch bundles 3 unrelated concerns; one touches the live webhook path
**Branch:** 3 ahead / 292 behind main, merge-base `f04d184e`
**Audit scope:** Read-only inspection. No code touched.

## Reality check vs mission prediction
Mission expected "107+ commits" — actual count is **3 commits**. Main has moved 292 commits ahead since merge-base; the branch itself only ever had 3.

## The 3 commits (unrelated concerns bundled)
| # | SHA | Subject | Concern |
|---|-----|---------|---------|
| 1 | `6e7d16a` | feat(backend): add TA-Lib C library + Python wrapper to Docker image | Infra |
| 2 | `9f26ee5` | feat(scripts): Docker rebuild test script for pre-deploy libta-lib validation | Tooling |
| 3 | `a4801f4` | feat(resolver): date-driven continuous-future resolver for Dhan execution | **LIVE TRADING** |

## Files touched (vs merge-base)
```
backend/Dockerfile                       |  26 +/- 1
backend/app/api/strategy_webhook.py      |  31 + (LIVE TRADING PATH)
backend/app/services/futures_resolver.py | 221 + (NEW)
backend/pyproject.toml                   |   6 +
scripts/docker_rebuild_test.sh           | 199 + (NEW)
                                          ──────────────
                                          5 files / +482 / -1
```

No alembic migrations. No model changes. No broker/router changes. The only live-trading touch is the symbol normalization step injected into the webhook handler.

## Commit 1 — Dockerfile + TA-Lib (infra)
- Adds `wget` + `ca-certificates` to builder image.
- Fetches and compiles `ta-lib v0.6.4` C library from upstream tarball (no apt package on slim).
- Multi-stage: `libta-lib.so*` copied from builder to runtime + `ldconfig`.
- `ARG TA_LIB_VERSION=0.6.4` parameterised — version must match pyproject pin.
- EC2 sizing: this requires `c7i-flex.large` or larger to compile in reasonable time (per session memory; the build is CPU-bound).

**Risk:** Low. Only affects indicator computation pipeline. No execution path touched.

## Commit 2 — docker_rebuild_test.sh (tooling)
- 199-line shell script for pre-deploy libta-lib validation.
- Lives in `scripts/` — runs nowhere automatically.

**Risk:** Zero.

## Commit 3 — futures_resolver + webhook patch (LIVE TRADING)
Adds a 221-line `app/services/futures_resolver.py` and patches `strategy_webhook.py` with a 31-line block between Pine mapping (step 11) and Pydantic validation (step 12).

### What it does
TradingView publishes `NSE:BSE` / `BSE1!` (continuous future). Dhan API requires the month-stamped contract symbol (`BSE-MAY2026-FUT`), which changes at every NSE F&O monthly expiry (last Thursday, 15:30 IST). The resolver:
1. Maps known TV roots → Dhan roots via static `_TV_ROOT_TO_DHAN_ROOT` (currently 4 entries, all BSE-rooted).
2. Reads `_SCRIP_MASTER._by_symbol` for `<ROOT>-<MMM><YYYY>-FUT` matches.
3. Computes "last Thursday of month" expiry per contract.
4. Picks earliest contract with expiry > today, OR expiry == today AND now < 15:30 IST.
5. Caches per `(root, today_iso)` — natural daily turnover.

### Defensive properties (verified)
- `resolve_or_passthrough(symbol)` never raises — every except branch returns the input.
- Unknown TV ticker → passthrough (no `_TV_ROOT_TO_DHAN_ROOT` entry).
- Empty / non-string → passthrough.
- Scrip master load failure → passthrough + ERROR log.
- No contracts found → passthrough + ERROR log.
- No active contract → passthrough + ERROR log.
- Expiry > 60 days out → passthrough + WARNING (sanity bound).
- Failure modes all surface as `BrokerInvalidSymbolError` downstream — clean, not silent.

### Holiday caveat (own docstring)
> NSE shifts F&O expiry to the previous working day when the last Thursday is a market holiday. v1 calculates "last Thursday" purely from the calendar — the 2026 NSE F&O holiday list shows no Thursday clashes on last-Thursdays so this is acceptable for the immediate trade window.

**Concern:** This is a hard-coded assumption. If a Thursday holiday lands, resolver will pick the wrong contract. A holiday-calendar refinement is flagged but not implemented.

### Risk analysis for BSE LTD live strategy
- `_TV_ROOT_TO_DHAN_ROOT` contains `"NSE:BSE": "BSE"` — so if the BSE LTD strategy fires with TV symbol `NSE:BSE`, the resolver WILL rewrite it to `BSE-<MMM><YYYY>-FUT` instead of cash equity.
- This is a SIGNIFICANT semantics change. Confirm with Jayesh: does the BSE LTD live strategy trade BSE *cash equity* or BSE *futures*?
- If cash equity: the resolver may unintentionally convert cash signals to futures signals. Need to verify the TV ticker the strategy fires with, and either remove `"NSE:BSE": "BSE"` from the map or guard on a futures-specific suffix.
- If futures: the resolver is correct, but rollover behavior should be validated end-to-end before live deploy.

## Recommended PR split

### PR 1 — Dockerfile + ta-lib infra (LOW RISK)
- Cherry-pick `6e7d16a` only.
- Files: `backend/Dockerfile`, `backend/pyproject.toml`.
- Test: build the image locally on a c7i-flex.large, verify `python -c "import talib; print(talib.__version__)"` returns `0.6.4`.
- Merge first — unblocks the chart/indicator pipeline.

### PR 2 — Docker rebuild test script (LOW RISK)
- Cherry-pick `9f26ee5` only.
- File: `scripts/docker_rebuild_test.sh`.
- Test: chmod +x and run once locally.
- Merge whenever convenient.

### PR 3 — Futures resolver + webhook integration (HIGH RISK, needs Jayesh review)
- Cherry-pick `a4801f4` only.
- Files: `backend/app/services/futures_resolver.py`, `backend/app/api/strategy_webhook.py`.
- **Block on Jayesh confirming BSE LTD strategy TV symbol + intended instrument (cash vs futures).**
- Test plan:
  - Unit tests for `_last_thursday_of_month` across edge dates (Dec→Jan rollover, leap years).
  - Unit tests for `_pick_active_contract` at the 15:30 boundary on expiry day.
  - Integration test: send a webhook signal with `NSE:BSE` after the resolver is live, confirm logged `symbol_normalized` event AND that the resulting Dhan order routes to the expected contract.
  - Manual paper-mode end-to-end before any live deploy.

## Paste-able commands (tomorrow evening)

```bash
git fetch origin

# PR 1: Dockerfile + ta-lib
git checkout -b infra/dockerfile-talib origin/main
git cherry-pick 6e7d16a
# resolve any pyproject conflict (likely a clean add)
git push -u origin infra/dockerfile-talib
gh pr create --base main --head infra/dockerfile-talib \
  --title "infra: TA-Lib C library + Python wrapper in Docker image" \
  --body "Adds libta-lib 0.6.4 build to backend/Dockerfile and pins ta-lib==0.6.4 in pyproject. EC2 build requires c7i-flex.large minimum."

# PR 2: rebuild test script
git checkout -b chore/docker-rebuild-test origin/main
git cherry-pick 9f26ee5
git push -u origin chore/docker-rebuild-test
gh pr create --base main --head chore/docker-rebuild-test \
  --title "chore: docker rebuild test script for libta-lib validation"

# PR 3: futures resolver — HOLD until Jayesh confirms BSE LTD intent
# Once green-lit:
git checkout -b feat/futures-resolver-dhan origin/main
git cherry-pick a4801f4
git push -u origin feat/futures-resolver-dhan
gh pr create --base main --head feat/futures-resolver-dhan \
  --title "feat(resolver): date-driven continuous-future resolver for Dhan execution" \
  --body "Adds futures_resolver service + webhook integration. NEEDS REVIEW: BSE LTD live strategy TV symbol assumption."

# After all 3 are merged
git push origin --delete feat/dockerfile-talib
```

## Open question for Jayesh
**The BSE LTD live strategy's TradingView symbol — is it `NSE:BSE` (cash) or `BSE1!` (continuous future)?**
- If the answer is "cash equity", PR 3 needs a guard before merge (remove `NSE:BSE` from the resolver map, leave `BSE1!`).
- If the answer is "futures rollover via continuous symbol", PR 3 is correct as written.

## Hard rule
**Do NOT deploy PR 3 before 4 PM IST on a trading day.** And do NOT deploy PR 3 before answering the open question above. PRs 1 + 2 can deploy any time.
