/**
 * The five vehicles a customer may one day run a strategy in, the measured
 * capital line, and the ATM/OTM/ITM table — types, the OFF flag, and the pure
 * helpers the picker renders with.
 *
 * Founder, 2026-09-24 (REQUIREMENTS §13, CUST-1 messages 1-3):
 *   - CASH / FUTURES / OPTION BUY / BULL CALL SPREAD / BEAR PUT SPREAD; FUTURES
 *     is the only one visible at launch; every locked vehicle says plainly what
 *     it is waiting for, never "coming soon".
 *   - Every figure carries its basis; where a number does not exist the screen
 *     says NOT MEASURED — never a guess, never a placeholder that looks like data.
 *   - For option vehicles the customer picks ATM / OTM / ITM; DEFAULT = OTM,
 *     marked as the recommended default; never a win rate without the drawdown
 *     beside it.
 *
 * ONE SOURCE PER FACT: nothing here holds a number. Every value is read from
 * the backend's flag-gated surface (`/customer-lane/vehicles/*`), which answers
 * from the same measured records the backend tests pin. This file only shapes
 * and formats.
 *
 * FLAG: `NEXT_PUBLIC_CUSTOMER_VEHICLES` — unset/"0" = OFF = the existing
 * disabled "Vehicle" control stays exactly as it is today.
 */

import { NOT_MEASURED } from "@/lib/risk-labels";

export const VEHICLE_FLAG = "NEXT_PUBLIC_CUSTOMER_VEHICLES";

/** OFF unless the env var is exactly "1". Read at call time so tests can flip it. */
export function customerVehiclesEnabled(): boolean {
  return process.env[VEHICLE_FLAG] === "1";
}

export const CUSTOMER_VEHICLES = [
  "FUTURES",
  "CASH",
  "OPTION_BUY",
  "BULL_CALL_SPREAD",
  "BEAR_PUT_SPREAD",
] as const;
export type CustomerVehicle = (typeof CUSTOMER_VEHICLES)[number];

export const MONEYNESS = ["OTM", "ATM", "ITM"] as const;
export type Moneyness = (typeof MONEYNESS)[number];
/** Founder-settled default (24 Sep 2026): OTM. Not re-litigated on the client. */
export const DEFAULT_MONEYNESS: Moneyness = "OTM";

/** Plain-Hinglish one-liners: what each vehicle IS, for someone who knows nothing. */
export const VEHICLE_PLAIN: Record<CustomerVehicle, { label: string; what: string }> = {
  FUTURES: {
    label: "Futures",
    what: "Wahi contract jo strategy khud live chala rahi hai. Iska asli record hai.",
  },
  CASH: {
    label: "Cash (shares)",
    what: "Seedha share kharidna. Short nahi ho sakta, isliye sirf long signal chalega.",
  },
  OPTION_BUY: {
    label: "Option buy",
    what: "Signal par CE (long) ya PE (short) kharidna. Premium poora zero ho sakta hai.",
  },
  BULL_CALL_SPREAD: {
    label: "Bull call spread",
    what: "Ek CE kharido, ek upar wala CE becho. Sirf long signal. Loss aur profit dono capped.",
  },
  BEAR_PUT_SPREAD: {
    label: "Bear put spread",
    what: "Ek PE kharido, ek neeche wala PE becho. Sirf short signal. Loss aur profit dono capped.",
  },
};

// ── API shapes (mirror backend/app/api/customer_vehicles.py) ───────────────

export interface VehicleStatus {
  vehicle: CustomerVehicle;
  label: string;
  visible: boolean;
  open: boolean;
  waiting_for: string;
  has_live_record: boolean;
  bar_registered: boolean;
  paper_trades_so_far: number | string;
  takes_moneyness: boolean;
  default_moneyness: Moneyness | null;
  /** The sealed bar, quoted by the backend (VEHICLE_BARS.md v2); absent on older payloads. */
  bar?: Record<string, string>;
  clock?: string;
  window_start?: string;
  /** Closed paper trades opened BEFORE the bar's window — shown beside, never counted. */
  paper_trades_pre_window?: number | string;
  min_paper_trades?: number | string;
  min_trading_days?: number | string;
}

export interface VehicleBoard {
  launch_vehicle: CustomerVehicle;
  vehicles: VehicleStatus[];
  locked_vehicles_visible: boolean;
  strike_selector_enabled: boolean;
}

export interface ApiFigure {
  label: string;
  value: number | string;
  basis: string;
  as_of: string | null;
  measured: boolean;
}

export interface CapitalLine {
  vehicle: CustomerVehicle;
  lots: number;
  lot_size: number | string;
  rule: string;
  rule_text: string;
  minimum_capital: ApiFigure;
  margin: ApiFigure;
  max_drawdown: ApiFigure;
  worst_day: ApiFigure;
  worst_trade: ApiFigure;
  live_record: ApiFigure;
  period: string;
  trades: number | string;
  margin_stale: boolean;
  not_measured: string[];
}

export interface MoneynessRow {
  vehicle: CustomerVehicle;
  moneyness: Moneyness;
  net_after_charges_rupees: number | string;
  worst_drawdown_rupees: number | string;
  win_rate_pct: number | string;
  trades: number | string;
  period: string;
  source: string;
  recommended: boolean;
  measured: boolean;
}

export interface MoneynessTable {
  vehicle: CustomerVehicle;
  default: Moneyness;
  default_basis: string;
  rows: MoneynessRow[];
  unfilled_cells: string[];
}

// ── pure helpers ──────────────────────────────────────────────────────────

/** A cell is shown as the literal NOT MEASURED unless it is a real number. */
export function cell(
  v: number | string | null | undefined,
  fmt: (n: number) => string,
): string {
  return typeof v === "number" ? fmt(v) : NOT_MEASURED;
}

/**
 * The founder's rule, enforced at render time as well as in the backend: a row
 * may show its win rate ONLY when its drawdown is a number. Returns the win-rate
 * text to render — NOT MEASURED when the drawdown is missing, even if a win rate
 * somehow arrived.
 */
export function winRateBesideDrawdown(row: Pick<MoneynessRow, "win_rate_pct" | "worst_drawdown_rupees">): string {
  if (typeof row.worst_drawdown_rupees !== "number") return NOT_MEASURED;
  return typeof row.win_rate_pct === "number" ? `${row.win_rate_pct.toFixed(1)}%` : NOT_MEASURED;
}

/** Sort rows so the recommended default is first, keeping the API order otherwise. */
export function defaultFirst(rows: MoneynessRow[]): MoneynessRow[] {
  return [...rows].sort((a, b) => Number(b.recommended) - Number(a.recommended));
}

/** The one sentence under a locked vehicle. Never "coming soon". */
export function lockLine(v: VehicleStatus): string {
  if (v.open) return "";
  return `Abhi band hai. Kis cheez ka intezaar: ${v.waiting_for}`;
}
