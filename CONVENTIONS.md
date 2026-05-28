# TRADETRI — Code Organization Conventions

> Read alongside `CLAUDE.md` (production-safety + workflow rules).
> **This is a going-forward standard. We do NOT big-bang rewrite the legacy
> layout. Existing code stays put; we migrate incrementally, one domain at a
> time, only when a task already touches that domain.**

---

## (a) Current reality

The backend is a **hybrid**: the top level is layer-split
(`app/api/`, `app/services/`, `app/schemas/`, `app/db/models/`) while a single
`app/strategy_engine/` god-package re-implements its own `api/`, `schema/`,
`models.py`, and services — effectively a second app inside the app. Routers are
fragmented across `app/api/` (22) and `app/strategy_engine/api/` (16), with 8
separate files all mounting the `/api/strategies` prefix. `app/services/` is a
30-file flat folder. It runs fine (imports are clean) but ownership and
discoverability are poor.

---

## (b) Going-forward rule — new code is domain-oriented

**Every new feature goes in its own domain package:**

```
app/domains/<domain>/
    router.py      # FastAPI APIRouter for this domain
    service.py     # business logic (split into service_*.py if large)
    schemas.py     # Pydantic request/response models
    models.py      # SQLAlchemy ORM models for this domain
    __init__.py
```

Router+service+schema+model for one domain live **together**. The router is
wired with a single `app.include_router(...)` in `app/main.py`.

**Hard don'ts for new code:**
- ❌ Do NOT add new modules to `app/strategy_engine/` (the god-package). It is
  legacy; treat it as frozen surface area.
- ❌ Do NOT drop new files into the flat `app/services/` folder.
- ❌ Do NOT create a new router that reuses a prefix already owned by another
  file. One prefix = one router.
- ❌ Do NOT introduce circular imports. A domain may import shared primitives
  (`app/core/`, `app/db/`) but domains must not import each other's internals —
  cross-domain calls go through the other domain's `service.py` public functions.

**Migrating legacy code:** allowed and encouraged, but only when a task already
touches that area. Move it into `app/domains/<domain>/` as a **pure move**
(keep URL prefixes identical so the API contract is unchanged), run the full
suite, and ship it as its own reviewable PR. Never mix a move with a behavior
change.

---

## (c) Naming rule — singular vs plural (fixes the indicator/indicators confusion)

Pick one and apply it everywhere:

| Thing | Convention | Example |
|-------|------------|---------|
| Domain folder | **singular** | `app/domains/indicator/`, `app/domains/strategy/` |
| ORM model class | **singular** | `class Indicator`, `class Strategy` |
| DB table name | **plural** | `indicators`, `strategies` |
| REST route prefix (collection) | **plural** | `/api/indicators`, `/api/strategies` |
| Module file names | **singular noun** | `router.py`, `service.py`, `schemas.py`, `models.py` |

So: the **module/domain is singular** (`indicator`), the **HTTP resource is
plural** (`/api/indicators`). No more `indicator.py` vs `indicators.py` sitting
side by side — there is exactly one domain module and one plural route prefix.
Same rule resolves `marker`/`markers`, `webhook`/`webhooks`, etc.

### FROZEN external contracts (the naming rule applies to NEW code ONLY)

The singular/plural convention governs **new** modules, models, and route
prefixes. It is **never** a license to rename an existing external-facing URL.
Outside systems hardcode these URLs; renaming them silently breaks production
even though our tests stay green (tests exercise handlers, not the third party's
config).

**Permanently frozen — do NOT rename these existing prefixes, ever:**

| Frozen endpoint(s) | Who hardcodes it | What a rename breaks |
|--------------------|------------------|----------------------|
| `/api/webhook` and `/api/webhook/strategy` | TradingView / Pine Script alert webhooks | Live trading signals stop arriving — strategies go silent |
| Fyers OAuth redirect/callback URL | Registered in the Fyers app console | Broker login (OAuth handshake) breaks |
| Dhan OAuth redirect/callback URL | Registered in the Dhan app console | Broker login (OAuth handshake) breaks |

These stay exactly as they are even though `/api/webhook/strategy` would, under a
greenfield reading of the rule, look like a candidate for normalization. It is
not. Leave it.

**Rule of thumb:**
- ✅ **Internal Python renames are safe** — module/file/symbol renames, moving a
  domain into `app/domains/<domain>/`, etc. The full test suite verifies these.
- ❌ **External URL prefix renames on existing endpoints are forbidden.** New
  endpoints follow the plural convention; existing public URLs are frozen
  contracts. If you believe an external URL truly must change, that is a
  coordinated, versioned migration with the third-party config updated first —
  STOP and ask (per CLAUDE.md), never do it as part of a refactor.

---

## (d) "Where does new code go?" decision tree

```
Adding new code?
│
├─ Is it a new business capability (its own routes/logic/data)?
│     └─ YES → create app/domains/<domain>/ (router+service+schema+model)
│
├─ Does it extend an EXISTING domain?
│     ├─ already under app/domains/<domain>/ → add to that package
│     └─ still in legacy (app/api or strategy_engine) →
│           prefer: move that domain to app/domains/<domain>/ first
│                   (pure move, same prefix, own PR), then extend.
│           if a move is out of scope for this task → extend in place,
│           leave a TODO pointing here, do NOT expand the god-package further.
│
├─ Is it cross-cutting infra (config, db session, auth primitives, logging)?
│     └─ app/core/ or app/db/ — never a domain package
│
└─ Is it a shared schema/util used by 2+ domains?
      └─ app/schemas/shared/ (or app/core/) — keep domain schemas domain-local
```

When unsure which domain something belongs to → **STOP and ask** (per CLAUDE.md).

---

## (e) Frontend conventions (Next.js App Router)

- **Server-first.** Components are React Server Components by default.
- **`'use client'` only at the leaf** — the smallest interactive component that
  truly needs state/effects/handlers. Do NOT mark a whole page/layout client;
  push the boundary down. (Today ~205 files are `'use client'` — new work must
  not grow this; refactor toward server shells when you touch a page.)
- **Every route group has `loading.tsx` and `error.tsx`** (and `not-found.tsx`
  where relevant). Add the missing ones as you touch each group.
- Each route group also has its own `layout.tsx`.
- Data fetching happens in server components / server actions; client components
  receive data as props.

---

## Reminder

Incremental, reversible, one domain per PR. URL contracts and the live trading
path stay untouched during any move. Legacy is migrated *opportunistically*,
never in a single big-bang.
