/**
 * The tracking cut-off is the SERVER's date, or it is nothing.
 *
 * WHY THESE TESTS EXIST
 * ─────────────────────
 * The platform's record starts on a date the backend owns
 * (`GET /api/system/mode` → `tracking_epoch`). Two failure modes are worth
 * more than the feature itself, and both are pinned here:
 *
 *   1. A HARDCODED DATE. A literal in a component keeps printing a confident
 *      sentence the day the cut-off moves — the copy still looks right and is
 *      wrong, and no test breaks. So the note's date must come from the
 *      server on every render, a different server value must produce a
 *      different sentence, and the component source must contain no year or
 *      month literal at all.
 *   2. A CUT-OFF WE HAVE NOT READ. `null`, an older backend that omits the
 *      field, a failed fetch — all three mean "we do not know", and an
 *      unknown date is printed as NOTHING, never as a fallback. Same rule as
 *      `lib/paper-mode.ts`: naming a state you have not read is the worst lie
 *      this product can tell.
 *
 * And the third thing a cut-off breaks if nobody looks: a strategy with no
 * post-cut activity must SAY so — "Is strategy ne <date> ke baad abhi tak koi
 * trade nahi kiya" — instead of reading as a strategy that never traded, or
 * quietly vanishing from the surface.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// ── Mocks ────────────────────────────────────────────────────────────

beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    class IO {
      observe() {} unobserve() {} disconnect() {}
      takeRecords() { return []; }
      root = null; rootMargin = ""; thresholds = [];
    }
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
  }
});

type Mode = {
  paper_mode: boolean;
  kill_switch_check_enabled: boolean;
  circuit_breaker_enabled: boolean;
  tracking_epoch?: string | null;
};

const systemMode = vi.hoisted(() => ({ current: null as Mode | null }));
vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: () => systemMode.current,
}));

/** Per-URL API responses, so each page's own rows drive what it says. */
const apiData = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
  errors: {} as Record<string, string>,
}));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    // Longest key first, so "/strategies/positions" wins over "/strategies".
    const key =
      url === null
        ? "__null__"
        : Object.keys({ ...apiData.current, ...apiData.errors })
            .sort((a, b) => b.length - a.length)
            .find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return {
      data: apiData.current[key] ?? null,
      isLoading: false,
      error: apiData.errors[key] ?? null,
      paywalled: false,
      paywallUrl: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/strategies",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number; detail: string; data?: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail); this.status = status; this.detail = detail; this.data = data;
    }
  }
  return {
    api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), download: vi.fn() },
    ApiError,
  };
});

import {
  NoTradesSinceNote,
  TrackingEpochNote,
} from "@/components/dashboard/tracking-epoch-note";
import {
  ARCHIVE_HINT,
  formatTrackingEpoch,
  formatTrackingEpochShort,
  isSinceEpoch,
  noTradesSinceText,
  sinceEpochHeadline,
  trackingNoteText,
} from "@/lib/tracking-epoch";
import StrategiesPage from "@/app/(dashboard)/strategies/page";
import TradesPage from "@/app/(dashboard)/trades/page";

/** The cut-off the backend is expected to serve, in its own IST offset. */
const EPOCH = "2026-09-01T00:00:00+05:30";
/** A DIFFERENT cut-off. If the copy is hardcoded, this test is the one that fails. */
const OTHER_EPOCH = "2027-03-15T00:00:00+05:30";

function mode(over: Partial<Mode> = {}): Mode {
  return {
    paper_mode: false,
    kill_switch_check_enabled: true,
    circuit_breaker_enabled: true,
    ...over,
  };
}

const STRATEGY_ID = "89423ecc-c76e-432c-b107-0791508542f0";

function strategies() {
  return {
    strategies: [
      {
        id: STRATEGY_ID,
        name: "BSE LTD Futures",
        is_active: true,
        is_paper: false,
        strategy_json: null,
        created_at: "2026-05-01T04:00:00Z",
        updated_at: "2026-08-01T04:00:00Z",
      },
    ],
    count: 1,
  };
}

