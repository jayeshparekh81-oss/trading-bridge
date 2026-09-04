"""Egress verification: prove a customer's order leaves from THEIR IP, not ours.

DISARMED IN THIS RUN. ``egress_verify_enabled`` defaults FALSE, and the only place
that could observe a real outbound IP (``_observe_public_ip``) is an unimplemented
seam. Nothing here makes a network call today.

FAIL CLOSED. When ``require_verified_egress`` is true (the default) and verification
cannot be performed or does not match, the answer is REFUSE. An unverified egress is
never treated as a pass, because the failure mode is sending one customer's order
from another identity.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.domains.customer_lane import config as lane_config

logger = logging.getLogger("customer_lane.egress")


class EgressUnverified(RuntimeError):
    """Raised when egress cannot be proved and proof is required."""


@dataclass(frozen=True)
class EgressVerdict:
    customer_id: uuid.UUID
    verified: bool
    reason: str
    expected_ip: str | None
    observed_ip: str | None


async def _observe_public_ip(proxy_url: str) -> str:  # pragma: no cover - seam
    """THE ONLY SEAM that could ever reach the network. Unimplemented by design."""
    raise NotImplementedError(
        "egress observation is not built in this run; no probe may leave the box")


async def verify_egress(customer_id: uuid.UUID, expected_ip: str | None,
                        proxy_url: str | None) -> EgressVerdict:
    cfg = lane_config.load()
    if not cfg.egress_verify_enabled:
        return EgressVerdict(customer_id, False, "verification_disarmed",
                             expected_ip, None)
    if not proxy_url:
        return EgressVerdict(customer_id, False, "no_proxy_configured", expected_ip, None)
    if not expected_ip:
        return EgressVerdict(customer_id, False, "no_expected_ip", None, None)
    try:
        observed = await _observe_public_ip(proxy_url)
    except NotImplementedError:
        return EgressVerdict(customer_id, False, "probe_unavailable", expected_ip, None)
    ok = observed == expected_ip
    return EgressVerdict(customer_id, ok,
                         "verified" if ok else "ip_mismatch", expected_ip, observed)


def enforce(verdict: EgressVerdict) -> None:
    """Turn a verdict into a decision. Unverified + required == refuse."""
    if verdict.verified:
        return
    if lane_config.load().require_verified_egress:
        raise EgressUnverified(
            f"egress for {verdict.customer_id} is unverified ({verdict.reason}); "
            f"refusing rather than sending from an unproven identity")
    logger.warning("egress unverified customer=%s reason=%s (not enforced)",
                   verdict.customer_id, verdict.reason)


__all__ = ["verify_egress", "enforce", "EgressVerdict", "EgressUnverified",
           "_observe_public_ip"]
