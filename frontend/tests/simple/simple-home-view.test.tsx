/** C7/C8: the Level home — tiles link where they say, the hero lands, unlocks announce. */
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
import { TILE_ROUTE, tilesForLevel } from "@/lib/simple/level";

const base = {
  lang: "hinglish" as const,
  name: "Ramesh",
  justUnlocked: null,
  brokerConnected: false,
  strategyRunning: false,
  learningMode: true,
  signalsToday: 0,
  latestSignal: null,
  signalIsNew: false,
  lesson: { title: "Stop-loss kya hota hai?", body: "…", href: "/help" },
  unlock: null,
  nextHint: null,
  locked: [],
  progress: { done: 1, total: 4, next: null },
  onOpenPro: () => {},
};

describe("SimpleHomeView", () => {
  it("Level 1: exactly the four tiles, each linking to its surface", () => {
    render(<SimpleHomeView {...base} level={1} tiles={tilesForLevel(1)} />);
    const tiles = screen.getByTestId("tiles").querySelectorAll('a[data-testid^="tile-"]');
    expect(tiles).toHaveLength(4);
    for (const id of ["strategy", "broker", "signals", "help"] as const) {
      expect(screen.getByTestId(`tile-${id}`)).toHaveAttribute("href", TILE_ROUTE[id]);
    }
    expect(screen.getByTestId("learning-mode")).toBeInTheDocument();
    expect(screen.getByTestId("lesson-card")).toBeInTheDocument();
    // The hero slot is always there; with no signal yet it says so, and shows no price.
    expect(screen.getByTestId("hero-signal")).toHaveTextContent(/koi signal nahi/i);
    expect(screen.getByTestId("hero-signal")).not.toHaveTextContent("₹");
  });

  it("Level 3: seven tiles including build + learn", () => {
    render(<SimpleHomeView {...base} level={3} tiles={tilesForLevel(3)} />);
    expect(screen.getByTestId("tiles").querySelectorAll('a[data-testid^="tile-"]')).toHaveLength(7);
    expect(screen.getByTestId("tile-build")).toHaveAttribute("href", "/strategies/new/beginner");
    expect(screen.getByTestId("tile-learn")).toHaveAttribute("href", "/indicators");
  });

  it("the hero moment: a landed signal shows symbol, side and price", () => {
    render(
      <SimpleHomeView
        {...base}
        level={2}
        tiles={tilesForLevel(2)}
        signalsToday={1}
        latestSignal={{ symbol: "BSE", sideLabel: "Kharida", price: "3,415.80", timeLabel: "13:15" }}
        signalIsNew
      />,
    );
    const hero = screen.getByTestId("hero-signal");
    expect(hero).toHaveTextContent("BSE");
    expect(hero).toHaveTextContent("Kharida");
    expect(hero).toHaveTextContent("3,415.80");
  });

  it("an unlock is announced with its CTA, the optional tour, and a dismiss", () => {
    const onDismiss = vi.fn();
    const onTour = vi.fn();
    render(
      <SimpleHomeView
        {...base}
        level={2}
        tiles={tilesForLevel(2)}
        justUnlocked="templates"
        unlock={{ level: 2, why: "Templates dekho", href: "/strategies/templates", onDismiss, secondary: { label: "2 minute ka tour", onClick: onTour } }}
      />,
    );
    const card = screen.getByTestId("unlock-card");
    expect(card).toHaveTextContent("Templates dekho");
    expect(card.querySelector('a[href="/strategies/templates"]')).not.toBeNull();
    fireEvent.click(screen.getByTestId("unlock-secondary"));
    expect(onTour).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("Baad mein"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("locked levels are VISIBLE: greyed, 🔒, one line of what opens them; the Pro tile opens Pro", () => {
    const onOpenPro = vi.fn();
    render(
      <SimpleHomeView
        {...base}
        level={1}
        tiles={tilesForLevel(1)}
        onOpenPro={onOpenPro}
        locked={[
          { id: "templates", title: "Templates dekho", hint: "Broker jodo + pehla signal dekho, phir yeh khulega" },
          { id: "build", title: "Apni strategy banao", hint: "Ek template try karo, phir yeh khulega" },
          { id: "pro", title: "Pro mode (poora menu)", hint: "Ya abhi kholo →" },
        ]}
        progress={{ done: 1, total: 4, next: "Broker jodo" }}
      />,
    );
    expect(screen.getByTestId("locked-templates")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("locked-templates")).toHaveTextContent("🔒 Templates dekho");
    expect(screen.getByTestId("locked-hint-templates")).toHaveTextContent("Broker jodo + pehla signal dekho, phir yeh khulega");
    expect(screen.getByTestId("locked-hint-build")).toHaveTextContent("Ek template try karo, phir yeh khulega");
    // locked tiles are not links — nothing to tap into a gate
    expect(screen.getByTestId("locked-templates").tagName).toBe("DIV");
    // the Pro tile IS tappable
    fireEvent.click(screen.getByTestId("locked-pro"));
    expect(onOpenPro).toHaveBeenCalledTimes(1);
    // the journey line
    expect(screen.getByTestId("progress-line")).toHaveTextContent("Aapka safar: 1 / 4 kadam");
    expect(screen.getByTestId("progress-line")).toHaveTextContent("Agla: Broker jodo");
    // the quiet Pro entry at the bottom of the home, one tap
    const entry = screen.getByTestId("pro-entry");
    expect(entry).toHaveTextContent("Sab kuch dekhna hai? Pro mode kholo →");
    expect(entry).toHaveTextContent("Poora menu: charts, builders, analytics");
    fireEvent.click(entry);
    expect(onOpenPro).toHaveBeenCalledTimes(2);
  });
});