/** A position of that strategy, opened/closed whenever the caller says. */
function position(over: Record<string, unknown> = {}) {
  return {
    id: "d0086394-e66b-4b49-b557-7c337df777ac",
    strategy_id: STRATEGY_ID,
    symbol: "BSE-SEP2026-FUT",
    side: "sell",
    total_quantity: 400,
    remaining_quantity: 0,
    avg_entry_price: "3393.1500",
    status: "closed",
    opened_at: "2026-08-10T04:00:00Z",
    closed_at: "2026-08-11T04:00:00Z",
    final_pnl: "1200.00",
    ...over,
  };
}

beforeEach(() => {
  systemMode.current = null;
  apiData.current = {};
  apiData.errors = {};
});
afterEach(() => {
  cleanup();
});

// ── The line itself ──────────────────────────────────────────────────

describe("TrackingEpochNote prints the SERVER's date, or nothing", () => {
  it("renders the founder's sentence with the date the server sent", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });

    render(<TrackingEpochNote />);

    expect(screen.getByTestId("tracking-epoch-note").textContent).toBe(
      "Record 1 Sept 2026 se — usse pehle ka data archive mein hai.",
    );
  });

  it("🔴 a DIFFERENT server date changes the sentence — nothing is hardcoded", () => {
    systemMode.current = mode({ tracking_epoch: OTHER_EPOCH });

    render(<TrackingEpochNote />);

    const text = screen.getByTestId("tracking-epoch-note").textContent ?? "";
    expect(text).toBe("Record 15 March 2027 se — usse pehle ka data archive mein hai.");
    // The date the other test asserts must be nowhere on screen.
    expect(text).not.toMatch(/2026/);
  });

  it("🔴 renders NOTHING when the server says there is no cut-off (null)", () => {
    systemMode.current = mode({ tracking_epoch: null });

    const { container } = render(<TrackingEpochNote />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId("tracking-epoch-note")).toBeNull();
  });

  it("🔴 renders NOTHING against an older backend that omits the field", () => {
    systemMode.current = mode(); // no tracking_epoch key at all

    const { container } = render(<TrackingEpochNote />);

    expect(container).toBeEmptyDOMElement();
  });

  it("🔴 renders NOTHING while the mode has not been read", () => {
    systemMode.current = null; // loading, or a persistent failure

    const { container } = render(<TrackingEpochNote />);

    expect(container).toBeEmptyDOMElement();
  });

  it("🔴 renders NOTHING for an unreadable date — never a fallback", () => {
    systemMode.current = mode({ tracking_epoch: "not-a-date" });

    const { container } = render(<TrackingEpochNote />);

    expect(container).toBeEmptyDOMElement();
  });

  it("names the IST day, not the browser's", () => {
    // The same instant as EPOCH, expressed in UTC. A browser abroad must
    // still read the Indian trading day the cut-off was drawn on.
    systemMode.current = mode({ tracking_epoch: "2026-08-31T18:30:00Z" });

    render(<TrackingEpochNote />);

    expect(screen.getByTestId("tracking-epoch-note").textContent).toMatch(/1 Sept 2026/);
  });
});

// ── The copy can never drift from the server value ───────────────────

