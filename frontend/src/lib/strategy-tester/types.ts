/**
 * Strategy-tester wire + render-ready TypeScript types.
 *
 * Mirrors the Phase B Pydantic schemas in
 * ``backend/app/schemas/strategy_tester.py``. Two parallel type
 * families per response shape — same convention as
 * :mod:`@/lib/chart/types`:
 *
 *   - ``Wire*``  → exact JSON shape on the wire. Decimal-valued
 *                  fields arrive as **strings** because the backend's
 *                  strict Pydantic encoder emits Decimals as JSON
 *                  strings to preserve cents-level precision. Caller
 *                  MUST NOT do arithmetic on these directly.
 *   - bare types → render-ready form with numeric prices/P&L and
 *                  epoch-seconds timestamps. Produced by the
 *                  ``parse*`` fns below — the hook calls them once on
 *                  response, components consume the parsed shape.
 *
 * Nullable fields follow the backend convention: explicit ``null`` in
 * the JSON (never absent). Open trades surface with ``exit_*`` +
 * ``pnl*`` + ``duration_minutes`` + ``exit_reason`` all ``null``.
 */

// ═══════════════════════════════════════════════════════════════════════
// Enums — string literals matching backend StrEnums
// ═══════════════════════════════════════════════════════════════════════

export type Mode = "BACKTEST" | "PAPER" | "LIVE";

export type Side = "LONG" | "SHORT";

export type ExitReason = "SIGNAL" | "STOP_LOSS" | "TAKE_PROFIT" | "MANUAL";

// ═══════════════════════════════════════════════════════════════════════
// Metrics
// ═══════════════════════════════════════════════════════════════════════

export interface WireStrategyTesterMetrics {
  total_pnl: string;
  win_rate_pct: number;
  /** ``null`` when there are no losers and at least one winner — the
   *  ratio is mathematically infinite. UI renders ``∞``. */
  profit_factor: number | null;
  total_trades: number;
  profitable_trades: number;
  max_drawdown_pct: number;
  /** ``null`` when fewer than 2 closed trades OR zero variance. */
  sharpe_ratio_proxy: number | null;
  avg_win: string;
  avg_loss: string;
  largest_win: string;
  largest_loss: string;
  expectancy: string;
}

export interface StrategyTesterMetrics {
  totalPnl: number;
  winRatePct: number;
  profitFactor: number | null;
  totalTrades: number;
  profitableTrades: number;
  maxDrawdownPct: number;
  sharpeRatioProxy: number | null;
  avgWin: number;
  avgLoss: number;
  largestWin: number;
  largestLoss: number;
  expectancy: number;
}

