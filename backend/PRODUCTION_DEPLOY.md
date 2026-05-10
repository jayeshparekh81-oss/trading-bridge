# Production Deploy Guide

The minimum viable runbook to take TRADETRI from a fresh server to
serving traffic. Updated alongside every infrastructure-shaped
commit; treat this as a living doc.

## 0. Pre-deploy checklist

Before touching production:

- [ ] All migrations 010-019 applied to the target database (or
      `alembic upgrade head` runs cleanly against it).
- [ ] `backend/.env.production` populated from the
      `.env.production.example` template — every `REPLACE_WITH_*`
      placeholder gone.
- [ ] `frontend/.env.local` populated on the build host (or
      Vercel project's environment-variable dashboard).
- [ ] Sentry project created (see §3).
- [ ] Dhan broker token issued for the production user.
- [ ] CI green on the commit being deployed.

## 1. Required env vars

The backend's `validate_production_env` blocks startup when any
of these is missing in `ENVIRONMENT=production`. Source:
`app/observability/env_check.py::REQUIRED_PRODUCTION_ENV`.

| Name | Notes |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db`. RDS endpoint in production. |
| `REDIS_URL` | `redis://host:port/db`. Required for rate-limiting + caching. |
| `JWT_SECRET` | `openssl rand -hex 32`. Rotating this invalidates every active session. |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Encrypts broker credentials at rest. |
| `WEBHOOK_HMAC_SECRET` | `openssl rand -hex 32`. TradingView webhook signature base. |

These are checked at app startup. A missing required var raises
`EnvValidationError`, which the orchestrator (Docker / k8s)
should treat as a crash + restart.

## 2. Optional env vars (warned, not fatal)

Source: `OPTIONAL_PRODUCTION_ENV` in the same file.

| Name | Behaviour without it |
|---|---|
| `SENTRY_DSN` | Error tracking disabled. Strongly recommended for production — Sentry's free tier covers our pre-launch volume. |
| `DHAN_ACCESS_TOKEN` | Live trading + intraday backtests unavailable. Paper trading still works. |
| `CORS_ALLOW_ORIGINS` | Falls back to permissive dev origins. ALWAYS set in production (`["https://tradetri.in"]` etc.). |
| `CELERY_BROKER_URL` | Background workers won't start. Audit cleanup, snapshot cron, etc. stop running. |

## 3. Sentry setup

### Create the project

1. Sign in to https://sentry.io (free tier OK for pre-launch).
2. Create a project: `Platform = Python · FastAPI`.
3. Copy the DSN from `Project Settings → Client Keys (DSN)`. It
   looks like `https://abc...@oXYZ.ingest.sentry.io/12345`.
4. Repeat for the frontend project: `Platform = Next.js`.
5. Optionally combine both into one project — TRADETRI's volume
   is small enough that a unified project is easier to triage.

### Wire the backend

The backend's `app.observability.sentry` module is already shipped.
Set `SENTRY_DSN` + `SENTRY_ENVIRONMENT=production` in
`.env.production` and the SDK initialises automatically at startup.

Required Python package (NOT yet in `pyproject.toml` —
deliberate: the module degrades to a no-op if the package isn't
installed, so the dev environment stays lean):

```bash
cd backend
.venv/bin/pip install 'sentry-sdk[fastapi]>=2.0,<3.0'
```

Optional (slow-query tracking, more autoinstrumentation):

```bash
.venv/bin/pip install 'sentry-sdk[fastapi,sqlalchemy,httpx]>=2.0,<3.0'
```

Verify post-install:

```bash
SENTRY_DSN=<your-dsn> ENVIRONMENT=development .venv/bin/python -c \
  "from app.observability import init_sentry; print(init_sentry())"
# Expected: True
```

### Wire the frontend

The four shipped config files
(`sentry.client.config.ts`, `sentry.server.config.ts`,
`sentry.edge.config.ts`, `src/app/global-error.tsx`) are
build-safe even before `@sentry/nextjs` is installed — the
imports use a variable-indirection pattern that bundlers can't
statically resolve.

Required npm package (NOT yet in `package.json` for the same
reason as the backend):

```bash
cd frontend
npm install '@sentry/nextjs@^8'
```

After install, also wrap `next.config.ts`:

```typescript
import { withSentryConfig } from "@sentry/nextjs";
const nextConfig = { /* existing config */ };
export default withSentryConfig(nextConfig, {
  org: "tradetri",
  project: "tradetri-frontend",
  silent: !process.env.CI,
  // Source map upload requires SENTRY_AUTH_TOKEN at build time.
  widenClientFileUpload: true,
});
```

Set `NEXT_PUBLIC_SENTRY_DSN` (and `SENTRY_DSN` for server) in the
Vercel project's environment-variable dashboard. Add
`SENTRY_AUTH_TOKEN` as a build-time-only secret if source-map
upload is desired.

## 4. Database migration order

Migrations run in numeric order. From a clean Postgres database:

```bash
cd backend
.venv/bin/alembic upgrade head
```

Current head is `019_ledger_tables`. Migrations 010-019 cover:

| ID | Title |
|---|---|
| 010 | paper_sessions / paper_trades |
| 011 | users.live_trading_enabled |
| 012 | strategies cached_scores |
| 013 | RBAC role column |
| 014 | RBAC role check constraint |
| 015 | entry_templates |
| 016 | exit_templates |
| 017 | risk_templates |
| 018 | marketplace_tables |
| 019 | ledger_tables |

If a deploy upgrades from a known-state cut, target that revision
explicitly: `alembic upgrade <revision>`.

## 5. Smoke test (post-deploy)

Quick checks that the deployed app actually serves traffic.

```bash
# Health check.
curl -s https://api.tradetri.in/health
# Expected: {"status":"ok",...}

# OpenAPI loads (verifies app booted past lifespan + router registration).
curl -s https://api.tradetri.in/openapi.json | jq .info.title
# Expected: "TRADETRI ..."

# Indicators registry endpoint (verifies migrations + seeders ran).
curl -s -H "Authorization: Bearer <test-token>" \
  https://api.tradetri.in/strategies/indicators | jq '. | length'
# Expected: >= 71 (Pack 5 baseline)

# Sentry test event.
SENTRY_DSN=<dsn> .venv/bin/python -c \
  "import sentry_sdk; sentry_sdk.init('${SENTRY_DSN}'); sentry_sdk.capture_message('deploy smoke test')"
# Then check Sentry dashboard for the event.
```

If any check fails, see §7.

## 6. Rollback

```bash
# 1. Roll back the application (orchestrator-specific).
#    Kubernetes: kubectl rollout undo deployment/tradetri-api
#    Docker:     docker service update --rollback tradetri-api
#    Vercel:     redeploy the previous git SHA from the dashboard.

# 2. Roll back migrations only if the new revision broke schema-
#    compatibility. Otherwise leave the DB at head and let the
#    older app code see the new tables (additive migrations are
#    backwards-safe).
.venv/bin/alembic downgrade <previous-revision>
```

Always rollback the app *first* and the schema *only if needed*.
Most TRADETRI migrations are additive; rolling back schema is
rarely the right answer.

## 7. Common issues + fixes

### App startup raises `EnvValidationError`

Missing required env var. Re-read `.env.production` against
`§1. Required env vars` above. The error message names the
specific missing var(s).

### Backend boots but Sentry never receives events

1. Confirm `sentry-sdk` package installed:
   `pip show sentry-sdk`.
2. Confirm `SENTRY_DSN` set + non-empty in the running
   environment: `printenv SENTRY_DSN`.
3. Check application logs for `sentry.skip` or
   `sentry.init_failed` records.

### Frontend build errors with "Cannot find module '@sentry/nextjs'"

Either:
- Install the package (per §3), OR
- Confirm `NEXT_PUBLIC_SENTRY_DSN` is unset at build time. With no
  DSN, the dynamic-import path is dead code and shouldn't reach the
  bundler. If the build still tries to resolve it, the
  variable-indirection pattern in the config files isn't being
  preserved by Turbopack — escalate to the deploy-engineer thread.

### `validate_production_env` warnings clutter the startup logs

Acceptable on initial deploy. Each warning names the missing
optional var; address them post-launch in priority order
(`SENTRY_DSN` first, then `DHAN_ACCESS_TOKEN`, then
`CORS_ALLOW_ORIGINS`).

## 8. What this guide does NOT cover (yet)

- CI/CD pipeline configuration (Vercel + GitHub Actions).
- Sentry release tracking via `SENTRY_RELEASE` git-SHA injection.
- Source-map upload pipeline.
- Custom Sentry alerts / dashboards.
- Disaster recovery (backup restore + migration replay).

These are tracked in the launch-readiness sprint and will land in
follow-up deploy-guide updates.
