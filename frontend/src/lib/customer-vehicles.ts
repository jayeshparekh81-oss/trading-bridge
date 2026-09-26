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

/** OFF unless the env var is exactly "1". Read at call time so tests can flip it.
 *
 * The read uses the literal `process.env.NEXT_PUBLIC_…` form — the only form Next's own
 * docs promise to inline (node_modules/next/dist/docs/01-app/02-guides/
 * environment-variables.md:182-192 say a lookup through a variable is NOT inlined; the
 * Turbopack build measured on the box on 26 Sep did inline it anyway, so this is about
 * staying inside the documented contract, not a measured failure).
 * A public variable enters the browser bundle ONLY at build time, and only for the
 * environment it is set in: the served 2c7b84ab chunk read
 * `"1"===P.default.env.NEXT_PUBLIC_CUSTOMER_VEHICLES` (browser env `{}`) — the value was
 * not in THAT production build, so the picker never showed. After any publish meant to
 * turn a flag on, grep the served chunk: the flag's NAME must be gone.
 * Guarded by tests/marketplace/settings-one-decision.test.tsx. */
export function customerVehiclesEnabled(): boolean {
  return process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES === "1";
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
    what: "Upar jaane ke signal par call option (CE) aur neeche jaane ke signal par put option (PE) kharidna. Jo daam (premium) diya, woh poora doob sakta hai.",
  },
  BULL_CALL_SPREAD: {
    label: "Bull call spread",
    what: "Ek call option (CE) kharido, ek upar wala call option (CE) becho. Sirf upar jaane (long) ke signal par. Nuksaan aur fayda dono ki had pehle se tay.",
  },
  BEAR_PUT_SPREAD: {
    label: "Bear put spread",
    what: "Ek put option (PE) kharido, ek neeche wala put option (PE) becho. Sirf neeche jaane (short) ke signal par. Nuksaan aur fayda dono ki had pehle se tay.",
  },
};

/** Which risk segment each vehicle belongs to — the key into SEGMENT_RISK /
 * SEGMENT_MIN_CAPITAL / SEGMENT_WORST_DAY for the one line per vehicle. A spread is
 * two option legs, so it carries the options segment's facts. */
export const VEHICLE_SEGMENT: Record<CustomerVehicle, "cash" | "futures" | "options"> = {
  FUTURES: "futures",
  CASH: "cash",
  OPTION_BUY: "options",
  BULL_CALL_SPREAD: "options",
  BEAR_PUT_SPREAD: "options",
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
  /** The customer may CHOOSE it today (FUTURES — it runs in paper like every subscription
   * does today); `open` = real orders, which wait the launch gate. */
  selectable?: boolean;
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
  /** the same fact in plain words for the customer (backend `DEFAULT_BASIS_HI`); absent on older payloads */
  default_basis_hi?: string;
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
  if (v.selectable) return `Chuna ja sakta hai — abhi paper me chalega. Asli order ke liye intezaar: ${v.waiting_for}`;
  return `Abhi band hai. Kis cheez ka intezaar: ${v.waiting_for}`;
}
