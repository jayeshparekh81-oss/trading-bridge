/**
 * Cuts to "signup → running" (founder's rule, 26 Sep 2026: "report the taps from signup to
 * running, and your plan to cut it"). Two built here, each proven both ways:
 *  1. Home's "Start Free" opens /start when the guided path is LIVE (its first step IS the
 *     signup), /register otherwise — never /start on the frontend flag alone.
 *  2. The "Dhan jud gaya" message carries the NEXT step ("Agla: strategy chuno").
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const live = vi.hoisted(() => ({ value: "off" as "off" | "checking" | "ready" | "not-ready" }));
// 1 Oct 2026: every signup link now asks the backend whether public signup is OPEN (fail closed —
// lib/signup-status.ts). These tests pin the OPEN-signup behaviour they were written for; the
// CLOSED behaviour is pinned in tests/site/signup-closed-and-practice.test.tsx.
vi.mock("@/hooks/useSignupOpen", () => ({ useSignupOpen: () => "open" }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => live.value }));
vi.mock("@/components/marketing/HomePricing", () => ({ HomePricing: () => null }));
vi.mock("@/components/marketing/RoadmapSection", () => ({ RoadmapSection: () => null }));
vi.mock("framer-motion", async () => {
  const React = await import("react");
  const strip = (p: Record<string, unknown>) => Object.fromEntries(Object.entries(p).filter(([k]) => !["initial", "animate", "exit", "transition", "variants", "whileHover", "whileTap", "layout"].includes(k)));
  const el = (tag: string) => { const C = ({ children, ...p }: React.PropsWithChildren<Record<string, unknown>>) => React.createElement(tag, strip(p), children); C.displayName = `motion.${tag}`; return C; };
  return { motion: { div: el("div"), section: el("section"), span: el("span"), p: el("p") }, useInView: () => true, AnimatePresence: ({ children }: React.PropsWithChildren) => children };
});

import HomePage from "@/app/(public)/home/page";

afterEach(cleanup);

const startFreeHrefs = () =>
  // 2 Oct 2026 (English default): the CTA reads "Start (free)"; Hinglish "Shuru karo (free)". Original filter: /Start Free/
  screen.getAllByRole("link").filter((a) => /Start \(free\)|Shuru karo \(free\)/.test(a.textContent ?? "")).map((a) => a.getAttribute("href"));

describe("cut 1 — Start Free opens the guided path only when it is live", () => {
  it("guided path LIVE → every Start Free goes to /start", () => {
    live.value = "ready";
    render(<HomePage />);
    const hrefs = startFreeHrefs();
    expect(hrefs.length).toBeGreaterThan(0);
    expect(new Set(hrefs)).toEqual(new Set(["/start"]));
  });
  it.each(["off", "checking", "not-ready"] as const)("guided path %s → /register, exactly as before", (v) => {
    live.value = v;
    render(<HomePage />);
    expect(new Set(startFreeHrefs())).toEqual(new Set(["/register"]));
  });
});

describe("cut 2 — the broker-joined message carries the next step", () => {
  const SRC = readFileSync(join(process.cwd(), "src/app/(dashboard)/brokers/page.tsx"), "utf8");
  it("both success messages (Broker jud gaya / Dhan jud gaya) offer 'Agla: strategy chuno' → /marketplace", () => {
    expect(SRC).toMatch(/label: "Agla: strategy chuno", onClick: \(\) => router\.push\("\/marketplace"\)/);
    expect(SRC).toMatch(/toast\.success\("Broker jud gaya!", \{ action: nextStepAction/);
    expect(SRC).toMatch(/toast\.success\("Dhan jud gaya — chart aur trading chalu\.", \{ action: nextStepAction/);
  });
});
