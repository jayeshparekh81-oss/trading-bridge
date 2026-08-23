/**
 * Per-segment risk labels — constants, chip rendering, and the two HONESTY
 * constraints that are the whole point of this feature:
 *
 *   1. The labels must never read as measured/computed. The chip renders no
 *      number, no "/100", no AnimatedNumber; EDITORIAL_NOTE is VISIBLE copy,
 *      not tooltip-only.
 *   2. Every certified performance number is FUTURES-priced, so a risk chip
 *      must NEVER render inside a certified-metrics container (the guard
 *      test), and selecting Cash/Options must surface the cross-segment
 *      warning without rendering segment-specific metrics.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

// URL-routed useApi mock so the REAL showcase page renders (list + detail +
// live), with a BSE strategy so the high-volatility note path is exercised.
vi.mock("@/lib/use-api", () => {
  const METRICS = {
    trades: 120,
    win_rate_pct: 58.2,
    avg_pct_per_trade: 0.42,
    profit_factor: 1.8,
    max_drawdown_pct: -11.13,
  };
  const DIR = { all: METRICS, long: METRICS, short: METRICS };
  return {
    useApi: (url: string | null) => {
      let data: unknown = null;
      if (url === "/showcase") {
        data = {
          strategies: [
            {
              key: "bse-ltd",
              instrument: "BSE",
              name: "BSE Ltd Futures",
              live_status: { track_type: "LIVE_REAL", label: "Live", disclaimer: "" },
              basis: "net",
              disclaimer: "",
              headline_net: { ...METRICS },
            },
          ],
          meta: { basis: "net", caveats: [], slippage_excluded: true, cost_model: {} },
        };
      } else if (url?.endsWith("/live")) {
        data = { status: "tracking_active", reconciled_trades: 0, note: "" };
      } else if (url?.startsWith("/showcase/")) {
        data = {
          key: "bse-ltd",
          instrument: "BSE",
          name: "BSE Ltd Futures",
          live_status: { track_type: "LIVE_REAL", label: "Live", disclaimer: "" },
          backtest: {
            track_type: "LIVE_REAL",
            label: "Live",
            disclaimer: "",
            strategy_version: "v1",
            in_sample_range: { from: "2024-01", to: "2026-06" },
            basis: "net",
            aggregate: DIR,
            by_year: {},
            by_month: {},
            series: null,
          },
          meta: { basis: "net", caveats: [], slippage_excluded: true, cost_model: {} },
        };
      }
      return { data, isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn() };
    },
  };
});

import {
  CROSS_SEGMENT_METRICS_WARNING,
  EDITORIAL_NOTE,
  FUTURES_BASIS_LABEL,
  RISK_SEGMENTS,
  RISK_TONE,
  SEGMENT_RISK,
  highVolatilityNote,
} from "@/lib/risk-labels";
import { RiskChip, RiskLegend } from "@/components/risk/risk-chip";

// ═══════════════════════════════════════════════════════════════════════
// 1. Constants — the founder's settled labels
// ═══════════════════════════════════════════════════════════════════════
describe("risk-labels constants", () => {
  it("maps the three segments to the settled levels", () => {
    expect(SEGMENT_RISK.cash.level).toBe("low");
    expect(SEGMENT_RISK.futures.level).toBe("medium");
    expect(SEGMENT_RISK.options.level).toBe("high");
  });

  it("labels read LOW / MEDIUM+return / HIGH+return", () => {
    expect(SEGMENT_RISK.cash.label).toMatch(/LOW risk/);
    expect(SEGMENT_RISK.futures.label).toMatch(/MEDIUM risk \/ medium return/);
    expect(SEGMENT_RISK.options.label).toMatch(/HIGH risk \/ high return/);
  });

  it("every segment has a non-empty plain-language why", () => {
    for (const seg of RISK_SEGMENTS) {
      expect(SEGMENT_RISK[seg].why.length).toBeGreaterThan(20);
    }
  });

  it("every level has a tone token", () => {
    for (const seg of RISK_SEGMENTS) {
      expect(RISK_TONE[SEGMENT_RISK[seg].level]).toBeTruthy();
    }
  });

  it("BSE is flagged high-volatility, and the note is SEPARATE from segment risk", () => {
    const note = highVolatilityNote("BSE");
    expect(note).toMatch(/high-volatility/i);
    // It must not smuggle a segment label into an instrument-level note.
    expect(note).not.toMatch(/LOW risk|MEDIUM risk|HIGH risk/);
    expect(highVolatilityNote("bse")).toBe(note); // case-insensitive
    expect(highVolatilityNote("RELIANCE")).toBeNull();
    expect(highVolatilityNote(null)).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. HONESTY #1 — must not look measured
// ═══════════════════════════════════════════════════════════════════════
describe("RiskChip — must never read as a computed score", () => {
  it.each(RISK_SEGMENTS)("chip for %s renders no number and no /100", (seg) => {
    const { container } = render(<RiskChip segment={seg} />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\d/); // no digits at all
    expect(text).not.toContain("/100");
    expect(text).not.toContain("%");
  });

  it("does not use the certified stat-tile numeric styling", () => {
    const { container } = render(<RiskChip segment="futures" />);
    const html = container.innerHTML;
    expect(html).not.toContain("tabular-nums");
    expect(html).not.toContain("font-mono");
  });
});

describe("RiskLegend — educational, not a strategy rating", () => {
  it("shows ALL THREE segments together", () => {
    render(<RiskLegend />);
    for (const seg of RISK_SEGMENTS) {
      expect(screen.getByTestId(`risk-legend-row-${seg}`)).toBeInTheDocument();
      expect(screen.getByTestId(`risk-chip-${seg}`)).toBeInTheDocument();
    }
  });

  it("renders EDITORIAL_NOTE as VISIBLE copy (not tooltip-only)", () => {
    render(<RiskLegend />);
    const note = screen.getByTestId("risk-editorial-note");
    expect(note).toBeInTheDocument();
    expect(note.textContent).toContain(EDITORIAL_NOTE);
    // Visible, not hidden behind a trigger.
    expect(note).toBeVisible();
    expect(note.getAttribute("aria-hidden")).not.toBe("true");
  });

  it("states it is not a rating of one strategy", () => {
    const { container } = render(<RiskLegend />);
    expect(container.textContent).toMatch(/kisi ek strategy ki rating nahi/i);
  });

  it("never claims the labels were measured/backtested", () => {
    const { container } = render(<RiskLegend />);
    const text = container.textContent ?? "";
    expect(text).toMatch(/judgement/i);
    expect(text).toMatch(/NAHI/); // "backtest se nikala hua score NAHI hai"
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. HONESTY #2 — cross-segment metric contamination
// ═══════════════════════════════════════════════════════════════════════
describe("cross-segment metric honesty", () => {
  it("the warning names futures-basis and says Cash/Options have no verified numbers", () => {
    expect(CROSS_SEGMENT_METRICS_WARNING).toMatch(/futures-basis/i);
    expect(CROSS_SEGMENT_METRICS_WARNING).toMatch(/Cash \/ Options/i);
  });

  it("FUTURES_BASIS_LABEL names NRML explicitly", () => {
    expect(FUTURES_BASIS_LABEL).toMatch(/futures/i);
    expect(FUTURES_BASIS_LABEL).toMatch(/NRML/);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. THE GUARD — a risk chip must never live inside certified metrics
// ═══════════════════════════════════════════════════════════════════════
describe("GUARD: risk chip never renders inside a certified-metrics container", () => {
  it("a certified-metrics container contains NO risk chip", () => {
    // Simulates the showcase layout: chip in the header, certified numbers in
    // their own container. If someone later moves the chip into the stat grid,
    // this fails.
    render(
      <div>
        <header data-testid="header-zone">
          <RiskChip segment="futures" />
        </header>
        <div data-testid="certified-metrics">
          <span>Win rate 58.2%</span>
          <span>Max drawdown -11.13%</span>
        </div>
      </div>,
    );

    const certified = screen.getByTestId("certified-metrics");
    for (const seg of RISK_SEGMENTS) {
      expect(within(certified).queryByTestId(`risk-chip-${seg}`)).toBeNull();
    }
    expect(within(certified).queryByTestId("risk-legend")).toBeNull();
    // …and the chip really is present, just elsewhere (so the test can fail).
    expect(
      within(screen.getByTestId("header-zone")).getByTestId("risk-chip-futures"),
    ).toBeInTheDocument();
  });

  it("would CATCH a chip wrongly placed inside certified metrics", () => {
    render(
      <div data-testid="certified-metrics">
        <RiskChip segment="cash" />
      </div>,
    );
    // Proving the guard has teeth: this arrangement is exactly what must fail.
    const certified = screen.getByTestId("certified-metrics");
    expect(within(certified).queryByTestId("risk-chip-cash")).not.toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 5. THE REAL GUARD — run against the ACTUAL showcase page markup.
//    The synthetic guard above proves the assertion mechanism; this one
//    proves the shipped page actually obeys it.
// ═══════════════════════════════════════════════════════════════════════
describe("GUARD (real page): showcase chip lives in the header, never in metrics", () => {
  it("renders the futures chip outside both certified-metrics containers", async () => {
    const ShowcasePage = (await import("@/app/(public)/showcase/page")).default;
    render(<ShowcasePage />);

    // The chip is present (header) …
    const chip = screen.getAllByTestId("risk-chip-futures");
    expect(chip.length).toBeGreaterThan(0);

    // … and absent from EVERY certified-metrics container on the real page.
    for (const testid of ["certified-metrics", "certified-metrics-risk"]) {
      for (const node of screen.queryAllByTestId(testid)) {
        expect(within(node).queryByTestId("risk-chip-futures")).toBeNull();
        expect(within(node).queryByTestId("risk-chip-cash")).toBeNull();
        expect(within(node).queryByTestId("risk-chip-options")).toBeNull();
        expect(within(node).queryByTestId("risk-legend")).toBeNull();
      }
    }
  });

  it("labels the certified metrics as futures-basis (NRML)", async () => {
    const ShowcasePage = (await import("@/app/(public)/showcase/page")).default;
    const { container } = render(<ShowcasePage />);
    expect(container.textContent).toContain(FUTURES_BASIS_LABEL);
  });

  it("shows the BSE high-volatility note separately from the segment chip", async () => {
    const ShowcasePage = (await import("@/app/(public)/showcase/page")).default;
    render(<ShowcasePage />);
    const note = screen.getAllByTestId("high-volatility-note")[0];
    expect(note.textContent).toMatch(/high-volatility/i);
    // The note must not itself carry a segment risk label.
    expect(within(note).queryByTestId("risk-chip-futures")).toBeNull();
  });
});
