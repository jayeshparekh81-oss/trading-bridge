/**
 * Day-5 mock data for the chart UI.
 *
 * Activated by setting ``NEXT_PUBLIC_USE_MOCK=true`` in
 * ``.env.local``. Two surfaces:
 *
 *   1. :func:`getMockHistory` — deterministic 200-candle response
 *      shaped exactly like ``GET /api/chart/history`` returns. Used
 *      until the backend smoke test is green tomorrow morning.
 *   2. :func:`createMockWsServer` — in-memory event emitter that
 *      pushes one new candle every ``tickIntervalMs`` (default
 *      ~5 seconds). Used by :mod:`useChartWebSocket` when the same
 *      env flag is on, so the live-tick pipeline can be exercised
 *      end-to-end without a backend.
 *
 * Both helpers produce data shaped after the Pydantic schemas in
 * ``app/schemas/candle.py`` — wire-Candle uses string OHLC values
 * matching the backend's Decimal-as-JSON convention.
 */

import type {
  ChartEnvelope,
  ChartHistoryResponse,
  Timeframe,
  WireCandle,
} from "./types";

// ═══════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════

const DEFAULT_FIXTURE_LENGTH = 200;
const DEFAULT_BASE_PRICE = 22500.0;
const DEFAULT_DRIFT_PER_BAR = 0.5;
const DEFAULT_NOISE_AMPLITUDE = 25.0;

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
// Deterministic LCG — same algorithm the backend tests use, so the
// numbers a developer sees in mock mode line up with the Python tests.
// ═══════════════════════════════════════════════════════════════════════

