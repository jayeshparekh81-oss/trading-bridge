/**
 * Subscriber signal-feed + confirm types — the REAL backend contract.
 *
 * Mirrors the backend Pydantic models in
 * `app/strategy_engine/api/marketplace.py`:
 *   - SubscriberSignalRead   (GET  /marketplace/subscriptions/signals)
 *   - SignalValidity         (server-computed window; the UI never runs a clock)
 *   - ConfirmSignalResult    (POST /marketplace/subscriptions/signals/{id}/confirm)
 *
 * Types only — no runtime, no fixtures. Prices are strings (backend serializes
 * Decimal as string). Note the two fields that trip people up:
 *   - `action` is the signal CLASS (ENTRY / EXIT / PARTIAL / SL_HIT).
 *   - `side`   is the payload buy/sell/long/short (or null) — NOT the class.
 * The green/red "entry vs exit" styling keys off `action`/`validity.window`,
 * never off `side`.
 */

export interface SignalValidity {
  /** entry = 5-min window from received_at; exit = valid till 15:30 IST EOD. */
  window: "entry" | "exit";
  /** Server truth: is the signal still confirmable right now? */
  valid: boolean;
  /** ISO timestamp when the window closes. */
  expires_at: string;
  /** Whole seconds until `expires_at` (0 once lapsed). Display-only; refreshed
   *  by the 15s feed poll — the UI deliberately runs no client countdown. */
  seconds_remaining: number;
}

export interface SubscriberSignal {
  id: string;
  listing_id: string;
  /** Marketplace listing name — shown instead of the internal strategy id. */
  listing_title: string;
  symbol: string;
  /** Signal class: ENTRY / EXIT / PARTIAL / SL_HIT. */
  action: string;
  /** Payload buy/sell/long/short, or null. NOT the entry/exit class. */
  side: string | null;
  entry: string | null;
  stop_loss: string | null;
  target: string | null;
  /** ISO timestamp the signal was received. */
  received_at: string;
  status: string;
  validity: SignalValidity;
}

export interface SubscriberSignalListResponse {
  signals: SubscriberSignal[];
  count: number;
}

export interface ConfirmSignalResult {
  signal_id: string;
  subscription_id: string;
  /** confirmed_paper = fresh paper fill; already_confirmed = idempotent replay. */
  status: "confirmed_paper" | "already_confirmed";
  /** ALWAYS false in this build — this endpoint never places a real order. */
  placed_real: boolean;
  execution_id: string;
  broker_order_id: string | null;
  quantity: number;
  price: string | null;
  validity: SignalValidity;
  /** Human-readable server note (paper-gated / idempotent) — surfaced in the toast. */
  note: string;
}
