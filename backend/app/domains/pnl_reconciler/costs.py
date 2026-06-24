"""Indian exchange-traded derivatives cost model (ESTIMATED charges).

The reconciler computes GROSS P&L from real fills; this module estimates the
standard Indian derivatives charge stack so it can report NET (``gross -
costs``). These are ESTIMATES from a published-rate model — ``broker_response``
does not carry the actual contract-note charges — so every breakdown is flagged
``estimated=True``. The shape leaves room for a future path to substitute
broker-actual charges (construct a :class:`CostBreakdown` with
``estimated=False``).

All rates live in ONE place: :data:`SEGMENT_RATES`, keyed by exchange segment
(NFO / BFO / MCX / CDS). Rates change over time and differ by segment — never
inline a magic number; add/adjust a :class:`CostRates` here. Defaults are
current NFO equity/stock-futures rates (a ``BSE-…-FUT`` single-stock future
trades on NSE's F&O segment = NFO, not on BSE's BFO).

Charge stack (per round trip):

* **Brokerage**     — flat ₹/order x number of executed orders (entry + exits)
* **STT**           — on SELL turnover only (futures rate)
* **Exchange txn**  — on TOTAL turnover (buy + sell), segment rate
* **SEBI turnover** — on TOTAL turnover (₹10 / crore)
* **Stamp duty**    — on BUY turnover only, segment rate
* **GST**           — 18% on (brokerage + exchange txn + SEBI fee)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_PAISE = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantize a money amount to paise (2 dp, half-up)."""
    return value.quantize(_PAISE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostRates:
    """Charge rates for ONE exchange segment.

    Turnover-based rates are FRACTIONS of turnover (``0.0002`` = 0.02%).
    ``brokerage_per_order`` is a flat ₹ amount per executed order.
    """

    brokerage_per_order: Decimal  # flat ₹ / executed order
    stt_sell: Decimal  # STT/CTT on SELL turnover (futures)
    exchange_txn: Decimal  # exchange transaction charge on TOTAL turnover
    sebi_fee: Decimal  # SEBI turnover fee on TOTAL turnover
    stamp_buy: Decimal  # stamp duty on BUY turnover
    gst: Decimal  # GST on (brokerage + exchange_txn + sebi_fee)


# ── Per-segment rates — single source of truth ─────────────────────────
# asof 2026-06. VERIFY against the latest exchange + broker circulars before
# trusting NET figures for anything official — Indian charges are revised
# periodically (e.g. NSE "true-to-label" transaction charges, 2024-10-01).
SEGMENT_RATES: dict[str, CostRates] = {
    # NSE F&O — equity index + single-stock FUTURES. ``BSE-…-FUT`` lives here.
    "NFO": CostRates(
        brokerage_per_order=Decimal("20"),  # Dhan F&O flat ₹20/order
        stt_sell=Decimal("0.0002"),  # 0.02% on sell (futures)
        exchange_txn=Decimal("0.0000173"),  # 0.00173% NSE futures (true-to-label)
        sebi_fee=Decimal("0.000001"),  # ₹10 per crore
        stamp_buy=Decimal("0.00002"),  # 0.002% on buy (₹200/crore)
        gst=Decimal("0.18"),  # 18%
    ),
    # BSE F&O FUTURES. NOTE: BSE derivative transaction charges have varied /
    # been incentivised — VERIFY before relying on BFO net figures.
    "BFO": CostRates(
        brokerage_per_order=Decimal("20"),
        stt_sell=Decimal("0.0002"),
        exchange_txn=Decimal("0"),  # BSE futures txn ~nil historically; VERIFY
        sebi_fee=Decimal("0.000001"),
        stamp_buy=Decimal("0.00002"),
        gst=Decimal("0.18"),
    ),
    # MCX commodity FUTURES (non-agri). CTT replaces STT on the sell leg.
    "MCX": CostRates(
        brokerage_per_order=Decimal("20"),
        stt_sell=Decimal("0.0001"),  # CTT 0.01% on sell (non-agri futures)
        exchange_txn=Decimal("0.0000260"),  # ~₹26/crore (varies by commodity); VERIFY
        sebi_fee=Decimal("0.000001"),
        stamp_buy=Decimal("0.00002"),  # 0.002% on buy
        gst=Decimal("0.18"),
    ),
    # NSE currency FUTURES (CDS). No STT/CTT on currency.
    "CDS": CostRates(
        brokerage_per_order=Decimal("20"),
        stt_sell=Decimal("0"),  # no STT on currency
        exchange_txn=Decimal("0.0000009"),  # ~₹9/crore; VERIFY
        sebi_fee=Decimal("0.000001"),
        stamp_buy=Decimal("0.000001"),  # 0.0001% on buy
        gst=Decimal("0.18"),
    ),
}

DEFAULT_SEGMENT = "NFO"

# ── Showcase NET-of-charges rate set (web-verified, dated) ──────────────────
# Used ONLY by the showcase metrics layer (backend/scripts/showcase_metrics.py)
# via the ``rates=`` override of :func:`compute_costs`. Kept SEPARATE from
# ``SEGMENT_RATES["NFO"]`` so the deployed (log-only) reconciler + its pinned
# tests are NOT disturbed. NOTE: the reconciler's SEGMENT_RATES["NFO"] still
# carries the pre-2026-04 STT (0.02%) and should be refreshed in its own task.
#
# asof 2026-06-22. Source: Zerodha charges page (https://zerodha.com/charges/),
# cross-checked vs NSE / CSV web search. NSE equity FUTURES:
#   * STT 0.05% on SELL (hiked from 0.02% eff. 2024 -> 0.05% eff. 2026-04-01).
#   * NSE txn 0.00183% on total turnover.  * SEBI ₹10/crore.
#   * Stamp 0.002% on BUY.  * GST 18% on (brokerage + txn + SEBI).
#   * Brokerage: Dhan F&O flat ₹20/executed order.
SHOWCASE_NFO_RATES_ASOF = "2026-06-22"
SHOWCASE_NFO_RATES = CostRates(
    brokerage_per_order=Decimal("20"),   # Dhan F&O flat ₹20/order
    stt_sell=Decimal("0.0005"),          # 0.05% on sell (futures, eff. 2026-04-01)
    exchange_txn=Decimal("0.0000183"),   # 0.00183% NSE futures txn
    sebi_fee=Decimal("0.000001"),        # ₹10 / crore
    stamp_buy=Decimal("0.00002"),        # 0.002% on buy
    gst=Decimal("0.18"),                 # 18%
)


@dataclass(frozen=True)
class CostBreakdown:
    """Itemised, auditable estimated charges for one round trip (Glass Box)."""

    segment: str
    orders: int
    buy_turnover: Decimal
    sell_turnover: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange_txn: Decimal
    sebi_fee: Decimal
    stamp_duty: Decimal
    gst: Decimal
    total: Decimal
    # Rate-model ESTIMATE, not broker contract-note actuals. A future capture
    # path can build a breakdown with ``estimated=False`` from real charges.
    estimated: bool = True


def compute_costs(
    *,
    buy_turnover: Decimal,
    sell_turnover: Decimal,
    orders: int,
    segment: str = DEFAULT_SEGMENT,
    rates: CostRates | None = None,
) -> CostBreakdown:
    """Estimate the Indian derivatives charge stack for one round trip.

    ``orders`` is the number of EXECUTED orders (entry legs + exit legs) — flat
    brokerage applies per order. Each itemised charge is quantised to paise and
    ``total`` is the sum of the itemised charges, so a reader can verify the
    breakdown adds up (Glass Box).
    """
    rate = rates if rates is not None else SEGMENT_RATES[segment]
    total_turnover = buy_turnover + sell_turnover

    brokerage = _q(rate.brokerage_per_order * orders)
    stt = _q(rate.stt_sell * sell_turnover)
    exchange_txn = _q(rate.exchange_txn * total_turnover)
    sebi_fee = _q(rate.sebi_fee * total_turnover)
    stamp_duty = _q(rate.stamp_buy * buy_turnover)
    gst = _q(rate.gst * (brokerage + exchange_txn + sebi_fee))
    total = brokerage + stt + exchange_txn + sebi_fee + stamp_duty + gst

    return CostBreakdown(
        segment=segment,
        orders=orders,
        buy_turnover=_q(buy_turnover),
        sell_turnover=_q(sell_turnover),
        brokerage=brokerage,
        stt=stt,
        exchange_txn=exchange_txn,
        sebi_fee=sebi_fee,
        stamp_duty=stamp_duty,
        gst=gst,
        total=total,
        estimated=True,
    )


__all__ = [
    "DEFAULT_SEGMENT",
    "SEGMENT_RATES",
    "CostBreakdown",
    "CostRates",
    "compute_costs",
]