describe("no date literal hides in the component", () => {
  const COMPONENT = join(process.cwd(), "src/components/dashboard/tracking-epoch-note.tsx");
  const source = readFileSync(COMPONENT, "utf8");

  it("🔴 the component source carries no year and no month name", () => {
    // A literal here is how the sentence goes stale silently: the copy still
    // reads well and is wrong, and nothing fails.
    expect(source).not.toMatch(/\b(19|20)\d{2}\b/);
    expect(source).not.toMatch(/\bSept?\b/);
    expect(source).not.toMatch(
      /\b(Jan|Feb|March|April|May|June|July|Aug|Oct|Nov|Dec)\b/,
    );
  });

  it("🔴 the component reads the epoch through the one owner, and fetches nothing", () => {
    expect(source).toMatch(/useTrackingEpoch/);
    // No second path to the fact: no fetch of its own, no direct read of the
    // system-mode endpoint or hook.
    expect(source).not.toMatch(/useSystemMode\s*\(/);
    expect(source).not.toMatch(/useApi\s*[<(]/);
    expect(source).not.toMatch(/\bfetch\s*\(/);
  });
});

describe("every affected surface mounts the line", () => {
  const SURFACES = [
    "src/app/(dashboard)/positions/page.tsx",
    "src/app/(dashboard)/trades/page.tsx",
    "src/app/(dashboard)/analytics/page.tsx",
    "src/app/(dashboard)/signals/page.tsx",
    "src/app/(dashboard)/page.tsx",
    "src/app/(dashboard)/strategies/page.tsx",
  ];

  it.each(SURFACES)("%s renders <TrackingEpochNote />", (file) => {
    const src = readFileSync(join(process.cwd(), file), "utf8");
    expect(src).toMatch(/<TrackingEpochNote\s*\/>/);
  });

  it.each(SURFACES)("%s writes no cut-off date of its own", (file) => {
    const src = readFileSync(join(process.cwd(), file), "utf8");
    // Month names anywhere in a surface's copy would mean a second, silent
    // owner of the date. (Symbols like BSE-SEP2026-FUT live in fixtures, not
    // in these files.)
    expect(src).not.toMatch(/\bSept\b/);
  });
});

// ── The empty states name the period ─────────────────────────────────

describe("an empty list reads as 'nothing since the cut-off'", () => {
  it("🔴 /trades names the period and points at the archive", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });
    apiData.current = { "/strategies/executions": { executions: [], count: 0 } };

    render(<TradesPage />);

    const empty = screen.getByTestId("start-here");
    expect(empty.textContent ?? "").toMatch(/1 Sept ke baad abhi tak koi trade nahi hui/);
    // ADR 0001 §4 — and it still says what to do next.
    expect(empty.textContent ?? "").toMatch(/strategy chalu karo/i);
    expect(empty.textContent ?? "").toMatch(/archive mein hai/);
  });

  it("🔴 /trades claims NO period when the server named none", () => {
    systemMode.current = mode({ tracking_epoch: null });
    apiData.current = { "/strategies/executions": { executions: [], count: 0 } };

    render(<TradesPage />);

    const empty = screen.getByTestId("start-here");
    expect(empty.textContent ?? "").toMatch(/Abhi tak koi trade nahi hui/);
    expect(empty.textContent ?? "").not.toMatch(/ke baad/);
    expect(empty.textContent ?? "").not.toMatch(/archive/);
  });
});

// ── A quiet strategy says it is quiet ────────────────────────────────

