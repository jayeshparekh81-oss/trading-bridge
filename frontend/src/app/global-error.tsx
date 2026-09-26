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
    // "Report sent" is shown ONLY when a report really went (founder's rule,
    // 26 Sep, point 10): with no DSN configured nothing is sent, and the page
    // used to say "team check kar rahi hai" anyway.
    void reportToSentry(error).then((sent) => setReportSent(sent));
  }, [error]);

  return (
    <html lang="hi">
      <body>
        <div className="min-h-screen flex items-center justify-center p-6 bg-surface-ink text-white">
          <div className="max-w-md w-full space-y-4 rounded-xl border border-white/[0.08] bg-white/[0.02] p-6 text-center">
            <div className="text-3xl" aria-hidden>
              😅
            </div>
            <h1 className="text-lg font-semibold">
              Yeh page khulte waqt atak gaya
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Galti hamari taraf hai, aapki nahi — sirf yeh page dikhane me dikkat aayi; is galti se
              koi order nahi bheja jaata. Neeche wala button dabao, page dobara khulega. Phir bhi na
              khule to Contact page se hume WhatsApp karo.
            </p>
            {error.digest ? (
              <p className="text-xs font-mono text-muted-foreground/70">
                Hume batana ho to yeh number bhejna: {error.digest}
              </p>
            ) : null}
            <div className="flex flex-col items-stretch gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== "undefined") window.location.reload();
                  else reset();
                }}
                className="min-h-11 px-4 py-2 rounded-md bg-accent-blue text-white text-base font-medium hover:bg-accent-blue/90 transition-colors"
              >
                Page dobara kholo
              </button>
              <a
                href="/"
                className="inline-flex min-h-11 items-center justify-center rounded-md border border-white/[0.08] px-4 text-sm font-medium hover:bg-white/[0.04] transition-colors"
              >
                Shuru ke page par jao
              </a>
              <a
                href="/contact"
                className="inline-flex min-h-11 items-center justify-center text-sm text-muted-foreground underline"
              >
                Contact page (WhatsApp)
              </a>
            </div>
            {reportSent ? (
              <p className="text-xs text-muted-foreground/70 pt-2">
                Galti ki report hamari team tak pahunch gayi hai.
              </p>
            ) : null}
          </div>
        </div>
      </body>
    </html>
  );
}

async function reportToSentry(error: Error): Promise<boolean> {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return false;
  try {
    const sentryPkg = "@sentry/nextjs";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Sentry: any = await import(sentryPkg);
    Sentry.captureException(error);
    return true;
  } catch {
    // Package absent — best-effort report only. The user-visible
    // fallback already does its job; missing telemetry is a known
    // pre-launch state.
    return false;
  }
}
