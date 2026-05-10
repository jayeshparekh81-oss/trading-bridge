/**
 * Sentry — Node.js server-runtime initialisation.
 *
 * Server side reads ``SENTRY_DSN`` (no ``NEXT_PUBLIC_`` prefix —
 * not exposed to browser). Same dynamic-import pattern as
 * ``sentry.client.config.ts``: if either the env var or the
 * ``@sentry/nextjs`` package is missing, this file is a no-op.
 */

const dsn = process.env.SENTRY_DSN;
if (dsn) {
  const sentryPkg = "@sentry/nextjs";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  void (import(sentryPkg) as Promise<any>)
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment:
          process.env.SENTRY_ENVIRONMENT ??
          process.env.NODE_ENV ??
          "development",
        tracesSampleRate: Number(
          process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
        ),
        sendDefaultPii: false,
      });
    })
    .catch(() => {
      // Package absent — silent no-op.
    });
}

export {};
