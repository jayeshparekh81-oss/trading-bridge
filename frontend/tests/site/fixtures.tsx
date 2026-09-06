/** One masked showcase strategy, shaped exactly like prod's public API (values are fixtures, not prod numbers). */
import type { LiveRecord, Metrics, ShowcaseDetail, ShowcaseListItem } from "@/lib/showcase/data";

const m = (over: Partial<Metrics> = {}): Metrics => ({
  trades: 412,
  win_rate_pct: 41.7,
  avg_pct_per_trade: 0.63,
  profit_factor: 1.71,
  max_drawdown_pct: -11.13,
  ...over,
});

export const LISTING_ID = "931d38f4-406e-46ec-88f9-5212b21a4d3b";

export const ITEM: ShowcaseListItem = {
  key: "s1",
  instrument: "Equity F&O",
  name: "Strategy S1",
  live_status: { track_type: "LIVE_REAL", label: "Live · Real money", disclaimer: "" },
  basis: "net",
  disclaimer: "",
  headline_net: { win_rate_pct: 41.7, avg_pct_per_trade: 0.63, profit_factor: 1.71, max_drawdown_pct: -11.13, trades: 412 },
};

export const DETAIL: ShowcaseDetail = {
  key: "s1",
  instrument: "Equity F&O",
  name: "Strategy S1",
  live_status: ITEM.live_status,
  backtest: {
    track_type: "BACKTEST",
    label: "In-sample",
    disclaimer: "",
    strategy_version: "v1",
    in_sample_range: { from: "2018-01-01", to: "2026-08-31" },
    basis: "net",
    aggregate: { all: m(), long: m({ trades: 250, win_rate_pct: 44.0 }), short: m({ trades: 162, win_rate_pct: 38.2 }) },
    by_year: { "2025": { all: m({ trades: 60 }), long: m({ trades: 30 }), short: m({ trades: 30 }) } },
    by_month: { "2025-08": { all: m({ trades: 6 }), long: m({ trades: 3 }), short: m({ trades: 3 }) } },
    series: null,
  },
  meta: { basis: "net", caveats: [], slippage_excluded: true, cost_model: {} },
};

export const LIVE: LiveRecord = {
  key: "s1",
  status: "verification_period",
  note: "Live execution is in a verification period — live results are not yet published.",
  listing_id: LISTING_ID,
};
