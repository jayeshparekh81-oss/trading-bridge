# Queue VV — Endpoint Exposure Audit (Phase 1 Discovery)

**Date:** 2026-05-31
**Branch:** none (pure discovery; no code change applied)
**Scope:** Backend HTTP routes only (FE→backend HTTP surface). Per
founder scope confirmation: WS endpoints, external-service URLs, and
env-var exposure are out of scope on this phase.
**Method:** FastAPI introspection (`app.routes` walked under
`STRATEGY_PAPER_MODE=true` settings), then `grep` of `frontend/src`
for each path prefix to verify customer-facing consumption.
**Reproducible script:**
`backend/tests/services/indicators/fixtures/_queue_uu_macd_quantification.py`
already shows the same venv pattern; the introspection script is
attached in §6.
**Status:** Phase 1 complete. Awaiting founder gate before Phase 2
(remediation: which flags to act on, which to defer, which to accept).

---

## 1. Topline numbers

| Bucket | Count |
|---|---:|
| Total `APIRoute` entries mounted (paper_mode=true) | **159** |
| Conditionally mounted (mounts only when `STRATEGY_PAPER_MODE=false`) | 1 (`POST /api/webhook/{token}`) |
| Defined-in-code but **not mounted by `main.py`** | 1 (`api/indicator.py` — see §3.1) |
| Truly unauth (by design) | 9 |
| Token-auth (not JWT) | 1 |
| Standard JWT-auth (`get_current_active_user`) | ~125 |
| Admin-tier (`get_current_admin` / `require_admin`) | 17 |
| Creator-tier (`require_creator_or_above`) | 9 |
| Pro-tier (`require_pro_user_or_above`) | 1 (demo) |
| Super-admin tier (`require_super_admin`) | 1 (demo) |

---

## 2. Unauthenticated surface (full enumeration)

These return 200 without a JWT. Every one was verified by reading the
file; rationale columns transcribe the file-level docstrings.

