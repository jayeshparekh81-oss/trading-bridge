/**
 * C6 end to end, as far as it can run without a trading day: the ENGINE's real stop-proof receipts
 * (Track A `executor/stop_proof.py`, judge + write_receipt) → the REAL backend truth handler
 * (`/api/customer-lane/dashboard/truth`, Track C) → THIS card. The fixture is the handler's actual
 * output for six accounts (see its `_how_made`), so a drift between producer, consumer and screen
 * turns this RED instead of showing a customer a wrong word.
 *
 * What it proves: an engine NAKED or WRONG_CONTRACT reads as UNPROTECTED (danger) with a next step;
 * a broker read that failed and an account with no receipt at all read NOT MEASURED — never green,
 * never "safe"; the machine's internal reason (file paths, English engine text) never reaches the screen.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import fixture from "../fixtures/truth-cards-from-engine-receipts.json";
import { truthHeadline, type TruthCard } from "@/lib/account-truth";

let current: TruthCard | null = null;
vi.mock("@/shared/api/use-api", () => ({
  useApi: () => ({ data: current, isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn() }),
}));
vi.mock("@/shared/api/client", () => ({ api: { post: vi.fn() }, ApiError: class extends Error {} }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { AccountTruthCard } from "@/components/marketplace/account-truth-card";

const cards = fixture.cards as unknown as Record<string, TruthCard>;
const EXPECT: Record<string, TruthCard["verdict"]> = {
  PROTECTED: "PROTECTED",
  NAKED: "UNPROTECTED",
  WRONG_CONTRACT: "UNPROTECTED",
  UNKNOWN_BROKER: "NOT MEASURED",
  FLAT: "FLAT",
  NO_RECEIPT: "NOT MEASURED",
};

describe("engine receipt → backend truth handler → the card", () => {
  for (const [scenario, verdict] of Object.entries(EXPECT)) {
    it(`${scenario} renders ${verdict}`, () => {
      current = cards[scenario];
      expect(current.verdict).toBe(verdict);
      render(<AccountTruthCard subscriptionId="s1" symbol="BSE-OCT2026-FUT" storedQuantity={400} />);
      const card = screen.getByTestId("truth-card");
      expect(card.getAttribute("data-verdict")).toBe(verdict);
      expect(screen.getByTestId("truth-headline").textContent).toBe(truthHeadline(verdict));
      expect((screen.getByTestId("truth-next-step").textContent ?? "").length).toBeGreaterThan(5);
      // the machine's own reason never reaches the customer's screen
      expect(card.textContent).not.toMatch(/receipts\/|\.json|UNKNOWN_BROKER|engine could not judge/);
    });
  }

  it("a stop that exists is named by its order id; a missing one is not invented", () => {
    current = cards.PROTECTED;
    const { unmount } = render(<AccountTruthCard subscriptionId="s1" symbol="x" storedQuantity={400} />);
    expect(screen.getByTestId("truth-verified").textContent).toContain(String(cards.PROTECTED.stop?.order_id));
    unmount();
    current = cards.NAKED;
    render(<AccountTruthCard subscriptionId="s1" symbol="x" storedQuantity={400} />);
    expect(screen.getByTestId("truth-verified").textContent).not.toContain("stop order");
  });

  it("no receipt at all = the last check is NOT MEASURED, never 'just now'", () => {
    current = cards.NO_RECEIPT;
    render(<AccountTruthCard subscriptionId="s1" symbol="x" storedQuantity={400} />);
    expect(screen.getByTestId("truth-verified").textContent).toContain("NOT MEASURED");
  });
});