function makeLcg(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    // Numerical Recipes constants — bit-identical with the backend
    // ``synthesise_candles`` helper.
    state = (Math.imul(1_664_525, state) + 1_013_904_223) >>> 0;
    return state / 0xffff_ffff;
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Generator
// ═══════════════════════════════════════════════════════════════════════

interface GenerateOptions {
  symbol: string;
  timeframe: Timeframe;
  length?: number;
  basePrice?: number;
  driftPerBar?: number;
  noiseAmplitude?: number;
  /** Bar-open time of the FIRST candle in the series (epoch seconds, UTC). */
  startEpochSeconds?: number;
  seed?: number;
}

export function generateCandles(opts: GenerateOptions): WireCandle[] {
  const length = opts.length ?? DEFAULT_FIXTURE_LENGTH;
  const base = opts.basePrice ?? DEFAULT_BASE_PRICE;
  const drift = opts.driftPerBar ?? DEFAULT_DRIFT_PER_BAR;
  const noise = opts.noiseAmplitude ?? DEFAULT_NOISE_AMPLITUDE;
  const seed = opts.seed ?? 42;
  const tfSeconds = TIMEFRAME_SECONDS[opts.timeframe];
  const start =
    opts.startEpochSeconds ??
    Math.floor(Date.UTC(2026, 0, 15, 3, 45) / 1000); // 09:15 IST 2026-01-15

  const rng = makeLcg(seed);
  const out: WireCandle[] = [];

  for (let i = 0; i < length; i++) {
    const r = rng() - 0.5;
    const noisePart = r * 2.0 * noise;
    const cyclePart = Math.sin(i / 7.0) * (noise * 0.4);
    const close = base + drift * i + noisePart + cyclePart;
    const open = close - noisePart * 0.3;
    const high = Math.max(open, close) + Math.abs(noisePart) * 0.5 + 0.01;
    const low = Math.min(open, close) - Math.abs(noisePart) * 0.5 - 0.01;

    out.push({
      symbol: opts.symbol.toUpperCase(),
      timeframe: opts.timeframe,
      timestamp: new Date((start + tfSeconds * i) * 1000).toISOString(),
      open: open.toFixed(4),
      high: high.toFixed(4),
      low: low.toFixed(4),
      close: close.toFixed(4),
      volume: 10_000 + Math.floor(rng() * 50_000),
    });
  }
  return out;
}

// ═══════════════════════════════════════════════════════════════════════
// Mock REST endpoint
// ═══════════════════════════════════════════════════════════════════════

export interface MockHistoryOptions {
  symbol: string;
  timeframe: Timeframe;
  length?: number;
}

export function getMockHistory(
  opts: MockHistoryOptions,
): ChartHistoryResponse {
  const length = opts.length ?? DEFAULT_FIXTURE_LENGTH;
  // C11: anchor the series END to the current timeframe bucket so the
  // mock history lands at "now-ish". The mock WS server's default
  // ``nextEpoch`` rolls to the NEXT bucket after "now", so the first
  // live tick is contiguous with the last history candle — no visible
  // time gap on the chart. (generateCandles itself stays
  // deterministic on the seed; only the start anchor moves.)
  const tfSeconds = TIMEFRAME_SECONDS[opts.timeframe];
  const nowSec = Math.floor(Date.now() / 1000);
  const currentBucket = nowSec - (nowSec % tfSeconds);
  const startEpochSeconds = currentBucket - (length - 1) * tfSeconds;

  const candles = generateCandles({
    symbol: opts.symbol,
    timeframe: opts.timeframe,
    length,
    startEpochSeconds,
  });
  const from = candles[0]?.timestamp ?? new Date().toISOString();
  const to = candles[candles.length - 1]?.timestamp ?? from;
  return {
    symbol: opts.symbol.toUpperCase(),
    timeframe: opts.timeframe,
    from_ts: from,
    to_ts: to,
    cached: false,
    candles,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Mock WS server — in-memory event emitter
// ═══════════════════════════════════════════════════════════════════════
//
// Behaviour:
//   * On ``start()``, pushes a CANDLE envelope every ``tickIntervalMs``.
//   * Each tick is the next chronological bar after the seed series.
//   * ``stop()`` clears the interval.
//   * ``onMessage(handler)`` registers exactly one handler; calling
//     again replaces it (mirrors the single-handler shape of the
//     WebSocket API's ``onmessage`` property).
//
// The mock does NOT simulate ``broker_disconnected`` /
// ``broker_reconnected`` for v1 — operator can manually invoke them
// via ``emitDisconnected()`` / ``emitReconnected()`` in dev tools if
// the disconnect UI needs exercising.

export interface MockWsServerOptions {
  symbol: string;
  timeframe: Timeframe;
  /** How often to push a new candle. Default 5000 ms. */
  tickIntervalMs?: number;
  /** Starting epoch second for the *next* candle after seed. */
  seedEndEpochSeconds?: number;
}

export interface MockWsServer {
  start: () => void;
  stop: () => void;
  onMessage: (handler: (env: ChartEnvelope) => void) => void;
  emitDisconnected: (reason?: string) => void;
  emitReconnected: () => void;
}

export function createMockWsServer(opts: MockWsServerOptions): MockWsServer {
  const tickMs = opts.tickIntervalMs ?? 5_000;
  const tfSeconds = TIMEFRAME_SECONDS[opts.timeframe];

  let handler: ((env: ChartEnvelope) => void) | null = null;
  let intervalId: ReturnType<typeof setInterval> | null = null;
  let nextEpoch =
    opts.seedEndEpochSeconds ?? Math.floor(Date.now() / 1000);
  // Roll the cursor onto the next timeframe boundary so the first emitted
  // candle aligns with a clean bucket boundary (not mid-bar).
  nextEpoch += tfSeconds - (nextEpoch % tfSeconds);
  let cursor = 0;
  const rngSeed = 4242;

  function emitNextCandle() {
    if (!handler) return;
    const [wire] = generateCandles({
      symbol: opts.symbol,
      timeframe: opts.timeframe,
      length: 1,
      startEpochSeconds: nextEpoch,
      seed: rngSeed + cursor,
    });
    cursor += 1;
    nextEpoch += tfSeconds;
    handler({ event: "candle", data: wire });
  }

  return {
    start() {
      if (intervalId !== null) return; // idempotent
      intervalId = setInterval(emitNextCandle, tickMs);
    },
    stop() {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    },
    onMessage(h) {
      handler = h;
    },
    emitDisconnected(reason = "mock disconnect") {
      if (!handler) return;
      handler({
        event: "broker_disconnected",
        symbol: opts.symbol.toUpperCase(),
        reason,
        failed_attempts: 1,
        since: new Date().toISOString(),
      });
    },
    emitReconnected() {
      if (!handler) return;
      handler({
        event: "broker_reconnected",
        symbol: opts.symbol.toUpperCase(),
        at: new Date().toISOString(),
      });
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Env-toggle helper
// ═══════════════════════════════════════════════════════════════════════

export function isMockEnabled(): boolean {
  if (typeof process === "undefined") return false;
  return process.env.NEXT_PUBLIC_USE_MOCK === "true";
}
