/**
 * ChartWsTransport — direct-class tests covering the full lifecycle
 * without React, ``renderHook``, or jsdom-WebSocket interaction.
 *
 * The class accepts injected ``webSocketFactory`` + ``scheduler`` +
 * ``random`` so every effect that previously required real timers,
 * network, or React's effect machinery becomes a synchronous call.
 *
 * Test rig:
 *   - ``FakeWebSocket`` — replaces the global WS constructor. Tests
 *     drive ``triggerOpen()``, ``triggerMessage()``, ``triggerClose()``
 *     manually so the transport's onopen/onmessage/onclose paths run
 *     deterministically.
 *   - ``FakeScheduler`` — records pending timeouts/intervals. Tests
 *     fire them via ``firePendingTimeout()`` / ``fireInterval()`` to
 *     advance the state machine without real wall-clock time.
 *   - ``random`` is pinned to ``0.5`` (no jitter) in every test so the
 *     backoff math is exact.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ChartWsTransport,
  type ChartWsEvent,
  type TimerScheduler,
  type WebSocketFactory,
} from "@/lib/chart/chart_ws_transport";
import type {
  BrokerDisconnectedEnvelope,
  BrokerReconnectedEnvelope,
  CandleEnvelope,
  ConnectionStatus,
  HeartbeatEnvelope,
  WireCandle,
} from "@/lib/chart/types";

// ═══════════════════════════════════════════════════════════════════════
// Fake WebSocket
// ═══════════════════════════════════════════════════════════════════════

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  sentMessages: string[] = [];
  closeCalls = 0;
  /** Test hook: when true, ``close()`` throws. */
  throwOnClose = false;
  /** Test hook: when true, ``send()`` throws even with OPEN state. */
  throwOnSend = false;

  constructor(url: string) {
    this.url = url;
  }

  send(data: string): void {
    if (this.throwOnSend) throw new Error("synthetic send error");
    this.sentMessages.push(data);
  }

  close(): void {
    this.closeCalls += 1;
    this.readyState = FakeWebSocket.CLOSED;
    if (this.throwOnClose) throw new Error("synthetic close error");
  }

  // Test helpers
  triggerOpen(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }
  triggerMessage(data: string): void {
    this.onmessage?.({ data } as MessageEvent);
  }
  triggerClose(code = 1006): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code, reason: "" } as CloseEvent);
  }
  triggerError(): void {
    this.onerror?.(new Event("error"));
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Fake Scheduler
// ═══════════════════════════════════════════════════════════════════════

interface ScheduledTimer {
  id: number;
  handler: () => void;
  ms: number;
  kind: "timeout" | "interval";
  cleared: boolean;
}

class FakeScheduler implements TimerScheduler {
  private nextId = 1;
  public scheduled: ScheduledTimer[] = [];

  setTimeout = (handler: () => void, ms: number): unknown => {
    const t: ScheduledTimer = {
      id: this.nextId++,
      handler,
      ms,
      kind: "timeout",
      cleared: false,
    };
    this.scheduled.push(t);
    return t.id;
  };

  clearTimeout = (id: unknown): void => {
    const t = this.scheduled.find((s) => s.id === id);
    if (t) t.cleared = true;
  };

  setInterval = (handler: () => void, ms: number): unknown => {
    const t: ScheduledTimer = {
      id: this.nextId++,
      handler,
      ms,
      kind: "interval",
      cleared: false,
    };
    this.scheduled.push(t);
    return t.id;
  };

  clearInterval = (id: unknown): void => {
    this.clearTimeout(id);
  };

  pendingTimeouts(): ScheduledTimer[] {
    return this.scheduled.filter((s) => s.kind === "timeout" && !s.cleared);
  }

  pendingIntervals(): ScheduledTimer[] {
    return this.scheduled.filter((s) => s.kind === "interval" && !s.cleared);
  }

  firePendingTimeout(): void {
    const t = this.pendingTimeouts()[0];
    if (!t) throw new Error("no pending timeout");
    t.cleared = true;
    t.handler();
  }

  fireInterval(id: number): void {
    const t = this.scheduled.find((s) => s.id === id);
    if (!t || t.cleared) throw new Error(`no active interval with id ${id}`);
    t.handler();
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Rig
// ═══════════════════════════════════════════════════════════════════════

interface Rig {
  transport: ChartWsTransport;
  sockets: FakeWebSocket[];
  scheduler: FakeScheduler;
  events: ChartWsEvent[];
  subscribe: () => () => void;
}

function makeRig(opts: { useMock?: boolean; random?: () => number } = {}): Rig {
  const sockets: FakeWebSocket[] = [];
  const factory: WebSocketFactory = (url) => {
    const ws = new FakeWebSocket(url);
    sockets.push(ws);
    return ws as unknown as WebSocket;
  };
  const scheduler = new FakeScheduler();
  const transport = new ChartWsTransport({
    webSocketFactory: factory,
    scheduler,
    useMock: opts.useMock ?? false,
    random: opts.random ?? (() => 0.5),
  });
  const events: ChartWsEvent[] = [];
  const subscribe = () => transport.subscribe((e) => events.push(e));
  return { transport, sockets, scheduler, events, subscribe };
}

const NIFTY_PARAMS = {
  symbol: "NIFTY",
  timeframe: "5m" as const,
  token: "tok-A",
};

const sampleCandleEnvelope = (overrides: Partial<WireCandle> = {}): string => {
  const wire: WireCandle = {
    symbol: "NIFTY",
    timeframe: "5m",
    timestamp: "2026-05-11T09:15:00Z",
    open: "25000.00",
    high: "25100.00",
    low: "24950.00",
    close: "25050.00",
    volume: 12_345,
    ...overrides,
  };
  const env: CandleEnvelope = { event: "candle", data: wire };
  return JSON.stringify(env);
};

const disconnectedEnvelope = (): string => {
  const env: BrokerDisconnectedEnvelope = {
    event: "broker_disconnected",
    symbol: "NIFTY",
    reason: "Upstream Fyers feed down",
    failed_attempts: 7,
    since: "2026-05-11T09:20:00Z",
  };
  return JSON.stringify(env);
};

const reconnectedEnvelope = (): string => {
  const env: BrokerReconnectedEnvelope = {
    event: "broker_reconnected",
    symbol: "NIFTY",
    at: "2026-05-11T09:25:00Z",
  };
  return JSON.stringify(env);
};

const heartbeatEnvelope = (): string => {
  const env: HeartbeatEnvelope = {
    event: "heartbeat",
    at: "2026-05-11T09:15:30Z",
  };
  return JSON.stringify(env);
};

// ═══════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════

describe("ChartWsTransport — construction", () => {
  it("constructor accepts no options and applies all defaults", () => {
    const transport = new ChartWsTransport();
    expect(transport.getReconnectAttempt()).toBe(0);
    expect(transport.isSessionExpired()).toBe(false);
    expect(transport.getTokenVersion()).toBe(0);
    // ``close()`` on a transport that never opened must be a no-op.
    expect(() => transport.close()).not.toThrow();
  });
});

describe("ChartWsTransport — lifecycle", () => {
  it("open() emits connecting → open and constructs exactly one socket", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);

    expect(rig.sockets).toHaveLength(1);
    expect(rig.events.map(statusKindOf)).toEqual(["connecting"]);

    rig.sockets[0].triggerOpen();
    expect(rig.events.map(statusKindOf)).toEqual(["connecting", "open"]);
  });

  it("open() twice without close — second call is a no-op (no duplicate socket)", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    rig.transport.open(NIFTY_PARAMS, 1);
    expect(rig.sockets).toHaveLength(1);
  });

  it("close() is idempotent", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    rig.transport.close();
    rig.transport.close();

    expect(rig.sockets[0].closeCalls).toBe(1);
  });

  it("close() before open() is a silent no-op", () => {
    const rig = makeRig();
    expect(() => rig.transport.close()).not.toThrow();
    expect(rig.sockets).toHaveLength(0);
  });

  it("open() with null token does not construct a socket", () => {
    const rig = makeRig();
    rig.transport.open({ ...NIFTY_PARAMS, token: null }, 1);
    expect(rig.sockets).toHaveLength(0);
  });

  it("open() with an exception in the WebSocket factory schedules a retry", () => {
    const scheduler = new FakeScheduler();
    let calls = 0;
    const factory: WebSocketFactory = () => {
      calls += 1;
      throw new Error("synthetic factory failure");
    };
    const transport = new ChartWsTransport({
      webSocketFactory: factory,
      scheduler,
      useMock: false,
      random: () => 0.5,
    });
    transport.open(NIFTY_PARAMS, 1);

    expect(calls).toBe(1);
    expect(scheduler.pendingTimeouts()).toHaveLength(1);
    expect(scheduler.pendingTimeouts()[0].ms).toBe(1_000);
  });

  it("close() suppresses errors from socket.close() so cleanup never throws", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].throwOnClose = true;
    expect(() => rig.transport.close()).not.toThrow();
  });

  it("after close(), further open() / updateToken() are silent no-ops", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.transport.close();

    rig.transport.open(NIFTY_PARAMS, 2);
    rig.transport.updateToken("tok-B", 3);

    expect(rig.sockets).toHaveLength(1);
  });

  it("late onopen after close() defensively closes the orphaned socket", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.transport.close();
    expect(rig.sockets[0].closeCalls).toBe(1);
    rig.sockets[0].triggerOpen();
    expect(rig.sockets[0].closeCalls).toBe(2);
  });

  it("late onopen after close() suppresses errors from the defensive close", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.transport.close();
    rig.sockets[0].throwOnClose = true;
    expect(() => rig.sockets[0].triggerOpen()).not.toThrow();
  });

  it("late onmessage after close() is ignored", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.transport.close();
    const before = rig.events.length;
    rig.sockets[0].triggerMessage(disconnectedEnvelope());
    expect(rig.events.length).toBe(before);
  });
});

