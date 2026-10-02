/**
 * While public signup is CLOSED (lib/signup-status.ts, fail closed), the two CTAs the 2 Oct voice pass
 * missed — the public top-bar button and the Showcase card's button — must read the LOGIN wording,
 * never an invitation to a form the server refuses; and while OPEN they read like the Home CTA
 * ("Shuru karo (free)"). The href swap already existed; this pins the WORDS with it.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const signup = { current: "closed" as "open" | "closed" | "checking" };
vi.mock("@/hooks/useSignupOpen", () => ({ useSignupOpen: () => signup.current }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: null, isLoading: false, logout: vi.fn() }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/showcase",
  useSearchParams: () => new URLSearchParams(),
}));

import { PublicStrategyCta } from "@/components/strategy/strategy-card";
import { SignupOrLogin } from "@/components/site/signup-or-login";

describe("the Showcase card CTA", () => {
  it("CLOSED → the login wording, and the href goes to /login with the way back", () => {
    signup.current = "closed";
    render(<PublicStrategyCta listingId="abc" />);
    const cta = screen.getByTestId("showcase-subscribe");
    expect(cta.textContent).toContain("Login karo (naye account abhi band)");
    expect(cta.textContent).not.toMatch(/Shuru karo|Start Free/);
    expect(cta.getAttribute("href")).toBe("/login?next=%2Fmarketplace%2Fabc");
  });
  it("OPEN → Shuru karo (free), the same words as the Home CTA, to /register", () => {
    signup.current = "open";
    render(<PublicStrategyCta listingId="abc" />);
    const cta = screen.getByTestId("showcase-subscribe");
    expect(cta.textContent).toContain("Shuru karo (free)");
    expect(cta.getAttribute("href")).toBe("/register?next=%2Fmarketplace%2Fabc");
  });
  it("CHECKING (backend not answered yet) → fails closed to the login wording", () => {
    signup.current = "checking";
    render(<PublicStrategyCta listingId="abc" />);
    expect(screen.getByTestId("showcase-subscribe").textContent).toContain("Login karo");
  });
});

describe("the public top-bar CTA (the SignupOrLogin the layout uses)", () => {
  it("CLOSED → the closed text and a /login link; OPEN → the Hinglish Start text and /register", () => {
    signup.current = "closed";
    const a = render(<SignupOrLogin href="/register" testid="public-start-free" closedText={<>Naye account abhi band</>}>Shuru karo (free)</SignupOrLogin>);
    const closed = screen.getByTestId("public-start-free-closed");
    expect(closed.textContent).toBe("Naye account abhi band");
    expect(closed.getAttribute("href")).toBe("/login");
    a.unmount();
    signup.current = "open";
    render(<SignupOrLogin href="/register" testid="public-start-free" closedText={<>Naye account abhi band</>}>Shuru karo (free)</SignupOrLogin>);
    const open = screen.getByTestId("public-start-free");
    expect(open.textContent).toBe("Shuru karo (free)");
    expect(open.getAttribute("href")).toBe("/register");
  });
});
