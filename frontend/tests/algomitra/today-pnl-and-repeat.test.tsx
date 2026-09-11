/**
 * The other three founder decisions behind the "🚀 ₹1,95,831! Killer day."
 * incident — the ones that live upstream of the renderer.
 *
 *   1. DERIVE today from the `curve` rows the server already sends. The
 *      stored per-IST-day baseline is deleted, not repaired.
 *   2. SILENCE, never zero. A day whose closes are all unpriced /
 *      `human_interfered` produces NO sentence, not "₹0".
 *   4. Speak only when the day BAND CHANGES. "profit-huge" is
 *      `important: true`, so it bypassed cooldown AND the dismissal
 *      blackout; the effect keyed on `[data]`, a new object every 60s poll;
 *      so the toast re-fired every minute and dismissing it did nothing.
 *
 * (Decision 3, the polarity guard, is covered exhaustively in
 * `no-celebration-on-a-loss.test.ts`.)
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deriveTodayPnl,
  istDateKey,
  purgeLegacyBaselines,
  recordDismissal,
  canShowReaction,
} from "@/lib/pnl-tracker";

const apiData = vi.hoisted(() => ({ current: null as unknown }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: () => ({
    data: apiData.current,
    isLoading: false,
    error: null,
    paywalled: false,
    paywallUrl: null,
    refetch: vi.fn(),
  }),
}));

import { useAlgoMitraLive } from "@/hooks/useAlgoMitraLive";

/** An instant inside a known IST day, expressed as a UTC ISO string. */
const IST_NOON_07_SEP = "2026-09-07T06:30:00+00:00"; // 12:00 IST, 7 Sept
const IST_LATE_07_SEP = "2026-09-07T18:29:00+00:00"; // 23:59 IST, 7 Sept
const IST_EARLY_08_SEP = "2026-09-07T18:31:00+00:00"; // 00:01 IST, 8 Sept

function row(closedAt: string | null, pnl: string | number | null) {
  return {
    position_id: "p",
    symbol: "BSE-SEP2026-FUT",
    closed_at: closedAt,
    pnl,
    attribution: "bot_only",
  };
}

const NOW_07_SEP = new Date("2026-09-07T09:00:00+00:00"); // 14:30 IST, 7 Sept

beforeEach(() => {
  localStorage.clear();
});

// ─── Decision 1: derive today from the curve ────────────────────────────