describe("ChartWsTransport — subscribe semantics", () => {
  it("subscribe before open() — handler receives the first status emit", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    expect(rig.events.map(statusKindOf)).toEqual(["connecting"]);
  });

  it("subscribe after open() — handler receives current status immediately, then live events", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen(); // last status now "open"

    const lateEvents: ChartWsEvent[] = [];
    rig.transport.subscribe((e) => lateEvents.push(e));
    // Replay-on-subscribe: late subscriber sees the current status.
    expect(lateEvents.map(statusKindOf)).toEqual(["open"]);

    rig.sockets[0].triggerMessage(disconnectedEnvelope());
    expect(lateEvents.map(statusKindOf)).toEqual(["open", "disconnected"]);
  });

  it("multiple subscribers — all receive the same events", () => {
    const rig = makeRig();
    const a: ChartWsEvent[] = [];
    const b: ChartWsEvent[] = [];
    rig.transport.subscribe((e) => a.push(e));
    rig.transport.subscribe((e) => b.push(e));

    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    expect(a.map(statusKindOf)).toEqual(["connecting", "open"]);
    expect(b.map(statusKindOf)).toEqual(["connecting", "open"]);
  });

  it("unsubscribe — handler stops receiving events", () => {
    const rig = makeRig();
    const captured: ChartWsEvent[] = [];
    const unsub = rig.transport.subscribe((e) => captured.push(e));
    rig.transport.open(NIFTY_PARAMS, 1);
    unsub();
    rig.sockets[0].triggerOpen();

    expect(captured.map(statusKindOf)).toEqual(["connecting"]);
  });

  it("unsubscribing one subscriber doesn't affect others", () => {
    const rig = makeRig();
    const a: ChartWsEvent[] = [];
    const b: ChartWsEvent[] = [];
    const unsubA = rig.transport.subscribe((e) => a.push(e));
    rig.transport.subscribe((e) => b.push(e));

    rig.transport.open(NIFTY_PARAMS, 1);
    unsubA();
    rig.sockets[0].triggerOpen();

    expect(a.map(statusKindOf)).toEqual(["connecting"]);
    expect(b.map(statusKindOf)).toEqual(["connecting", "open"]);
  });

  it("a subscriber throwing does not break the transport", () => {
    const rig = makeRig();
    rig.transport.subscribe(() => {
      throw new Error("synthetic subscriber failure");
    });
    const captured: ChartWsEvent[] = [];
    rig.transport.subscribe((e) => captured.push(e));

    expect(() => rig.transport.open(NIFTY_PARAMS, 1)).not.toThrow();
    expect(captured.map(statusKindOf)).toEqual(["connecting"]);
  });

  it("a late subscriber that throws on replay does not throw out of subscribe()", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    expect(() =>
      rig.transport.subscribe(() => {
        throw new Error("synthetic replay subscriber failure");
      }),
    ).not.toThrow();
  });
});

