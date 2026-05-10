"""Pure-Python polynomial-regression helper.

Solves ``X @ b = X.T @ y`` (the OLS normal equations) for
polynomial fits of small degree (1..5 in practice). Uses
straightforward Gaussian elimination — for the matrix sizes
we care about (3x3 for quadratic, 4x4 for cubic) the cost is
negligible and avoids a numpy dependency.

The :func:`polyfit_value_at_end` helper returns the fitted
polynomial's value at the LAST x of the window — i.e. the
"current" point's projection onto the fit. That's what the
Pack-14 polynomial-regression indicators emit.
"""

from __future__ import annotations

from collections.abc import Sequence


def polyfit_value_at_end(
    values: Sequence[float], degree: int,
) -> float | None:
    """Fit a degree-``degree`` polynomial to ``values`` (with x = 0..N-1)
    and return the polynomial's value at ``x = N - 1``.

    Returns ``None`` when the system is singular (e.g. constant
    input + degree>=1 sometimes degenerates) or input is too short.
    """
    n = len(values)
    if n < degree + 1:
        return None
    # Build the design matrix X (n x (degree+1)) implicitly via the
    # Gram matrix X.T @ X (which is (degree+1) x (degree+1)) and
    # X.T @ y. For polynomial features [1, x, x^2, ...] the i,j
    # entry of X.T @ X is sum(x^(i+j) for x in 0..n-1). We compute
    # the cumulative power sums once.
    max_power = 2 * degree
    power_sums = [0.0] * (max_power + 1)
    for x in range(n):
        x_pow = 1.0
        for k in range(max_power + 1):
            power_sums[k] += x_pow
            x_pow *= x

    xt_x: list[list[float]] = [
        [power_sums[i + j] for j in range(degree + 1)]
        for i in range(degree + 1)
    ]
    xt_y: list[float] = [0.0] * (degree + 1)
    for x in range(n):
        x_pow = 1.0
        for k in range(degree + 1):
            xt_y[k] += x_pow * values[x]
            x_pow *= x

    coeffs = _solve_linear(xt_x, xt_y)
    if coeffs is None:
        return None
    # Evaluate the polynomial at x = n - 1 (the most recent bar).
    x_eval = n - 1
    result = 0.0
    x_pow = 1.0
    for k in range(degree + 1):
        result += coeffs[k] * x_pow
        x_pow *= x_eval
    return result


def _solve_linear(
    matrix: list[list[float]], rhs: list[float],
) -> list[float] | None:
    """Gaussian elimination with partial pivoting for small (<=5x5)
    systems. Returns ``None`` when the matrix is singular."""
    n = len(matrix)
    # Build augmented matrix in-place (clone first so we don't
    # mutate the caller's lists).
    aug = [[*list(row), rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        # Partial pivot — find the row with the largest absolute
        # value in this column at or below ``col``.
        pivot = col
        for r in range(col + 1, n):
            if abs(aug[r][col]) > abs(aug[pivot][col]):
                pivot = r
        if abs(aug[pivot][col]) < 1e-12:
            return None  # singular
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        # Eliminate below.
        for r in range(col + 1, n):
            factor = aug[r][col] / aug[col][col]
            for c in range(col, n + 1):
                aug[r][c] -= factor * aug[col][c]

    # Back-substitute.
    out = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = aug[i][n]
        for j in range(i + 1, n):
            s -= aug[i][j] * out[j]
        out[i] = s / aug[i][i]
    return out


__all__ = ["polyfit_value_at_end"]
