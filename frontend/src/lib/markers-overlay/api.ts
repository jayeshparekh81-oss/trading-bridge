/**
 * Phase E — Trade-markers REST wrappers (thin typed shell over
 * :mod:`@/lib/api`).
 *
 * Endpoint:
 *   GET /api/markers
 *     ?strategy_id=<uuid>  (required)
 *     &mode=BACKTEST|PAPER|LIVE  (required)
 *     &from=<iso8601>      (optional, tz-aware)
 *     &to=<iso8601>        (optional, tz-aware)
 *     &symbol=<str>        (optional)
 *     &side=<MarkerSide>   (optional)
 *     &limit=<1..500>      (default 100)
 *     &offset=<int>        (default 0)
 *
 * Auth + 401 refresh are handled by the shared ``api`` client. Strategy
 * ownership is enforced server-side — non-owners + missing-strategies
 * collapse to a single 403. Caller decides whether to surface that as
 * empty state or an error banner.
 *
 * URL builder kept separate from the fetcher so tests can assert the
 * exact querystring without standing up a fetch mock — same pattern
 * as ``@/lib/strategy-tester/api``.
 */

import { api } from "@/lib/api";

import type {
  MarkerMode,
  MarkerSide,
  WireTradeMarkerListResponse,
} from "./types";

// ═══════════════════════════════════════════════════════════════════════
// /api/markers — list
// ═══════════════════════════════════════════════════════════════════════

export interface FetchMarkersOptions {
  strategyId: string;
  mode: MarkerMode;
  /** ISO 8601 with tz offset (inclusive). */
  fromIso?: string | null;
  /** ISO 8601 with tz offset (inclusive). */
  toIso?: string | null;
  symbol?: string | null;
  side?: MarkerSide | null;
  /** Backend default 100, max 500. */
  limit?: number | null;
  /** Backend default 0. */
  offset?: number | null;
}

export function buildMarkersUrl(opts: FetchMarkersOptions): string {
  const qs = new URLSearchParams({
    strategy_id: opts.strategyId,
    mode: opts.mode,
  });
  if (opts.fromIso) qs.set("from", opts.fromIso);
  if (opts.toIso) qs.set("to", opts.toIso);
  if (opts.symbol) qs.set("symbol", opts.symbol);
  if (opts.side) qs.set("side", opts.side);
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  if (opts.offset != null) qs.set("offset", String(opts.offset));
  return `/markers?${qs.toString()}`;
}

export async function fetchMarkers(
  opts: FetchMarkersOptions,
): Promise<WireTradeMarkerListResponse> {
  return api.get<WireTradeMarkerListResponse>(buildMarkersUrl(opts));
}
