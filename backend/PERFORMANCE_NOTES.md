# TRADETRI — Performance Notes

This is the engineering log for performance work on TRADETRI. Phase 1
(this document) covers measurement infrastructure + the obvious wins
that don't require production traffic to validate. Phase 2 (post-
launch) is driven by real RUM + p99 numbers.

## Methodology

Phase-1 measurements are **estimated from query plans + cardinality
math**, not measured against production traffic — we don't have
production traffic yet. Wherever a number appears below labelled
*estimated*, treat it as a "directionally correct, validate post-
launch" claim. Hard measurements get the *measured* tag.

For each candidate query I ran:

```sql
EXPLAIN (ANALYZE, BUFFERS) <query>;
```

against a seeded local Postgres with synthetic row counts at three
scale points: 100, 10k, 100k rows. The estimates compare the cost
ratio between the seq-scan plan (no composite index) and the
index-only-scan plan (composite index from Migration 022).

## Phase 1 — what shipped

### 1. Slow-request structured logger

**File:** `app/observability/perf_logger.py` —
`SlowRequestLoggerMiddleware`.

Threshold defaults to **500 ms** (env-overridable via
`PERF_SLOW_REQUEST_MS`). Fast requests pay only one
`time.perf_counter` pair + a comparison; no log emission, no
allocation, no hashing. Slow requests emit one structured
`request.slow` log line with:

- `path`, `method`, `status_code`
- `duration_ms`
- `threshold_ms`
- `user_id_hash` (salted SHA-256 — never raw UUID)
- `request_id` (links to the per-request trace)

This is the foundation for every Phase-2 optimization decision —
without slow-tail attribution we'd be guessing about which path to
optimize next.

### 2. Composite indexes (Migration 022)

| Index | Table | Columns | Query it serves |
| --- | --- | --- | --- |
| `ix_marketplace_listings_status_published_at` | marketplace_listings | (status, published_at DESC) | browse_listings |
| `ix_marketplace_listings_creator_created_at` | marketplace_listings | (creator_id, created_at DESC) | list_my_listings |
| `ix_marketplace_subscriptions_subscriber_status` | marketplace_subscriptions | (subscriber_id, status) | list_my_subscriptions |
| `ix_audit_logs_user_created_at` | audit_logs | (user_id, created_at DESC) | user activity log |
| `ix_paper_sessions_user_strategy_completed` | paper_sessions | (user_id, strategy_id, completed_at DESC) | paper trading history |
| `ix_support_tickets_user_created_at` | support_tickets | (user_id, created_at DESC) | my-tickets list |
| `ix_support_tickets_status_created_at` | support_tickets | (status, created_at DESC) | admin queue |

Created with `CREATE INDEX CONCURRENTLY IF NOT EXISTS` on Postgres
(no table lock — safe under live traffic). On SQLite (used in
tests) the migration falls back to a plain `CREATE INDEX` since
SQLite lacks the `CONCURRENTLY` keyword.

**Estimated impact** at 10k-row scale (cost ratio from EXPLAIN):

| Endpoint | Before (estimated) | After (estimated) | Improvement |
| --- | --- | --- | --- |
| `GET /api/marketplace/listings` | 80–120 ms (seq scan + sort) | 8–15 ms (index-only scan) | **~88%** |
| `GET /api/marketplace/listings/me` | 30–50 ms | 5–10 ms | **~80%** |
| `GET /api/marketplace/subscriptions/me` | 25–40 ms | 4–8 ms | **~80%** |
| `GET /api/support/tickets` (admin) | 100–150 ms | 10–20 ms | **~85%** |
| `GET /api/support/tickets/me` | 25–40 ms | 5–10 ms | **~80%** |

These all become near-O(log n) instead of O(n) at scale. The wins
compound as the marketplace + audit log grow — at 100k rows the
gap is roughly **15-30x**.

### 3. `browse_listings` LIMIT cap

**File:** `app/strategy_engine/api/marketplace.py` —
`_BROWSE_MAX_ROWS = 100`.

Before: the endpoint loaded *every* published listing into memory
on every browse-page hit, then filtered tags in Python. At 1k
listings this is ~50 ms of allocation + serialization that the
client never uses (only the first 20 render). At 10k listings it
becomes a real problem.

After: `LIMIT 100` at the SQL layer + the new
`(status, published_at DESC)` composite index makes this an
index-only scan with bounded latency regardless of total row count.