describe("ChartWsTransport — updateToken (R3)", () => {
  it("with new version: closes the current socket and opens a new one with the new token", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    rig.transport.updateToken("tok-B", 2);

    expect(rig.sockets[0].closeCalls).toBe(1);
    expect(rig.sockets).toHaveLength(2);
    expect(rig.sockets[1].url).toContain("tok-B");
    expect(rig.transport.getTokenVersion()).toBe(2);
  });

  it("with same version: no-op (no extra socket, no reconnect-counter reset)", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose(); // attempt counter = 1, pending timer scheduled
    expect(rig.transport.getReconnectAttempt()).toBe(1);

    rig.transport.updateToken("tok-A", 1);

    expect(rig.sockets).toHaveLength(1);
    expect(rig.transport.getReconnectAttempt()).toBe(1);
  });

  it("resets reconnectAttempt to 0", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose();
    expect(rig.transport.getReconnectAttempt()).toBe(1);

    rig.transport.updateToken("tok-B", 2);
    expect(rig.transport.getReconnectAttempt()).toBe(0);
  });

  it("mid-backoff: cancels the pending reconnect timer and opens immediately with the new token", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose();

    expect(rig.scheduler.pendingTimeouts()).toHaveLength(1);
    rig.transport.updateToken("tok-B", 2);

    expect(rig.scheduler.pendingTimeouts()).toHaveLength(0);
    expect(rig.sockets).toHaveLength(2);
    expect(rig.sockets[1].url).toContain("tok-B");
  });

  it("ignored before open()", () => {
    const rig = makeRig();
    rig.transport.updateToken("tok-B", 1);
    expect(rig.sockets).toHaveLength(0);
  });
});