describe("deriveTodayPnl — today's own rows, no baseline", () => {
  it("sums only the rows that closed in the current IST day", () => {
    const today = deriveTodayPnl(
      [
        row("2026-09-05T06:30:00+00:00", "-1000"), // 5 Sept — not today
        row(IST_NOON_07_SEP, "-2500.25"),
        row(IST_NOON_07_SEP, "900.25"),
        row(IST_EARLY_08_SEP, "50000"), // already 8 Sept in IST
      ],
      NOW_07_SEP,
    );
    expect(today).toEqual({ amount: -1600, rows: 2 });
  });

  it("cuts the day at IST midnight, not the browser's midnight", () => {
    // 23:59 IST on the 7th is today; two minutes later is not.
    expect(deriveTodayPnl([row(IST_LATE_07_SEP, "100")], NOW_07_SEP)).toEqual({
      amount: 100,
      rows: 1,
    });
    expect(deriveTodayPnl([row(IST_EARLY_08_SEP, "100")], NOW_07_SEP)).toBeNull();
    // And the cut is the platform's one "aaj" cutter.
    expect(istDateKey(new Date(IST_LATE_07_SEP))).toBe("2026-09-07");
    expect(istDateKey(new Date(IST_EARLY_08_SEP))).toBe("2026-09-08");
  });

  it("accepts pnl as a decimal string (what the server actually sends)", () => {
    expect(deriveTodayPnl([row(IST_NOON_07_SEP, "-195830.5100")], NOW_07_SEP)).toEqual({
      amount: -195830.51,
      rows: 1,
    });
  });

  it("does not subtract across time — a changed cumulative total is irrelevant", () => {
    // THE INCIDENT: the cut-off moved cumulative total_pnl from -195,830.51
    // to 0.00. The derivation never reads it, so the same curve gives the
    // same answer no matter what the total says.
    const curve = [row(IST_NOON_07_SEP, "-2500")];
    expect(deriveTodayPnl(curve, NOW_07_SEP)).toEqual({ amount: -2500, rows: 1 });
    expect(deriveTodayPnl(curve, NOW_07_SEP)).toEqual({ amount: -2500, rows: 1 });
  });

  it("the deleted baseline mechanism is gone from the module", async () => {
    const mod = await import("@/lib/pnl-tracker");
    expect("getDailyBaseline" in mod).toBe(false);
  });

  it("purges the dead baseline keys a previous build left in localStorage", () => {
    localStorage.setItem("tb_algomitra_live_baseline_2026-09-08", "-195830.51");
    localStorage.setItem("tb_algomitra_live_baseline_2026-09-09", "0");
    localStorage.setItem("tb_algomitra_live_notif_mode", "all");
    purgeLegacyBaselines();
    expect(localStorage.getItem("tb_algomitra_live_baseline_2026-09-08")).toBeNull();
    expect(localStorage.getItem("tb_algomitra_live_baseline_2026-09-09")).toBeNull();
    // Unrelated keys survive.
    expect(localStorage.getItem("tb_algomitra_live_notif_mode")).toBe("all");
  });
});

// ─── Decision 2: silence, never zero ────────────────────────────────────