describe("a strategy with no post-cut trade says so, and does not vanish", () => {
  it("🔴 names the period on the card when nothing happened since the cut-off", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });
    apiData.current = {
      "/strategies": strategies(),
      // Its only position is from BEFORE the cut-off.
      "/strategies/positions": { positions: [position()], count: 1 },
    };

    render(<StrategiesPage />);

    // The strategy is still on the page — silence is not deletion.
    expect(screen.getByText("BSE LTD Futures")).toBeInTheDocument();
    expect(screen.getByTestId("no-trades-since-epoch").textContent).toBe(
      "Is strategy ne 1 Sept ke baad abhi tak koi trade nahi kiya.",
    );
  });

  it("says nothing when the strategy HAS traded since the cut-off", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });
    apiData.current = {
      "/strategies": strategies(),
      "/strategies/positions": {
        positions: [position({ opened_at: "2026-09-08T08:30:11Z", closed_at: null, status: "open" })],
        count: 1,
      },
    };

    render(<StrategiesPage />);

    expect(screen.queryByTestId("no-trades-since-epoch")).toBeNull();
  });

  it("🔴 says nothing when there is no cut-off to speak of", () => {
    systemMode.current = mode({ tracking_epoch: null });
    apiData.current = {
      "/strategies": strategies(),
      "/strategies/positions": { positions: [], count: 0 },
    };

    render(<StrategiesPage />);

    expect(screen.queryByTestId("no-trades-since-epoch")).toBeNull();
  });

  it("🔴 says nothing when the activity fetch failed — a failure is not a zero", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });
    apiData.current = { "/strategies": strategies() };
    apiData.errors = { "/strategies/positions": "Network error" };

    render(<StrategiesPage />);

    expect(screen.getByText("BSE LTD Futures")).toBeInTheDocument();
    expect(screen.queryByTestId("no-trades-since-epoch")).toBeNull();
  });

  it("🔴 says nothing when the position list was TRUNCATED", () => {
    // 100 rows returned out of 400: an absent row proves nothing, so "koi
    // trade nahi kiya" would be a claim about rows we never saw.
    systemMode.current = mode({ tracking_epoch: EPOCH });
    apiData.current = {
      "/strategies": strategies(),
      "/strategies/positions": {
        positions: Array.from({ length: 100 }, (_, i) =>
          position({ id: `p-${i}`, strategy_id: "some-other-strategy" }),
        ),
        count: 400,
      },
    };

    render(<StrategiesPage />);

    expect(screen.queryByTestId("no-trades-since-epoch")).toBeNull();
  });
});

describe("NoTradesSinceNote renders only what it was told", () => {
  it("🔴 renders NOTHING for unknown activity", () => {
    systemMode.current = mode({ tracking_epoch: EPOCH });
    const { container } = render(<NoTradesSinceNote tradedSince={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("🔴 renders NOTHING when there is no cut-off, even with no activity", () => {
    systemMode.current = mode({ tracking_epoch: null });
    const { container } = render(<NoTradesSinceNote tradedSince={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

// ── The owner module ─────────────────────────────────────────────────

describe("lib/tracking-epoch is the one place the date is shaped", () => {
  it("formats in IST, long and short", () => {
    expect(formatTrackingEpoch(EPOCH)).toBe("1 Sept 2026");
    expect(formatTrackingEpochShort(EPOCH)).toBe("1 Sept");
    expect(formatTrackingEpoch(OTHER_EPOCH)).toBe("15 March 2027");
  });

  it("🔴 returns null for every kind of unknown", () => {
    for (const bad of [null, undefined, "", "   ", "not-a-date"]) {
      expect(formatTrackingEpoch(bad)).toBeNull();
      expect(formatTrackingEpochShort(bad)).toBeNull();
    }
  });

  it("writes the founder's sentences from a label it is handed", () => {
    expect(trackingNoteText("1 Sept 2026")).toBe(
      "Record 1 Sept 2026 se — usse pehle ka data archive mein hai.",
    );
    expect(noTradesSinceText("1 Sept")).toBe(
      "Is strategy ne 1 Sept ke baad abhi tak koi trade nahi kiya.",
    );
    expect(sinceEpochHeadline("1 Sept", "abhi tak koi trade nahi hui")).toBe(
      "1 Sept ke baad abhi tak koi trade nahi hui",
    );
    expect(ARCHIVE_HINT).toMatch(/archive mein hai/);
  });

  it("puts the boundary instant itself INSIDE the tracked period", () => {
    expect(isSinceEpoch(EPOCH, EPOCH)).toBe(true);
    expect(isSinceEpoch("2026-09-01T09:15:00+05:30", EPOCH)).toBe(true);
    expect(isSinceEpoch("2026-08-31T23:59:59+05:30", EPOCH)).toBe(false);
  });

  it("🔴 an unknown timestamp or epoch is null, never false", () => {
    // false would mean "before the cut-off" — a fact we do not have.
    expect(isSinceEpoch(null, EPOCH)).toBeNull();
    expect(isSinceEpoch(EPOCH, null)).toBeNull();
    expect(isSinceEpoch("garbage", EPOCH)).toBeNull();
    expect(isSinceEpoch(EPOCH, "garbage")).toBeNull();
  });
});
