/**
 * Parser unit tests — wire → render-ready shape conversion for the
 * Phase B aggregator endpoints. Verifies:
 *
 *   - Decimal-as-string fields parse to numbers.
 *   - Nullable fields preserved (profit_factor, sharpe, exit_*, pnl).
 *   - ISO timestamps convert to epoch-seconds (UTC-aware).
 *   - Mode + Side + ExitReason enum literals round-trip.
 */

import { describe, expect, it } from "vitest";

import {
  parseEquityCurveResponse,
  parseEquityPoint,
  parseStrategyTesterMetrics,
  parseTradeListResponse,
  parseTradeRecord,
  type WireEquityCurveResponse,
  type WireEquityPoint,
  type WireStrategyTesterMetrics,
  type WireTradeListResponse,
  type WireTradeRecord,
} from "@/lib/strategy-tester/types";

describe("parseStrategyTesterMetrics", () => {
  const wire: WireStrategyTesterMetrics = {
    total_pnl: "12345.67",
    win_rate_pct: 62.5,
    profit_factor: 2.34,
    total_trades: 24,
    profitable_trades: 15,
    max_drawdown_pct: 8.4,
    sharpe_ratio_proxy: 0.42,
    avg_win: "800.00",
    avg_loss: "-300.50",
    largest_win: "2500.00",
    largest_loss: "-1200.00",
    expectancy: "350.25",
  };

  it("parses all Decimal-string fields to numbers", () => {
    const m = parseStrategyTesterMetrics(wire);
    expect(m.totalPnl).toBe(12345.67);
    expect(m.avgWin).toBe(800);
    expect(m.avgLoss).toBe(-300.5);
    expect(m.largestWin).toBe(2500);
    expect(m.largestLoss).toBe(-1200);
    expect(m.expectancy).toBe(350.25);
  });

  it("preserves non-Decimal numeric fields verbatim", () => {
    const m = parseStrategyTesterMetrics(wire);
    expect(m.winRatePct).toBe(62.5);
    expect(m.totalTrades).toBe(24);
    expect(m.profitableTrades).toBe(15);
    expect(m.maxDrawdownPct).toBe(8.4);
    expect(m.profitFactor).toBe(2.34);
    expect(m.sharpeRatioProxy).toBe(0.42);
  });

  it("propagates null profit_factor (mathematically-infinite case)", () => {
    const m = parseStrategyTesterMetrics({ ...wire, profit_factor: null });
    expect(m.profitFactor).toBeNull();
  });

  it("propagates null sharpe (insufficient sample case)", () => {
    const m = parseStrategyTesterMetrics({
      ...wire,
      sharpe_ratio_proxy: null,
    });
    expect(m.sharpeRatioProxy).toBeNull();
  });
});

describe("parseEquityPoint", () => {
  it("converts ISO timestamp to epoch-seconds and Decimal to number", () => {
    const wire: WireEquityPoint = {
      timestamp: "2026-05-14T09:15:00+00:00",
      equity: "105000.50",
      drawdown_pct: 2.5,
      trade_id_or_none: "abc-123",
    };
    const p = parseEquityPoint(wire);
    expect(p.time).toBe(Math.floor(Date.parse(wire.timestamp) / 1000));
    expect(p.equity).toBe(105000.5);
    expect(p.drawdownPct).toBe(2.5);
    expect(p.tradeId).toBe("abc-123");
    expect(p.timestamp).toBe(wire.timestamp);
  });

  it("propagates null tradeId for the starting-equity anchor", () => {
    const wire: WireEquityPoint = {
      timestamp: "2026-05-14T09:15:00+00:00",
      equity: "100000.00",
      drawdown_pct: 0,
      trade_id_or_none: null,
    };
    expect(parseEquityPoint(wire).tradeId).toBeNull();
  });
});

