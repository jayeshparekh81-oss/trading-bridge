/**
 * C2 in the STATIC picker (founder, 26 Sep 2026: "finish the ATM/OTM/ITM selector (OTM default) end
 * to end"; C4: "Until filled: NOT MEASURED, nothing unlocks"):
 *   - the rows are the backend's GENERATED snapshot of moneyness.table() over the KB file, never
 *     retyped — the generator and the source file's md5 travel with them;
 *   - OTM is first, pre-selected and marked recommended; ATM and ITM are one tap away;
 *   - every cell of an unfilled row reads NOT MEASURED — including the trade count and the period,
 *     which the file carries as a placeholder "0" (RULES #50.10: nothing that looks like data but isn't);
 *   - the static picker makes NO server call.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

import staticMoneyness from "@/lib/moneyness-table.static.json";
import { staticMoneynessTable } from "@/lib/vehicle-cards";
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
});

describe("the static ATM/OTM/ITM tables are the backend's generated snapshot", () => {
  it("names its generator and the KB file it read, and says C4 is NOT filled", () => {
    expect(staticMoneyness._generated_by).toContain("dump_moneyness_table_static.py");
    expect(staticMoneyness._source_file).toBe("kb/ATM_OTM_ITM_MEASURED.md");
    expect(staticMoneyness._source_present).toBe(true);
    expect(staticMoneyness._source_md5).toMatch(/^[0-9a-f]{32}$/);
    expect(staticMoneyness.c4_filled).toBe(false);
  });

  it("covers exactly the three option vehicles; FUTURES and CASH take no strike", () => {
    expect(Object.keys(staticMoneyness.tables).sort()).toEqual(["BEAR_PUT_SPREAD", "BULL_CALL_SPREAD", "OPTION_BUY"]);
    expect(staticMoneynessTable("FUTURES")).toBeNull();
    expect(staticMoneynessTable("CASH")).toBeNull();
  });

  it("OTM first and recommended; every row unmeasured; no number anywhere", () => {
    for (const v of ["OPTION_BUY", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"] as const) {
      const t = staticMoneynessTable(v)!;
      expect(t.default).toBe("OTM");
      expect(t.rows.map((r) => r.moneyness)).toEqual(["OTM", "ATM", "ITM"]);
      expect(t.rows.map((r) => r.recommended)).toEqual([true, false, false]);
      for (const r of t.rows) {
        expect(r.measured).toBe(false);
        expect(r.net_after_charges_rupees).toBe(NOT_MEASURED);
        expect(r.worst_drawdown_rupees).toBe(NOT_MEASURED);
        expect(r.win_rate_pct).toBe(NOT_MEASURED);
        expect(r.period).toBe(NOT_MEASURED);
      }
      expect(t.unfilled_cells).toHaveLength(9);
    }
  });
});

describe("the static picker shows the choice, OTM pre-selected, NOT MEASURED everywhere", () => {
  it("tapping OPTION BUY shows the three strikes with OTM selected, and makes no server call", () => {
    render(<VehiclePicker lots={2} source="static" />);
    expect(screen.queryByTestId("moneyness-picker")).toBeNull();          // FUTURES first: no strike
    fireEvent.click(screen.getByTestId("vehicle-card-OPTION_BUY"));
    const picker = screen.getByTestId("moneyness-picker");
    expect(within(picker).getByTestId("moneyness-OTM").getAttribute("aria-checked")).toBe("true");
    expect(within(picker).getByTestId("moneyness-ATM").getAttribute("aria-checked")).toBe("false");
    expect(within(picker).getByTestId("moneyness-OTM").getAttribute("data-recommended")).toBe("true");
    expect(urls.every((u) => u === null)).toBe(true);
  });

  it("every row says NOT MEASURED — never '0 trades' — and the basis is plain words", () => {
    render(<VehiclePicker lots={2} source="static" />);
    fireEvent.click(screen.getByTestId("vehicle-card-BULL_CALL_SPREAD"));
    for (const m of ["OTM", "ATM", "ITM"]) {
      const row = screen.getByTestId(`moneyness-row-${m}`);
      expect(row.getAttribute("data-measured")).toBe("false");
      expect(row.textContent).toContain(NOT_MEASURED);
      expect(row.textContent).not.toMatch(/\b0 (trades|sauda)/);
      expect(screen.getByTestId(`moneyness-trades-${m}`).textContent).toContain(NOT_MEASURED);
    }
    const basis = screen.getByTestId("moneyness-default-basis").textContent ?? "";
    expect(basis).toContain("OTM (thoda door wala strike) pehle se chuna hua hai");
    expect(basis).not.toContain("do not re-litigate");
  });

  it("the customer can choose ATM or ITM; the choice is reported up", () => {
    const onMoneyness = vi.fn();
    render(<VehiclePicker lots={2} source="static" onMoneyness={onMoneyness} />);
    fireEvent.click(screen.getByTestId("vehicle-card-OPTION_BUY"));
    fireEvent.click(screen.getByTestId("moneyness-ITM"));
    expect(onMoneyness).toHaveBeenCalledWith("ITM");
    expect(screen.getByTestId("moneyness-ITM").getAttribute("aria-checked")).toBe("true");
  });
});

describe("the settings screen (compact picker): the comparison lives behind 'Aur jaano'", () => {
  it("each closed option vehicle shows its OTM/ATM/ITM comparison, read-only, NOT MEASURED, no server call", () => {
    render(<VehiclePicker lots={2} source="static" compact />);
    // closed vehicles cannot be chosen, so no choosing radios are offered anywhere
    expect(screen.queryByTestId("moneyness-picker")).toBeNull();
    for (const v of ["OPTION_BUY", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]) {
      const cmp = screen.getByTestId(`moneyness-compare-${v}`);
      expect(within(cmp).queryByRole("radio")).toBeNull();
      for (const m of ["OTM", "ATM", "ITM"]) {
        const row = within(cmp).getByTestId(`moneyness-row-${m}-${v}`);
        expect(row.getAttribute("data-measured")).toBe("false");
        expect(row.textContent).toContain(NOT_MEASURED);
        expect(row.textContent).not.toMatch(/\b0 (trades|sauda)/);
      }
      expect(within(cmp).getByTestId(`moneyness-row-OTM-${v}`).textContent).toContain("recommended");
    }
    expect(screen.queryByTestId("moneyness-compare-FUTURES")).toBeNull();
    expect(screen.queryByTestId("moneyness-compare-CASH")).toBeNull();
    expect(urls.every((u) => u === null)).toBe(true);
  });
});
