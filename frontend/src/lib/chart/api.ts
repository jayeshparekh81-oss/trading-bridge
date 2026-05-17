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

import {
  getMockHistory,
  getMockMarkers,
  getMockOlderHistory,
  isMockEnabled,
} from "./mock_data";
import type {
  ChartHistoryResponse,
  ChartMarkersResponse,
  Exchange,
  Timeframe,
  WsTokenResponse,
} from "./types";

// Timeframe→seconds duplicated here so the older-history API can
// translate ``beforeEpochSeconds`` + ``barCount`` into the (from, to)
// the backend route expects, without dragging mock_data into the
// hot path of every history fetch.
const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  "1m": 60,
  "3m": 180,
  "5m": 300,
  "15m": 900,
  "30m": 1_800,
  "1h": 3_600,
  "1d": 86_400,
};

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
// Phase 5 — older-history fetch for scroll-back lazy loading
// ═══════════════════════════════════════════════════════════════════════

export interface FetchOlderHistoryOptions {
  symbol: string;
  exchange: Exchange;
  timeframe: Timeframe;
  /** Inclusive epoch (seconds). The response carries bars STRICTLY
   *  older than this — ``response.candles[length-1].time +
   *  tfSeconds === beforeEpochSeconds`` so the prepend boundary is
   *  contiguous with no overlap on the chart. */
  beforeEpochSeconds: number;
  /** How many bars to fetch. Default 200, matching the initial
   *  history window so memory usage scales linearly with scroll. */
  barCount?: number;
  /** Test-injection override of the env-based mock toggle. */
  forceMock?: boolean;
}

export async function fetchOlderHistory(
  opts: FetchOlderHistoryOptions,
): Promise<ChartHistoryResponse> {
  const length = opts.barCount ?? 200;
  if (opts.forceMock ?? isMockEnabled()) {
    return Promise.resolve(
      getMockOlderHistory({
        symbol: opts.symbol,
        timeframe: opts.timeframe,
        beforeEpochSeconds: opts.beforeEpochSeconds,
        length,
      }),
    );
  }
  const tfSeconds = TIMEFRAME_SECONDS[opts.timeframe];
  const toEpoch = opts.beforeEpochSeconds - tfSeconds;
  const fromEpoch = toEpoch - tfSeconds * (length - 1);
  const qs = new URLSearchParams({
    symbol: opts.symbol,
    exchange: opts.exchange,
    timeframe: opts.timeframe,
    from: new Date(fromEpoch * 1_000).toISOString(),
    to: new Date(toEpoch * 1_000).toISOString(),
  });
  return api.get<ChartHistoryResponse>(`/chart/history?${qs.toString()}`);
}

// ═══════════════════════════════════════════════════════════════════════
// Phase 7 — /api/chart/markers (Day 3 prep, route currently
// UNREGISTERED in main.py; mock mode is the only working path until
// Day-3 dispatch — see PATCH_INSTRUCTIONS_FRONTEND_DAY3.md).
// ═══════════════════════════════════════════════════════════════════════

export interface FetchChartMarkersOptions {
  /** UUID of the strategy whose paper-trading markers to fetch. */
  strategyId: string;
  symbol: string;
  timeframe: Timeframe;
  /** ISO 8601 with tz offset (inclusive). */
  fromIso: string;
  /** ISO 8601 with tz offset (inclusive). */
  toIso: string;
  /** Test-injection override of the env-based mock toggle. */
  forceMock?: boolean;
}

export async function fetchChartMarkers(
  opts: FetchChartMarkersOptions,
): Promise<ChartMarkersResponse> {
  if (opts.forceMock ?? isMockEnabled()) {
    return Promise.resolve(
      getMockMarkers({
        strategyId: opts.strategyId,
        symbol: opts.symbol,
        timeframe: opts.timeframe,
        fromIso: opts.fromIso,
        toIso: opts.toIso,
      }),
    );
  }
  const qs = new URLSearchParams({
    strategy_id: opts.strategyId,
    symbol: opts.symbol,
    timeframe: opts.timeframe,
    from: opts.fromIso,
    to: opts.toIso,
  });
  return api.get<ChartMarkersResponse>(`/chart/markers?${qs.toString()}`);
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
  // Hotfix 2026-05-17: hardcoded production fallback. NEXT_PUBLIC_API_URL
  // env var still takes precedence when set (?? short-circuits on the
  // first non-nullish operand) — this only changes what happens when
  // the env var is undefined at build time, which has been happening
  // intermittently on Vercel's NEXT_PUBLIC_* bake. The previous fallback
  // (window.location.origin) produced wss://tradetri.com/ws/... which
  // Vercel doesn't proxy. See WS_URL_FIX_DIAGNOSIS.md at repo root for
  // the full investigation.
  const apiBase =
    process.env.NEXT_PUBLIC_API_URL ?? "https://api.tradetri.com";
  const wsBase = apiBase.replace(/^http/i, "ws");
  const symbol = encodeURIComponent(opts.symbol.toUpperCase());
  const tf = encodeURIComponent(opts.timeframe);
  const token = encodeURIComponent(opts.token);
  return `${wsBase}/ws/chart/${symbol}/${tf}?token=${token}`;
}