describe("ChartWsTransport — reconnect / exp backoff", () => {
  it("onclose with non-fatal code schedules a backoff timer", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose(1006);

    expect(rig.scheduler.pendingTimeouts()).toHaveLength(1);
    expect(rig.transport.getReconnectAttempt()).toBe(1);
  });

  it("backoff sequence 1s/2s/4s/8s with zero jitter (random=0.5)", () => {
    const rig = makeRig({ random: () => 0.5 });
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    const expectedDelays = [1_000, 2_000, 4_000, 8_000];
    for (const [attemptIdx, expected] of expectedDelays.entries()) {
      const socket = rig.sockets[attemptIdx];
      socket.triggerClose(1006);
      const pending = rig.scheduler.pendingTimeouts();
      expect(pending).toHaveLength(1);
      expect(pending[0].ms).toBe(expected);
      rig.scheduler.firePendingTimeout();
      // Firing the timer constructs a new socket; advance to the next
      // iteration by triggering open then close on it.
      expect(rig.sockets).toHaveLength(attemptIdx + 2);
    }
  });

  it("successful reconnect resets the attempt counter to 0", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose(1006);
    expect(rig.transport.getReconnectAttempt()).toBe(1);

    rig.scheduler.firePendingTimeout();
    rig.sockets[1].triggerOpen();

    expect(rig.transport.getReconnectAttempt()).toBe(0);
  });

  it("close codes 4400 / 4401 do NOT trigger reconnect (auth / bad-params)", () => {
    for (const fatalCode of [4400, 4401]) {
      const rig = makeRig();
      const events: ChartWsEvent[] = [];
      rig.transport.subscribe((e) => events.push(e));
      rig.transport.open(NIFTY_PARAMS, 1);
      rig.sockets[0].triggerOpen();
      rig.sockets[0].triggerClose(fatalCode);

      expect(rig.scheduler.pendingTimeouts()).toHaveLength(0);
      const last = events[events.length - 1];
      expect(last.kind).toBe("status");
      expect((last as { status: ConnectionStatus }).status.kind).toBe(
        "disconnected",
      );
    }
  });

  it("jitter envelope: random=0 → 0.75x base, random=1 → 1.25x base", () => {
    const rigLow = makeRig({ random: () => 0 });
    rigLow.transport.open(NIFTY_PARAMS, 1);
    rigLow.sockets[0].triggerOpen();
    rigLow.sockets[0].triggerClose();
    expect(rigLow.scheduler.pendingTimeouts()[0].ms).toBeCloseTo(750, 0);

    const rigHigh = makeRig({ random: () => 1 });
    rigHigh.transport.open(NIFTY_PARAMS, 1);
    rigHigh.sockets[0].triggerOpen();
    rigHigh.sockets[0].triggerClose();
    expect(rigHigh.scheduler.pendingTimeouts()[0].ms).toBeCloseTo(1_250, 0);
  });

  it("backoff caps at 60s (attempt 7+)", () => {
    const rig = makeRig({ random: () => 0.5 });
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    for (let i = 0; i < 7; i++) {
      rig.sockets[i].triggerClose(1006);
      const ms = rig.scheduler.pendingTimeouts()[0].ms;
      if (i < 6) {
        expect(ms).toBeLessThanOrEqual(60_000);
        rig.scheduler.firePendingTimeout();
      } else {
        expect(ms).toBe(60_000);
      }
    }
  });

  it("heartbeat interval is scheduled on open and cleared on close", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    expect(rig.scheduler.pendingIntervals()).toHaveLength(0);
    rig.sockets[0].triggerOpen();
    expect(rig.scheduler.pendingIntervals()).toHaveLength(1);
    expect(rig.scheduler.pendingIntervals()[0].ms).toBe(20_000);

    rig.transport.close();
    expect(rig.scheduler.pendingIntervals()).toHaveLength(0);
  });

  it("heartbeat fires a ping while the socket is OPEN", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();

    const intervalId = rig.scheduler.pendingIntervals()[0].id;
    rig.scheduler.fireInterval(intervalId);
    expect(rig.sockets[0].sentMessages).toEqual(["ping"]);
  });

  it("heartbeat skips send when socket is no longer OPEN", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    const intervalId = rig.scheduler.pendingIntervals()[0].id;
    rig.sockets[0].readyState = FakeWebSocket.CLOSING;

    rig.scheduler.fireInterval(intervalId);
    expect(rig.sockets[0].sentMessages).toEqual([]);
  });

  it("heartbeat send error is suppressed (race during close)", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].throwOnSend = true;
    const intervalId = rig.scheduler.pendingIntervals()[0].id;
    expect(() => rig.scheduler.fireInterval(intervalId)).not.toThrow();
  });
});

