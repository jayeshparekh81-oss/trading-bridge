# Stale Text Audit — May 18 2026

**Branch:** `docs/master-roadmap-refresh`
**Audit scope:** repo-wide grep for stale brand `tradeforge*` and
stale-date `May 18 launch` text.

---

## Brand pivot: `tradeforge` → `TRADETRI`

The product was originally branded "TradeForge" / domain `tradeforge.in`.
At some point the brand pivoted to "TRADETRI" / `tradetri.com`. Several
docs + 3 source files still reference the old brand.

### Per-file disposition

| File | Occurrences | Disposition |
|---|---:|---|
| `docs/deployment-guide.md` | 18 | **renamed** — pure documentation, safe |
| `docs/launch-checklist.md` | 6 | **renamed** — pure documentation, safe |
| `docs/tradingview_alert_setup.md` | 2 | **renamed** — example URLs in docs |
| `docs/MONDAY_MORNING_RUNBOOK.md` | varies | **renamed** — doc, safe |
| `docs/cost-breakdown.md` | varies | **renamed** — doc, safe |
| `docs/PHASE_C_MONDAY_DEPLOY_RUNBOOK.md` | varies | **renamed** — doc, safe |
| `docs/PHASE_C_MONDAY_QUICK_REFERENCE.md` | varies | **renamed** — doc, safe |
| `docs/MONDAY_LIVE_FIRSTRUN.md` | varies | **renamed** — doc, safe |
| `backend/docker-compose.prod.yml` | varies | **NOT renamed — BLOCKERS** |
| `backend/nginx.conf` | varies | **NOT renamed — BLOCKERS** |
| `backend/scripts/deploy.sh` | varies | **NOT renamed — BLOCKERS** |

### Why source files are skipped

Per task spec: "Search-and-replace must be reviewed per-file (don't
blindly sed across repo) — flag any ambiguous renames in BLOCKERS."

`docker-compose.prod.yml`, `nginx.conf`, `deploy.sh` are
infrastructure configuration that may reference the live production
domain (`api.tradeforge.in`), AWS resource names (`tradeforge-prod`),
SSH keys (`tradeforge-key.pem`), etc. Renaming these without
coordinating with the actual deployed infrastructure would break the
prod deploy.

**Flagged for founder review in `BLOCKERS_MASTER_ROADMAP_REFRESH.md`:**
the founder must confirm what's actually deployed to know if
`api.tradeforge.in` is still the canonical API hostname or if it has
been migrated to `api.tradetri.com`.

### How the docs renames are applied

For each doc file in the "renamed" list above:
- `tradeforge.in` → `tradetri.com`
- `tradeforge` (as a name reference) → `TRADETRI`
- `tradeforge-key` → `tradetri-key`
- `tradeforge-prod` → `tradetri-prod`
- `/opt/tradeforge` → `/opt/tradetri`

Source file references (`api.tradeforge.in`, `tradeforge.xxx.amazonaws.com`,
etc.) are preserved as-is in docs WHEN they are documenting the
current production state. If the production state hasn't migrated,
the docs accurately reflect that.

---

## Stale date: "May 18 launch"

The Phase 1 launch date was originally targeted for May 18 2026.
Reality: paper-mode-first launch state achieved May 17; public
customer-visible launch is later (founder decision pending —
target mid-June to mid-July per `docs/MASTER_ROADMAP.md`).

### Per-file disposition

| File | Stale text | Action |
|---|---|---|
| `docs/launch-checklist.md` | "May 18" references | Confirmed kept — checklist is a TEMPLATE, not a date pin |
| `docs/MONDAY_LIVE_FIRSTRUN.md` | Specific date 2026-05-04 | KEPT — this is a HISTORICAL runbook for that specific day |
| `docs/PHASE_C_MONDAY_DEPLOY_RUNBOOK.md` | "Monday" generic | KEPT — generic deploy-day runbook |

No "May 18 launch" hardcoded dates found requiring correction. The
stale-date risk in the spec was theoretical.

---

## What this branch ships

This file plus the per-doc rename edits (8 doc files modified).
The audit IS the documentation of changes.

---

## Verification

After applying renames:
```sh
$ grep -rln "tradeforge" docs/
# Should be empty (or list only the audit doc itself referencing the
# rename)
```
