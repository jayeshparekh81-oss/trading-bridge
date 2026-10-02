import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { SiteFooter } from "@/components/compliance/SiteFooter";
import { CHOSEN_KEY, LanguageProvider, STORAGE_KEY } from "@/contexts/LanguageContext";
import { FOOTER_COPY } from "@/lib/compliance/disclaimer-text";

describe("SiteFooter", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  // FLIPPED FORWARD 2 Oct 2026 (the founder's language ruling, item 1: DEFAULT = ENGLISH for everyone).
  // Original: it("renders Hindi disclaimer + CTA by default (no localStorage)") expecting data-lang "hi" +
  // FOOTER_COPY.hi — that default is the live defect he found (an English page with a Hinglish footer).
  it("renders the ENGLISH disclaimer + CTA by default (no storage, no provider) — the SSR shape", async () => {
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    const footer = screen.getByTestId("site-footer");
    expect(footer).toHaveAttribute("data-lang", "en");
    expect(screen.getByTestId("site-footer-disclaimer")).toHaveTextContent(
      FOOTER_COPY.en.slice(0, 30),
    );
    expect(screen.getByTestId("site-footer-cta")).toHaveTextContent(
      FOOTER_COPY.cta_en,
    );
  });

  it("renders the Hinglish copy ONLY when Hinglish is the explicit choice (through the provider)", async () => {
    window.localStorage.setItem(STORAGE_KEY, "hinglish");
    window.localStorage.setItem(CHOSEN_KEY, "1");
    render(<LanguageProvider><SiteFooter /></LanguageProvider>);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("site-footer")).toHaveAttribute("data-lang", "hi");
    expect(screen.getByTestId("site-footer-disclaimer")).toHaveTextContent(FOOTER_COPY.hi.slice(0, 30));
  });

  it("a stale tradetri_lang='hi' on the device (no explicit choice) can no longer flip the footer — the live defect", async () => {
    window.localStorage.setItem("tradetri_lang", "hi");
    render(<LanguageProvider><SiteFooter /></LanguageProvider>);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("site-footer")).toHaveAttribute("data-lang", "en");
    expect(screen.getByTestId("site-footer-disclaimer")).toHaveTextContent(FOOTER_COPY.en.slice(0, 30));
  });

  it("हिन्दी / ગુજરાતી chosen → the legal strip has no twin there, so it renders WHOLE in English (never mixed)", async () => {
    for (const l of ["hi", "gu"]) {
      window.localStorage.setItem(STORAGE_KEY, l);
      window.localStorage.setItem(CHOSEN_KEY, "1");
      const r = render(<LanguageProvider><SiteFooter /></LanguageProvider>);
      await act(async () => {
        await Promise.resolve();
      });
      expect(screen.getByTestId("site-footer")).toHaveAttribute("data-lang", "en");
      r.unmount();
    }
  });

  it("renders English copy when tradetri_lang='en' in localStorage", async () => {
    window.localStorage.setItem("tradetri_lang", "en");
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("site-footer")).toHaveAttribute(
      "data-lang",
      "en",
    );
    expect(screen.getByTestId("site-footer-disclaimer")).toHaveTextContent(
      FOOTER_COPY.en.slice(0, 30),
    );
    expect(screen.getByTestId("site-footer-cta")).toHaveTextContent(
      FOOTER_COPY.cta_en,
    );
  });

  it("CTA link points at the PUBLIC /disclaimer when nobody is logged in (no login bounce)", async () => {
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    const cta = screen.getByTestId("site-footer-cta");
    expect(cta).toHaveAttribute("href", "/disclaimer");
  });

  it("CTA link points at the in-app /compliance/legal for a logged-in user", async () => {
    const auth = await import("@/lib/auth");
    const spy = vi.spyOn(auth, "useAuthOptional").mockReturnValue({ user: { id: "u1" } } as never);
    try {
      render(<SiteFooter />);
      await act(async () => {
        await Promise.resolve();
      });
      expect(screen.getByTestId("site-footer-cta")).toHaveAttribute("href", "/compliance/legal");
    } finally {
      spy.mockRestore();
    }
  });

  // FLIPPED FORWARD 2 Oct 2026: original expected "hi" ("falls back to 'hi' when localStorage holds an
  // unsupported value") — the fallback is English now, and the legacy key is not read at all.
  it("falls back to 'en' when localStorage holds an unsupported value", async () => {
    window.localStorage.setItem("tradetri_lang", "fr");
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("site-footer")).toHaveAttribute(
      "data-lang",
      "en",
    );
  });
});
