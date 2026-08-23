/**
 * MOCK signal fixtures for the Phase-1a signal-feed UI.
 *
 * ⚠️ MOCK ONLY — there is NO backend signal-feed or confirm endpoint yet
 * (Phase-1 audit: `/signals` is owner-scoped; the subscriber feed + the
 * one-click confirm endpoint + a server-enforced validity field are all
 * separate, gated BACKEND tasks). This file exists so the UI can be built and
 * QA'd with ZERO chance of firing a real order. When the backend lands, delete
 * this file and swap the page's `MOCK_SIGNALS` for a `useApi` fetch of the same
 * shape (see the swap note in `signals/page.tsx`).
 *
 * The shape here is the eventual API contract, chosen to match the backend's
 * StrategySignal fields + the marketplace listing name:
 *   id, strategyName, symbol, side, entry, sl, target, received_at, status.
 */

export type SignalSide = "ENTRY" | "EXIT";

/** Subscriber-facing pending-signal status (eventual backend contract). */
export type MockSignalStatus = "pending" | "confirmed" | "expired";

export interface MockSignal {
  id: string;
  /** Marketplace listing / strategy display name (never the real strategy id). */
  strategyName: string;
  symbol: string;
  side: SignalSide;
  /** Prices are strings to match the backend's Decimal-as-string serialization. */
  entry: string | null;
  sl: string | null;
  target: string | null;
  /** ISO timestamp the signal was received — validity is COMPUTED from this. */
  received_at: string;
  status: MockSignalStatus;
}

/**
 * Marks everything on the page as mock — the page renders a visible "MOCK DATA"
 * badge off this. Never flip this to false without real wiring.
 */
export const IS_MOCK = true as const;

/**
 * Simulates the B3 paywall result for the one-click action. In production this
 * comes from `useApi`'s `paywalled` flag on the confirm endpoint's 402
 * (PLAN_REQUIRED) — NOT a client-side plan check. Toggle here only to preview
 * the wall vs the button while building.
 */
export const MOCK_PAYWALLED = false as const;

/**
 * Fixed "now" anchor (epoch ms) so the mock countdowns are deterministic at
 * mount + in tests. The page ticks a local seconds counter off this, so the
 * demo countdown feels live without depending on the real wall clock (which
 * would render every fixture "expired"). Real wiring uses the actual timestamp.
 */
export const MOCK_NOW_MS = Date.UTC(2026, 6, 20, 6, 30, 0); // 2026-07-20 12:00 IST
const minsAgo = (m: number) => new Date(MOCK_NOW_MS - m * 60_000).toISOString();

/** Entry-window length (minutes) — DISPLAY ONLY; real value is server-enforced. */
export const ENTRY_VALIDITY_MINUTES = 5;

export const MOCK_SIGNALS: MockSignal[] = [
  {
    id: "sig-mock-0001",
    strategyName: "Strategy S1",
    symbol: "BSE-JUL2026-FUT",
    side: "ENTRY",
    entry: "2437.50",
    sl: "2402.00",
    target: "2510.00",
    received_at: minsAgo(1), // fresh — inside the 5-min entry window
    status: "pending",
  },
  {
    id: "sig-mock-0002",
    strategyName: "Strategy S2",
    symbol: "CDSL-JUL2026-FUT",
    side: "ENTRY",
    entry: "1585.00",
    sl: "1560.00",
    target: "1640.00",
    received_at: minsAgo(4), // nearly lapsed — entry window almost closed
    status: "pending",
  },
  {
    id: "sig-mock-0003",
    strategyName: "Strategy S1",
    symbol: "BSE-JUL2026-FUT",
    side: "EXIT",
    entry: null,
    sl: null,
    target: null,
    received_at: minsAgo(20), // EXIT — valid till EOD, entry-window N/A
    status: "pending",
  },
  {
    id: "sig-mock-0004",
    strategyName: "Strategy S3",
    symbol: "ANGELONE-JUL2026-FUT",
    side: "ENTRY",
    entry: "2680.00",
    sl: "2645.00",
    target: "2760.00",
    received_at: minsAgo(9), // ENTRY past 5 min — lapsed, shown as expired
    status: "expired",
  },
];