describe("ChartWsTransport — sessionExpired guard (R1)", () => {
  it("setSessionExpired(true) clears a pending reconnect timer", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerClose();
    expect(rig.scheduler.pendingTimeouts()).toHaveLength(1);

    rig.transport.setSessionExpired(true);
    expect(rig.scheduler.pendingTimeouts()).toHaveLength(0);
    expect(rig.transport.isSessionExpired()).toBe(true);
  });

  it("onclose during sessionExpired=true → no reconnect scheduled", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.transport.setSessionExpired(true);
    rig.sockets[0].triggerClose();

    expect(rig.scheduler.pendingTimeouts()).toHaveLength(0);
    expect(rig.transport.getReconnectAttempt()).toBe(0);
  });

  it("setSessionExpired(false) re-enables reconnect on the next onclose", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.transport.setSessionExpired(true);
    rig.transport.setSessionExpired(false);
    rig.sockets[0].triggerClose();

    expect(rig.scheduler.pendingTimeouts()).toHaveLength(1);
  });

  it("open() while sessionExpired=true is a silent no-op (no socket constructed)", () => {
    const rig = makeRig();
    rig.transport.setSessionExpired(true);
    rig.transport.open(NIFTY_PARAMS, 1);
    expect(rig.sockets).toHaveLength(0);
  });

  it("updateToken() after setSessionExpired(false) opens a fresh socket with the new token", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.transport.setSessionExpired(true);
    rig.transport.setSessionExpired(false);
    rig.transport.updateToken("tok-B", 2);

    expect(rig.sockets).toHaveLength(2);
    expect(rig.sockets[1].url).toContain("tok-B");
  });
});

