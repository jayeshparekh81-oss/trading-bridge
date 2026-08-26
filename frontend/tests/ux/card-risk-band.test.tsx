/**
 * STEP 5 — risk on the CARD (StrykeX pattern), without a claim we can't back.
 *
 * StrykeX shows a risk band up front. They know each strategy's segment; we do
 * NOT — instrument_type is not exposed on ListingRead. So a specific band
 * ("MEDIUM") on the card would assert exactly the per-strategy segment the
 * whole risk-label design refuses to assert.
 *
 * The card therefore shows the RANGE and points at the legend.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { ListingCard, type ListingCardData } from "@/components/marketplace/listing-card";
import {
  CARD_RISK_BAND_HINT,
  CARD_RISK_BAND_LABEL,
  SEGMENT_RISK,
} from "@/lib/risk-labels";

const listing: ListingCardData = {
  id: "l1", title: "BSE Momentum", description: "A strategy",
  price_inr: 999, tags: ["futures"], status: "published",
  subscriber_count: 12, rating_avg: 4.5, rating_count: 8,
  published_at: "2026-08-01T00:00:00Z",
};

describe("risk band is on the card", () => {
  it("renders", () => {
    render(<ListingCard listing={listing} />);
    expect(screen.getByTestId("card-risk-band")).toBeInTheDocument();
  });

  it("shows the range, and points at the segment", () => {
    render(<ListingCard listing={listing} />);
    const t = screen.getByTestId("card-risk-band").textContent ?? "";
    expect(t).toContain(CARD_RISK_BAND_LABEL);
    expect(t).toMatch(/by segment/i);
  });

  it("carries the explanatory hint", () => {
    render(<ListingCard listing={listing} />);
    expect(screen.getByTestId("card-risk-band").getAttribute("title"))
      .toBe(CARD_RISK_BAND_HINT);
  });
});

// ═══════════════════════════════════════════════════════════════════
// ⚠️ THE HONESTY RULE — no per-strategy claim
// ═══════════════════════════════════════════════════════════════════
describe("the card must NOT claim a per-strategy band", () => {
  it("never shows a single specific segment band", () => {
    render(<ListingCard listing={listing} />);
    const t = screen.getByTestId("card-risk-band").textContent ?? "";
    // The three specific labels must not appear on their own.
    expect(t).not.toContain(SEGMENT_RISK.cash.label);
    expect(t).not.toContain(SEGMENT_RISK.futures.label);
    expect(t).not.toContain(SEGMENT_RISK.options.label);
  });

  it("does not name one segment as THE segment", () => {
    render(<ListingCard listing={listing} />);
    const t = (screen.getByTestId("card-risk-band").textContent ?? "").toLowerCase();
    for (const seg of ["cash", "futures", "options"]) {
      expect(t).not.toContain(seg);
    }
  });

  it("the label states a RANGE, not a value", () => {
    expect(CARD_RISK_BAND_LABEL).toMatch(/LOW.{0,3}HIGH/);
    expect(CARD_RISK_BAND_LABEL).toMatch(/by segment/i);
  });

  it("renders no RiskChip on the card (that would be a claim)", () => {
    render(<ListingCard listing={listing} />);
    for (const seg of ["cash", "futures", "options"]) {
      expect(screen.queryByTestId(`risk-chip-${seg}`)).toBeNull();
    }
  });

  it("is identical for every listing — it cannot vary per strategy", () => {
    const { container: a } = render(<ListingCard listing={listing} />);
    const { container: b } = render(
      <ListingCard listing={{ ...listing, id: "l2", tags: ["options"] }} />);
    const txt = (c: HTMLElement) =>
      c.querySelector('[data-testid="card-risk-band"]')?.textContent;
    expect(txt(a)).toBe(txt(b));
  });
});
