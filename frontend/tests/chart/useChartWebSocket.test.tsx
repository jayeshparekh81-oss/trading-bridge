/**
 * useChartWebSocket — Day-5 unit-test surface.
 *
 * Day-5 scope: pure-function-only tests, no hook rendering.
 *
 * Rendering the hook in jsdom inevitably collides with three things
 * that don't compose cleanly:
 *
 *   1. The reset-on-seed-change effect must run on every render
 *      (orchestrator passes a fresh array reference on every parent
 *      re-render). The mitigation (ref-based compare instead of dep
 *      array) is now in source.
 *   2. Native WebSocket isn't available in jsdom; a fake's
 *      construction sometimes drives the hook's connect→close→
 *      schedule-reconnect loop into a heap-exhausting fork.
 *   3. ``vi.useFakeTimers()`` interacts poorly with
 *      ``@testing-library/react``'s asynchronous rendering, leaving
 *      microtask queues that drain only after the worker is killed.
 *
 * The end-to-end behaviour (open / message / reconnect / heartbeat /
 * disconnect overlay) will be verified by the operator smoke test
 * against the real backend tomorrow morning. PATCH_INSTRUCTIONS_FRONTEND.md
 * flags this gap + a Day-4 polish task to add msw-based ws-mock tests
 * once the smoke test surfaces the actual contract corner cases.
 */

import { describe, expect, it } from "vitest";

import { reconnectDelayMs } from "@/hooks/useChartWebSocket";

describe("reconnectDelayMs — exp backoff math mirrors backend", () => {
  it("returns 0 for attempt 0 or negative", () => {
    expect(reconnectDelayMs(0)).toBe(0);
    expect(reconnectDelayMs(-1)).toBe(0);
  });

  it.each([
    [1, 1_000],
    [2, 2_000],
    [3, 4_000],
    [4, 8_000],
    [5, 16_000],
    [6, 32_000],
    [7, 60_000], // capped
    [42, 60_000], // capped indefinitely past attempt 7
  ])(
    "attempt %d produces base %dms within ±25%% jitter envelope",
    (attempt, base) => {
      const min = base * 0.75;
      const max = base * 1.25;
      // Probe min-jitter (random=0 → negative arm) and max-jitter
      // (random=1 → positive arm).
      expect(reconnectDelayMs(attempt, () => 0)).toBeGreaterThanOrEqual(
        min - 0.01,
      );
      expect(reconnectDelayMs(attempt, () => 1)).toBeLessThanOrEqual(
        max + 0.01,
      );
    },
  );

  it("never returns a negative delay even at worst-case jitter floor", () => {
    expect(reconnectDelayMs(1, () => 0)).toBeGreaterThanOrEqual(0);
    expect(reconnectDelayMs(7, () => 0)).toBeGreaterThanOrEqual(0);
  });

  it("randomness source is injectable for determinism", () => {
    // Pinning random to 0.5 → no jitter.
    expect(reconnectDelayMs(3, () => 0.5)).toBe(4_000);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Day-4 A1 — coverage gap acknowledgement
// ═══════════════════════════════════════════════════════════════════════
//
// Four distinct test approaches were attempted for the WS lifecycle:
//   1. Day-5: hand-rolled fake-WebSocket, fork-pool — heap OOM (the
//      ``initialCandles`` dep-loop bug, since fixed in commit 9714232).
//   2. Day-4 attempt 1: msw/ws via setupServer — heap OOM at module
//      import (msw's polyfill + this hook's reconnect handler).
//   3. Day-4 attempt 2: hand-rolled fake-WebSocket v2 (post seed-loop
//      fix) — heap OOM at module import despite the fix.
//   4. Day-4 attempt 3: WebSocket-constructor SPY only (no
//      onopen/onclose handling, ``sessionExpired=true`` so no
//      construction expected) — heap OOM at module import.
//
// The pathological interaction is between vitest's worker-pool
// (forks AND threads both OOM), jsdom, ``renderHook``, and the
// ``useChartWebSocket`` effect lifecycle. All four attempts crash
// BEFORE any test body executes (``Tests (N) Duration ... tests 0ms``),
// pointing at import-time/module-level cost rather than test logic.
//
// R1 sessionExpired guard is implemented in source (see hook
// ``connect()`` + ``scheduleReconnect()`` guards). Verification path:
//   - Compile-time: TypeScript enforces the new ``sessionExpired``
//     prop on every consumer (ChartContainer wired in this branch).
//   - Runtime: manual smoke scenario A (``docs/chart_fe_manual_smoke.md``)
//     covers the end-to-end token-refresh-fails-twice → banner appears
//     → no WS retry storm path with a real backend + browser.
//
// Coverage threshold for ``src/hooks/useChartWebSocket.ts`` will NOT
// hit the 96% target tonight as a result. Day-4 PATCH file documents
// this gap + the Phase-2 mitigation (e.g. extract the lifecycle into
// an injectable transport layer that can be unit-tested without
// renderHook).