| Method | Path | File | Rationale |
|---|---|---|---|
| POST | `/api/auth/login` | `api/auth.py` | Issues the JWT itself — auth ROOT |
| POST | `/api/auth/logout` | `api/auth.py` | Stateless logout (revokes refresh, doesn't read user) |
| POST | `/api/auth/refresh` | `api/auth.py` | Refresh-token exchange — accepts refresh JWT in body |
| POST | `/api/auth/register` | `api/auth.py` | Self-serve user signup |
| GET | `/api/system/mode` | `api/system.py` | Returns 3 booleans (`paper_mode`, `kill_switch_check_enabled`, `circuit_breaker_enabled`). Docstring: "Banner needs to render BEFORE the user is authenticated." Reviewed — exposes no PII, no secrets. **Design-acceptable.** |
| GET | `/api/brokers/fyers/callback` | `api/brokers.py` | OAuth callback from Fyers — verified by `state` token, not JWT |
| GET | `/health` | `api/health.py` | k8s liveness — public on purpose |
| GET | `/health/` | `api/health.py` | Alias for `/health` |
| GET | `/health/detailed`, `/health/ready` | `api/health.py` + `strategy_engine/api/health.py` | Liveness/readiness probes |
| POST | `/api/webhook/strategy/{webhook_token}` | `api/strategy_webhook.py` | **Token-auth (not unauth).** `_resolve_webhook_token` looks up the 16-128 char URL token in `webhook_tokens` table; 404 on unknown. Optional HMAC layer (gated by `webhook_require_hmac` setting). Per-user rate limit. Strategy-binding check (line 311). Auth IS the token. |

### 2.1 Conditionally mounted unauth route

`POST /api/webhook/{token}` (`api/webhook.py`) is the LEGACY webhook
that bypasses the strategy-engine paper-mode gate and places real
broker orders.

**`main.py:238-239`:**
```python
if not get_settings().strategy_paper_mode:
    app.include_router(webhook_router)
```

When `STRATEGY_PAPER_MODE=true` (current production posture per the
May 18 paper-only launch), this route **does not exist on the
router table** — verified empirically by my introspection script
returning 159 routes, with no `/api/webhook/{token}` entry. Defense in
depth: the handler itself ALSO refuses (HTTP 503) in paper mode (per
the comment at `main.py:236`).

**Flag for Phase 2 review:** when `STRATEGY_PAPER_MODE` flips to
`false` for live trading (per CLAUDE.md — BSE Ltd `89423ecc` is
already live, but presumably through a different code path or a
narrower flag), this route appears. Verify the handler-level refusal
isn't dependent on the same flag (single-point-of-failure risk).

---

## 3. Dead-code findings

### 3.1 `app/api/indicator.py` — defines a router that is never mounted

**File:** `backend/app/api/indicator.py:30-50`
defines `POST /api/chart/indicator` powered by
`compute_indicator()` from `services/indicator_service.py`, which
dispatches to `services.indicators.MacdIndicator` (the aligned-seeded
impl we touched in Queue UU).

**Mounting status:** `main.py` does NOT import or include this router.

Verification:
```bash
grep "from app.api.indicator\b\|app.api.indicator import" backend
→ Only the file's own docstring example (line 6)
   + the test file tests/api/test_indicator.py:18
   No main.py import.
```

**Production impact:** The route is **inaccessible** in production
deployments — neither the FE chart panel nor any other HTTP consumer
can hit it. This corroborates Queue UU's architectural finding from a
third independent angle (after FE grep + dependency-tree
inspection). The aligned-seeded `MacdIndicator` is fully
unreachable through HTTP.

**Recommendation:** delete `api/indicator.py` + its test file, OR
mount it intentionally. Currently it's just ~50 LOC of dead surface
that confuses future readers.

### 3.2 `app/api/role_demo.py` — Phase 2 scaffolding, "Removable"

**File:** `backend/app/api/role_demo.py:14-18`
docstring says verbatim: *"Removable: when Phase 3 ships actual
paywalled / publishing / super-admin endpoints, these demo routes can
be deleted in the same commit."*

**FE consumption:** **0 matches** across `frontend/src` for
`/api/roles`. None of the demo endpoints are wired up customer-side.

**Production impact:** 4 routes (`/api/roles/me`, `/api/roles/pro/feature`,
`/api/roles/creator/publish`, `/api/roles/super-admin/system`) are
authenticated but echo only the user's tier flags back. They don't
expose PII or take destructive action. **Surface-area concern only,
not a security finding.**

**Recommendation:** if Phase 3 RBAC has landed any real role-gated
endpoints, this file can be deleted in the same sprint. If Phase 3 is
still pending, keep the smoke-test surface for now.

---

## 4. Tier inventory — admin-tier route classification

The audit verified each admin-tier route walks one of two dependency
paths to enforcement:

- `get_current_admin` (existing pre-RBAC check) — 11 routes under
  `/api/admin/*`
- `require_admin` (Phase 2 RBAC dependency) — 6 routes under
  `/api/admin/indicators/*` + 1 under `/api/health/backups` +
  `/api/compliance/{indicators,strategies/all}` + 2 under
  `/api/support/tickets/{...}` (DELETE/PUT)

**Mixed enforcement is intentional** (Phase 2 RBAC migration in
progress per role_demo.py docstring), but worth tracking: any new
admin-tier route should land on `require_admin` (the RBAC one), not
`get_current_admin` (the legacy one). Phase 3 should consolidate.

**Creator-tier (9 routes):** marketplace publish/listing CRUD,
indicator queue file, marketplace ledger snapshots. All correctly
gated by `require_creator_or_above`. No anomalies.

**Pro-tier & Super-admin tier:** only the role-demo routes. Real Pro
& super-admin features land in Phase 3.

---

## 5. FE consumption summary (path-prefix granularity)

Cross-checked every backend prefix against `grep -rln` over
`frontend/src`. Note: these counts are file matches, not call-site
counts — they catch routes referenced in code but may include
non-call references (e.g. constant strings). Used as a coarse
"is anyone calling this prefix" gate.

| Prefix | # routes | FE files referencing | Verdict |
|---|---:|---:|---|
| `/api/strategies` | 19 | 212 | Heavily consumed — core domain |
| `/api/chart` | 3 | 122 | Heavily consumed — chart panel + WS-token |
| `/api/templates` | 19 | 25 | Consumed via templates UI |
| `/api/users` | 19 | 48 | Profile + brokers + webhooks UI |
| `/api/backtest` | 4 | 62 | Backtest async API (Queue CC) |
| `/api/admin` | 18 | 22 | Admin dashboard (FE prob filters by role) |
| `/api/marketplace` | 18 | 14 | Marketplace UI |
| `/api/kill-switch` | 9 | 19 | Kill-switch page |
| `/api/auth` | 6 | 60 | Auth flows |
| `/api/support` | 6 | 92 | Support tickets UI |
| `/api/onboarding` | 4 | 24 | Onboarding flow |
| `/api/brokers` | 4 | 28 | Brokers page |
| `/api/compliance` | 4 | 28 | Compliance dashboard |
| `/api/algomitra` | 4 | 24 | AI chat |
| `/api/indicators` | 4 | 78 | Indicator request flow |
| `/api/strategy-tester` | 3 | 9 | Chart strategy tester |
| `/api/markers` | 2 | 16 | Chart markers overlay |
| `/api/orders` | 2 | 24 | Live order endpoint |
| `/api/system` | 1 | 42 | System banner |
| `/api/webhook` | 1 | 13 | Strategy webhook only (paper mode) |
| **`/api/roles`** | **4** | **0** | **DEAD-CODE / demo** — see §3.2 |
| `/health/detailed`, `/health/ready` | 2 | 0 | Probes (expected 0 FE consumers) |

---

## 6. Flagged items for Phase 2 (founder gate)

Findings ranked by criticality. Action requires explicit founder
authorization — sacred-zone files (`strategy_executor`, `direct_exit`,
`webhook` legacy handler, `kill_switch`, broker adapters) are off-limits
per CLAUDE.md.

### 6.A — Dead route file (LOW risk, HIGH cleanliness)

**`app/api/indicator.py`** defines an unmounted POST endpoint.
~50 LOC of code + a test file that exercises a route inaccessible in
production.

Options:
1. **Delete** the file + its test (cleanest; matches the Queue UU
   finding that nothing in production uses it).
2. **Mount it intentionally** by adding `include_router` in
   `main.py` — would expose the aligned-seeded `MacdIndicator` to
   admin tooling. Requires deciding which auth tier it gates on.
3. **Park** with a `# UNMOUNTED — see Queue VV §3.1` header comment.

**My recommendation: Option 1 (delete).** No production caller has
materialized in the months since the file was committed. The
backtest_adapter dead-code finding from Queue UU + this finding +
the FE grep all point the same direction.

### 6.B — Role-demo scaffolding (LOW risk, MEDIUM staleness)

**`app/api/role_demo.py`** ships 4 endpoints labeled "Removable" with
0 FE consumers. Production-mounted via `main.py:258`.

Options:
1. **Delete** if Phase 3 RBAC endpoints have landed and the smoke-
   test surface is no longer needed.
2. **Park** until Phase 3 ships real role-gated endpoints, then
   remove in the same commit (as the docstring itself suggests).

**My recommendation: Option 2 (park).** The file documents its own
exit criterion; no security issue holds it in place; deleting now
removes a smoke-test surface Phase 3 wiring will likely re-use.

### 6.C — Legacy webhook conditional mount (MEDIUM risk, HIGH attention)

**`POST /api/webhook/{token}`** (`api/webhook.py`) is unauthenticated
+ places real broker orders + is currently invisible because
`STRATEGY_PAPER_MODE=true`. When the flag flips for live trading, the
route appears.

Verified defense layers (read but did not re-test):
- Token validation in the handler.
- Per-user rate limit.
- Handler-level paper-mode refusal (HTTP 503) — defense in depth that
  STILL fires if router accidentally mounts in paper mode.

Subtle question: the handler's paper-mode refusal reads the SAME
`strategy_paper_mode` setting that gates the router mount. If a
production deploy ever runs with `STRATEGY_PAPER_MODE=false` but
intends paper mode (config drift / env-var typo), the legacy webhook
route activates AND the handler-level refusal turns off
simultaneously — single point of failure for paper-mode safety.

**Recommendation for Phase 2:** add a separate, narrower
`webhook_legacy_enabled` setting that gates ONLY the router mount.
The paper-mode refusal stays on `strategy_paper_mode`. Two
independent flags → no shared-failure mode. ~10 LOC config change +
matching env var. **Sacred-zone-adjacent — `api/webhook.py` is a
protected file per CLAUDE.md.** Phase 2 needs explicit founder
authorization to touch it.

### 6.D — Admin-tier dual enforcement (LOW risk, MEDIUM hygiene)

Two competing admin checks ship simultaneously:
- `get_current_admin` (legacy) — 11 routes
- `require_admin` (Phase 2 RBAC) — 7 routes

Both are correct; the divergence is a migration artifact. New admin
routes should land on `require_admin`. Phase 3 RBAC sprint should
consolidate `get_current_admin` → `require_admin` so there's one
admin dependency.

**Recommendation: defer to Phase 3 RBAC sprint.** Not urgent.

### 6.E — System mode endpoint exposes operational posture (NO risk, design-acceptable)

`GET /api/system/mode` is unauth and returns `paper_mode`,
`kill_switch_check_enabled`, `circuit_breaker_enabled`. A scraper
could poll it and learn TRADETRI's safety posture without
authentication.

Per the file's docstring, this is deliberate (banner needs pre-auth
render). The exposed information is operational state, not a secret;
seeing "we are in paper mode" is not exploitable. **No action; record
the design decision.**

