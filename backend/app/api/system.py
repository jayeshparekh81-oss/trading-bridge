"""System-mode endpoint — surfaces master safety toggles for the UI banner.

Read-only. Powers the dashboard's PAPER-MODE banner and operator tooling
that needs to confirm the current global posture without shelling into
the container to read env vars.

Authentication: NONE on purpose. The endpoint exposes only boolean flags
(no secrets, no PII, no per-user data). Wrapping it in JWT would force
the banner to wait for auth bootstrapping on every page load — and the
banner needs to render BEFORE the user is authenticated (e.g. on /login,
so a paper-mode test deployment is unmistakable). If we ever surface
sensitive fields here, gate them behind a separate authenticated route.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/mode")
async def system_mode() -> dict[str, object]:
    """Return the master safety toggles, and where the record begins.

    Polled every ~5 minutes from the dashboard banner. Cheap (no I/O)
    so a high poll rate is harmless.

    ``tracking_epoch`` is the ONE owner of the cut-off, published so the UI can
    say "Record 1 Sept 2026 se" with the date coming FROM THE SERVER. A
    hardcoded date in the frontend would be a second spelling that drifts the
    day the epoch moves — the same defect the paper banner was fixed for.
    ``null`` means no cut-off is set, and the UI must then say nothing at all
    rather than invent a fallback date.
    """
    s = get_settings()
    epoch = s.tracking_epoch
    return {
        "paper_mode": bool(s.strategy_paper_mode),
        "kill_switch_check_enabled": bool(s.kill_switch_check_enabled),
        "circuit_breaker_enabled": bool(s.circuit_breaker_enabled),
        "tracking_epoch": epoch.isoformat() if epoch else None,
    }


__all__ = ["router"]
