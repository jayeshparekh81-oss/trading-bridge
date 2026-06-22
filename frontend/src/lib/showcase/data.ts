/**
 * Types for the read-only Module 2 showcase API (GET /api/showcase, /{key},
 * /{key}/live). The page consumes the API at runtime — there is NO static data
 * copy here (the old-shape JSON was removed). NET basis throughout.
 */
export type Direction = "all" | "long" | "short";

export interface Metrics {
  trades: number;
  win_rate_pct: number;
  avg_pct_per_trade: number;
  profit_factor: number | null;
  max_drawdown_pct: number; // already negative (e.g. -11.13)
  wins?: number;
  losses?: number;
  best_trade_pct?: number;
  worst_trade_pct?: number;
  longest_losing_streak?: number;
  slice_of_full_system?: boolean;
  caveat?: string;
}

export interface DirBlock {
  all: Metrics;
  long: Metrics;
  short: Metrics;
}

export interface LiveStatus {
  track_type: "LIVE_REAL" | "LIVE_NO_TRADES" | "PAPER";
  label: string;
  disclaimer: string;
}

export interface ShowcaseMeta {
  strategy_version?: string;
  basis: string;
  caveats: string[];
  slice_caveat?: string;
  slippage_excluded: boolean;
  cost_model: {
    rates_asof?: string;
    estimated?: boolean;
    segment?: string;
    [k: string]: unknown;
  };
}

export interface HeadlineNet {
  win_rate_pct: number;
  avg_pct_per_trade: number;
  profit_factor: number | null;
  max_drawdown_pct: number;
  trades: number;
}

export interface ShowcaseListItem {
  key: string;
  instrument: string;
  name: string;
  live_status: LiveStatus;
  basis: string;
  disclaimer: string;
  headline_net: HeadlineNet;
}

export interface ShowcaseListResponse {
  strategies: ShowcaseListItem[];
  meta: ShowcaseMeta;
}

export interface ShowcaseDetail {
  key: string;
  instrument: string;
  name: string;
  live_status: LiveStatus;
  backtest: {
    track_type: string;
    label: string;
    disclaimer: string;
    strategy_version: string;
    in_sample_range: { from: string; to: string };
    basis: string;
    aggregate: DirBlock;
    by_year: Record<string, DirBlock>;
    by_month: Record<string, DirBlock>;
  };
  meta: ShowcaseMeta;
}

export interface LiveRecord {
  key?: string;
  status: "tracking_active" | "paper_no_live" | string;
  reconciled_trades: number;
  note: string;
}

/** Per-live-state badge styling (token classes, dark theme). */
export const BADGE: Record<
  LiveStatus["track_type"],
  { text: string; cls: string; dot: string }
> = {
  LIVE_REAL: {
    text: "Live · Real money",
    cls: "text-profit bg-profit/10 border-profit/30",
    dot: "bg-profit shadow-[0_0_8px_var(--color-profit)]",
  },
  LIVE_NO_TRADES: {
    text: "Newly live · No live trades yet",
    cls: "text-accent-blue bg-accent-blue/10 border-accent-blue/30",
    dot: "bg-accent-blue",
  },
  PAPER: {
    text: "Paper · Not deployed live",
    cls: "text-muted-foreground bg-muted/30 border-border",
    dot: "bg-muted-foreground",
  },
};
