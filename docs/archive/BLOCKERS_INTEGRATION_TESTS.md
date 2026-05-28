# BLOCKERS — Integration Test Framework

**Date:** 2026-05-17 (overnight queue Task 3 of 5)
**Branch:** `feat/integration-test-framework`

---

## Open questions for founder review

### 1. CI provider — GitHub Actions confirmed? + manual install step

This branch was meant to add `.github/workflows/integration.yml` directly, but the push was rejected by GitHub because the automation's PAT lacks the `workflow` scope. The workflow YAML is therefore parked at `docs/integration-workflow.yml.staged` and the install instructions are in `MANUAL_INSTALL_CI_WORKFLOW.md` at repo root. Founder runs a one-line `git mv` (or web-UI copy) to activate.

Before that activation, confirm:

- Are we standardising on **GitHub Actions** for backend CI?
- If Vercel/another provider is also in the picture, should the integration workflow be mirrored or migrated?

If GH Actions is correct, run the manual install per `MANUAL_INSTALL_CI_WORKFLOW.md`.

### 2. `CI_ENCRYPTION_KEY` secret

The workflow references `${{ secrets.CI_ENCRYPTION_KEY }}` with a hardcoded test-only fallback inside the YAML. The fallback is a randomly-generated Fernet key that is **safe to commit because it is only used in CI for module-import sanity** (no real data is ever encrypted with it). However:

- Decision needed: should we add `CI_ENCRYPTION_KEY` as a real GitHub secret and remove the hardcoded fallback?
- The hardcoded fallback is fine for the Tier-1 shield (no encrypted data touched) but **must be replaced** before any Tier-3 test runs against real DB rows.

Action: add the secret to repo settings (`Settings → Secrets and variables → Actions → New repository secret`) sometime before activating the `full-stack-integration` job.

### 3. CI runner cost

Every push to `feat/**` and `fix/**` triggers the workflow. With heavy parallel-CC branch churn (per the chart-module sprint), this could add up to a non-trivial number of runner minutes per day.

Two mitigations available, neither implemented on this branch:

- **(a)** Add a `paths:` filter so the workflow only runs when `backend/**` or `.github/workflows/integration.yml` changes. Frontend-only PRs skip the gate.
- **(b)** Move the trigger to `pull_request` only (drop the `push` half), so feature-branch pushes don't fire the workflow until a PR is opened.

Recommendation: **(a)** — keeps the gate active for backend-touching changes, lets frontend churn pass through freely. Easy one-line change post-merge.

### 4. Tier-3 tests — what comes first?

The `full-stack-integration` job is gated `if: false` because no Tier-3 test exists yet. Once one is written, removing the `if` line activates the gate. The first Tier-3 test that would deliver value:

- **Migration-chain test**: bring up empty Postgres, run `alembic upgrade head`, then `alembic downgrade base`, then upgrade again. Catches non-reversible migrations. Most valuable; would have caught the 027 backtest migration (see `BLOCKERS_BACKTEST_ENGINE.md`) if it had been merged with a bad downgrade.

- **Seed-loader real-PG test**: run the seed loader against the live test DB, assert every row's `config_json` round-trips through the JSONB column without lossy serialisation.

Either is a small (~30-line) test once the scaffold is enabled. Decision needed: which one ships first, and on which branch?

### 5. Test data isolation between Tier-3 runs

The `docker-compose-test.yml` mounts named volumes (`postgres_data_test`, `redis_data_test`). The compose file's docstring instructs operators to tear down with `-v` to drop volumes between runs. CI doesn't need this (the runner is ephemeral), but a developer running tests locally repeatedly will accumulate cruft.

Decision needed: do we add a `Makefile` target `make test-integration-clean` that runs `down -v` for ergonomics? Or leave it as an operator concern?

### 6. Should test_deploy_path.py also assert prod-only invariants?

The current test parses the **backend/Dockerfile** for the data-copy directive. It does NOT also check:

- `backend/docker-compose.prod.yml` references the right image tag
- `nginx.conf` upstreams point at the right backend service
- TLS cert paths in nginx config exist

These are deploy-config invariants that could also bite during a future deploy. Surface them now or wait for the first incident?

Recommendation: **add per-incident**, not pre-emptively. The May-17 trio of bugs all touched a single deploy artefact (the templates seed pipeline); adding regression shields for hypothetical future failure modes risks both test bloat and false confidence.

### 7. The `full-stack-integration` job is structurally complete but disabled

Reviewers may flag the gated job as dead code. It's intentional — kept inline so when a Tier-3 test ships, the only change needed is removing the `if: false` line. Removing the job entirely now would mean re-deriving the secrets / service / step layout when the time comes.

If the founder prefers a strictly-minimal YAML, the gated job can be deleted from this PR and added back as part of the first Tier-3 PR. **Recommendation: keep the scaffold** — saves friction when Tier-3 work begins.

---

## What this branch ships

```
backend/tests/deploy_path/test_deploy_path.py          regression shield, 4 test classes + integrity smoke
backend/tests/deploy_path/__init__.py                  package marker (no conftest baggage)
docs/integration-workflow.yml.staged                   CI workflow YAML — needs manual move to .github/workflows/integration.yml (see MANUAL_INSTALL_CI_WORKFLOW.md)
MANUAL_INSTALL_CI_WORKFLOW.md                          one-line git-mv instructions
docker-compose-test.yml                                Postgres + Redis on ports 5433/6380
.github/workflows/integration.yml                      two-job CI workflow
docs/INTEGRATION_TEST_FRAMEWORK.md                     design rationale + taxonomy
BLOCKERS_INTEGRATION_TESTS.md                          this file
```

NOT touched: any existing test, any existing CI config (there was none), any source file. Pure additive.

## What still needs to happen post-merge

1. Founder reviews + answers the 7 questions above
2. (If approved) merge to main → CI workflow goes live on next push
3. (If GH Actions confirmed) add `CI_ENCRYPTION_KEY` repo secret
4. (Optional) add `paths:` filter from Q3 above
5. (Future) write first Tier-3 test → remove `if: false` in workflow
