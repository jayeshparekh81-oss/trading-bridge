/**
 * /strategies/templates/[slug] — explainer page rendering test.
 *
 * Confirms:
 *   - For a known explainer slug, the page renders all 9 sections
 *     (scores, what-it-does, best/worst, mistakes, returns + disclaimer,
 *     example trade, follow-ups).
 *   - For an unknown slug, the page renders the "no explainer yet"
 *     fallback (not a 404).
 *   - Bilingual rendering: by default Hinglish (matches /help and
 *     /indicators behaviour); after writing "en" to localStorage the
 *     page renders English copy.
 *   - Follow-up links resolve to /strategies/templates/<slug>.
 *
 * No backend calls; pure content render. The page reads from the
 * static explainer registry imported at module load.
 */

import { render, screen, act } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";

import ExplainerPage from "@/app/(dashboard)/strategies/templates/[slug]/page";
import { LS_KEY_LANG } from "@/components/help/LangToggle";

// next/link — render as plain anchor so we can read href.
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    "data-testid"?: string;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  window.localStorage.clear();
});

const renderPage = async (slug: string) => {
  // The page is a client component that uses React.use() on a
  // Promise<{slug}>. Pass a resolved promise.
  const params = Promise.resolve({ slug });
  // Wrap render in act to allow the use() suspense to settle.
  await act(async () => {
    render(<ExplainerPage params={params} />);
  });
};

describe("StrategyTemplateExplainerPage", () => {
  it("renders a complete explainer for a known slug", async () => {
    await renderPage("ema-crossover-9-21");

    // Page shell
    expect(screen.getByTestId("explainer-page")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-page")).toHaveAttribute(
      "data-slug",
      "ema-crossover-9-21",
    );

    // Body sections
    expect(screen.getByTestId("explainer-body")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-difficulty")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-capital-eff")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-what-it-does")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-best-conditions")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-worst-conditions")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-mistakes")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-returns")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-disclaimer")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-example")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-followups")).toBeInTheDocument();

    // Example trade fields are populated
    expect(screen.getByTestId("explainer-example-symbol").textContent).toBeTruthy();
    expect(screen.getByTestId("explainer-example-entry").textContent).toBeTruthy();
    expect(screen.getByTestId("explainer-example-exit").textContent).toBeTruthy();
    expect(screen.getByTestId("explainer-example-pnl").textContent).toBeTruthy();

    // At least one mistake renders
    expect(screen.getByTestId("explainer-mistake-0")).toBeInTheDocument();
  });

  it("renders the missing-explainer fallback for an unknown slug", async () => {
    await renderPage("does-not-exist-and-will-never");

    expect(screen.getByTestId("explainer-missing")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-missing")).toHaveAttribute(
      "data-slug",
      "does-not-exist-and-will-never",
    );
    // No body section should render
    expect(screen.queryByTestId("explainer-body")).not.toBeInTheDocument();
    // Back link is present
    expect(screen.getByTestId("explainer-missing-back")).toHaveAttribute(
      "href",
      "/strategies/templates",
    );
  });

  it("renders multiple known slugs without crashing", async () => {
    const slugs = [
      "rsi-oversold-bounce",
      "bb-mean-reversion",
      "macd-trend-signal",
      "supertrend-rider",
      "orb-15min",
    ];
    for (const slug of slugs) {
      const params = Promise.resolve({ slug });
      let captured: { unmount: () => void } | null = null;
      await act(async () => {
        captured = render(<ExplainerPage params={params} />);
      });
      expect(screen.getByTestId("explainer-page")).toHaveAttribute(
        "data-slug",
        slug,
      );
      (captured as { unmount: () => void } | null)?.unmount();
    }
  });

  it("respects the tradetri_lang localStorage key for English render", async () => {
    window.localStorage.setItem(LS_KEY_LANG, "en");
    await renderPage("ema-crossover-9-21");

    // English label "Common mistakes" should appear (not the HI form)
    expect(
      screen.getByRole("heading", { name: /common mistakes/i }),
    ).toBeInTheDocument();
  });

  it("renders follow-up strategy links pointing back at /strategies/templates/<slug>", async () => {
    await renderPage("ema-crossover-9-21");

    const followUpsContainer = screen.getByTestId("explainer-followups");
    const anchors = followUpsContainer.querySelectorAll("a[href]");
    expect(anchors.length).toBeGreaterThan(0);
    anchors.forEach((a) => {
      const href = a.getAttribute("href");
      expect(href).toMatch(/^\/strategies\/templates\/[a-z0-9-]+$/);
    });
  });
});