describe("parseEquityCurveResponse", () => {
  it("parses envelope + every point", () => {
    const wire: WireEquityCurveResponse = {
      points: [
        {
          timestamp: "2026-05-14T09:00:00+00:00",
          equity: "100000.00",
          drawdown_pct: 0,
          trade_id_or_none: null,
        },
        {
          timestamp: "2026-05-14T10:00:00+00:00",
          equity: "101500.00",
          drawdown_pct: 0,
          trade_id_or_none: "t1",
        },
      ],
      starting_equity: "100000.00",
      ending_equity: "101500.00",
      max_equity: "101500.00",
      min_equity: "100000.00",
    };
    const res = parseEquityCurveResponse(wire);
    expect(res.points).toHaveLength(2);
    expect(res.startingEquity).toBe(100000);
    expect(res.endingEquity).toBe(101500);
    expect(res.maxEquity).toBe(101500);
    expect(res.minEquity).toBe(100000);
    expect(res.points[1].tradeId).toBe("t1");
  });
});

describe("parseTradeRecord", () => {
  const baseWire: WireTradeRecord = {
    entry_marker_id: "entry-1",
    exit_marker_id: "exit-1",
    symbol: "RELIANCE",
    side: "LONG",
    entry_time: "2026-05-14T09:15:00+00:00",
    exit_time: "2026-05-14T09:45:00+00:00",
    entry_price: "2500.00",
    exit_price: "2520.50",
    qty: 10,
    pnl: "205.00",
    pnl_pct: 0.82,
    duration_minutes: 30,
    exit_reason: "TAKE_PROFIT",
  };

  it("parses a closed trade — all numeric fields parsed", () => {
    const t = parseTradeRecord(baseWire);
    expect(t.entryPrice).toBe(2500);
    expect(t.exitPrice).toBe(2520.5);
    expect(t.pnl).toBe(205);
    expect(t.pnlPct).toBe(0.82);
    expect(t.qty).toBe(10);
    expect(t.exitReason).toBe("TAKE_PROFIT");
    expect(t.side).toBe("LONG");
    expect(t.symbol).toBe("RELIANCE");
    expect(t.entryTime).toBe(Math.floor(Date.parse(baseWire.entry_time) / 1000));
    expect(t.exitTime).toBe(
      Math.floor(Date.parse(baseWire.exit_time!) / 1000),
    );
    expect(t.entryTimeIso).toBe(baseWire.entry_time);
    expect(t.exitTimeIso).toBe(baseWire.exit_time);
  });

  it("parses an open trade — all exit-side fields null", () => {
    const wire: WireTradeRecord = {
      ...baseWire,
      exit_marker_id: null,
      exit_time: null,
      exit_price: null,
      pnl: null,
      pnl_pct: null,
      duration_minutes: null,
      exit_reason: null,
    };
    const t = parseTradeRecord(wire);
    expect(t.exitMarkerId).toBeNull();
    expect(t.exitTime).toBeNull();
    expect(t.exitPrice).toBeNull();
    expect(t.pnl).toBeNull();
    expect(t.pnlPct).toBeNull();
    expect(t.durationMinutes).toBeNull();
    expect(t.exitReason).toBeNull();
    expect(t.exitTimeIso).toBeNull();
  });

  it("supports SHORT side + STOP_LOSS reason", () => {
    const wire: WireTradeRecord = {
      ...baseWire,
      side: "SHORT",
      exit_reason: "STOP_LOSS",
    };
    const t = parseTradeRecord(wire);
    expect(t.side).toBe("SHORT");
    expect(t.exitReason).toBe("STOP_LOSS");
  });
});

describe("parseTradeListResponse", () => {
  it("parses envelope + every trade + carries pagination + mode", () => {
    const wire: WireTradeListResponse = {
      trades: [
        {
          entry_marker_id: "e1",
          exit_marker_id: "x1",
          symbol: "TCS",
          side: "LONG",
          entry_time: "2026-05-14T09:15:00+00:00",
          exit_time: "2026-05-14T09:30:00+00:00",
          entry_price: "3500.00",
          exit_price: "3510.00",
          qty: 5,
          pnl: "50.00",
          pnl_pct: 0.28,
          duration_minutes: 15,
          exit_reason: "SIGNAL",
        },
      ],
      pagination: { limit: 100, offset: 0, total: 1 },
      mode: "PAPER",
    };
    const res = parseTradeListResponse(wire);
    expect(res.trades).toHaveLength(1);
    expect(res.trades[0].symbol).toBe("TCS");
    expect(res.pagination).toEqual({ limit: 100, offset: 0, total: 1 });
    expect(res.mode).toBe("PAPER");
  });
});
