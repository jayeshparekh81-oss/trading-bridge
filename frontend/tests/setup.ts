/**
 * Global Vitest setup — runs once before any test file.
 *
 *   - ``@testing-library/jest-dom`` adds DOM-aware matchers
 *     (``toBeInTheDocument``, ``toHaveAttribute``, etc.).
 *   - ``ResizeObserver`` is polyfilled because jsdom doesn't ship
 *     it but the chart component depends on it.
 *   - ``WebSocket`` is stubbed at the global level so the WS hook
 *     can construct fake instances without hitting the network.
 */

import "@testing-library/jest-dom/vitest";

// ── ResizeObserver polyfill ───────────────────────────────────────────

class ResizeObserverPolyfill {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver =
    ResizeObserverPolyfill as unknown as typeof ResizeObserver;
}

// ── matchMedia polyfill (Tailwind + framer-motion occasionally probe) ─

if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (() =>
    ({
      matches: false,
      media: "",
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as unknown as typeof window.matchMedia;
}