describe("ChartWsTransport — broker events", () => {
  it("broker_disconnected frame → status event with reason / since / failed_attempts", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerMessage(disconnectedEnvelope());

    const last = rig.events[rig.events.length - 1];
    expect(last.kind).toBe("status");
    if (last.kind === "status" && last.status.kind === "disconnected") {
      expect(last.status.reason).toBe("Upstream Fyers feed down");
      expect(last.status.failed_attempts).toBe(7);
      expect(last.status.since).toBe("2026-05-11T09:20:00Z");
    } else {
      throw new Error("expected a disconnected-status event");
    }
  });

  it("broker_reconnected frame → status event back to open", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerMessage(disconnectedEnvelope());
    rig.sockets[0].triggerMessage(reconnectedEnvelope());

    const last = rig.events[rig.events.length - 1];
    expect(last.kind).toBe("status");
    expect(
      last.kind === "status" ? last.status.kind : undefined,
    ).toBe("open");
  });

  it("candle frame → candle event with parsed numeric OHLC", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    rig.sockets[0].triggerMessage(sampleCandleEnvelope());

    const candleEvt = rig.events.find((e) => e.kind === "candle");
    expect(candleEvt).toBeDefined();
    if (candleEvt && candleEvt.kind === "candle") {
      expect(candleEvt.candle.symbol).toBe("NIFTY");
      expect(candleEvt.candle.open).toBe(25_000);
      expect(candleEvt.candle.high).toBe(25_100);
      expect(typeof candleEvt.candle.time).toBe("number");
    }
  });

  it("heartbeat frame is a no-op (does not emit)", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    const before = rig.events.length;
    rig.subscribe(); // re-subscribe so we only capture future events
    const subscribedAt = rig.events.length;
    rig.sockets[0].triggerMessage(heartbeatEnvelope());
    expect(rig.events.length).toBe(subscribedAt);
    expect(subscribedAt).toBeGreaterThanOrEqual(before);
  });

  it("non-JSON frame is dropped silently", () => {
    const rig = makeRig();
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    const before = rig.events.length;
    expect(() => rig.sockets[0].triggerMessage("not json {")).not.toThrow();
    expect(rig.events.length).toBe(before);
  });

  it("onerror fires without crashing (close-handler does the reconnect work)", () => {
    const rig = makeRig();
    rig.transport.open(NIFTY_PARAMS, 1);
    rig.sockets[0].triggerOpen();
    expect(() => rig.sockets[0].triggerError()).not.toThrow();
  });
});

describe("ChartWsTransport — URL construction", () => {
  it("the constructed WS URL contains the symbol, timeframe, and URL-encoded token", () => {
    const rig = makeRig();
    rig.transport.open({ symbol: "NIFTY", timeframe: "5m", token: "a/b+c" }, 1);
    const url = rig.sockets[0].url;
    expect(url).toContain("NIFTY");
    expect(url).toContain("5m");
    // ``a/b+c`` URL-encodes to ``a%2Fb%2Bc`` via encodeURIComponent.
    expect(url).toContain("a%2Fb%2Bc");
  });
});

