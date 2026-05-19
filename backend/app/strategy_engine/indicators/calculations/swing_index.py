"""Swing Index (SI) — Welles Wilder, 1978.

No Pine ``ta.*`` canonical. Locked variant per reference doc.

Definition:
    For each bar ``i >= 1``:
        TR1 = abs(H[i] - C[i-1])
        TR2 = abs(L[i] - C[i-1])
        TR3 = abs(H[i] - L[i])

        # 3-branch R selection (LOCKED variant, per reference)
        IF TR1 >= TR2 and TR1 >= TR3:
            R = (H - C_prev) - 0.5*(L - C_prev) + 0.25*(C_prev - O_prev)
        ELIF TR2 >= TR1 and TR2 >= TR3:
            R = (L - C_prev) - 0.5*(H - C_prev) + 0.25*(C_prev - O_prev)
        ELSE:  # TR3 largest
            R = (H - L) + 0.25*(C_prev - O_prev)

        N = (C - C_prev) + 0.5*(C - O) + 0.25*(C_prev - O_prev)
        K = max(TR1, TR2)
        T = 1.0      # limit_move LOCKED for equities/indices

        SI[i] = 50 * (N / R) * (K / T)

    Guards:
        * R == 0 ⇒ SI = 0
        * Bar 0 (no prior) ⇒ SI[0] = 0 by convention

Output length equals input length.

Source: J. Welles Wilder, "New Concepts in Technical Trading Systems"
(1978). 3-branch variant per the reference doc; some implementations
use a 4-branch tie-break variant which produces identical results in
the strict-inequality cases.
"""

from __future__ import annotations

from collections.abc import Sequence


def swing_index(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    limit_move: float = 1.0,
) -> list[float]:
    """Welles Wilder's Swing Index. Returns per-bar SI values."""
    if not isinstance(limit_move, (int, float)) or isinstance(limit_move, bool):
        raise ValueError(f"limit_move must be numeric; got {limit_move!r}.")
    if limit_move <= 0:
        raise ValueError(f"limit_move must be > 0; got {limit_move}.")

    n = len(opens)
    if not (n == len(highs) == len(lows) == len(closes)):
        raise ValueError(
            f"opens, highs, lows, closes must be same length; "
            f"got {n}, {len(highs)}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []

    out: list[float] = [0.0] * n  # SI[0] = 0 by convention

    for i in range(1, n):
        H = float(highs[i])
        L = float(lows[i])
        C = float(closes[i])
        O = float(opens[i])
        C_prev = float(closes[i - 1])
        O_prev = float(opens[i - 1])

        TR1 = abs(H - C_prev)
        TR2 = abs(L - C_prev)
        TR3 = abs(H - L)

        if TR1 >= TR2 and TR1 >= TR3:
            R = (
                (H - C_prev)
                - 0.5 * (L - C_prev)
                + 0.25 * (C_prev - O_prev)
            )
        elif TR2 >= TR1 and TR2 >= TR3:
            R = (
                (L - C_prev)
                - 0.5 * (H - C_prev)
                + 0.25 * (C_prev - O_prev)
            )
        else:  # TR3 largest
            R = (H - L) + 0.25 * (C_prev - O_prev)

        if R == 0.0:
            out[i] = 0.0
            continue

        N = (
            (C - C_prev)
            + 0.5 * (C - O)
            + 0.25 * (C_prev - O_prev)
        )
        K = max(TR1, TR2)
        out[i] = 50.0 * (N / R) * (K / limit_move)

    return out


__all__ = ["swing_index"]
