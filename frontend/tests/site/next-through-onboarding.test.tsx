/**
 * ONE SITE — the public "Start Free" must LAND on the strategy the visitor
 * clicked. A new account is sent through onboarding first, so `?next=` has to
 * survive register → dashboard guard → /onboarding → finish.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { onboardingReturnPath } from "@/lib/simple/onboarding-return";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }), usePathname: () => "/onboarding", useSearchParams: () => new URLSearchParams("") }));
vi.mock("@/shared/api/client", () => ({ api: { post: vi.fn(async () => ({})), get: vi.fn(async () => ({})) }, ApiError: class extends Error {} }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ refreshUser: vi.fn(async () => {}), user: { id: "u1" } }) }));
vi.mock("@/hooks/useLadder", () => ({ useLadderOptional: () => ({ markSimpleOnboardingDone: vi.fn() }) }));
vi.mock("@/contexts/LanguageContext", () => ({ useLanguage: () => ({ lang: "hinglish", setLang: vi.fn() }) }));
vi.mock("@/lib/simple/language-sync", () => ({ SIMPLE_LANGS: [{ code: "hinglish", label: "Hinglish" }], ensureSimpleDefaultLanguage: () => {}, mirrorLanguage: () => {} }));
vi.mock("framer-motion", async () => {
  const React = await import("react");
  const strip = (p: Record<string, unknown>) => Object.fromEntries(Object.entries(p).filter(([k]) => !["initial", "animate", "exit", "transition", "variants", "whileHover", "whileTap", "layout"].includes(k)));
  const el = (tag: string) => { const C = ({ children, ...p }: React.PropsWithChildren<Record<string, unknown>>) => React.createElement(tag, strip(p), children); C.displayName = `motion.${tag}`; return C; };
  return { motion: { div: el("div"), section: el("section"), button: el("button"), p: el("p"), h1: el("h1") }, AnimatePresence: function AnimatePresence({ children }: React.PropsWithChildren) { return children; }, useReducedMotion: () => true };
});
vi.mock("@/components/logo", () => ({ Logo: function Logo() { return <span />; } }));

import { SimpleOnboarding } from "@/components/simple/simple-onboarding";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

describe("onboardingReturnPath", () => {
  it("keeps a same-site destination, drops the default and anything off-site", () => {
    expect(onboardingReturnPath("/marketplace/abc")).toBe("/marketplace/abc");
    expect(onboardingReturnPath("/")).toBeNull();
    expect(onboardingReturnPath(null)).toBeNull();
    expect(onboardingReturnPath("https://evil.example")).toBeNull();
    expect(onboardingReturnPath("//evil.example")).toBeNull();
  });
});

describe("next survives the whole way", () => {
  it("the dashboard guard sends first-timers to /onboarding WITH where they were going", () => {
    expect(read("src/app/(dashboard)/layout.tsx")).toMatch(/router\.replace\(withNext\("\/onboarding"/);
  });

  it("the onboarding page reads ?next and hands it to both flows", () => {
    const src = read("src/app/onboarding/page.tsx");
    expect(src).toMatch(/onboardingReturnPath\(useSearchParams\(\)\.get\("next"\)\)/);
    expect(src).toMatch(/<SimpleOnboarding next=\{next\}/);
    expect(src).toMatch(/router\.push\(next \?\? href\)/);
    expect(src).toMatch(/<Suspense/); // useSearchParams needs it for `next build`
  });

  it("Simple onboarding finishes on the strategy the visitor chose", async () => {
    push.mockClear();
    render(<SimpleOnboarding next="/marketplace/l1" />);
    fireEvent.click(screen.getByTestId("ob-next")); // bhasha → broker
    fireEvent.click(screen.getByTestId("ob-next")); // skip broker → strategy
    fireEvent.click(screen.getByTestId("ob-go-strategy"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/marketplace/l1"));
  });

  it('but an explicit "Broker jodo" tap still goes to brokers', async () => {
    push.mockClear();
    render(<SimpleOnboarding next="/marketplace/l1" />);
    fireEvent.click(screen.getByTestId("ob-next"));
    fireEvent.click(screen.getByTestId("ob-go-broker"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/brokers"));
  });

  it("without a next, the strategy step goes to the marketplace as before", async () => {
    push.mockClear();
    render(<SimpleOnboarding />);
    fireEvent.click(screen.getByTestId("ob-next"));
    fireEvent.click(screen.getByTestId("ob-next"));
    fireEvent.click(screen.getByTestId("ob-go-strategy"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/marketplace"));
  });
});
