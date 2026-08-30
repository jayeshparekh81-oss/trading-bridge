/**
 * Where to send someone AFTER they log in or register.
 *
 * A `?next=` parameter is an OPEN-REDIRECT surface: it is attacker-supplied
 * and it is followed by an authenticated browser the instant credentials are
 * accepted. `?next=https://evil.example/login` would hand a freshly logged-in
 * customer to a convincing fake, which on a trading platform is a credential
 * and money problem, not a cosmetic one.
 *
 * So the rule is allow-list, not deny-list: a destination is accepted ONLY if
 * it is a path on THIS site. Anything else silently falls back to the default
 * — never an error page, because a bad `next` is not the customer's fault and
 * should not block them from getting in.
 *
 * REJECTED, each for its own reason:
 *   "https://evil.com"   absolute — a different origin entirely
 *   "//evil.com"         protocol-relative; browsers treat it as absolute
 *   "/\evil.com"         backslashes, which some parsers fold into "//"
 *   "javascript:..."     a scheme, not a path
 *   "evil.com"           no leading slash; resolves relative to the CURRENT
 *                        page, so it is not the path it appears to be
 *   ""/null/undefined    nothing to go to
 */

export const DEFAULT_NEXT = "/";

/** Control chars: browsers strip these before parsing a URL, so we must too. */
const CONTROL_CHARS = /[\x00-\x1F\x7F]/g;

export function safeNextPath(
  raw: string | null | undefined,
  fallback: string = DEFAULT_NEXT,
): string {
  if (typeof raw !== "string") return fallback;

  // Percent-encoding can hide any of the shapes below ("%2F%2Fevil.com").
  // A malformed escape throws, and a value we cannot even decode is one we
  // certainly should not follow.
  let value: string;
  try {
    value = decodeURIComponent(raw.trim());
  } catch {
    return fallback;
  }

  if (value === "") return fallback;

  // "/\tjavascript:x" and "//\nevil.com" must not slip past on a stripped char.
  const cleaned = value.replace(CONTROL_CHARS, "");

  // Must be a site-absolute path...
  if (!cleaned.startsWith("/")) return fallback;
  // ...and NOT protocol-relative, in either slash direction ("//" or "/\").
  if (/^[/\\]{2}/.test(cleaned)) return fallback;

  return cleaned;
}

/** Build a login/register URL that will return to `to` afterwards. */
export function withNext(base: "/login" | "/register", to: string): string {
  const safe = safeNextPath(to);
  return safe === DEFAULT_NEXT
    ? base
    : `${base}?next=${encodeURIComponent(safe)}`;
}
