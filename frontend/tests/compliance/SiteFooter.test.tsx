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
import { FOOTER_COPY } from "@/lib/compliance/disclaimer-text";

describe("SiteFooter", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders Hindi disclaimer + CTA by default (no localStorage)", async () => {
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    const footer = screen.getByTestId("site-footer");
    expect(footer).toHaveAttribute("data-lang", "hi");
    expect(screen.getByTestId("site-footer-disclaimer")).toHaveTextContent(
      FOOTER_COPY.hi.slice(0, 30),
    );
    expect(screen.getByTestId("site-footer-cta")).toHaveTextContent(
      FOOTER_COPY.cta_hi,
    );
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

  it("CTA link points at /compliance/legal", async () => {
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    const cta = screen.getByTestId("site-footer-cta");
    expect(cta).toHaveAttribute("href", "/compliance/legal");
  });

  it("falls back to 'hi' when localStorage holds an unsupported value", async () => {
    window.localStorage.setItem("tradetri_lang", "fr");
    render(<SiteFooter />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("site-footer")).toHaveAttribute(
      "data-lang",
      "hi",
    );
  });
});
