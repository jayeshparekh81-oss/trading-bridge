/**
 * The founder's FOUR cards (26 Sep 2026, REQUIREMENTS §13 — the vehicle order):
 *   - FUTURES · CASH · OPTION BUY · SPREADS, in his build order; SPREADS carries two rows;
 *   - every locked card says exactly what it is waiting for and quotes its OWN sealed bar;
 *   - no fake numbers: a count the page cannot know renders the literal NOT MEASURED;
 *   - the STATIC board (before the backend surface is deployed) makes NO server call and is
 *     the backend's own generated snapshot, never retyped copy;
 *   - FUTURES shows the offered lots 2/4/6/8/10 and long/short/both.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

import staticJson from "@/lib/vehicle-board.static.json";
import {
  FUTURES_LOT_CHOICES,
  PICKER_CARDS,
  barLines,
  groupIntoCards,
  paperProgress,
  staticVehicleBoard,
  vehiclePickerSource,
} from "@/lib/vehicle-cards";
import type { VehicleStatus } from "@/lib/customer-vehicles";
import { NOT_MEASURED } from "@/lib/risk-labels";

const urls: Array<string | null> = [];
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    urls.push(url);
    return { data: null, isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn() };
  },
}));

import { VehiclePicker } from "@/components/marketplace/vehicle-picker";

beforeEach(() => {
  urls.length = 0;
  delete process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE;
});

describe("the four cards", () => {
  it("are FUTURES, CASH, OPTION BUY, SPREADS — in that order, SPREADS with both directions", () => {
    expect(PICKER_CARDS.map((c) => c.card)).toEqual(["FUTURES", "CASH", "OPTION_BUY", "SPREADS"]);
    expect(PICKER_CARDS[3].members).toEqual(["BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]);
    const cards = groupIntoCards(staticVehicleBoard().vehicles);
    expect(cards.map((c) => c.card)).toEqual(["FUTURES", "CASH", "OPTION_BUY", "SPREADS"]);
    expect(cards.every((c) => !c.open)).toBe(true);
  });

  it("the offered FUTURES lots are exactly 2/4/6/8/10", () => {
    expect([...FUTURES_LOT_CHOICES]).toEqual([2, 4, 6, 8, 10]);
    expect(staticJson.futures_lot_choices).toEqual([2, 4, 6, 8, 10]);
    expect(staticJson.directions).toEqual(["long", "short", "both"]);
  });

  it("a card with no visible member is not shown (live, flags OFF → FUTURES alone)", () => {
    const only = staticVehicleBoard().vehicles.map((v) => ({ ...v, visible: v.vehicle === "FUTURES" }));
    expect(groupIntoCards(only as VehicleStatus[]).map((c) => c.card)).toEqual(["FUTURES"]);
  });
});

describe("the static board is the backend's generated snapshot, with no fake number", () => {
  it("carries the seal of the bars and names its generator", () => {
    expect(staticJson._bars_seal_sha256).toBe("f437c49beb9440d5a1845c0e26116500908d8e481168fe96380545a5a271d10a");
    expect(staticJson._generated_by).toContain("dump_vehicle_board_static.py");
  });

  it("every non-futures count is NOT MEASURED, and nothing is open", () => {
    for (const v of staticVehicleBoard().vehicles) {
      expect(v.open).toBe(false);
      expect(v.visible).toBe(true);
      if (v.vehicle !== "FUTURES") {
        expect(v.paper_trades_so_far).toBe(NOT_MEASURED);
        expect(paperProgress(v)).toContain(NOT_MEASURED);
      }
    }
  });

  it("every locked vehicle says what it waits for, with its own sealed bar — never 'coming soon'", () => {
    const by = new Map(staticVehicleBoard().vehicles.map((v) => [v.vehicle, v] as const));
    expect(by.get("FUTURES")!.waiting_for).toContain("22 Oct 2026");
    expect(by.get("CASH")!.waiting_for).toContain("15:15");
    expect(by.get("OPTION_BUY")!.waiting_for).toContain("Dhan-billed");
    expect(by.get("BULL_CALL_SPREAD")!.waiting_for).toContain("after");
    for (const v of by.values()) expect(v.waiting_for.toLowerCase()).not.toContain("coming soon");
    const cash = barLines(by.get("CASH")!);
    expect(cash[0]).toContain("30");
    expect(cash.join(" ")).toContain("<= Rs 12,500");
    expect(barLines(by.get("OPTION_BUY")!).join(" ")).toContain("<= Rs 50,000");
  });
});

describe("VehiclePicker in STATIC mode", () => {
  it("shows all four cards, calls no server address, and says nothing is sent", () => {
    process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE = "static";
    expect(vehiclePickerSource()).toBe("static");
    render(<VehiclePicker lots={2} />);
    expect(urls.every((u) => u === null)).toBe(true);
    const picker = screen.getByTestId("vehicle-picker");
    expect(picker).toHaveAttribute("data-source", "static");
    expect(screen.getByTestId("vehicle-picker-static-note").textContent).toMatch(/order nahi bhejta/);
    for (const v of ["FUTURES", "CASH", "OPTION_BUY", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]) {
      const card = screen.getByTestId(`vehicle-card-${v}`);
      expect(card).toHaveAttribute("data-open", "false");
      expect(within(card).getByTestId(`vehicle-waiting-${v}`).textContent!.length).toBeGreaterThan(40);
    }
    const spreads = screen.getByTestId("vehicle-group-SPREADS");
    expect(within(spreads).getByTestId("vehicle-card-BULL_CALL_SPREAD")).toBeInTheDocument();
    expect(within(spreads).getByTestId("vehicle-card-BEAR_PUT_SPREAD")).toBeInTheDocument();
    expect(screen.getByTestId("vehicle-futures-choices").textContent).toContain("2 · 4 · 6 · 8 · 10");
    expect(screen.getByTestId("vehicle-progress-OPTION_BUY").textContent).toContain(NOT_MEASURED);
    expect(screen.getByTestId("vehicle-bar-CASH").textContent).toContain("seal");
    expect(screen.queryByTestId("capital-line")).toBeNull();
  });

  it("the default source is live (the backend decides) — no silent static", () => {
    expect(vehiclePickerSource()).toBe("live");
    render(<VehiclePicker lots={2} />);
    expect(urls).toContain("/customer-lane/vehicles/board");
  });
});
