# BLOCKERS — Brand Cleanup Batch 1

**Branch:** `chore/brand-cleanup-batch-1`
**Date:** 2026-05-18
**Sibling doc:** `docs/BRAND_CLEANUP_BATCH_1.md`

---

## Open questions for founder review

### Q1. Production infrastructure: rename or keep `tradeforge`?

Three files in `backend/` reference the old brand as stable infrastructure
identifiers (DNS, container names, install paths, SSL cert paths):

| File | What it references |
|---|---|
| `backend/nginx.conf` | `api.tradeforge.in` server_name + Let's Encrypt cert paths (`/etc/letsencrypt/live/api.tradeforge.in/fullchain.pem`) |
| `backend/docker-compose.prod.yml` | 5 container names: `tradeforge_redis`, `tradeforge_backend`, `tradeforge_celery_worker`, `tradeforge_celery_beat`, `tradeforge_nginx`. Image tag `tradeforge_backend:latest` |
| `backend/scripts/deploy.sh` | Install path `/opt/tradeforge/backend`, backup path `/opt/tradeforge/backups`, container reference `tradeforge_backend` |

These are NOT cosmetic strings — they map to live production
infrastructure. Renaming requires coordinated changes:

1. New SSL cert issuance for `api.tradetri.com`
2. New DNS A/AAAA records for `api.tradetri.com`
3. Docker container rename (which destroys persistent volumes unless
   migrated)
4. Filesystem move `/opt/tradeforge → /opt/tradetri` on EC2

**Decision needed:** is the brand pivot tied to a planned
infrastructure migration window? If so, schedule + rename in
coordinated fashion. If the live infra stays on `tradeforge.in`,
keep these files as-is; only the customer-facing brand changes.

Recommendation: **keep as-is until infra migration is scheduled**.
Rename in a single coordinated PR + deploy when ready.

### Q2. Stale `"May-18 launch"` reference in frontend source

`frontend/src/components/algomitra/always-on-panel.tsx:4` opens with:

```ts
/**
 * Always-On AlgoMitra side panel — Phase 1 of the May-18 launch plan.
 */
```

This is a comment, not user-visible. But it's now stale (May 18 has
passed; the actual launch is pending).

**Decision needed:** what's the current public launch target?

- If "mid-June 2026", update the comment to "Phase 1 of the mid-June launch plan"
- If "Q3 2026" or later, update to "Phase 1 launch"
- If TBD, replace with "Phase 1 customer-facing launch"

Recommend: **third option** ("Phase 1 customer-facing launch") — it
removes the date dependency while preserving the original intent
("this panel is part of the first customer-visible launch wave").

### Q3. Should `docs/STALE_TEXT_AUDIT.md` and `docs/POST_MAY_18_RETROSPECTIVE.md` keep tradeforge references?

Both docs contain `tradeforge` in their content because they ARE the
audit doc + retrospective documenting the rename. Removing the
references would break their narrative integrity.

**Decision needed:** these references are intentional. No action
required, just confirming the audit treats them as kept.

Recommend: **keep**. The audit doc literally has to mention the old
brand to document the rename.

---

## What this branch ships

```
docs/BRAND_CLEANUP_BATCH_1.md    completion report + per-file disposition
BLOCKERS_BRAND_CLEANUP.md        this file
```

NOT modified: any source code, any test, any other doc.

## Hard constraints honoured

- ✅ Per-file review of every rename candidate (no blind sed)
- ✅ NO modifications to code paths using `tradeforge` as stable
  identifier (the 3 infrastructure files)
- ✅ NO modifications to generated files (.lock, build outputs,
  .next/)
- ✅ NO auto-replacement of `"May 18 launch"` (founder picks the
  new target)
