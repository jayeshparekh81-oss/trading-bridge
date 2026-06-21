"""Post-hoc P&L reconciler domain.

A SEPARATE, read-first job that reconstructs realized P&L for a strategy's
already-CLOSED positions from the REAL broker fills captured in
``strategy_executions.broker_response`` — and (only in write mode) annotates
``strategy_positions.final_pnl``.

It deliberately lives OUTSIDE the live order/close path. It never imports or
mutates the sacred execution modules (``strategy_executor``, ``direct_exit``,
``brokers/*``, ``webhook``). It only READS executions + positions, COMPUTES
P&L, and post-hoc ANNOTATES ``final_pnl`` on closed rows.
"""

from app.domains.pnl_reconciler.costs import (
    DEFAULT_SEGMENT,
    SEGMENT_RATES,
    CostBreakdown,
    CostRates,
    compute_costs,
)
from app.domains.pnl_reconciler.service import (
    ExitLeg,
    FillInfo,
    ReconcileResult,
    RoundTrip,
    build_fill_index,
    format_report,
    parse_fill,
    plan_reconciliation,
    reconcile,
    reconcile_position,
    reconcile_strategy,
    reconcile_unrecorded,
)

__all__ = [
    "DEFAULT_SEGMENT",
    "SEGMENT_RATES",
    "CostBreakdown",
    "CostRates",
    "ExitLeg",
    "FillInfo",
    "ReconcileResult",
    "RoundTrip",
    "build_fill_index",
    "compute_costs",
    "format_report",
    "parse_fill",
    "plan_reconciliation",
    "reconcile",
    "reconcile_position",
    "reconcile_strategy",
    "reconcile_unrecorded",
]
