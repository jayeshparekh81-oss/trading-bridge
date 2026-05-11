/**
 * ErrorState — full-area error banner with retry CTA.
 *
 * Two distinct shapes:
 *   - ``fetch`` — initial REST history failed (no candles to render).
 *     Shown full-area with a retry button.
 *   - ``broker_disconnected`` — backend's 5-minute reconnect
 *     threshold breached; live feed is dark. Chart history still
 *     visible underneath; this surfaces as an overlay banner.
 *
 * Day-4 polish will swap the inline banner for a toast (sonner is
 * already in the dep tree).
 */

"use client";

import { AlertTriangle, RotateCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface ErrorStateProps {
  kind: "fetch" | "broker_disconnected";
  message: string;
  /** Optional retry handler. When supplied, renders a retry button. */
  onRetry?: () => void;
}

export function ErrorState({ kind, message, onRetry }: ErrorStateProps) {
  const title =
    kind === "fetch"
      ? "Chart data load nahi ho sake"
      : "Broker connection toot gaya";
  return (
    <div
      className="flex h-full w-full items-center justify-center p-6"
      data-testid={`chart-error-${kind}`}
    >
      <Alert variant="destructive" className="max-w-xl">
        <AlertTriangle aria-hidden="true" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{message}</AlertDescription>
        {onRetry && (
          <div className="mt-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              data-testid="chart-error-retry"
            >
              <RotateCw className="mr-1.5 h-3 w-3" />
              Retry
            </Button>
          </div>
        )}
      </Alert>
    </div>
  );
}