describe("silence is never zero", () => {
  it("says nothing when the day's closes are all unpriced / human_interfered", () => {
    // The server omits those round trips from `curve` rather than folding
    // them in as 0 — which is exactly the state of the three post-cut
    // positions (844b8037, a13ddeb0, d0086394) today.
    expect(deriveTodayPnl([], NOW_07_SEP)).toBeNull();
  });

  it("says nothing when there is no curve at all", () => {
    expect(deriveTodayPnl(undefined, NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl(null, NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl("nope", NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl({ curve: [] }, NOW_07_SEP)).toBeNull();
  });

  it("says nothing rather than a confident wrong number when a row is unreadable", () => {
    // A timestamp with no zone would be read as the BROWSER's local time and
    // could land on the wrong IST day — so it is refused, not guessed.
    expect(deriveTodayPnl([row("2026-09-07T12:00:00", "100")], NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl([row("not-a-date", "100")], NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl([row(null, "100")], NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl([row(IST_NOON_07_SEP, "abc")], NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl([row(IST_NOON_07_SEP, null)], NOW_07_SEP)).toBeNull();
    expect(deriveTodayPnl([null], NOW_07_SEP)).toBeNull();
    // Even when a perfectly good row sits beside it: a partial sum is a lie.
    expect(
      deriveTodayPnl([row(IST_NOON_07_SEP, "100"), row("not-a-date", "5")], NOW_07_SEP),
    ).toBeNull();
  });

  it("never lets an unreadable pnl coerce to a silent zero", () => {
    // `Number(null)`, `Number("")`, `Number(" ")` and `Number(false)` are all
    // 0 and all finite. A day's number built on those is a fabricated flat.
    for (const bad of [null, "", "   ", false, true, {}, [], "1,000"]) {
      expect(
        deriveTodayPnl(
          [row(IST_NOON_07_SEP, bad as unknown as string)],
          NOW_07_SEP,
        ),
      ).toBeNull();
    }
    // A real zero, sent as a real number, is still a real zero.
    expect(deriveTodayPnl([row(IST_NOON_07_SEP, "0.0000")], NOW_07_SEP)).toEqual({
      amount: 0,
      rows: 1,
    });
    expect(deriveTodayPnl([row(IST_NOON_07_SEP, 0)], NOW_07_SEP)).toEqual({
      amount: 0,
      rows: 1,
    });
  });

  it("the hook renders NO message for a day with no priced closes", () => {
    apiData.current = { total_trades: 3, total_pnl: "0", win_rate: 0, curve: [] };
    const { result } = renderHook(() => useAlgoMitraLive());
    expect(result.current.message).toBeNull();
  });

  it("the hook renders NO message when total_pnl swings but the curve is empty", () => {
    // The exact incident shape: cumulative total moves, nothing closed today.
    apiData.current = {
      total_trades: 3,
      total_pnl: "-195830.51",
      win_rate: 0,
      curve: [],
    };
    const first = renderHook(() => useAlgoMitraLive());
    expect(first.result.current.message).toBeNull();
    apiData.current = { total_trades: 3, total_pnl: "0.00", win_rate: 0, curve: [] };
    act(() => {
      first.rerender();
    });
    expect(first.result.current.message).toBeNull();
  });
});

// ─── Decision 4: speak only when the band changes ───────────────────────

describe("the toast does not re-fire every poll", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW_07_SEP);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  function pollWith(pnl: string) {
    apiData.current = {
      total_trades: 1,
      total_pnl: pnl,
      win_rate: 100,
      curve: [row(IST_NOON_07_SEP, pnl)],
    };
  }

  it("speaks once for a band and stays quiet while the band holds", () => {
    pollWith("25000"); // profit-huge, important:true — bypasses every gate
    const { result, rerender } = renderHook(() => useAlgoMitraLive());
    const spoken = result.current.message;
    expect(spoken).not.toBeNull();

    // Dismiss, then poll 20 more times with a drifting-but-same-band number.
    act(() => {
      result.current.dismiss();
    });
    expect(result.current.message).toBeNull();

    for (let i = 1; i <= 20; i++) {
      pollWith(String(25000 + i)); // new object AND a new amount each poll
      act(() => {
        rerender();
      });
      expect(result.current.message).toBeNull();
    }
  });

  it("speaks again when the band actually changes", () => {
    pollWith("25000"); // profit-huge
    const { result, rerender } = renderHook(() => useAlgoMitraLive());
    expect(result.current.message).not.toBeNull();
    act(() => {
      result.current.dismiss();
    });

    pollWith("-25000"); // loss-big — a genuinely different band
    act(() => {
      rerender();
    });
    expect(result.current.message).not.toBeNull();
    expect(result.current.message).not.toContain("🚀");
  });

  it("auto-dismiss clears the toast without a further repeat", () => {
    pollWith("25000");
    const { result, rerender } = renderHook(() => useAlgoMitraLive());
    expect(result.current.message).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(9_000);
    });
    expect(result.current.message).toBeNull();
    pollWith("25001");
    act(() => {
      rerender();
    });
    expect(result.current.message).toBeNull();
  });
});

// ─── The blackout the deleted baseline used to reset ────────────────────

describe("the dismissal blackout still rolls over", () => {
  it("is day-stamped, so it cannot become a permanent silence", () => {
    const gate = { triggerId: "loss-small", isImportant: false };
    recordDismissal();
    recordDismissal();
    recordDismissal();
    expect(canShowReaction(gate, "all")).toBe(false);

    // Yesterday's counter must not silence today.
    localStorage.setItem(
      "tb_algomitra_live_dismissals",
      JSON.stringify({ istDate: "2020-01-01", count: 99 }),
    );
    expect(canShowReaction(gate, "all")).toBe(true);
    expect(istDateKey()).not.toBe("2020-01-01");
  });

  it("a bare counter written by the OLD build reads as a fresh day", () => {
    localStorage.setItem("tb_algomitra_live_dismissals", "7");
    expect(canShowReaction({ triggerId: "loss-small", isImportant: false }, "all")).toBe(
      true,
    );
  });
});
