/**
 * Step 6 — the execution log's honesty label.
 *
 * The rule this file exists to enforce: every row on this screen is a
 * simulated fill today, the screen must SAY so, and it must say so by DERIVING
 * the label from the row — never by hardcoding it.
 *
 * A hardcoded "SIMULATED" would pass every test you could write today and
 * become a lie the moment a real fill first appears. So the load-bearing test
 * here is the one asserting a `paper_mode: false` row renders DIFFERENTLY —
 * different text, different tone, different meaning. If someone replaces the
 * derivation with a constant, that test is what fails.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

const apiState: { current: { data: unknown; isLoading: boolean; error: null } } = {
  current: { data: null, isLoading: false, error: null },
};
const seenUrls: (string | null)[] = [];
vi.mock("@/lib/use-api", () => ({
  useApi: (url: string | null) => {
    seenUrls.push(url);
    return apiState.current;
  },
}));

import { ExecutionLog } from "@/components/marketplace/execution-log";
import {
  executionLabel,
  executionLogSummary,
  EXECUTION_LABELS,
  ALL_SIMULATED_NOTE,
  CONTAINS_REAL_NOTE,
  MIXED_UNVERIFIED_NOTE,
  EMPTY_LOG_NOTE,
} from "@/lib/execution-label";

type Row = {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  leg_role: string;
  order_type: string;
  price: string | null;
  broker_order_id: string | null;
  broker_status: string | null;
  error_code: string | null;
  error_message: string | null;
  placed_at: string;
  completed_at: string | null;
  paper_mode: boolean | null;
};

function row(over: Partial<Row> = {}): Row {
  return {
    id: "e1",
    symbol: "BSE-AUG2026-FUT",
    side: "buy",
    quantity: 1,
    leg_role: "entry",
    order_type: "market",
    price: "742.5000",
    broker_order_id: "PAPER-1",
    broker_status: "complete",
    error_code: null,
    error_message: null,
    placed_at: "2026-08-26T10:00:00Z",
    completed_at: "2026-08-26T10:00:00Z",
    paper_mode: true,
    ...over,
  };
}

function mount(rows: Row[], loading = false) {
  apiState.current = {
    data: { subscription_id: "s1", executions: rows, count: rows.length },
    isLoading: loading,
    error: null,
  };
  return render(<ExecutionLog subscriptionId="s1" />);
}

beforeEach(() => {
  seenUrls.length = 0;
});

// ═══════════════════════════════════════════════════════════════════════
// The label is DERIVED — the whole point
// ═══════════════════════════════════════════════════════════════════════

describe("the simulated label is derived, not hardcoded", () => {
  it("labels a paper row SIMULATED", () => {
    mount([row({ paper_mode: true })]);
    const chip = within(screen.getByTestId("execution-row-e1")).getByText("SIMULATED");
    expect(chip).toBeInTheDocument();
    expect(chip.getAttribute("data-label-kind")).toBe("simulated");
  });

  it("🔴 a paper_mode=false row renders DIFFERENTLY — the anti-rot test", () => {
    mount([row({ paper_mode: false })]);
    const cell = within(screen.getByTestId("execution-row-e1"));

    // not the simulated label
    expect(cell.queryByText("SIMULATED")).toBeNull();
    // a distinct one
    const chip = cell.getByText("REAL");
    expect(chip.getAttribute("data-label-kind")).toBe("real");
    // and visibly distinct, not just different words
    expect(EXECUTION_LABELS.real.tone).not.toBe(EXECUTION_LABELS.simulated.tone);
    expect(EXECUTION_LABELS.real.meaning).not.toBe(
      EXECUTION_LABELS.simulated.meaning,
    );
  });

  it("labels an unknown row UNVERIFIED — never guessed either way", () => {
    mount([row({ paper_mode: null })]);
    const cell = within(screen.getByTestId("execution-row-e1"));
    expect(cell.queryByText("SIMULATED")).toBeNull();
    expect(cell.queryByText("REAL")).toBeNull();
    expect(cell.getByText("UNVERIFIED")).toBeInTheDocument();
  });

  it("labels each row independently in a mixed log", () => {
    mount([
      row({ id: "a", paper_mode: true }),
      row({ id: "b", paper_mode: false }),
      row({ id: "c", paper_mode: null }),
    ]);
    const kind = (id: string) =>
      within(screen.getByTestId(`execution-row-${id}`))
        .getByText(/SIMULATED|REAL|UNVERIFIED/)
        .getAttribute("data-label-kind");

    expect([kind("a"), kind("b"), kind("c")]).toEqual([
      "simulated",
      "real",
      "unverified",
    ]);
  });

  it("carries the meaning as an accessible description, not just colour", () => {
    mount([row({ paper_mode: true })]);
    const chip = screen.getByText("SIMULATED");
    expect(chip.getAttribute("aria-label")).toContain("simulated");
    expect(chip.getAttribute("title")).toBe(EXECUTION_LABELS.simulated.meaning);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// It must not read as a broker fill history
// ═══════════════════════════════════════════════════════════════════════

describe("the log never reads as broker fill history", () => {
  it("states plainly that an all-paper log is simulated", () => {
    mount([row({ paper_mode: true }), row({ id: "e2", paper_mode: true })]);
    const note = screen.getByTestId("execution-log-summary").textContent ?? "";
    expect(note).toBe(ALL_SIMULATED_NOTE);
    expect(note).toMatch(/broker ka fill history NAHI/i);
  });

  it("STOPS claiming all-simulated as soon as one real row appears", () => {
    mount([row({ paper_mode: true }), row({ id: "e2", paper_mode: false })]);
    const note = screen.getByTestId("execution-log-summary").textContent;
    expect(note).not.toBe(ALL_SIMULATED_NOTE);
    expect(note).toBe(CONTAINS_REAL_NOTE);
  });

  it("does not claim all-simulated when a row is unverified", () => {
    mount([row({ paper_mode: true }), row({ id: "e2", paper_mode: null })]);
    expect(screen.getByTestId("execution-log-summary").textContent).toBe(
      MIXED_UNVERIFIED_NOTE,
    );
  });

  it("says nothing reassuring when there is nothing to show", () => {
    mount([]);
    expect(screen.getByTestId("execution-log-summary").textContent).toBe(
      EMPTY_LOG_NOTE,
    );
  });

  it("has no hardcoded label string in the component source", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const src = readFileSync(
      join(process.cwd(), "src/components/marketplace/execution-log.tsx"),
      "utf8",
    );
    // Strip comments first — this file DISCUSSES the word "SIMULATED" at
    // length, and prose about the rule is not the rule being broken.
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");

    // the words must come from the label module, never be typed inline
    expect(code).not.toMatch(/SIMULATED|UNVERIFIED/);
    expect(code).toContain("executionLabel(row.paper_mode)");
    expect(code).toContain("executionLogSummary(rows)");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Pure label logic
// ═══════════════════════════════════════════════════════════════════════

describe("executionLabel", () => {
  it("maps the tri-state exactly", () => {
    expect(executionLabel(true).kind).toBe("simulated");
    expect(executionLabel(false).kind).toBe("real");
    expect(executionLabel(null).kind).toBe("unverified");
    expect(executionLabel(undefined).kind).toBe("unverified");
  });

  it("gives every state a distinct text and tone", () => {
    const kinds = ["simulated", "real", "unverified"] as const;
    expect(new Set(kinds.map((k) => EXECUTION_LABELS[k].text)).size).toBe(3);
    expect(new Set(kinds.map((k) => EXECUTION_LABELS[k].tone)).size).toBe(3);
  });
});

describe("executionLogSummary", () => {
  it("only says all-simulated when EVERY row says so", () => {
    expect(executionLogSummary([{ paper_mode: true }, { paper_mode: true }])).toBe(
      ALL_SIMULATED_NOTE,
    );
    expect(executionLogSummary([{ paper_mode: true }, { paper_mode: null }])).not.toBe(
      ALL_SIMULATED_NOTE,
    );
    expect(executionLogSummary([{ paper_mode: true }, { paper_mode: false }])).not.toBe(
      ALL_SIMULATED_NOTE,
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Fetch scoping
// ═══════════════════════════════════════════════════════════════════════

describe("fetching", () => {
  it("asks the subscription-scoped endpoint", () => {
    mount([row()]);
    expect(seenUrls).toContain("/marketplace/subscriptions/s1/executions");
  });

  it("does NOT fetch when disabled — no log-per-row on page load", () => {
    apiState.current = { data: null, isLoading: false, error: null };
    render(<ExecutionLog subscriptionId="s1" enabled={false} />);
    expect(seenUrls).toEqual([null]);
  });

  it("shows NO P&L column — there is no LTP to source one from", () => {
    mount([row()]);
    const log = screen.getByTestId("execution-log");
    expect(log.textContent).not.toMatch(/P&L|PnL|Unrealised|Unrealized/i);
  });
});
