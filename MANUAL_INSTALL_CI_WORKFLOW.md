# Manual install — integration GitHub Actions workflow

## Why this is a manual step

This task wanted to ship the CI workflow in the same PR as the
regression-shield tests. The push attempt was rejected by GitHub:

```
! [remote rejected] feat/integration-test-framework -> feat/integration-test-framework
  (refusing to allow a Personal Access Token to create or update
   workflow `.github/workflows/integration.yml` without `workflow` scope)
```

The PAT used by the automation has `repo` scope but not the `workflow`
scope, so it cannot create or modify files under `.github/workflows/`.

The workflow YAML is therefore parked at `docs/integration-workflow.yml.staged`
on this branch. Installing it is a one-line `git mv` performed by the
founder using a PAT (or web UI) that does have workflow scope.

## How to install

Option A — local CLI with a workflow-scoped PAT or SSH key:

```sh
git checkout feat/integration-test-framework
mkdir -p .github/workflows
git mv docs/integration-workflow.yml.staged .github/workflows/integration.yml
git commit -m "ci(integration): install workflow YAML from staged location"
git push
```

Option B — GitHub web UI:

1. Open `docs/integration-workflow.yml.staged` on the branch in the
   GitHub web view.
2. Copy its contents.
3. In the web UI, create a new file at `.github/workflows/integration.yml`,
   paste, and commit.
4. Delete `docs/integration-workflow.yml.staged` in a follow-up commit.

After install, the workflow fires on the next push to `main`, any
`feat/**`, any `fix/**`, or any PR to `main`.

## What the workflow does

Two jobs:

- **`deploy-path-regression`** — blocking gate. Installs a curated subset
  of backend deps (no `ta-lib` to avoid the C-library compile), runs
  `pytest tests/deploy_path/test_deploy_path.py`. Catches the three
  May-17 latent bugs if any of them regress. Runs in <60s.

- **`full-stack-integration`** — scaffold, gated `if: false`. Brings up
  Postgres 16 + Redis 7 as GH Actions service containers, applies
  Alembic migrations, runs `backend/tests/integration/` excluding broker
  contract tests. Activate by removing the `if: false` line once at
  least one Tier-3 test exists.

## Secrets required

- `CI_ENCRYPTION_KEY` — optional for `deploy-path-regression` (the YAML
  has a hardcoded test-only fallback); required for `full-stack-integration`
  before activating it. Generate with:

  ```sh
  python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  ```

  Add at `Settings → Secrets and variables → Actions → New repository secret`.

## See also

- `docs/INTEGRATION_TEST_FRAMEWORK.md` — design rationale + test taxonomy
- `BLOCKERS_INTEGRATION_TESTS.md` — open questions
- `docs/integration-workflow.yml.staged` — the YAML itself
