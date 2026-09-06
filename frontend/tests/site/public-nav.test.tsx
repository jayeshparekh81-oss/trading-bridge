/**
 * ONE SITE — items 3 + 4: the public nav shrinks to Home · Proof · Pricing,
 * About/Contact live in the footer, a logged-in visitor sees ONE "App kholo →"
 * on every public page, and public + app render the same header shell.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const authState: { current: { user: unknown; isLoading: boolean } } = { current: { user: null, isLoading: false } };
vi.mock("@/lib/auth", () => ({ useAuth: () => authState.current }));
vi.mock("@/components/logo", () => ({
  Logo: ({ variant, width, height }: { variant: string; width?: number; height?: number }) => <span data-testid={`logo-${variant}`} data-w={width} data-h={height} />,
}));
vi.mock("framer-motion", () => ({
  motion: { div: ({ children, className, ...rest }: React.PropsWithChildren<{ className?: string; [k: string]: unknown }>) => <div className={className} data-testid={rest["data-testid"] as string | undefined}>{children}</div> },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/" }));
vi.mock("@/components/dashboard/mobile-drawer", () => ({ MobileDrawer: () => <button data-testid="mobile-drawer-trigger" /> }));
vi.mock("@/lib/theme-context", () => ({ useCustomTheme: () => ({ theme: "t", setTheme: vi.fn(), font: "f", setFont: vi.fn(), mode: "dark", setMode: vi.fn() }) }));
vi.mock("@/lib/themes", () => ({ themes: [] }));
vi.mock("@/lib/fonts", () => ({ fontPairs: [] }));
vi.mock("@/hooks/useOnboarding", () => ({ triggerOnboardingRestart: vi.fn() }));

import PublicLayout from "@/app/(public)/layout";
import { PUBLIC_NAV, PUBLIC_FOOTER_COLS } from "@/lib/public-nav";
import { TopBar } from "@/components/dashboard/top-bar";
import { HEADER_SHELL_TOKENS, HEADER_LOGO } from "@/components/site/header-shell";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

function mountPublic(user: unknown = null) {
  authState.current = { user, isLoading: false };
  return render(
    <PublicLayout>
      <p>page</p>
    </PublicLayout>,
  );
}

describe("the public nav is a shop window", () => {
  it("is exactly Home · Proof · Pricing", () => {
    expect(PUBLIC_NAV.map((l) => l.label)).toEqual(["Home", "Proof", "Pricing"]);
    expect(PUBLIC_NAV.map((l) => l.href)).toEqual(["/home", "/showcase", "/pricing"]);
    mountPublic();
    const nav = screen.getByTestId("public-nav");
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual(["Home", "Proof", "Pricing"]);
  });

  it("About and Contact moved to the footer (the routes still exist)", () => {
    mountPublic();
    const nav = screen.getByTestId("public-nav");
    expect(within(nav).queryByText("About")).toBeNull();
    expect(within(nav).queryByText("Contact")).toBeNull();
    const footer = screen.getByTestId("public-footer");
    expect(within(footer).getByText("About").closest("a")?.getAttribute("href")).toBe("/about");
    expect(within(footer).getByText("Contact").closest("a")?.getAttribute("href")).toBe("/contact");
    expect(PUBLIC_FOOTER_COLS.flatMap((c) => c.links.map((l) => l.href))).toEqual(expect.arrayContaining(["/about", "/contact", "/showcase", "/pricing", "/terms", "/privacy", "/disclaimer", "/sebi"]));
  });

  it("the old nav words are gone from the header", () => {
    mountPublic();
    const header = screen.getByTestId("public-header");
    expect(header.textContent).not.toMatch(/Track Record|Features/);
  });
});

describe("logged out vs logged in", () => {
  it("logged out: Login + Start Free", () => {
    mountPublic(null);
    expect(screen.getByTestId("public-login").getAttribute("href")).toBe("/login");
    expect(screen.getByTestId("public-start-free").getAttribute("href")).toBe("/register");
    expect(screen.queryByTestId("public-open-app")).toBeNull();
  });

  it('logged in: ONE "App kholo →" that opens the app, no Login / Start Free', () => {
    mountPublic({ id: "u1" });
    const open = screen.getByTestId("public-open-app");
    expect(open.textContent).toContain("App kholo");
    expect(open.getAttribute("href")).toBe("/");
    expect(screen.queryByTestId("public-login")).toBeNull();
    expect(screen.queryByTestId("public-start-free")).toBeNull();
  });

  it("the mobile menu swaps the same way", () => {
    mountPublic({ id: "u1" });
    fireEvent.click(screen.getByTestId("public-menu"));
    const menu = screen.getByTestId("public-mobile-menu");
    expect(within(menu).getByTestId("public-open-app")).toBeInTheDocument();
    expect(within(menu).queryByTestId("public-login")).toBeNull();
    expect(within(menu).getAllByRole("link").map((a) => a.textContent?.trim())).toEqual(expect.arrayContaining(["Home", "Proof", "Pricing"]));
  });
});

describe("ONE FACE: public and app share the header shell", () => {
  it("both headers are the shared HeaderShell with identical tokens", () => {
    mountPublic();
    const pub = screen.getByTestId("public-header");
    render(<TopBar userName="Test User" />);
    const app = screen.getByTestId("app-header");
    for (const el of [pub, app]) {
      expect(el.getAttribute("data-header-shell")).toBe("v1");
      for (const token of HEADER_SHELL_TOKENS.split(" ")) expect(el.classList.contains(token), token).toBe(true);
    }
  });

  it("the public logo is the app's logo (same sizes)", () => {
    mountPublic();
    const header = screen.getByTestId("public-header");
    expect(within(header).getByTestId("logo-icon").getAttribute("data-w")).toBe(String(HEADER_LOGO.icon));
    expect(within(header).getByTestId("logo-wordmark").getAttribute("data-h")).toBe(String(HEADER_LOGO.wordmark));
  });

  it("neither header hand-rolls its own <header> any more", () => {
    for (const p of ["src/app/(public)/layout.tsx", "src/components/dashboard/top-bar.tsx"]) {
      const src = read(p);
      expect(src, p).toContain("@/components/site/header-shell");
      expect(src, p).not.toMatch(/<header\b/);
    }
  });
});
