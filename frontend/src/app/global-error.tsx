"use client";

/**
 * Global error boundary for the App Router.
 *
 * Renders when an unhandled exception escapes every other boundary
 * — surfaced to the user as a friendly Hinglish fallback rather
 * than the default Next.js stack trace. Forwards the exception to
 * Sentry via dynamic import (same build-safe pattern as the
 * sentry.*.config.ts files): if ``@sentry/nextjs`` isn't installed
 * the call is a silent no-op and the user still sees the fallback.
 */

import { useEffect, useState } from "react";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  const [reportSent, setReportSent] = useState(false);

  useEffect(() => {
    // Auto-report once per error instance. Dynamic import keeps
    // the page renderable even when ``@sentry/nextjs`` is absent.
    void reportToSentry(error).then(() => setReportSent(true));
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex items-center justify-center p-6 bg-[#0b0e14] text-white">
          <div className="max-w-md w-full space-y-4 rounded-xl border border-white/[0.08] bg-white/[0.02] p-6 text-center">
            <div className="text-3xl" aria-hidden>
              😅
            </div>
            <h1 className="text-lg font-semibold">
              Kuch galti ho gayi
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Hum theek kar rahe hain. 1 minute mein refresh karo,
              aur ho jayega.
            </p>
            {error.digest ? (
              <p className="text-[10px] font-mono text-muted-foreground/70">
                Reference: {error.digest}
              </p>
            ) : null}
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={reset}
                className="px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 transition-colors"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== "undefined") {
                    window.location.reload();
                  }
                }}
                className="px-4 py-2 rounded-md border border-white/[0.08] text-sm font-medium hover:bg-white/[0.04] transition-colors"
              >
                Refresh page
              </button>
            </div>
            {reportSent ? (
              <p className="text-[10px] text-muted-foreground/70 pt-2">
                Error report send kar diya — team check kar rahi hai.
              </p>
            ) : null}
          </div>
        </div>
      </body>
    </html>
  );
}

async function reportToSentry(error: Error): Promise<void> {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return;
  try {
    const sentryPkg = "@sentry/nextjs";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Sentry: any = await import(sentryPkg);
    Sentry.captureException(error);
  } catch {
    // Package absent — best-effort report only. The user-visible
    // fallback already does its job; missing telemetry is a known
    // pre-launch state.
  }
}
