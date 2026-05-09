/**
 * PostHog analytics helper — graceful no-op without configuration.
 *
 * Same posture as the Sentry config files: the
 * ``@sentry/nextjs``-style variable-indirection dynamic import
 * pattern keeps the build green even before ``posthog-js`` is
 * installed, and ``trackEvent`` always swallows exceptions so a
 * misbehaving analytics pipe never breaks user-facing UI.
 *
 * Privacy contract:
 *
 *   * The user id is SHA-256 hashed before any event leaves the
 *     browser. Same algorithm + salt as the backend's
 *     :func:`hash_user_id` so the same user produces the same
 *     ``distinct_id`` regardless of which side fires the event.
 *   * Property keys named after PII (email, phone, full_name,
 *     password, secret, token) are stripped at the call site by
 *     :func:`scrubProperties`.
 *   * Per-user opt-out is honoured via the
 *     ``tradetri_analytics_opt_out`` localStorage key. The
 *     ``<PrivacyBanner />`` component is the user-facing way to
 *     set this; programmatic callers can use
 *     :func:`setOptedOut`.
 *
 * Configuration:
 *
 *   * ``NEXT_PUBLIC_POSTHOG_KEY`` — without it, init never runs
 *     and ``trackEvent`` is a no-op.
 *   * ``NEXT_PUBLIC_POSTHOG_HOST`` — defaults to
 *     ``https://app.posthog.com``.
 *   * ``NEXT_PUBLIC_ANALYTICS_SALT`` — defaults to a stable
 *     baseline so dev / staging hashes are deterministic.
 */

const STORAGE_KEY = "tradetri_analytics_opt_out";
const SALT_DEFAULT = "tradetri-analytics-v1";

const PII_KEYS = new Set([
  "email",
  "email_address",
  "phone",
  "phone_number",
  "telephone",
  "mobile",
  "full_name",
  "first_name",
  "last_name",
  "name",
  "password",
  "password_hash",
  "api_key",
  "secret",
  "secret_key",
  "access_token",
  "refresh_token",
  "jwt",
  "ip_address",
  "remote_addr",
  "broker_token",
  "broker_secret",
  "session_token",
]);

const AMOUNT_KEYS = new Set([
  "pnl_inr",
  "pnl",
  "amount_paid_inr",
  "trade_amount_inr",
  "capital_inr",
]);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _posthog: any = null;
let _initStarted = false;

function getDsn(): string | undefined {
  return process.env.NEXT_PUBLIC_POSTHOG_KEY;
}

function getHost(): string {
  return process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://app.posthog.com";
}

function getSalt(): string {
  return process.env.NEXT_PUBLIC_ANALYTICS_SALT ?? SALT_DEFAULT;
}

/**
 * Browser-side opt-out check. Returns ``true`` when the user has
 * dismissed the privacy banner with the opt-out choice. Defaults
 * to ``false`` (analytics on) for both unset users and SSR.
 */
export function isOptedOut(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setOptedOut(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, "true");
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage may throw in private mode — silent fall-through.
  }
}

/**
 * Strip PII / amount keys from a property bag. Only direct keys
 * are inspected — nested dicts pass through untouched (events
 * should be flat by analytics-schema convention).
 */
export function scrubProperties(
  properties: Record<string, unknown>,
): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(properties)) {
    const lower = key.toLowerCase();
    if (PII_KEYS.has(lower) || AMOUNT_KEYS.has(lower)) continue;
    cleaned[key] = value;
  }
  return cleaned;
}

async function _ensureLoaded(): Promise<unknown> {
  if (_posthog != null) return _posthog;
  if (_initStarted) return null;
  _initStarted = true;

  const dsn = getDsn();
  if (!dsn) return null;
  if (typeof window === "undefined") return null;

  // Variable-indirection — bundlers can't statically resolve a
  // non-literal dynamic-import target, so the build stays clean
  // when ``posthog-js`` isn't installed yet.
  const pkg = "posthog-js";
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mod = (await import(pkg)) as any;
    const sdk = mod.default ?? mod;
    sdk.init(dsn, {
      api_host: getHost(),
      // We send our own ``distinct_id`` (hashed user id), so disable
      // the SDK's auto-generated cookie identity.
      autocapture: false,
      capture_pageview: false,
      persistence: "localStorage",
      // We hash user ids ourselves; don't let posthog-js record
      // raw IPs.
      ip: false,
    });
    _posthog = sdk;
    return sdk;
  } catch {
    // Package absent — silent no-op. The privacy banner still
    // works; just no events ship until ``posthog-js`` lands.
    return null;
  }
}

async function _hash(input: string): Promise<string> {
  const salt = getSalt();
  const data = new TextEncoder().encode(`${salt}:user:${input}`);
  if (typeof crypto === "undefined" || !crypto.subtle) {
    // SSR or extremely old browser — fall back to a non-crypto
    // hash. Acceptable here because analytics is best-effort
    // anyway; security-critical hashes don't go through this path.
    let h = 0;
    for (const c of input) h = (h * 31 + c.charCodeAt(0)) | 0;
    return `fallback-${h.toString(16)}`;
  }
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Emit one analytics event. Never throws.
 *
 * The ``userId`` is hashed before emission. Properties are
 * scrubbed of PII / amount keys before being forwarded to
 * PostHog. If the user has opted out, or the SDK isn't
 * configured, the call is a silent no-op.
 */
export async function trackEvent(
  userId: string,
  eventName: string,
  properties: Record<string, unknown> = {},
): Promise<void> {
  try {
    if (isOptedOut()) return;
    const sdk = await _ensureLoaded();
    if (sdk == null) return;
    const hashedUser = await _hash(userId);
    const cleanProps = scrubProperties(properties);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (sdk as any).identify(hashedUser);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (sdk as any).capture(eventName, cleanProps);
  } catch {
    // Never let analytics break the page.
  }
}

/**
 * Synchronous fire-and-forget wrapper for components that don't
 * want to ``await`` the async path. Schedules ``trackEvent`` on
 * a microtask + swallows any rejection.
 */
export function trackEventSync(
  userId: string,
  eventName: string,
  properties: Record<string, unknown> = {},
): void {
  void trackEvent(userId, eventName, properties);
}
