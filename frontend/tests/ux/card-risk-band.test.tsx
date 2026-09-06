/**
 * STEP 5 — risk on the CARD, without a claim we can't back.
 *
 * The bare marketplace card is retired; the ONE strategy card renders on
 * every surface. For a listing the showcase knows, the segment IS known
 * (futures) and the chip is truthful. For any other listing we do NOT know
 * the segment (instrument_type is not exposed on ListingRead) — the card
 * shows the RANGE and points at the legend, never a per-strategy band.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: null, isLoading: false }) }));
vi.mock("@/components/charts/equity-curve", () => ({ EquityCurve: () => <div /> }));

import { StrategyCard, unprovenItem } from "@/components/strategy/strategy-card";
import { CARD_RISK_BAND_HINT, CARD_RISK_BAND_LABEL, SEGMENT_RISK } from "@/lib/risk-labels";
import { ITEM, DETAIL, LIVE } from "../site/fixtures";

const listing = { id: "l1", price_inr: 999, subscriber_count: 12, rating_avg: 4.5, rating_count: 8 };
const mountUnproven = (id = "l1", title = "Someone's strategy") =>
  render(<StrategyCard item={unprovenItem(id, title)} listing={{ ...listing, id }} surface="app" layout="compact" unproven />);

describe("risk band is on the (unproven) card", () => {
  it("renders", () => {
    mountUnproven();
    expect(screen.getByTestId("card-risk-band")).toBeInTheDocument();
  });

  it("shows the range, and points at the segment", () => {
    mountUnproven();
    const t = screen.getByTestId("card-risk-band").textContent ?? "";
    expect(t).toContain(CARD_RISK_BAND_LABEL);
    expect(t).toMatch(/by segment/i);
  });

  it("carries the explanatory hint", () => {
    mountUnproven();
    expect(screen.getByTestId("card-risk-band").getAttribute("title")).toBe(CARD_RISK_BAND_HINT);
  });
});

// ═══════════════════════════════════════════════════════════════════
// ⚠️ THE HONESTY RULE — no per-strategy claim we cannot back
// ═══════════════════════════════════════════════════════════════════
describe("an unproven card must NOT claim a per-strategy band", () => {
  it("never shows a single specific segment band", () => {
    mountUnproven();
    const t = screen.getByTestId("card-risk-band").textContent ?? "";
    expect(t).not.toContain(SEGMENT_RISK.cash.label);
    expect(t).not.toContain(SEGMENT_RISK.futures.label);
    expect(t).not.toContain(SEGMENT_RISK.options.label);
  });

  it("does not name one segment as THE segment", () => {
    mountUnproven();
    const t = (screen.getByTestId("card-risk-band").textContent ?? "").toLowerCase();
    for (const seg of ["cash", "futures", "options"]) expect(t).not.toContain(seg);
  });

  it("the label states a RANGE, not a value", () => {
    expect(CARD_RISK_BAND_LABEL).toMatch(/LOW.{0,3}HIGH/);
    expect(CARD_RISK_BAND_LABEL).toMatch(/by segment/i);
  });

  it("renders no RiskChip (that would be a claim)", () => {
    mountUnproven();
    for (const seg of ["cash", "futures", "options"]) expect(screen.queryByTestId(`risk-chip-${seg}`)).toBeNull();
  });

  it("is identical for every unproven listing — it cannot vary per strategy", () => {
    const { container: a } = mountUnproven("l1");
    const { container: b } = mountUnproven("l2", "Other");
    const txt = (c: HTMLElement) => c.querySelector('[data-testid="card-risk-band"]')?.textContent;
    expect(txt(a)).toBe(txt(b));
  });
});

describe("a showcase-backed card states the segment it actually knows", () => {
  it("futures chip + the editorial note, no range band", () => {
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="app" layout="compact" />);
    expect(screen.getByTestId("risk-chip-futures")).toBeInTheDocument();
    expect(screen.queryByTestId("card-risk-band")).toBeNull();
  });
});
