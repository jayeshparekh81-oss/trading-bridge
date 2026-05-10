"""Polygon attestation stub — placeholder for Phase 4.

Phase 4 swaps this module for a real Polygon-mainnet client that
posts each attestation hash as ``calldata`` on a ledger smart
contract and returns the resulting transaction hash. Phase 2 ships
a deterministic stub so the rest of the ledger pipeline is
end-to-end testable today.

The stub returns ``None`` from :func:`submit_attestation_to_polygon`
— the API layer treats ``None`` as "off-chain only", which is the
Phase 2 reality. A future Phase 4 patch only needs to:

    1. Replace this module's body with a real Polygon client.
    2. Make :func:`submit_attestation_to_polygon` async.
    3. Return the txid.

No other code in the ledger pipeline needs to change.
"""

from __future__ import annotations


def submit_attestation_to_polygon(attestation_hash: str) -> str | None:
    """Off-chain stub. Always returns ``None``.

    Phase 4 swap-in expectations:
        * Same signature (``attestation_hash: str``), but the
          callable becomes ``async``.
        * Returns the Polygon tx hash on success, ``None`` on
          submission failure (caller logs + retries).
    """
    _ = attestation_hash  # Phase 4 will sign + emit this on-chain.
    return None


__all__ = ["submit_attestation_to_polygon"]