export function parseStrategyTesterMetrics(
  wire: WireStrategyTesterMetrics,
): StrategyTesterMetrics {
  return {
    totalPnl: parseFloat(wire.total_pnl),
    winRatePct: wire.win_rate_pct,
    profitFactor: wire.profit_factor,
    totalTrades: wire.total_trades,
    profitableTrades: wire.profitable_trades,
    maxDrawdownPct: wire.max_drawdown_pct,
    sharpeRatioProxy: wire.sharpe_ratio_proxy,
    avgWin: parseFloat(wire.avg_win),
    avgLoss: parseFloat(wire.avg_loss),
    largestWin: parseFloat(wire.largest_win),
    largestLoss: parseFloat(wire.largest_loss),
    expectancy: parseFloat(wire.expectancy),
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Equity curve
// ═══════════════════════════════════════════════════════════════════════

export interface WireEquityPoint {
  /** ISO 8601 with tz offset. */
  timestamp: string;
  equity: string;
  drawdown_pct: number;
  /** UUID of the exit marker that produced this step. ``null`` for the
   *  starting-equity anchor point. */
  trade_id_or_none: string | null;
}

export interface WireEquityCurveResponse {
  points: WireEquityPoint[];
  starting_equity: string;
  ending_equity: string;
  max_equity: string;
  min_equity: string;
}

export interface EquityPoint {
  /** Epoch seconds (UTC). */
  time: number;
  equity: number;
  drawdownPct: number;
  tradeId: string | null;
  /** Echo of the original ISO string — kept for tooltip labelling. */
  timestamp: string;
}

export interface EquityCurveResponse {
  points: EquityPoint[];
  startingEquity: number;
  endingEquity: number;
  maxEquity: number;
  minEquity: number;
}

export function parseEquityPoint(wire: WireEquityPoint): EquityPoint {
  return {
    time: Math.floor(new Date(wire.timestamp).getTime() / 1000),
    equity: parseFloat(wire.equity),
    drawdownPct: wire.drawdown_pct,
    tradeId: wire.trade_id_or_none,
    timestamp: wire.timestamp,
  };
}

export function parseEquityCurveResponse(
  wire: WireEquityCurveResponse,
): EquityCurveResponse {
  return {
    points: wire.points.map(parseEquityPoint),
    startingEquity: parseFloat(wire.starting_equity),
    endingEquity: parseFloat(wire.ending_equity),
    maxEquity: parseFloat(wire.max_equity),
    minEquity: parseFloat(wire.min_equity),
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Trade list
// ═══════════════════════════════════════════════════════════════════════

export interface WireTradeRecord {
  entry_marker_id: string;
  exit_marker_id: string | null;
  symbol: string;
  side: Side;
  /** ISO 8601 with tz offset. */
  entry_time: string;
  exit_time: string | null;
  entry_price: string;
  exit_price: string | null;
  qty: number;
  pnl: string | null;
  pnl_pct: number | null;
  duration_minutes: number | null;
  exit_reason: ExitReason | null;
}

export interface WireTradePagination {
  limit: number;
  offset: number;
  total: number;
}

export interface WireTradeListResponse {
  trades: WireTradeRecord[];
  pagination: WireTradePagination;
  mode: Mode;
}

export interface TradeRecord {
  entryMarkerId: string;
  exitMarkerId: string | null;
  symbol: string;
  side: Side;
  /** Epoch seconds (UTC). */
  entryTime: number;
  exitTime: number | null;
  entryPrice: number;
  exitPrice: number | null;
  qty: number;
  pnl: number | null;
  pnlPct: number | null;
  durationMinutes: number | null;
  exitReason: ExitReason | null;
  /** Echo of original ISO strings — kept for human-readable rendering. */
  entryTimeIso: string;
  exitTimeIso: string | null;
}

export interface TradePagination {
  limit: number;
  offset: number;
  total: number;
}

export interface TradeListResponse {
  trades: TradeRecord[];
  pagination: TradePagination;
  mode: Mode;
}

export function parseTradeRecord(wire: WireTradeRecord): TradeRecord {
  return {
    entryMarkerId: wire.entry_marker_id,
    exitMarkerId: wire.exit_marker_id,
    symbol: wire.symbol,
    side: wire.side,
    entryTime: Math.floor(new Date(wire.entry_time).getTime() / 1000),
    exitTime:
      wire.exit_time !== null
        ? Math.floor(new Date(wire.exit_time).getTime() / 1000)
        : null,
    entryPrice: parseFloat(wire.entry_price),
    exitPrice: wire.exit_price !== null ? parseFloat(wire.exit_price) : null,
    qty: wire.qty,
    pnl: wire.pnl !== null ? parseFloat(wire.pnl) : null,
    pnlPct: wire.pnl_pct,
    durationMinutes: wire.duration_minutes,
    exitReason: wire.exit_reason,
    entryTimeIso: wire.entry_time,
    exitTimeIso: wire.exit_time,
  };
}

export function parseTradeListResponse(
  wire: WireTradeListResponse,
): TradeListResponse {
  return {
    trades: wire.trades.map(parseTradeRecord),
    pagination: { ...wire.pagination },
    mode: wire.mode,
  };
}
