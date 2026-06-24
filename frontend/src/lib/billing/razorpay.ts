/**
 * Razorpay Checkout loader + recurring-subscription open helper.
 *
 * SECURITY: only the PUBLIC ``key_id`` (returned by the backend subscribe
 * endpoints) is ever used here. The key SECRET and webhook secret live ONLY on
 * the server. Activation is webhook-driven on the backend — this module never
 * marks anything paid/active; on a successful checkout it just hands control
 * back so the caller can poll backend status.
 *
 * checkout.js is loaded lazily (only when a paid checkout actually starts) from
 * Razorpay's CDN, so no third-party script weighs down the rest of the app.
 */

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

/** Razorpay's success payload (we forward it to the backend poll, not trust it). */
export interface RazorpaySuccess {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}

interface RazorpayOptions {
  key: string;
  subscription_id: string;
  name: string;
  description?: string;
  prefill?: { name?: string; email?: string; contact?: string };
  notes?: Record<string, string>;
  theme?: { color?: string };
  handler?: (response: RazorpaySuccess) => void;
  modal?: { ondismiss?: () => void };
}

interface RazorpayInstance {
  open: () => void;
  on: (event: string, cb: (response: unknown) => void) => void;
}

type RazorpayConstructor = new (options: RazorpayOptions) => RazorpayInstance;

declare global {
  interface Window {
    Razorpay?: RazorpayConstructor;
  }
}

let loadPromise: Promise<RazorpayConstructor> | null = null;

/** Inject checkout.js once; resolve when ``window.Razorpay`` is available. */
export function ensureRazorpay(): Promise<RazorpayConstructor> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Razorpay checkout needs a browser."));
  }
  if (window.Razorpay) return Promise.resolve(window.Razorpay);
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<RazorpayConstructor>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${CHECKOUT_SRC}"]`,
    );
    const onLoad = () => {
      if (window.Razorpay) resolve(window.Razorpay);
      else reject(new Error("Razorpay loaded but window.Razorpay is missing."));
    };
    const onError = () => {
      loadPromise = null; // allow a retry on the next attempt
      reject(new Error("Couldn't load the payment gateway. Check your connection."));
    };
    if (existing) {
      existing.addEventListener("load", onLoad, { once: true });
      existing.addEventListener("error", onError, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = CHECKOUT_SRC;
    script.async = true;
    script.addEventListener("load", onLoad, { once: true });
    script.addEventListener("error", onError, { once: true });
    document.head.appendChild(script);
  });
  return loadPromise;
}

export interface OpenSubscriptionCheckoutParams {
  /** PUBLIC Razorpay key id (never the secret). */
  keyId: string;
  /** The ``sub_…`` handle from the backend subscribe response. */
  subscriptionId: string;
  name?: string;
  description?: string;
  prefill?: { name?: string; email?: string; contact?: string };
  notes?: Record<string, string>;
  /** Fired when the customer completes the checkout (does NOT mean active —
   *  the caller must poll the backend, which activates via the webhook). */
  onSuccess: (response: RazorpaySuccess) => void;
  /** Fired when the customer closes/cancels the checkout modal. */
  onDismiss: () => void;
  /** Fired when Razorpay reports a failed payment attempt. */
  onFailure?: (response: unknown) => void;
}

/**
 * Open the Razorpay Checkout modal for a recurring subscription. Loads
 * checkout.js on demand. Rejects only if the gateway script can't load (so the
 * caller can show a fallback / retry); user-cancel resolves via ``onDismiss``.
 */
export async function openSubscriptionCheckout(
  params: OpenSubscriptionCheckoutParams,
): Promise<void> {
  const Razorpay = await ensureRazorpay();
  const rzp = new Razorpay({
    key: params.keyId,
    subscription_id: params.subscriptionId,
    name: params.name ?? "TRADETRI",
    description: params.description,
    prefill: params.prefill,
    notes: params.notes,
    theme: { color: "#3B82F6" }, // accent-blue brand token
    handler: (response) => params.onSuccess(response),
    modal: { ondismiss: () => params.onDismiss() },
  });
  if (params.onFailure) {
    rzp.on("payment.failed", (response) => params.onFailure?.(response));
  }
  rzp.open();
}
