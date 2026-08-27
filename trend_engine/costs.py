"""Transaction-cost + slippage models — default = NSE INDEX FUTURES intraday.

Every statutory rate is a labelled constant flagged for verification. These
drift with budgets/circulars — confirm against the current NSE/broker schedule
before trusting PnL. For a 61-day smoke test the exact basis points barely move
the conclusion, but the machinery is here so later rungs inherit real costs.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── NSE equity/index FUTURES statutory rates (fractions of turnover unless noted) ──
STT_RATE = 0.0002          # 0.020% on the SELL leg only          # VERIFY current NSE rate
EXCHANGE_TXN_RATE = 0.0000173  # ~0.00173% of turnover (NSE fut)  # VERIFY current NSE rate
SEBI_RATE = 0.000001       # ₹10 per crore = 0.0001% of turnover  # VERIFY current NSE rate
STAMP_RATE = 0.00002       # 0.002% on the BUY leg only           # VERIFY current NSE rate
GST_RATE = 0.18            # 18% on (brokerage + exchange txn)     # VERIFY current NSE rate
DEFAULT_BROKERAGE_PER_ORDER = 20.0  # flat INR/order               # VERIFY broker plan

# ── NSE EQUITY INTRADAY (MIS) statutory rates — differ from futures. ──
EQ_STT_RATE = 0.00025        # 0.025% on the SELL leg (intraday)    # VERIFY current NSE rate
EQ_EXCH_TXN_RATE = 0.0000297  # ~0.00297% of turnover (NSE cash)    # VERIFY current NSE rate
EQ_SEBI_RATE = 0.000001      # ₹10 per crore = 0.0001% of turnover  # VERIFY current NSE rate
EQ_STAMP_RATE = 0.00003      # 0.003% on the BUY leg (intraday)     # VERIFY current NSE rate


@dataclass
class CostModel:
    """Round-trip cost in INR for one futures position (1 buy + 1 sell leg)."""

    brokerage_per_order: float = DEFAULT_BROKERAGE_PER_ORDER
    stt_rate: float = STT_RATE
    exch_txn_rate: float = EXCHANGE_TXN_RATE
    sebi_rate: float = SEBI_RATE
    stamp_rate: float = STAMP_RATE
    gst_rate: float = GST_RATE

    @classmethod
    def default(cls, brokerage_per_order: float = DEFAULT_BROKERAGE_PER_ORDER) -> "CostModel":
        """NSE index-futures intraday default."""
        return cls(brokerage_per_order=brokerage_per_order)

    @classmethod
    def default_equity_intraday(cls, brokerage_per_order: float = DEFAULT_BROKERAGE_PER_ORDER) -> "CostModel":
        """NSE cash-equity INTRADAY (MIS) default — different STT/stamp than futures."""
        return cls(
            brokerage_per_order=brokerage_per_order,
            stt_rate=EQ_STT_RATE,
            exch_txn_rate=EQ_EXCH_TXN_RATE,
            sebi_rate=EQ_SEBI_RATE,
            stamp_rate=EQ_STAMP_RATE,
            gst_rate=GST_RATE,
        )

    @classmethod
    def zero(cls) -> "CostModel":
        """All-zero cost model — lets the harness emit RAW gross so an external
        sizing/cost layer can own the accounting."""
        return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def round_trip(self, buy_value: float, sell_value: float) -> float:
        """Total INR cost given the buy-leg and sell-leg notional values.

        STT hits the sell leg, stamp duty the buy leg; txn/SEBI hit total
        turnover; GST is charged on brokerage + exchange txn charge.
        """
        turnover = buy_value + sell_value
        brokerage = 2.0 * self.brokerage_per_order  # entry + exit orders
        stt = self.stt_rate * sell_value
        txn = self.exch_txn_rate * turnover
        sebi = self.sebi_rate * turnover
        stamp = self.stamp_rate * buy_value
        gst = self.gst_rate * (brokerage + txn)
        return brokerage + stt + txn + sebi + stamp + gst


@dataclass
class SlippageModel:
    """N ticks of adverse slippage per fill."""

    ticks: int = 1
    tick_size: float = 0.05  # VERIFY current NSE tick size

    def adjust(self, price: float, side: int) -> float:
        """Worsen a fill: BUY (side +1) fills higher, SELL (side -1) fills lower."""
        return price + side * self.ticks * self.tick_size

    def per_fill_inr(self, qty: int) -> float:
        return self.ticks * self.tick_size * qty

    def bps(self, price: float) -> float:
        return (self.ticks * self.tick_size / price) * 1e4
