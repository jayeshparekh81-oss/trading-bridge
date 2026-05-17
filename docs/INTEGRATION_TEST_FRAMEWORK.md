# Integration Test Framework

**Owner:** Backend platform
**Branch:** `feat/integration-test-framework`
**Date:** 2026-05-17

## Why this exists

On the night of May 17, 2026, three latent bugs nearly broke the Strategy Template System deploy. Each bug had unit-test-shaped predecessors that *passed* — they tested code in isolation but missed the inter-file / inter-stage interactions. The bugs were:

1. **Missing CLI script** — the deploy runbook calls `python -m app.templates.scripts.seed_strategy_templates`, but the `scripts/` package wasn't shipped in the repo. Caught by smoke-running the deploy step against staging.
2. **Dockerfile data-copy missing** — the runtime stage didn't `COPY data ./data`, so the seed JSON was absent inside the container. Caught when the container's first seed-loader run raised `FileNotFoundError`.
3. **`registry._default_seed_path` host-only path** — the resolver hard-coded `parents[3] / backend / data / ...` which works on the host repo but resolves to a non-existent `/backend/data/...` inside the container. Caught after Bug #2 was fixed and the container then crashed on path resolution.

Each was a one-line fix, but **unit tests alone could not have caught them.** The bugs lived in the seams between (a) a Python module's expectations, (b) the file layout of the deployed container, and (c) the deploy runbook's expectations of what's in the repo.

This framework adds a **regression shield** for those three bugs and a **scaffold** for future integration tests that need real Postgres + Redis behind them.

## What lives here

| Artifact | Purpose |
|---|---|
| `backend/tests/deploy_path/test_deploy_path.py` | The regression shield — four test classes, one per latent bug, plus a seed-file integrity smoke. All static-analysis; no Docker, no DB. Lives in a separate dir from `tests/integration/` so its `conftest.py` baggage (FastAPI app, asyncpg, bcrypt, fakeredis…) isn't loaded — the shield runs in a thin CI environment with only pytest + cryptography. |
| `docker-compose-test.yml` | Throwaway Postgres + Redis on alternate ports (5433/6380) so the local dev stack and the test stack don't collide. Used by future full-stack integration tests. |
| `.github/workflows/integration.yml` | Two-job CI workflow: (a) `deploy-path-regression` — runs the May-17 shield on every push/PR (<60s); (b) `full-stack-integration` — gated `if: false` until full-stack tests exist. |
| `BLOCKERS_INTEGRATION_TESTS.md` | Open questions for the founder. |

## Test taxonomy (with examples)

Three tiers, decided by what each tier can and cannot catch.

### Tier 1 — Static-analysis integration tests (FAST, ALWAYS-ON)

What they check: file system facts, parsed source text, import-time behaviour, JSON shape.
What they catch: deploy-path bugs, file-copy bugs, hard-coded paths, missing CLI entry points.
What they cannot catch: runtime concurrency issues, DB constraint violations, transaction-isolation bugs.

Examples: every test class in `test_deploy_path.py`.

These run on every CI push without external dependencies. They are the cheapest possible safeguard against "deploy-day surprise" bugs.

### Tier 2 — Behavioural integration tests with mocked externals (MEDIUM, ALWAYS-ON)

What they check: cross-module behaviour with in-memory SQLite, fakeredis, mocked broker clients.
What they catch: FastAPI route ↔ service-layer wiring, SQLAlchemy session lifecycle within a single request, schema/serialiser drift.
What they cannot catch: anything Postgres-specific (JSON operators, partial indexes, advisory locks, native enum types).

Examples: most existing tests in `backend/tests/integration/test_strategy_webhook_*.py`. They use the StaticPool SQLite trick from `conftest.py`.

### Tier 3 — Full-stack integration tests with real Postgres + Redis (SLOW, OPT-IN)

What they check: real Postgres schema, real Alembic migrations, real Redis pubsub, real Celery handoff.
What they catch: migration order bugs, native PG operator behaviour (JSONB, full-text), connection-pool exhaustion, Redis eviction semantics.
What they cannot catch: anything broker-specific (Fyers/Dhan API behaviour) — those need contract tests or live-staging.

Implementation: `docker-compose-test.yml` brings up `postgres_test` + `redis_test`. The CI job stub is in place but gated `if: false` until at least one Tier-3 test exists. Activating the gate prematurely just slows down CI for no benefit.

## How the May-17 bugs would now be caught

Each bug now has a regression test in `test_deploy_path.py`:

| Bug | Test class | What it asserts |
|---|---|---|
| #1 Missing CLI | `TestSeedCLIScriptShipped` | `__init__.py` + `seed_strategy_templates.py` files exist; module imports; `--help` exits clean |
| #2 Dockerfile data-copy | `TestDockerfileCopiesDataDirectory` | Parses backend/Dockerfile; asserts runtime stage contains `COPY ... data ./data`; seed JSON exists at source path |
| #3 Path resolution | `TestRegistryPathResolutionContainerLayout` | Asserts registry.py source contains the `/app/data/...` explicit fallback AND `parents[2] / "data"` container-layout probe; asserts the resolver returns an existing path or a descriptive FileNotFoundError |

The first time any of these three regress, the CI gate fires on the PR introducing the regression — before merge to main, before deploy.

## Running locally

```bash
# Tier-1 shield (no external deps, <10s):
cd backend
JWT_SECRET="local-test-jwt-secret-do-not-use-in-prod-32bytes" \
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
ENVIRONMENT=test \
pytest tests/deploy_path/test_deploy_path.py -v --no-cov

# Future Tier-3 tests (with real PG + Redis):
docker compose -f docker-compose-test.yml up -d
# ... run tests against DATABASE_URL=postgresql+asyncpg://...@localhost:5433/...
docker compose -f docker-compose-test.yml down -v
```

## CI gate posture

- **`deploy-path-regression` job**: must pass on every push to `main`, `feat/**`, `fix/**`, and every PR to main. Blocking gate.
- **`full-stack-integration` job**: currently disabled (`if: false`). Re-enable by removing the `if` line in `.github/workflows/integration.yml` once at least one Tier-3 test exists.

## Coverage policy

Per the engineering standard (96%+ for everything), `test_deploy_path.py` itself sits at 100% by virtue of testing file-level facts directly. Future Tier-3 tests inherit the same coverage bar.

## What this framework deliberately does NOT include

- **Production-broker smoke tests** — Fyers and Dhan live API tests belong in a separate `backend/tests/contract/` directory with manual credential injection. Mixing them with the standard pytest sweep risks accidental live orders.
- **Long-running performance tests** — `backend/tests/benchmarks/` is the right home for those.
- **End-to-end browser tests** — the chart frontend has its own test runner; cross-stack E2E is a separate sprint.

## See also

- `BLOCKERS_INTEGRATION_TESTS.md` — open questions and decisions needed
- `backend/tests/integration/conftest.py` — existing Tier-2 fixture setup
- `backend/Dockerfile:75-82` — the COPY directives the regression test parses
- `backend/app/templates/registry.py:73-108` — the multi-path resolver under test
