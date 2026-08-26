/**
 * Defects found by adversarial review of Step 6, and the tests that hold them
 * shut. All three are the same family: the screen stating something it did not
 * learn.
 *
 *   1. CRITICAL — the position card is the ALWAYS-VISIBLE surface (the log
 *      hides behind an expand) and it carried NO simulated label at all. A
 *      symbol with a side, entry, stop and target is precisely what a live
 *      broker position looks like.
 *   2. HIGH — a FAILED fetch rendered as "you have no executions". An empty
 *      list from a failed read is not evidence of an empty log.
 *   3. MEDIUM — `_simulate_fill` stores Decimal("0") to mean "no price in the
 *      payload". That sentinel rendered as "Entry 0.0000" — a fill price that
 *      never happened.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const apiState: {
  current: { data: unknown; isLoading: boolean; error: string | null };
} = { current: { data: null, isLoading: false, error: null } };
vi.mock("@/lib/use-api", () => ({ useApi: () => apiState.current }));

import { ExecutionLog } from "@/components/marketplace/execution-log";
import { PositionDetail } from "@/components/marketplace/position-detail";
import {
  EMPTY_LOG_NOTE,
  FETCH_FAILED_NOTE,
  LOADING_LOG_NOTE,
  MANUAL_CLOSE_GAP_NOTE,
  TRUNCATED_LOG_NOTE,
  EXECUTION_LABELS,
} from "@/lib/execution-label";
import { displayPrice, isUnknownPrice, NO_PRICE } from "@/lib/price-display";

const POS = {
  id: "p1",
  symbol: "BSE-AUG2026-FUT",
  quantity: 4,
  side: "long",
  avg_entry_price: "742.5000",
  remaining_quantity: 4,
  stop_loss_price: "730.0000",
  target_price: "770.0000",
  opened_at: "2026-08-26T04:30:00Z",
  paper_mode: true as boolean | null,
};

function mountLog(
  rows: unknown[],
  error: string | null = null,
  extra: { isLoading?: boolean; truncated?: boolean } = {},
) {
  apiState.current = {
    data: {
      subscription_id: "s1", executions: rows, count: rows.length,
      truncated: extra.truncated ?? false,
    },
    isLoading: extra.isLoading ?? false,
    error,
  };
  return render(<ExecutionLog subscriptionId="s1" />);
}

// ═══════════════════════════════════════════════════════════════════════
// 1. The position card must not read as a live broker position
// ═══════════════════════════════════════════════════════════════════════

describe("the position card carries the honesty label too", () => {
  it("labels a simulated position SIMULATED", () => {
    render(<PositionDetail position={POS} />);
    const card = within(screen.getByTestId("position-detail-p1"));
    expect(card.getByText("SIMULATED")).toBeInTheDocument();
  });

  it("🔴 a REAL position renders differently — derived, not hardcoded", () => {
    render(<PositionDetail position={{ ...POS, paper_mode: false }} />);
    const card = within(screen.getByTestId("position-detail-p1"));
    expect(card.queryByText("SIMULATED")).toBeNull();
    expect(card.getByText("REAL").getAttribute("data-label-kind")).toBe("real");
  });

  it("claims neither when the position does not say", () => {
    render(<PositionDetail position={{ ...POS, paper_mode: null }} />);
    const card = within(screen.getByTestId("position-detail-p1"));
    expect(card.queryByText("SIMULATED")).toBeNull();
    expect(card.queryByText("REAL")).toBeNull();
    expect(card.getByText("UNVERIFIED")).toBeInTheDocument();
  });

  it("the label is never a literal in the component source", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const code = readFileSync(
      join(process.cwd(), "src/components/marketplace/position-detail.tsx"),
      "utf8",
    )
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/SIMULATED|UNVERIFIED/);
    expect(code).toContain("executionLabel(position.paper_mode)");
  });

  it("the meaning is readable, not colour-only", () => {
    render(<PositionDetail position={POS} />);
    expect(screen.getByText("SIMULATED").getAttribute("aria-label")).toBe(
      EXECUTION_LABELS.simulated.meaning,
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. A failed read must not claim an empty log
// ═══════════════════════════════════════════════════════════════════════

describe("a failed fetch never claims 'you have no executions'", () => {
  it("says the read failed, not that the log is empty", () => {
    mountLog([], "Network error");
    const note = screen.getByTestId("execution-log-summary").textContent;
    expect(note).toBe(FETCH_FAILED_NOTE);
    expect(note).not.toBe(EMPTY_LOG_NOTE);
  });

  it("explicitly denies the wrong inference", () => {
    mountLog([], "boom");
    expect(screen.getByTestId("execution-log-summary").textContent).toMatch(
      /matlab yeh NAHI hai ki koi execution nahi hui/i,
    );
  });

  it("a genuinely empty log still says empty", () => {
    mountLog([], null);
    expect(screen.getByTestId("execution-log-summary").textContent).toBe(
      EMPTY_LOG_NOTE,
    );
  });

  it("does not render stale rows alongside an error", () => {
    mountLog([{ id: "e1", symbol: "X", side: "buy", quantity: 1,
      leg_role: "entry", order_type: "market", price: "1", broker_order_id: null,
      broker_status: null, error_code: null, error_message: null,
      placed_at: "2026-08-26T10:00:00Z", completed_at: null, paper_mode: true }],
      "boom");
    expect(screen.queryByTestId("execution-row-e1")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. The zero-price sentinel is not a price
// ═══════════════════════════════════════════════════════════════════════

describe("the zero sentinel never renders as a price", () => {
  it.each(["0", "0.0", "0.0000", "", null, undefined, "abc"])(
    "treats %p as unknown",
    (raw) => {
      expect(isUnknownPrice(raw as string | null)).toBe(true);
      expect(displayPrice(raw as string | null)).toBe(NO_PRICE);
    },
  );

  it("passes a real price through VERBATIM — no re-rounding", () => {
    expect(displayPrice("742.5000")).toBe("742.5000");
    expect(displayPrice("0.0500")).toBe("0.0500");
  });

  it("the log shows a dash, not 0.0000", () => {
    mountLog([{ id: "e1", symbol: "X", side: "buy", quantity: 1,
      leg_role: "entry", order_type: "market", price: "0.0000",
      broker_order_id: null, broker_status: null, error_code: null,
      error_message: null, placed_at: "2026-08-26T10:00:00Z",
      completed_at: null, paper_mode: true }]);
    const row = screen.getByTestId("execution-row-e1").textContent ?? "";
    expect(row).not.toContain("0.0000");
    expect(row).toContain(NO_PRICE);
  });

  it("the position card OMITS an entry it does not have", () => {
    render(<PositionDetail position={{ ...POS, avg_entry_price: "0.0000" }} />);
    const card = screen.getByTestId("position-detail-p1").textContent ?? "";
    // the Entry fact is dropped entirely — label and value both
    expect(card).not.toMatch(/Entry/);
    // ...while the facts it genuinely HAS are untouched. (Asserting on the
    // bare string "0.0000" would be wrong here: "730.0000" contains it.)
    expect(card).toContain("Stop730.0000");
    expect(card).toContain("Target770.0000");
  });

  it("a zero stop/target is dropped too", () => {
    render(<PositionDetail position={{
      ...POS, stop_loss_price: "0.0000", target_price: "0" }} />);
    const card = screen.getByTestId("position-detail-p1").textContent ?? "";
    expect(card).not.toMatch(/Stop|Target/);
    expect(card).toContain("742.5000");
  });
});


// ═══════════════════════════════════════════════════════════════════════
// 4. Loading, truncation, and the gap we cannot close
// ═══════════════════════════════════════════════════════════════════════

describe("an in-flight read claims nothing either", () => {
  it("says loading, not 'you have no executions'", () => {
    mountLog([], null, { isLoading: true });
    const note = screen.getByTestId("execution-log-summary").textContent;
    expect(note).toBe(LOADING_LOG_NOTE);
    expect(note).not.toBe(EMPTY_LOG_NOTE);
  });

  it("an error outranks loading — the failure is the more important truth", () => {
    mountLog([], "boom", { isLoading: true });
    expect(screen.getByTestId("execution-log-summary").textContent).toBe(
      FETCH_FAILED_NOTE,
    );
  });
});

describe("truncation is never silent", () => {
  it("says so when the server cut the list short", () => {
    mountLog([], null, { truncated: true });
    expect(screen.getByTestId("execution-log-truncated").textContent).toBe(
      TRUNCATED_LOG_NOTE,
    );
  });

  it("says nothing when the log is complete", () => {
    mountLog([], null, { truncated: false });
    expect(screen.queryByTestId("execution-log-truncated")).toBeNull();
  });
});

describe("the manual-close gap is stated, not hidden", () => {
  it("warns that a hand-closed exit is absent from this log", () => {
    mountLog([]);
    expect(screen.getByTestId("execution-log-gap").textContent).toBe(
      MANUAL_CLOSE_GAP_NOTE,
    );
  });

  it("explains it in terms a customer can act on", () => {
    mountLog([]);
    expect(screen.getByTestId("execution-log-gap").textContent).toMatch(
      /Close button.*record nahi hota/i,
    );
  });

  it("is not shown when the read itself failed — one problem at a time", () => {
    mountLog([], "boom");
    expect(screen.queryByTestId("execution-log-gap")).toBeNull();
  });
});