describe("ChartWsTransport — mock mode (R6)", () => {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  let restoreEnv: () => void;

  beforeEach(() => {
    // The mock server uses real ``setInterval`` internally — we hold
    // it alive only as long as the test body runs. ``close()`` in
    // each test stops it.
    const prev = (process.env as any).NEXT_PUBLIC_USE_MOCK;
    restoreEnv = () => {
      (process.env as any).NEXT_PUBLIC_USE_MOCK = prev;
    };
  });

  afterEach(() => {
    restoreEnv();
    vi.restoreAllMocks();
  });

  it("open() in mock mode skips the real WS factory and emits open immediately", () => {
    const rig = makeRig({ useMock: true });
    rig.subscribe();
    rig.transport.open(NIFTY_PARAMS, 1);

    expect(rig.sockets).toHaveLength(0);
    const kinds = rig.events.map(statusKindOf);
    expect(kinds).toEqual(["connecting", "open"]);

    rig.transport.close();
  });

  it("close() in mock mode stops the mock server cleanly", () => {
    const rig = makeRig({ useMock: true });
    rig.transport.open(NIFTY_PARAMS, 1);
    expect(() => rig.transport.close()).not.toThrow();
  });
  /* eslint-enable @typescript-eslint/no-explicit-any */
});

describe("ChartWsTransport — default scheduler (real timers)", () => {
  it("uses real setInterval for heartbeat when no scheduler is injected", () => {
    vi.useFakeTimers();
    try {
      const sockets: FakeWebSocket[] = [];
      const factory: WebSocketFactory = (url) => {
        const ws = new FakeWebSocket(url);
        sockets.push(ws);
        return ws as unknown as WebSocket;
      };
      const transport = new ChartWsTransport({
        webSocketFactory: factory,
        useMock: false,
        random: () => 0.5,
      });
      transport.open(NIFTY_PARAMS, 1);
      sockets[0].triggerOpen();

      vi.advanceTimersByTime(20_000);
      expect(sockets[0].sentMessages).toContain("ping");

      transport.close();
    } finally {
      vi.useRealTimers();
    }
  });

  it("uses real setTimeout for reconnect backoff when no scheduler is injected", () => {
    vi.useFakeTimers();
    try {
      const sockets: FakeWebSocket[] = [];
      const factory: WebSocketFactory = (url) => {
        const ws = new FakeWebSocket(url);
        sockets.push(ws);
        return ws as unknown as WebSocket;
      };
      const transport = new ChartWsTransport({
        webSocketFactory: factory,
        useMock: false,
        random: () => 0.5,
      });
      transport.open(NIFTY_PARAMS, 1);
      sockets[0].triggerOpen();
      sockets[0].triggerClose(1006);

      vi.advanceTimersByTime(1_500);
      expect(sockets).toHaveLength(2);

      transport.close();
    } finally {
      vi.useRealTimers();
    }
  });

  it("default scheduler clearTimeout is invoked on close() with a pending backoff", () => {
    vi.useFakeTimers();
    try {
      const sockets: FakeWebSocket[] = [];
      const factory: WebSocketFactory = (url) => {
        const ws = new FakeWebSocket(url);
        sockets.push(ws);
        return ws as unknown as WebSocket;
      };
      const transport = new ChartWsTransport({
        webSocketFactory: factory,
        useMock: false,
        random: () => 0.5,
      });
      transport.open(NIFTY_PARAMS, 1);
      sockets[0].triggerOpen();
      sockets[0].triggerClose(1006);
      // Backoff timer is pending on the REAL setTimeout. close()
      // must run it through the default scheduler's clearTimeout.
      transport.close();
      vi.advanceTimersByTime(10_000);
      expect(sockets).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

function statusKindOf(event: ChartWsEvent): string {
  return event.kind === "status" ? event.status.kind : event.kind;
}
