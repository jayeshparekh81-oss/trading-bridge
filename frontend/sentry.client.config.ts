/**
 * Sentry — client (browser) initialisation.
 *
 * The init is doubly-guarded so this file is safe to ship even
 * before ``@sentry/nextjs`` is installed:
 *
 *   1. ``NEXT_PUBLIC_SENTRY_DSN`` must be set at build time (the
 *      ``NEXT_PUBLIC_`` prefix exposes it to the browser bundle).
 *      No DSN -> the entire dynamic-import path is dead code.
 *
 *   2. The ``@sentry/nextjs`` import is read via a variable to
 *      defeat static-resolution by Webpack / Turbopack. If the
 *      package isn't on disk the runtime ``import()`` rejects;
 *      we swallow that and Sentry stays disabled.
 *
 * Once the package is added (``npm i @sentry/nextjs`` per
 * ``backend/PRODUCTION_DEPLOY.md``) and ``NEXT_PUBLIC_SENTRY_DSN``
 * is set, this file initialises automatically — no further code
 * change required.
 */

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  // Variable indirection — bundlers can't resolve a non-literal
  // dynamic-import target at build time, so the file ships clean
  // even with ``@sentry/nextjs`` absent.
  const sentryPkg = "@sentry/nextjs";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  void (import(sentryPkg) as Promise<any>)
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment:
          process.env.NEXT_PUBLIC_ENVIRONMENT ??
          process.env.NODE_ENV ??
          "development",
        // Keep tracing modest in production — TRADETRI's hot
        // builder pages emit a lot of client events.
        tracesSampleRate: 0.1,
        // Replays + session-tracking off by default; opt in via
        // separate config once the legal review of session
        // recordings clears.
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 0,
        // Defensive — Sentry's defaults already strip cookies,
        // but locking ``sendDefaultPii`` here so an SDK upgrade
        // doesn't silently flip the default.
        sendDefaultPii: false,
        beforeSend: scrubBrowserEvent,
      });
    })
    .catch(() => {
      // Package not installed yet — silent no-op. The deploy
      // guide flags this as a follow-up step before launch.
    });
}

/**
 * Trim browser PII before any event leaves the page. Mirrors the
 * backend's :func:`app.observability.sentry.scrub_event_for_pii`.
 *
 * Pure dict-in/dict-out so it's testable without the SDK and
 * cheap to call inline.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function scrubBrowserEvent(event: any): any {
  const request = event?.request;
  if (request && typeof request === "object") {
    const headers = request.headers;
    if (headers && typeof headers === "object") {
      for (const key of Object.keys(headers)) {
        const lower = key.toLowerCase();
        if (lower === "authorization" || lower === "cookie" || lower === "x-api-key") {
          headers[key] = "[scrubbed]";
        }
      }
    }
    if (typeof request.url === "string") {
      request.url = scrubUrlTokens(request.url);
    }
  }

  const user = event?.user;
  if (user && typeof user === "object") {
    if (typeof user.email === "string") {
      user.email = anonymiseEmail(user.email);
    }
    for (const key of ["phone", "phone_number", "telephone"]) {
      if (typeof user[key] === "string") user[key] = "[scrubbed]";
    }
    delete user.ip_address;
  }

  return event;
}

const TOKEN_PARAM_RE = /((?:access_token|token|api_key|secret|jwt)=)[^&\s]+/gi;
const EMAIL_RE =
  /\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/;

function scrubUrlTokens(url: string): string {
  return url.replace(TOKEN_PARAM_RE, "$1[scrubbed]");
}

function anonymiseEmail(email: string): string {
  const match = email.trim().match(EMAIL_RE);
  if (!match) return "[scrubbed]";
  return `[user]@[${match[2]}]`;
}

export {};
