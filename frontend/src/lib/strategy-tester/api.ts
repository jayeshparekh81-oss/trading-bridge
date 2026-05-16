/**
 * Strategy-tester REST wrappers — thin typed shell over
 * :mod:`@/lib/api`.
 *
 * Endpoints (all under ``/api/strategy-tester``):
 *   GET /{strategy_id}/metrics  ?mode=...&from=...&to=...&starting_equity=...
 *   GET /{strategy_id}/equity   ?mode=...&starting_equity=...&from=...&to=...
 *   GET /{strategy_id}/trades   ?mode=...&from=...&to=...&symbol=...&limit=...&offset=...
 *
 * Auth is handled by the shared ``api`` client (JWT attach + 401
 * refresh). Ownership probes return 403 (collapsed with "doesn't
 * exist" for security) — caller surfaces as empty-state.
 *
 * URL builders separated from fetchers so tests can assert the exact
 * querystring without standing up a fetch mock.
 */

import { api } from "@/lib/api";

import type {
  Mode,
  WireEquityCurveResponse,
  WireStrategyTesterMetrics,
  WireTradeListResponse,
} from "./types";

// ═══════════════════════════════════════════════════════════════════════
// Shared query-param helpers
// ═══════════════════════════════════════════════════════════════════════

export interface CommonWindowOptions {
  /** ISO 8601 with tz offset. */
  fromIso?: string | null;
  /** ISO 8601 with tz offset. */
  toIso?: string | null;
}

function appendWindow(qs: URLSearchParams, opts: CommonWindowOptions): void {
  if (opts.fromIso) qs.set("from", opts.fromIso);
  if (opts.toIso) qs.set("to", opts.toIso);
}

// ═══════════════════════════════════════════════════════════════════════
// /metrics
// ═══════════════════════════════════════════════════════════════════════

export interface FetchMetricsOptions extends CommonWindowOptions {
  strategyId: string;
  mode: Mode;
  /** Default 100000 on backend; passing through only when caller cares. */
  startingEquity?: number | null;
}

export function buildMetricsUrl(opts: FetchMetricsOptions): string {
  const qs = new URLSearchParams({ mode: opts.mode });
  appendWindow(qs, opts);
  if (opts.startingEquity != null) {
    qs.set("starting_equity", String(opts.startingEquity));
  }
  return `/strategy-tester/${opts.strategyId}/metrics?${qs.toString()}`;
}

export async function fetchStrategyTesterMetrics(
  opts: FetchMetricsOptions,
): Promise<WireStrategyTesterMetrics> {
  return api.get<WireStrategyTesterMetrics>(buildMetricsUrl(opts));
}

// ═══════════════════════════════════════════════════════════════════════
// /equity
// ═══════════════════════════════════════════════════════════════════════

export interface FetchEquityOptions extends CommonWindowOptions {
  strategyId: string;
  mode: Mode;
  startingEquity?: number | null;
}

export function buildEquityUrl(opts: FetchEquityOptions): string {
  const qs = new URLSearchParams({ mode: opts.mode });
  if (opts.startingEquity != null) {
    qs.set("starting_equity", String(opts.startingEquity));
  }
  appendWindow(qs, opts);
  return `/strategy-tester/${opts.strategyId}/equity?${qs.toString()}`;
}

export async function fetchStrategyTesterEquity(
  opts: FetchEquityOptions,
): Promise<WireEquityCurveResponse> {
  return api.get<WireEquityCurveResponse>(buildEquityUrl(opts));
}

// ═══════════════════════════════════════════════════════════════════════
// /trades
// ═══════════════════════════════════════════════════════════════════════

export interface FetchTradesOptions extends CommonWindowOptions {
  strategyId: string;
  mode: Mode;
  symbol?: string | null;
  /** Backend default 100, max 500. */
  limit?: number | null;
  /** Backend default 0. */
  offset?: number | null;
}

export function buildTradesUrl(opts: FetchTradesOptions): string {
  const qs = new URLSearchParams({ mode: opts.mode });
  appendWindow(qs, opts);
  if (opts.symbol) qs.set("symbol", opts.symbol);
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  if (opts.offset != null) qs.set("offset", String(opts.offset));
  return `/strategy-tester/${opts.strategyId}/trades?${qs.toString()}`;
}

export async function fetchStrategyTesterTrades(
  opts: FetchTradesOptions,
): Promise<WireTradeListResponse> {
  return api.get<WireTradeListResponse>(buildTradesUrl(opts));
}
