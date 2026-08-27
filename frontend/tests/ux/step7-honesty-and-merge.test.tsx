/**
 * STEP 7 — remove live falsehoods, merge the duplicate FAQ, surface /support,
 * and fix a CTA that silently did nothing.
 */

import { beforeAll, describe, it, expect, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/help",
}));

// ChatWidget -> useAlgoMitra -> useAuth. Same mock shape the existing
// marketplace tests use (tests/marketplace/subscribe-button.test.tsx).
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "trader@x.com" } }),
}));

import { ChatWidget } from "@/components/algomitra/ChatWidget";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

// jsdom has no IntersectionObserver; AnimatedNumber inside the listing header
// needs one. Stubbing it keeps the RENDER-based proof (that the false badge is
// really absent from output), which is stronger than a source grep alone.
beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    class IO {
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() { return []; }
      root = null; rootMargin = ""; thresholds = [];
    }
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
  }
});

// ═══════════════════════════════════════════════════════════════════
// 1. The "L&T Engineer Built" badge was FALSE for any other creator
// ═══════════════════════════════════════════════════════════════════
describe("no false creator attribution", () => {
  const src = read("src/components/marketplace/listing-detail-header.tsx");

  it("the hardcoded badge is gone from the component", () => {
    // It appeared on EVERY listing regardless of who created it.
    expect(src).not.toMatch(/<span[^>]*>\s*L&T Engineer Built/);
  });

  it("does not render it for an arbitrary creator", async () => {
    const { ListingDetailHeader } = await import(
      "@/components/marketplace/listing-detail-header"
    );
    render(
      <ListingDetailHeader
        listing={{
          id: "l1", title: "Someone else's strategy", description: "d",
          price_inr: 0, tags: [], status: "published",
          performance_snapshot: null, subscriber_count: 0,
          rating_avg: null, rating_count: 0, published_at: null,
          creator_id: "11111111-2222-3333-4444-555555555555",
        }}
      />,
    );
    expect(document.body.textContent).not.toContain("L&T Engineer Built");
  });

  it("still attributes honestly by creator id", async () => {
    const { ListingDetailHeader } = await import(
      "@/components/marketplace/listing-detail-header"
    );
    render(
      <ListingDetailHeader
        listing={{
          id: "l1", title: "t", description: "d", price_inr: 0, tags: [],
          status: "published", performance_snapshot: null,
          subscriber_count: 0, rating_avg: null, rating_count: 0,
          published_at: null, creator_id: "abcdef01-2222-3333-4444-555555555555",
        }}
      />,
    );
    expect(document.body.textContent).toContain("Creator ID:");
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2. Don't promise a control that does not exist
// ═══════════════════════════════════════════════════════════════════
describe("no promise of a clone feature", () => {
  it("the clone claim is gone", () => {
    const src = read("src/app/(dashboard)/strategies/new/page.tsx");
    expect(src).not.toContain("Clone one with a click");
  });
});

// ═══════════════════════════════════════════════════════════════════
// 3. FAQ merge — nothing lost
// ═══════════════════════════════════════════════════════════════════
describe("the two FAQs are merged into one", () => {
  const faq = read("src/lib/help/faq-content.ts");

  it.each([
    ["pine-import", "Pine"],
    ["transparency-ledger", "Ledger"],
    ["mobile-support", "mobile"],
    ["multi-language", "language"],
    ["ai-doctor-apply-fix", "AI Doctor"],
    ["execution-guard", "Execution Guard"],
    ["auto-priority-categories", "auto-priority"],
    ["strategy-versioning", "versioning"],
  ])("carried over: %s", (id) => {
    expect(faq).toContain(`id: "${id}"`);
  });

  it("every carried entry is bilingual, like the rest", () => {
    for (const id of ["pine-import", "transparency-ledger", "strategy-versioning"]) {
      const at = faq.indexOf(`id: "${id}"`);
      const block = faq.slice(at, at + 1600);
      expect(block).toContain("question_hi:");
      expect(block).toContain("answer_hi:");
    }
  });

  it("the ledger answer does NOT claim on-chain notarisation", () => {
    const at = faq.indexOf('id: "transparency-ledger"');
    const block = faq.slice(at, at + 1600);
    // The chain is off-chain today — the legacy copy implied more.
    expect(block).toMatch(/OFF-CHAIN/i);
    expect(block).not.toMatch(/blockchain pe commit ho (chuka|gaya)/i);
  });

  it("/support/faq is retired to a redirect, not left as a stale duplicate", () => {
    const src = read("src/app/(dashboard)/support/faq/page.tsx");
    expect(src).toContain('redirect("/help")');
    expect(src.length).toBeLessThan(1200); // no second copy of the content
  });
});

// ═══════════════════════════════════════════════════════════════════
// 4. /support is no longer orphaned
// ═══════════════════════════════════════════════════════════════════
describe("/support is reachable", () => {
  it("is in the sidebar", () => {
    expect(read("src/components/dashboard/sidebar.tsx")).toContain('href: "/support"');
  });
  it("is in the mobile drawer", () => {
    expect(read("src/components/dashboard/mobile-drawer.tsx")).toContain('href: "/support"');
  });
});

// ═══════════════════════════════════════════════════════════════════
// 5. The AlgoMitra CTA no longer no-ops when the chat is already open
// ═══════════════════════════════════════════════════════════════════
describe("Open AlgoMitra CTA", () => {
  it("dispatches an event instead of clicking a button that may not exist", () => {
    const src = read("src/app/(dashboard)/help/page.tsx");
    expect(src).toContain('new CustomEvent("algomitra:open")');
    // The old hack looked up the launcher by aria-label — unmounted while open.
    expect(src).not.toContain('button[aria-label="Open AlgoMitra chat"]');
  });

  it("the widget listens for it", () => {
    const src = read("src/components/algomitra/ChatWidget.tsx");
    expect(src).toContain('addEventListener("algomitra:open"');
    expect(src).toContain('removeEventListener("algomitra:open"');
  });

  it("the event fires even with no launcher in the DOM (the broken case)", () => {
    const heard = vi.fn();
    window.addEventListener("algomitra:open", heard);
    // No launcher rendered at all — this is exactly the already-open state.
    expect(document.querySelector('button[aria-label="Open AlgoMitra chat"]')).toBeNull();
    window.dispatchEvent(new CustomEvent("algomitra:open"));
    expect(heard).toHaveBeenCalledTimes(1);
    window.removeEventListener("algomitra:open", heard);
  });

  // The real proof. The three tests above check the two HALVES of the bridge in
  // isolation; this one checks they actually meet — render the widget, fire the
  // event the /help CTA fires, and assert the chat OPENS. Without this, a
  // renamed event on either side passes every source-level assertion above.
  it("OPENS the chat when the event fires (both halves connected)", async () => {
    render(<ChatWidget />);
    expect(screen.queryByPlaceholderText(/Bhai, message likh/i)).toBeNull();

    await act(async () => {
      window.dispatchEvent(new CustomEvent("algomitra:open"));
    });

    expect(
      await screen.findByPlaceholderText(/Bhai, message likh/i),
    ).toBeInTheDocument();
  });
});
