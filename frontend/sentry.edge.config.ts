/**
 * Sentry — Edge-runtime initialisation.
 *
 * Edge runtime (middleware, edge route handlers) gets a separate
 * SDK profile because it runs in a Workers-like environment that
 * doesn't support the full Node.js SDK surface. Same DSN env var
 * as the server config; same dynamic-import-and-swallow pattern
 * for build safety without ``@sentry/nextjs`` installed.
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
    .catch(() => {});
}

export {};
