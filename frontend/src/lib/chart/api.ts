/**
 * Chart REST wrappers — thin typed shell over the existing
 * :mod:`@/lib/api` client.
 *
 * The shared ``api`` object handles:
 *   - JWT attachment from ``localStorage`` (``tb_access_token``).
 *   - 401 → automatic refresh via ``/api/auth/refresh``.
 *   - ``ApiError`` wrapping for non-2xx responses.
 *
 * We add chart-specific typing + the ``NEXT_PUBLIC_USE_MOCK`` toggle
 * that short-circuits to the mock fixture during Day-5 development.
 */

import { api } from "@/lib/api";

import { getMockHistory, isMockEnabled } from "./mock_data";
import type {
  ChartHistoryResponse,
  Exchange,
  Timeframe,
  WsTokenResponse,
} from "./types";

// ═══════════════════════════════════════════════════════════════════════
// /api/chart/history
// ═══════════════════════════════════════════════════════════════════════

export interface FetchHistoryOptions {
  symbol: string;
  exchange: Exchange;
  timeframe: Timeframe;
  /** ISO 8601 datetime string with tz offset. */
  from: string;
  /** ISO 8601 datetime string with tz offset. */
  to: string;
  /** Override the env-based mock toggle (test injection point). */
  forceMock?: boolean;
}

export async function fetchChartHistory(
  opts: FetchHistoryOptions,
): Promise<ChartHistoryResponse> {
  if (opts.forceMock ?? isMockEnabled()) {
    return Promise.resolve(
      getMockHistory({ symbol: opts.symbol, timeframe: opts.timeframe }),
    );
  }
  const qs = new URLSearchParams({
    symbol: opts.symbol,
    exchange: opts.exchange,
    timeframe: opts.timeframe,
    from: opts.from,
    to: opts.to,
  });
  return api.get<ChartHistoryResponse>(`/chart/history?${qs.toString()}`);
}

// ═══════════════════════════════════════════════════════════════════════
// /api/chart/ws-token
// ═══════════════════════════════════════════════════════════════════════

/**
 * Issues a fresh 15-min JWT for the live WebSocket connection. Mock
 * mode returns a static placeholder string — the mock WS server
 * ignores the token anyway.
 */
export async function fetchWsToken(
  opts: { forceMock?: boolean } = {},
): Promise<WsTokenResponse> {
  if (opts.forceMock ?? isMockEnabled()) {
    return Promise.resolve({
      token: "mock-ws-token",
      expires_in: 900,
    });
  }
  return api.get<WsTokenResponse>("/chart/ws-token");
}

// ═══════════════════════════════════════════════════════════════════════
// WS URL construction
// ═══════════════════════════════════════════════════════════════════════

/**
 * Build the absolute ``wss://`` URL for the chart WebSocket route.
 *
 * The HTTP base lives in ``NEXT_PUBLIC_API_URL`` (or relative). We
 * derive the WS host by replacing the scheme — ``http`` → ``ws``,
 * ``https`` → ``wss``. If the API URL is relative, we use the current
 * page origin.
 */
export function buildChartWsUrl(opts: {
  symbol: string;
  timeframe: Timeframe;
  token: string;
}): string {
  const apiBase =
    process.env.NEXT_PUBLIC_API_URL ??
    (typeof window !== "undefined" ? window.location.origin : "");
  const wsBase = apiBase.replace(/^http/i, "ws");
  const symbol = encodeURIComponent(opts.symbol.toUpperCase());
  const tf = encodeURIComponent(opts.timeframe);
  const token = encodeURIComponent(opts.token);
  return `${wsBase}/ws/chart/${symbol}/${tf}?token=${token}`;
}
