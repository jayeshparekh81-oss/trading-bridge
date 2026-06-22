/**
 * DRAFT showcase data loader — reads the honest static artifact copied from
 * `backend/scripts/showcase_backtest.json`. Size-independent metrics only; NO
 * compounded totals, NO INR P&L, NO fabricated live numbers.
 *
 * This is a DRAFT data source (a copied static file) — not the production data
 * pipeline. The real version would come from the read-only /api/showcase
 * endpoint (see SHOWCASE_BACKEND_DESIGN.md).
 */
import raw from "./showcase-backtest.json";

export type LiveTrackType = "LIVE_REAL" | "FORWARD_TEST" | "PAPER";

export interface BacktestMetrics {
  closed_trades: number;
  win_rate_pct: number;
  avg_gross_pct_per_trade: number;
  avg_net_pct_per_trade: number;
  median_net_pct_per_trade: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  profit_factor: number;
  longest_losing_streak: number;
  max_drawdown_pct: number;
  wins: number;
  losses: number;
  flats: number;
}

export interface ShowcaseStrategy {
  key: string;
  instrument: string;
  display_name: string;
  backtest: {
    track_type: "BACKTEST_IN_SAMPLE";
    label: string;
    disclaimer: string;
    strategy_version: string;
    in_sample_range: { from: string; to: string };
    metrics: BacktestMetrics;
  };
  live_status: {
    track_type: LiveTrackType;
    label: string;
    disclaimer: string;
  };
}

interface ShowcaseDoc {
  meta: { caveats: string[]; strategy_version: string; generated_utc: string };
  strategies: ShowcaseStrategy[];
}

const doc = raw as unknown as ShowcaseDoc;

export const showcaseStrategies: ShowcaseStrategy[] = doc.strategies;
export const showcaseCaveats: string[] = doc.meta.caveats;
export const showcaseVersion: string = doc.meta.strategy_version;

/**
 * Public-facing label + tone for each honest live-status (per Jayesh's spec:
 * BSE = LIVE (real), CDSL = FORWARD-TEST (paper), ANGELONE = PAPER). DRAFT copy.
 */
export const LIVE_BADGE: Record<
  LiveTrackType,
  { text: string; sub: string; tone: "profit" | "gold" | "muted"; dot: string }
> = {
  LIVE_REAL: {
    text: "Live (real)",
    sub: "Real-money trading — live forward-tracking",
    tone: "profit",
    dot: "bg-profit",
  },
  FORWARD_TEST: {
    text: "Forward-test (paper)",
    sub: "Out-of-sample, paper — not yet real money",
    tone: "gold",
    dot: "bg-accent-gold",
  },
  PAPER: {
    text: "Paper",
    sub: "Simulated — no real money traded",
    tone: "muted",
    dot: "bg-muted-foreground",
  },
};
