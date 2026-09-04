/**
 * Founder decision (2026-09-04): the AlgoMitra coaching panel starts CLOSED
 * on phones (below Tailwind md = 768px) and OPEN on desktop, unless the
 * customer has already chosen — a stored choice wins on every viewport.
 * The panel is a fixed 320px column; on a 375px phone it covered the
 * builder's goal cards.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { useAlgoMitraPanelState } from "@/hooks/use-algomitra-context";

const realMatchMedia = window.matchMedia;

function stubViewport(mobile: boolean) {
  window.matchMedia = ((query: string) =>
    ({
      matches: mobile && /max-width:\s*767px/.test(query),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as unknown as typeof window.matchMedia;
}

beforeEach(() => localStorage.removeItem("algomitra_panel_state"));
afterEach(() => { window.matchMedia = realMatchMedia; });

describe("AlgoMitra panel default by viewport", () => {
  it("🔴 phone, first run → closed (bubble), no write to storage", () => {
    stubViewport(true);
    const { result } = renderHook(() => useAlgoMitraPanelState());
    expect(result.current.isOpen).toBe(false);
    expect(localStorage.getItem("algomitra_panel_state")).toBeNull();
  });

  it("desktop, first run → open (unchanged behaviour)", () => {
    stubViewport(false);
    const { result } = renderHook(() => useAlgoMitraPanelState());
    expect(result.current.isOpen).toBe(true);
  });

  it("a stored choice wins on a phone: 'open' opens it", () => {
    stubViewport(true);
    localStorage.setItem("algomitra_panel_state", "open");
    const { result } = renderHook(() => useAlgoMitraPanelState());
    expect(result.current.isOpen).toBe(true);
  });

  it("a stored choice wins on desktop: 'closed' keeps it closed", () => {
    stubViewport(false);
    localStorage.setItem("algomitra_panel_state", "closed");
    const { result } = renderHook(() => useAlgoMitraPanelState());
    expect(result.current.isOpen).toBe(false);
  });

  it("opening on a phone persists, so the next visit shows the panel", () => {
    stubViewport(true);
    const { result } = renderHook(() => useAlgoMitraPanelState());
    act(() => result.current.open());
    expect(result.current.isOpen).toBe(true);
    expect(localStorage.getItem("algomitra_panel_state")).toBe("open");
  });

  it("the panel still renders the toggle bubble whenever it is closed", () => {
    const src = readFileSync(join(process.cwd(), "src/components/algomitra/always-on-panel.tsx"), "utf8");
    expect(src).toMatch(/\{!isOpen \? <AlgoMitraToggleButton onClick=\{open\} \/> : null\}/);
  });
});