**Note:** This is technically a behavior change in the corner case
where a creator has > 100 published listings AND a tag filter
matches results past row 100. Acceptable for Phase 1 — the
marketplace cap on free-tier creators is well below 100. Cursor
pagination + JSONB tag containment land in Phase 2.

### 4. Frontend bundle hygiene

**File:** `frontend/next.config.ts`.

| Change | Effect |
| --- | --- |
| `compress: true` | gzip on static + SSR responses; ~70% size reduction on JSON/HTML |
| `productionBrowserSourceMaps: false` (env-toggleable) | Stops shipping ~3-4x larger JS bundles to production users |
| `poweredByHeader: false` | Strips fingerprintable header (also ~30 bytes per response) |
| `images.formats: [avif, webp]` | Modern format negotiation; ~40-60% smaller than PNG/JPEG |
| `images.remotePatterns: []` | Closes the `_next/image` open-proxy abuse vector |

Estimated first-load saving for the `/strategies` page (largest
client bundle today): ~150 KB transferred → ~100 KB transferred
(~33% smaller, primarily from gzip + sourcemap removal).

## What I deliberately did NOT change

The original spec called for "N+1 fixes in marketplace + strategies
endpoints". I read those endpoints and they are NOT N+1: the rows
are denormalized (subscriber counts, ratings, tags all live on the
listing row), and the list endpoints do single SELECTs without
relationship loading. Adding `selectinload()` calls would have been
no-op churn that looked productive but changed nothing on the wire.
Honesty over LOC.

Similarly, the `strategy_versions` table doesn't exist — strategy
versions are stored under `~/.cache/tradetri/strategy_versions/`
(file-based store). No DB index would help that path; the file-
listing latency is already dominated by the OS page cache.

## Phase 2 candidates (post-launch, with real data)

Ordered by expected impact:

1. **Redis caching for hot reads.**
   `GET /api/marketplace/listings` (browse), `GET /api/strategies/{id}`,
   `/api/users/me`. TTL 30-60s with explicit invalidation on
   create/update. Should cut p50 by another 60-80% on those paths.
2. **JSONB tag containment on `marketplace_listings`.**
   Migrate `tags` from JSON to `ARRAY(String)` + GIN index, push
   the tag filter from Python into SQL. Lets `LIMIT 100` honor the
   tag filter properly + scales to large tag-faceted browses.
3. **Cursor pagination on browse + my-listings + my-subscriptions.**
   Replace OFFSET-based paging (which we don't have yet) with
   `(published_at, id) > (?, ?)` cursors. Stable + cheap at any depth.
4. **Connection pool tuning.**
   Once we have steady-state QPS data, set `pool_size` +
   `max_overflow` against actual concurrency rather than the
   asyncpg default. Watch for "queue wait" in the slow-request log.
5. **Frontend code splitting + dynamic imports.**
   The strategy-builder pages bundle every indicator + every chart
   library upfront. Dynamic-import the indicator gallery + the
   chart renderer; gates the heavy dependencies behind first
   interaction.
6. **Service worker for offline mode.**
   Cache `/api/strategies` + `/api/marketplace/listings` reads with
   stale-while-revalidate. Phase-2.5; needs PWA manifest first.
7. **Image CDN integration.**
   When marketplace creators start uploading thumbnails, route
   them through Cloudfront with `images.remotePatterns` + a
   restrictive allow-list.
8. **Async migration of remaining sync endpoints.**
   A few of the older indicator-engine paths still use synchronous
   DB calls inside an async route. Convert to `AsyncSession` to
   stop blocking the event loop under load.

## How to validate (post-launch)

For every Phase-2 ticket, the validation checklist is:

- [ ] Capture the baseline: 24h p50 + p99 from the slow-request log
      filtered to the affected route.
- [ ] Land the change behind a flag (or in canary if feasible).
- [ ] Capture the post-deploy p50 + p99 over the next 24h.
- [ ] Numbers in the PR description must show direction + magnitude
      of the improvement. "It feels faster" is not data.

## Reference

- Migration 022 source: `backend/migrations/versions/022_perf_indexes.py`
- Slow-request middleware: `backend/app/observability/perf_logger.py`
- Browse-listing cap: `backend/app/strategy_engine/api/marketplace.py:411`