---

## 7. What I deliberately did NOT do in Phase 1

- ❌ No code changes; pure read-only discovery.
- ❌ No router-mount edits.
- ❌ No deletion of dead files (pending §6.A founder decision).
- ❌ No `api/webhook.py` changes (protected file per CLAUDE.md).
- ❌ No WS-layer audit (out of scope per founder confirmation).
- ❌ No external-service URL audit (out of scope per founder confirmation).
- ❌ No commit (Phase 1 doc lands in Phase 2 commit alongside chosen
  remediations).

---

## 8. Reproducible introspection script (inline)

```python
# /tmp/uu-venv/bin/python (or any venv with backend installed)
import os
from cryptography.fernet import Fernet
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test"*8)
os.environ.setdefault("DHAN_CLIENT_ID", "test")
os.environ.setdefault("DHAN_ACCESS_TOKEN", "test")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("STRATEGY_PAPER_MODE", "true")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.main import app
from fastapi.routing import APIRoute
for route in app.routes:
    if not isinstance(route, APIRoute): continue
    methods = sorted(route.methods - {"HEAD","OPTIONS"})
    deps = []
    def walk(d, seen):
        if d.call and getattr(d.call, "__name__", None):
            n = d.call.__name__
            if n != "<lambda>" and n not in seen:
                deps.append(n); seen.add(n)
        for sub in d.dependencies: walk(sub, seen)
    walk(route.dependant, set())
    print(f"{','.join(methods):>10s}  {route.path:60s}  deps={deps}")
```

Flip `STRATEGY_PAPER_MODE=false` to see the additional legacy-
webhook route appear.

---

## 9. Awaiting founder gate

Phase 2 candidate actions, smallest-first:

| # | Action | Effort | Risk | My recommendation |
|---|---|---|---|---|
| 6.A | Delete `api/indicator.py` + test | ~10 min | low | **Do** (matches Queue UU evidence) |
| 6.B | Delete `api/role_demo.py` | ~5 min | low | **Park** (file documents own exit) |
| 6.C | Split `webhook_legacy_enabled` from `strategy_paper_mode` | ~30 min code + ~15 min env | medium | **Defer until next live-trading sprint** unless you want it now |
| 6.D | Consolidate `get_current_admin` → `require_admin` | ~1 hr | low | **Defer to Phase 3 RBAC** |
| 6.E | System-mode design-acceptance | 0 | none | Record + no action |

Pick which Phase 2 items to execute and I proceed.
