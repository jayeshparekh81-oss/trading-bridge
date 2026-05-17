# Brand Cleanup Batch 1 — May 18 audit + completion report

**Branch:** `chore/brand-cleanup-batch-1`
**Cut from:** `docs/master-roadmap-refresh`
**Date:** 2026-05-18
**Audit predecessor:** Queue III Task 5's `docs/STALE_TEXT_AUDIT.md`

---

## TL;DR

Queue III Task 5 already auto-renamed `tradeforge → TRADETRI` across
all 8 doc files that were safe to rename. This batch confirms the
prior cleanup is intact + executes the next layer:

- **8 doc files**: ✅ already renamed by Queue III (no further work)
- **Source code under `backend/app/` + `frontend/src/`**: ✅ ZERO
  remaining `tradeforge` refs found
- **3 infrastructure config files**: ⚠️ STILL flagged — see Q1 in
  `BLOCKERS_BRAND_CLEANUP.md`. Per hard constraint #2 of Task 5,
  these reference live production infra and won't be auto-renamed
  without founder confirmation
- **1 frontend source comment**: ⚠️ Stale "May-18 launch plan"
  reference in `frontend/src/components/algomitra/always-on-panel.tsx:4`
  — surfaced in BLOCKERS Q2

---

## Per-file disposition (full audit)

### Brand references (`tradeforge`)

| File | Refs | Disposition |
|---|---:|---|
| `docs/deployment-guide.md` | 0 | renamed by Queue III |
| `docs/launch-checklist.md` | 0 | renamed by Queue III |
| `docs/tradingview_alert_setup.md` | 0 | renamed by Queue III |
| `docs/MONDAY_MORNING_RUNBOOK.md` | 0 | renamed by Queue III |
| `docs/cost-breakdown.md` | 0 | renamed by Queue III |
| `docs/PHASE_C_MONDAY_DEPLOY_RUNBOOK.md` | 0 | renamed by Queue III |
| `docs/PHASE_C_MONDAY_QUICK_REFERENCE.md` | 0 | renamed by Queue III |
| `docs/MONDAY_LIVE_FIRSTRUN.md` | 0 | renamed by Queue III |
| `docs/STALE_TEXT_AUDIT.md` | 3 | **kept** — intentional historical references (it's the audit doc itself) |
| `docs/POST_MAY_18_RETROSPECTIVE.md` | 1 | **kept** — intentional historical reference |
| `docs/README.md` | 1 | **kept** — intentional historical reference |
| `backend/nginx.conf` | 5 | **NOT renamed** — `api.tradeforge.in` is the production DNS name in the SSL cert paths; founder must confirm migration |
| `backend/docker-compose.prod.yml` | 8 | **NOT renamed** — container names + image tag are live production identifiers; rename requires coordinated infra change |
| `backend/scripts/deploy.sh` | 5 | **NOT renamed** — `/opt/tradeforge/backend` install path; `tradeforge_backend` container name |
| `backend/app/**`, `frontend/src/**` | 0 | clean (no source-code refs) |

### Stale date (`May 18 launch`)

| File | Line | Disposition |
|---|---:|---|
| `frontend/src/components/algomitra/always-on-panel.tsx` | 4 | **flagged** — comment says "Phase 1 of the May-18 launch plan"; needs update to current launch target |
| `docs/STALE_TEXT_AUDIT.md` | 5, 64, 79 | kept — intentional audit references |

### Lock files / generated files / .next / node_modules

Skipped per hard constraint #3.

---

## What this branch ships

No source-code edits. The audit confirms Queue III's prior cleanup
is intact + identifies the remaining work that needs founder input.

```
docs/BRAND_CLEANUP_BATCH_1.md    this file — audit + completion report
BLOCKERS_BRAND_CLEANUP.md        ambiguous renames + founder-required infra confirmations
```

---

## Verification commands

```sh
# Confirm no tradeforge in source code:
grep -rln "tradeforge" backend/app/ frontend/src/
# (empty)

# Confirm 3 infrastructure files still have refs (intentional):
grep -rln "tradeforge" backend/nginx.conf backend/docker-compose.prod.yml backend/scripts/deploy.sh

# Confirm 1 stale May-18 reference in frontend:
grep -rln "May-18 launch" frontend/src/
```

---

## Hard constraints honoured

- ✅ Per-file review of every rename candidate (no blind sed)
- ✅ NO modifications to code paths using "tradeforge" as stable
  identifier (the 3 infrastructure files)
- ✅ NO modifications to generated files (.lock, build outputs)
- ✅ Stale May-18 date FLAGGED (not auto-fixed) since "actual current
  target" is a founder decision

## See also

- `docs/STALE_TEXT_AUDIT.md` — Queue III Task 5 audit doc (predecessor)
- `BLOCKERS_BRAND_CLEANUP.md` — open questions + founder asks
- `BLOCKERS_MASTER_ROADMAP_REFRESH.md` Q1 — original surfacing of
  the infrastructure-file rename ambiguity
