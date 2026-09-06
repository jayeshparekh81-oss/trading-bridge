/**
 * ONE SITE, NOT TWO — item 1: ONE STRATEGY COMPONENT.
 *
 * The public Track Record and the app's Marketplace/detail must render the
 * SAME card from the SAME fields. A number that could differ between the two
 * surfaces is a bug — so these tests render both surfaces from one fixture
 * and compare the printed strings, and pin every consumer to the one file.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { ITEM, DETAIL, LIVE, LISTING_ID } from "./fixtures";

const authState: { current: { user: unknown; isLoading: boolean } } = { current: { user: null, isLoading: false } };
vi.mock("@/lib/auth", () => ({ useAuth: () => authState.current }));
vi.mock("@/components/charts/equity-curve", () => ({ EquityCurve: () => <div data-testid="equity-curve" /> }));

import { StrategyCard, unprovenItem, fmt, liveLineFor, VERIFICATION_PERIOD_NOTE } from "@/components/strategy/strategy-card";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
function walk(dir: string, out: string[] = []): string[] {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(f)) out.push(p);
  }
  return out;
}

const FIELDS = ["strategy-name", "stat-win-value", "stat-avg-value", "stat-pf-value", "stat-dd-value", "stat-trades-value", "strategy-dd-value"] as const;
function snapshot(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const id of FIELDS) out[id] = screen.getByTestId(id).textContent ?? "";
  out["live"] = screen.getByTestId("strategy-live-line").textContent ?? "";
  out["badge"] = screen.getByText(ITEM.live_status.label).textContent ?? "";
  return out;
}

describe("both surfaces render from the ONE component", () => {
  it("public Track Record, in-app Marketplace, detail and StrategyDetail all import the one card", () => {
    const CARD = "@/components/strategy/strategy-card";
    expect(read("src/app/(public)/showcase/page.tsx")).toContain(CARD);
    // The marketplace page renders the card through the one listing→card adapter (Simple picker + Pro grid share it).
    expect(read("src/app/(dashboard)/marketplace/page.tsx")).toContain("@/components/simple/strategy-pick");
    expect(read("src/components/simple/strategy-pick.tsx")).toContain(CARD);
    expect(read("src/components/strategy/strategy-detail.tsx")).toContain(CARD);
    expect(read("src/app/(dashboard)/marketplace/[id]/page.tsx")).toContain("@/components/strategy/strategy-detail");
  });

  it("both surfaces read the ONE data hook", () => {
    for (const p of ["src/app/(public)/showcase/page.tsx", "src/app/(dashboard)/marketplace/page.tsx", "src/components/simple/strategy-pick.tsx", "src/app/(dashboard)/marketplace/[id]/page.tsx"]) {
      expect(read(p), p).toContain("@/hooks/useShowcase");
    }
  });

  it("the bare marketplace card and the old listing header are retired everywhere", () => {
    const files = walk(join(process.cwd(), "src"));
    for (const f of files) {
      const src = readFileSync(f, "utf8");
      expect(src, f).not.toContain("marketplace/listing-card");
      expect(src, f).not.toContain("listing-detail-header");
      expect(src, f).not.toContain("showcase/subscribe-cta");
    }
  });
});

describe("identical numbers, public vs app", () => {
  it("public full card and app full card print the same fields", () => {
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" layout="full" />);
    const pub = snapshot();
    cleanup();
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="app" layout="full" listing={{ id: LISTING_ID, price_inr: 999, subscriber_count: 3, rating_avg: null, rating_count: 0 }} />);
    const app = snapshot();
    for (const k of Object.keys(pub)) expect(app[k], k).toBe(pub[k]);
  });

  it("the Pro compact card prints the same headline numbers as the public card", () => {
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" layout="full" />);
    const pub = snapshot();
    cleanup();
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="app" layout="compact" href="/marketplace/x" />);
    for (const id of FIELDS) expect(screen.getByTestId(id).textContent, id).toBe(pub[id]);
    expect(screen.getByTestId("strategy-open").getAttribute("href")).toBe("/marketplace/x");
  });

  it("before detail loads the headline (list) numbers are the same values the detail prints", () => {
    render(<StrategyCard item={ITEM} live={LIVE} surface="public" layout="full" />);
    expect(screen.getByTestId("stat-win-value").textContent).toBe(fmt.pct1(DETAIL.backtest.aggregate.all.win_rate_pct));
    expect(screen.getByTestId("stat-dd-value").textContent).toBe(fmt.dd(DETAIL.backtest.aggregate.all.max_drawdown_pct));
  });

  it("drawdown is shown as the negative the API returns, never flipped", () => {
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="app" layout="full" />);
    expect(screen.getByTestId("strategy-dd-value").textContent).toBe("-11.13%");
  });
});

describe("the live-record line is honest on both surfaces", () => {
  it("verification period = the founder's exact wording", () => {
    expect(liveLineFor(LIVE).em).toBe(VERIFICATION_PERIOD_NOTE);
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" />);
    expect(screen.getByTestId("strategy-live-record").textContent).toContain(VERIFICATION_PERIOD_NOTE);
  });

  it('says "Verified" only once reconciled trades are published', () => {
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" />);
    expect(screen.getByTestId("strategy-live-heading-text").textContent).toBe("Live record");
    cleanup();
    render(<StrategyCard item={ITEM} detail={DETAIL} live={{ status: "tracking_active", reconciled_trades: 3, note: "" }} surface="public" />);
    expect(screen.getByTestId("strategy-live-heading-text").textContent).toBe("Verified live record");
  });

  it("paper strategies say backtest-only, no invented live numbers", () => {
    const line = liveLineFor({ status: "paper_no_live", note: "" });
    expect(line.em).toMatch(/Backtest-only/);
    expect(line.sub).toMatch(/No real-money results exist/);
  });
});

describe("the public CTA (subscribe lives in the app)", () => {
  it("logged out → Start Free, registering with the way back to this strategy", () => {
    authState.current = { user: null, isLoading: false };
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" />);
    const cta = screen.getByTestId("showcase-subscribe");
    expect(cta.textContent).toContain("Start Free");
    expect(cta.getAttribute("href")).toBe(`/register?next=${encodeURIComponent(`/marketplace/${LISTING_ID}`)}`);
  });

  it('logged in → "App mein kholo" straight to the in-app strategy', () => {
    authState.current = { user: { id: "u1" }, isLoading: false };
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" />);
    const cta = screen.getByTestId("showcase-subscribe");
    expect(cta.textContent).toContain("App mein kholo");
    expect(cta.getAttribute("href")).toBe(`/marketplace/${LISTING_ID}`);
  });

  it("no listing → no CTA at all (nothing to subscribe to)", () => {
    authState.current = { user: null, isLoading: false };
    render(<StrategyCard item={ITEM} detail={DETAIL} live={{ status: "paper_no_live", note: "", listing_id: null }} surface="public" />);
    expect(screen.queryByTestId("showcase-subscribe")).toBeNull();
  });

  it("the public card never renders a Subscribe control", () => {
    authState.current = { user: { id: "u1" }, isLoading: false };
    render(<StrategyCard item={ITEM} detail={DETAIL} live={LIVE} surface="public" />);
    expect(screen.queryByText(/^Subscribe/)).toBeNull();
  });
});

describe("a listing the showcase does not know", () => {
  it("renders the same card, honestly empty — no numbers, no segment claim", () => {
    render(<StrategyCard item={unprovenItem("l9", "Someone's strategy")} listing={{ id: "l9", price_inr: 0, subscriber_count: 0, rating_avg: null, rating_count: 0 }} surface="app" unproven />);
    expect(screen.getByTestId("strategy-unproven")).toBeInTheDocument();
    expect(screen.queryByTestId("stat-win-value")).toBeNull();
    expect(screen.queryByTestId("certified-metrics")).toBeNull();
    expect(screen.getByTestId("card-risk-band")).toBeInTheDocument();
    for (const seg of ["cash", "futures", "options"]) expect(screen.queryByTestId(`risk-chip-${seg}`)).toBeNull();
    expect(screen.getByTestId("strategy-live-record").textContent).toMatch(/No verified record yet/);
  });
});

describe("the mask holds", () => {
  it("the card and the hook name no instrument and no strategy uuid", () => {
    for (const p of ["src/components/strategy/strategy-card.tsx", "src/hooks/useShowcase.ts", "src/app/(public)/showcase/page.tsx"]) {
      const src = read(p).replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
      expect(src, p).not.toMatch(/\bBSE\b|NIFTY|BANKNIFTY|89423ecc|0252e82c/);
      expect(src, p).not.toMatch(/"s1"|'s1'/);
    }
  });
});
