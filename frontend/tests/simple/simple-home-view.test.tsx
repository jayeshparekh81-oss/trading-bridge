/** The Simple home: four open tiles on top, "Aur seekhein" open tiles below, no locks anywhere. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: Record<string, unknown> & { children?: ReactNode }) => {
    const { children, ...rest } = props;
    const dom = Object.fromEntries(Object.entries(rest).filter(([k]) => /^(data-|aria-|className|href|onClick|role|id)/.test(k)));
    return <div {...dom}>{children}</div>;
  } }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
}));

import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { LEARN_TILES, MAIN_TILES, TILE_ROUTE } from "@/lib/simple/level";

const base = {
  lang: "hinglish" as const,
  name: "Ramesh",
  level: 1 as const,
  mainTiles: MAIN_TILES,
  learnTiles: LEARN_TILES,
  onLearnTap: () => {},
  onOpenPro: () => {},
  brokerConnected: false,
  strategyRunning: false,
  learningMode: true,
  signalsToday: 0,
  latestSignal: null,
  signalIsNew: false,
  lesson: { title: "Stop-loss kya hota hai?", body: "…", href: "/help" },
  progress: { done: 1, total: 4, next: "Broker jodo" },
};

describe("SimpleHomeView", () => {
  it("four open tiles on top, each linking to its surface", () => {
    render(<SimpleHomeView {...base} />);
    const tiles = screen.getByTestId("tiles").querySelectorAll('a[data-testid^="tile-"]');
    expect(tiles).toHaveLength(4);
    for (const id of MAIN_TILES) expect(screen.getByTestId(`tile-${id}`)).toHaveAttribute("href", TILE_ROUTE[id]);
    expect(screen.getByTestId("learning-mode")).toBeInTheDocument();
    expect(screen.getByTestId("lesson-card")).toBeInTheDocument();
    expect(screen.getByTestId("hero-signal")).toHaveTextContent(/koi signal nahi/i);
  });

  it("'Aur seekhein' below: Templates and Apni strategy are real links, Pro is one tap; a soft hint, no lock", () => {
    const onLearnTap = vi.fn();
    const onOpenPro = vi.fn();
    render(<SimpleHomeView {...base} onLearnTap={onLearnTap} onOpenPro={onOpenPro} />);
    const section = screen.getByTestId("learn-section");
    expect(section).toHaveTextContent("Aur seekhein");
    expect(screen.getByTestId("learn-hint")).toHaveTextContent("Pehle upar wale 4 karo, phir yeh — aaram se.");
    expect(screen.getByTestId("learn-templates")).toHaveAttribute("href", "/strategies/templates");
    expect(screen.getByTestId("learn-build")).toHaveAttribute("href", "/strategies/new/beginner");
    expect(screen.getByTestId("learn-templates").tagName).toBe("A");
    expect(screen.getByTestId("learn-build").tagName).toBe("A");
    expect(screen.getByTestId("learn-pro")).toHaveTextContent("Pro mode (poora menu)");
    // no lock, no "phir yeh khulega", no aria-disabled anywhere on the home
    expect(screen.getByTestId("simple-home").textContent).not.toMatch(/🔒|khulega/);
    expect(screen.getByTestId("simple-home").querySelector("[aria-disabled]")).toBeNull();
    // first tap reports the tile (for AlgoMitra's one line); Pro also opens Pro
    fireEvent.click(screen.getByTestId("learn-templates"));
    expect(onLearnTap).toHaveBeenCalledWith("templates");
    fireEvent.click(screen.getByTestId("learn-pro"));
    expect(onLearnTap).toHaveBeenCalledWith("pro");
    expect(onOpenPro).toHaveBeenCalledTimes(1);
  });

  it("the journey line is guidance and the quiet Pro card is one tap", () => {
    const onOpenPro = vi.fn();
    render(<SimpleHomeView {...base} onOpenPro={onOpenPro} />);
    expect(screen.getByTestId("progress-line")).toHaveTextContent("Aapka safar: 1 / 4 kadam");
    expect(screen.getByTestId("progress-line")).toHaveTextContent("Agla: Broker jodo");
    const entry = screen.getByTestId("pro-entry");
    expect(entry).toHaveTextContent("Sab kuch dekhna hai? Pro mode kholo →");
    fireEvent.click(entry);
    expect(onOpenPro).toHaveBeenCalledTimes(1);
  });

  it("the hero moment: a landed signal shows symbol, side and price", () => {
    render(<SimpleHomeView {...base} level={2} signalsToday={1} latestSignal={{ symbol: "BSE", sideLabel: "Kharida", price: "3,415.80", timeLabel: "13:15" }} signalIsNew />);
    const hero = screen.getByTestId("hero-signal");
    expect(hero).toHaveTextContent("BSE");
    expect(hero).toHaveTextContent("Kharida");
    expect(hero).toHaveTextContent("3,415.80");
  });
});
