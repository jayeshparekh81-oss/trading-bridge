/**
 * VehiclePicker — the honesty mechanics, each asserted:
 *   - with every flag OFF the backend board lists FUTURES alone → one card;
 *   - a locked vehicle shows what it is WAITING FOR, never "coming soon";
 *   - every capital figure carries a VISIBLE basis; NOT MEASURED is the literal;
 *   - OTM is pre-selected and marked recommended; a win rate never shows beside an
 *     unmeasured drawdown;
 *   - loading / empty / error states each render.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

import type { CapitalLine, MoneynessTable, VehicleBoard } from "@/lib/customer-vehicles";
import {
  DEFAULT_MONEYNESS,
  cell,
  customerVehiclesEnabled,
  defaultFirst,
  lockLine,
  winRateBesideDrawdown,
} from "@/lib/customer-vehicles";
import { NOT_MEASURED } from "@/lib/risk-labels";

const responses: Record<string, unknown> = {};
let loading = false;
let failing = false;

vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => ({
    data: url && !loading && !failing ? (responses[url] ?? null) : null,
    isLoading: loading,
    error: failing ? "boom" : null,
    paywalled: false,
    paywallUrl: null,
    refetch: vi.fn(),
  }),
}));

import { CapitalLineCard, MoneynessPicker, VehiclePicker } from "@/components/marketplace/vehicle-picker";

const futures = {
  vehicle: "FUTURES" as const,
  label: "Futures",
  visible: true,
  open: false,
  waiting_for: "the customer launch gate: roll-follow LIVE through a real roll, platform auto-close LIVE, the lane's blockers closed, the founder's SEBI/legal answer, SES production + support email",
  has_live_record: true,
  bar_registered: true,
  paper_trades_so_far: "n/a (live record since 2026-08-20)",
  takes_moneyness: false,
  default_moneyness: null,
};
const optionBuy = {
  vehicle: "OPTION_BUY" as const,
  label: "Option buy",
  visible: true,
  open: false,
  waiting_for: "a pre-registered evidence bar (not written yet) and the option paper lane producing closable P&L at book prices with real charges applied",
  has_live_record: false,
  bar_registered: false,
  paper_trades_so_far: "NOT MEASURED",
  takes_moneyness: true,
  default_moneyness: "OTM" as const,
};

const fig = (label: string, value: number | string, basis: string) => ({
  label, value, basis, as_of: "2026-08-19", measured: typeof value === "number",
});
const capital: CapitalLine = {
  vehicle: "FUTURES", lots: 2, lot_size: 200, rule: "MARGIN_PLUS_2X_MAXDD",
  rule_text: "minimum capital for N lots = margin + 2 x worst drawdown",
  minimum_capital: fig("Minimum capital", 631765, "359555 + 2 x 136105 = 631765"),
  margin: fig("Margin", 359555, "Dhan margin calculator, 2026-08-19"),
  max_drawdown: fig("Worst drawdown", 136105, "sealed 715-trade record re-priced at 2 lots"),
  worst_day: fig("Worst day", 63105, "largest one-day loss, 2026-06-05"),
  worst_trade: fig("Worst trade", 63105, "largest single-trade loss"),
  live_record: fig("Live record", 78659, "7 real Dhan fills since 2026-08-20"),
  period: "2020-02-03 to 2026-07-16", trades: 715, margin_stale: true, not_measured: ["brokerage"],
};
const unmeasuredCapital: CapitalLine = {
  ...capital, vehicle: "OPTION_BUY", lot_size: NOT_MEASURED, trades: NOT_MEASURED, period: NOT_MEASURED,
  minimum_capital: fig("Minimum capital", NOT_MEASURED, "no record exists for OPTION_BUY"),
  margin: fig("Margin", NOT_MEASURED, "no record"), max_drawdown: fig("Worst drawdown", NOT_MEASURED, "no record"),
  worst_day: fig("Worst day", NOT_MEASURED, "no record"), margin_stale: false,
};
const row = (m: "OTM" | "ATM" | "ITM", recommended: boolean) => ({
  vehicle: "OPTION_BUY" as const, moneyness: m, net_after_charges_rupees: NOT_MEASURED,
  worst_drawdown_rupees: NOT_MEASURED, win_rate_pct: NOT_MEASURED, trades: 0, period: NOT_MEASURED,
  source: "founder's research lane (Mac) — not on the box", recommended, measured: false,
});
const table: MoneynessTable = {
  vehicle: "OPTION_BUY", default: "OTM", default_basis: "founder, 2026-09-24, settled in his research lane",
  rows: [row("ATM", false), row("OTM", true), row("ITM", false)], unfilled_cells: [],
};

beforeEach(() => {
  loading = false;
  failing = false;
  for (const k of Object.keys(responses)) delete responses[k];
  responses["/customer-lane/vehicles/board"] = {
    launch_vehicle: "FUTURES", vehicles: [futures], locked_vehicles_visible: false, strike_selector_enabled: false,
  } satisfies VehicleBoard;
  responses["/customer-lane/vehicles/capital?vehicle=FUTURES&lots=2"] = capital;
});

describe("flag", () => {
  it("is OFF unless NEXT_PUBLIC_CUSTOMER_VEHICLES is exactly 1", () => {
    const prev = process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES;
    delete process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES;
    expect(customerVehiclesEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES = "true";
    expect(customerVehiclesEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES = "1";
    expect(customerVehiclesEnabled()).toBe(true);
    if (prev === undefined) delete process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES;
    else process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES = prev;
  });
});

describe("pure helpers", () => {
  it("cell renders NOT MEASURED for anything that is not a number", () => {
    expect(cell(NOT_MEASURED, String)).toBe(NOT_MEASURED);
    expect(cell(null, String)).toBe(NOT_MEASURED);
    expect(cell(12, (n) => `₹${n}`)).toBe("₹12");
  });
  it("never a win rate without the drawdown beside it", () => {
    expect(winRateBesideDrawdown({ win_rate_pct: 61, worst_drawdown_rupees: NOT_MEASURED })).toBe(NOT_MEASURED);
    expect(winRateBesideDrawdown({ win_rate_pct: 61, worst_drawdown_rupees: -3800 })).toBe("61.0%");
    expect(winRateBesideDrawdown({ win_rate_pct: NOT_MEASURED, worst_drawdown_rupees: -3800 })).toBe(NOT_MEASURED);
  });
  it("defaultFirst puts the recommended row first and the default is OTM", () => {
    expect(DEFAULT_MONEYNESS).toBe("OTM");
    expect(defaultFirst(table.rows).map((r) => r.moneyness)).toEqual(["OTM", "ATM", "ITM"]);
  });
  it("lockLine says what it is waiting for, never coming soon", () => {
    const line = lockLine(optionBuy);
    expect(line).toContain(optionBuy.waiting_for);
    expect(line.toLowerCase()).not.toContain("coming soon");
    expect(lockLine({ ...futures, open: true })).toBe("");
  });
});

describe("VehiclePicker", () => {
  it("with flags OFF shows FUTURES alone, locked, with its waiting-for sentence", () => {
    render(<VehiclePicker lots={2} />);
    expect(screen.getAllByRole("radio", { name: /Futures|Option|Cash|spread/i })).toHaveLength(1);
    const card = screen.getByTestId("vehicle-card-FUTURES");
    expect(card).toHaveAttribute("data-open", "false");
    const waiting = within(card).getByTestId("vehicle-waiting-FUTURES");
    expect(waiting.textContent).toContain("roll-follow");
    expect(waiting.textContent!.toLowerCase()).not.toContain("coming soon");
    expect(screen.queryByTestId("vehicle-card-OPTION_BUY")).toBeNull();
  });

  it("renders every capital figure with a VISIBLE basis", () => {
    render(<VehiclePicker lots={2} />);
    for (const id of ["capital-minimum", "capital-margin", "capital-drawdown", "capital-worst-day"]) {
      const node = screen.getByTestId(id);
      expect(node).toHaveAttribute("data-measured", "true");
      expect(screen.getByTestId(`${id}-basis`).textContent!.length).toBeGreaterThan(10);
    }
    expect(screen.getByTestId("capital-minimum").textContent).toContain("₹6.3L");
    expect(screen.getByTestId("capital-margin-stale")).toBeInTheDocument();
  });

  it("locked vehicles appear only when the backend marks them visible, and unmeasured capital renders the literal", () => {
    responses["/customer-lane/vehicles/board"] = {
      launch_vehicle: "FUTURES", vehicles: [futures, optionBuy], locked_vehicles_visible: true, strike_selector_enabled: true,
    } satisfies VehicleBoard;
    responses["/customer-lane/vehicles/capital?vehicle=OPTION_BUY&lots=2"] = unmeasuredCapital;
    responses["/customer-lane/vehicles/moneyness?vehicle=OPTION_BUY"] = table;
    render(<VehiclePicker lots={2} />);
    const card = screen.getByTestId("vehicle-card-OPTION_BUY");
    expect(within(card).getByTestId("vehicle-waiting-OPTION_BUY").textContent).toContain("pre-registered");
    card.click();
  });

  it("three states: loading, error, empty", () => {
    loading = true;
    const { unmount } = render(<VehiclePicker lots={2} />);
    expect(screen.getByTestId("vehicle-picker-loading")).toBeInTheDocument();
    unmount();
    loading = false;
    failing = true;
    const r2 = render(<VehiclePicker lots={2} />);
    expect(screen.getByTestId("vehicle-picker-error").textContent).toMatch(/refresh/i);
    r2.unmount();
    failing = false;
    responses["/customer-lane/vehicles/board"] = {
      launch_vehicle: "FUTURES", vehicles: [], locked_vehicles_visible: false, strike_selector_enabled: false,
    } satisfies VehicleBoard;
    render(<VehiclePicker lots={2} />);
    expect(screen.getByTestId("vehicle-picker-empty")).toBeInTheDocument();
  });
});

describe("CapitalLineCard / MoneynessPicker", () => {
  it("NOT MEASURED figures render the literal, never 0 or a dash", () => {
    render(<CapitalLineCard line={unmeasuredCapital} />);
    const node = screen.getByTestId("capital-minimum");
    expect(node).toHaveAttribute("data-measured", "false");
    expect(node.textContent).toContain(NOT_MEASURED);
    expect(node.textContent).not.toMatch(/₹0|—/);
  });

  it("OTM is pre-selected, first, and marked recommended; every row shows net, drawdown, win rate, trades, period", () => {
    const onChange = vi.fn();
    render(<MoneynessPicker table={table} value={DEFAULT_MONEYNESS} onChange={onChange} />);
    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("data-testid", "moneyness-OTM");
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(radios[0]).toHaveAttribute("data-recommended", "true");
    expect(radios[0].textContent).toMatch(/Recommended \(default\)/);
    for (const m of ["OTM", "ATM", "ITM"]) {
      const r = screen.getByTestId(`moneyness-row-${m}`);
      expect(r).toHaveAttribute("data-measured", "false");
      // FLIPPED FORWARD 2026-09-26 (C2 + RULES #50): plain labels, and an UNMEASURED row's trade count reads
      // NOT MEASURED — the old pin asserted the file's placeholder "0 trades", which reads like data but is not.
      // Originals kept:
      //   expect(r.textContent).toContain("Net: NOT MEASURED");
      //   expect(r.textContent).toContain("Drawdown: NOT MEASURED");
      //   expect(r.textContent).toContain("Win rate: NOT MEASURED");
      //   expect(r.textContent).toContain("0 trades");
      expect(r.textContent).toContain("Kharcha kaat ke munafa (net, Dhan ke bill ke baad): NOT MEASURED");
      expect(r.textContent).toContain("Sabse bada girna (drawdown): NOT MEASURED");
      expect(r.textContent).toContain("Kitni baar munafa (win rate): NOT MEASURED");
      expect(r.textContent).toContain("Sauda (trades): NOT MEASURED");
      expect(r.textContent).not.toMatch(/\b0 (trades|sauda)/);
    }
    screen.getByTestId("moneyness-ITM").click();
    expect(onChange).toHaveBeenCalledWith("ITM");
  });
});
