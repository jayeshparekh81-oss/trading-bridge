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
async def system_mode() -> dict[str, bool]:
    """Return the three master safety toggles in one read.

    Polled every ~5 minutes from the dashboard banner. Cheap (no I/O)
    so a high poll rate is harmless.
    """
    s = get_settings()
    return {
        "paper_mode": bool(s.strategy_paper_mode),
        "kill_switch_check_enabled": bool(s.kill_switch_check_enabled),
        "circuit_breaker_enabled": bool(s.circuit_breaker_enabled),
    }


__all__ = ["router"]
